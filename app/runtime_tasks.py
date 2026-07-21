from __future__ import annotations

import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .database import DEFAULT_SQLITE_PATH, connect_database, use_mysql
from .observability import (
    bind_request_id,
    log_event,
    metrics,
    reset_request_id,
    safe_exception_frames,
)
from .order_service import OrderService

import logging


LOGGER = logging.getLogger("yujian.logistics")
TASK_NAME = "logistics_sync"
COMMERCE_TASK_NAME = "commerce_maintenance"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(value: datetime) -> str:
    return value.isoformat()


def logistics_enabled() -> bool:
    return str(os.getenv("LOGISTICS_SYNC_ENABLED", "false")).strip().lower() in {"1", "true", "yes", "on"}


def commerce_maintenance_enabled() -> bool:
    return str(os.getenv("COMMERCE_MAINTENANCE_ENABLED", "false")).strip().lower() in {
        "1", "true", "yes", "on"
    }


class RuntimeTaskStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_SQLITE_PATH
        self._force_sqlite = db_path is not None

    def connect(self):
        return connect_database(self.db_path if self._force_sqlite else None)

    @property
    def mysql(self) -> bool:
        return use_mysql() and not self._force_sqlite

    def acquire(self, task_name: str, owner_id: str, lease_seconds: int, now: datetime | None = None) -> bool:
        current = now or utc_now()
        lease_until = current + timedelta(seconds=max(30, lease_seconds))
        with self.connect() as connection:
            if not self.mysql:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO runtime_task_leases(task_name, owner_id, lease_until, updated_at)
                    VALUES (?, '', '1970-01-01T00:00:00+00:00', ?)
                    ON CONFLICT(task_name) DO NOTHING
                    """,
                    (task_name, iso(current)),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO runtime_task_leases(task_name, owner_id, lease_until, updated_at)
                    VALUES (?, '', '1970-01-01T00:00:00+00:00', ?)
                    ON DUPLICATE KEY UPDATE task_name=VALUES(task_name)
                    """,
                    (task_name, iso(current)),
                )
            cursor = connection.execute(
                """
                UPDATE runtime_task_leases
                SET owner_id = ?, lease_until = ?, updated_at = ?
                WHERE task_name = ? AND lease_until <= ?
                """,
                (owner_id, iso(lease_until), iso(current), task_name, iso(current)),
            )
            return cursor.rowcount == 1

    def start_run(self, run_id: str, task_name: str, owner_id: str, started_at: datetime) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO runtime_task_runs
                (run_id, task_name, owner_id, status, attempt_count, checked_count,
                 failed_count, error_type, started_at, finished_at)
                VALUES (?, ?, ?, 'running', 0, 0, 0, '', ?, NULL)
                """,
                (run_id, task_name, owner_id, iso(started_at)),
            )

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        attempts: int,
        checked: int,
        failed: int,
        error_type: str = "",
        finished_at: datetime | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE runtime_task_runs
                SET status = ?, attempt_count = ?, checked_count = ?, failed_count = ?,
                    error_type = ?, finished_at = ?
                WHERE run_id = ?
                """,
                (status, attempts, checked, failed, error_type[:100], iso(finished_at or utc_now()), run_id),
            )


class LogisticsTaskRunner:
    def __init__(
        self,
        db_path: Path | None = None,
        order_service: OrderService | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        owner_id: str | None = None,
    ) -> None:
        self.db_path = db_path
        self.store = RuntimeTaskStore(db_path)
        self.order_service = order_service or OrderService(db_path or DEFAULT_SQLITE_PATH)
        self.sleep_fn = sleep_fn
        self.owner_id = owner_id or f"logistics-{secrets.token_hex(12)}"

    @staticmethod
    def interval_seconds() -> int:
        return max(300, int(os.getenv("LOGISTICS_SYNC_INTERVAL_SECONDS", "1800")))

    @classmethod
    def lease_seconds(cls) -> int:
        configured = int(os.getenv("LOGISTICS_SYNC_LEASE_SECONDS", "3600"))
        return max(cls.interval_seconds() * 2, configured, 600)

    @staticmethod
    def max_attempts() -> int:
        return max(1, min(int(os.getenv("LOGISTICS_SYNC_MAX_ATTEMPTS", "3")), 5))

    @staticmethod
    def batch_size() -> int:
        return max(1, min(int(os.getenv("LOGISTICS_SYNC_BATCH_SIZE", "50")), 100))

    def run_once(self) -> dict[str, Any]:
        if not logistics_enabled():
            return {"status": "disabled", "executed": False}
        started_at = utc_now()
        run_id = f"ltr_{secrets.token_hex(16)}"
        if not self.store.acquire(TASK_NAME, self.owner_id, self.lease_seconds(), started_at):
            log_event(LOGGER, "logistics.sync.skipped_locked", result="skipped")
            return {"status": "skipped_locked", "executed": False}
        request_token = bind_request_id(run_id)
        run_recorded = False
        attempts = 0
        checked = 0
        failed_ids: list[str] = []
        try:
            self.store.start_run(run_id, TASK_NAME, self.owner_id, started_at)
            run_recorded = True
            metrics.increment("logistics_sync_total")
            while True:
                attempts += 1
                try:
                    result = self.order_service.refresh_active_shipments(limit=self.batch_size())
                    break
                except Exception:
                    if attempts >= self.max_attempts():
                        raise
                    self.sleep_fn(min(2 ** (attempts - 1), 8))
            checked = int(result.get("checked") or 0)
            failed_ids = list(result.get("failed_order_ids") or [])
            while failed_ids and attempts < self.max_attempts():
                self.sleep_fn(min(2 ** (attempts - 1), 8))
                attempts += 1
                remaining: list[str] = []
                for order_id in failed_ids:
                    try:
                        item = self.order_service.refresh_order_logistics(order_id, force=False)
                        if (item.get("logistics") or {}).get("sync_error"):
                            remaining.append(order_id)
                    except Exception:
                        remaining.append(order_id)
                failed_ids = remaining
            status = "completed" if not failed_ids else "partial_failed"
            if failed_ids:
                metrics.increment("logistics_sync_failed_total", result="partial_failed")
            self.store.finish_run(
                run_id,
                status=status,
                attempts=attempts,
                checked=checked,
                failed=len(failed_ids),
            )
            log_event(
                LOGGER,
                "logistics.sync.finished",
                result=status,
                checked=checked,
                failed=len(failed_ids),
                attempts=attempts,
            )
            return {
                "status": status,
                "executed": True,
                "run_id": run_id,
                "checked": checked,
                "failed": len(failed_ids),
                "attempts": attempts,
            }
        except Exception as exc:
            metrics.increment("logistics_sync_failed_total", result="failed")
            if run_recorded:
                try:
                    self.store.finish_run(
                        run_id,
                        status="failed",
                        attempts=max(1, attempts),
                        checked=checked,
                        failed=max(1, len(failed_ids)),
                        error_type=type(exc).__name__,
                    )
                except Exception as record_exc:
                    log_event(
                        LOGGER,
                        "logistics.sync.run_record_failed",
                        level=logging.ERROR,
                        error_type=type(record_exc).__name__,
                        result="failed",
                    )
            log_event(
                LOGGER,
                "logistics.sync.failed",
                level=logging.ERROR,
                result="failed",
                error_type=type(exc).__name__,
                stack=safe_exception_frames(exc),
            )
            return {"status": "failed", "executed": True, "run_id": run_id, "error_type": type(exc).__name__}
        finally:
            reset_request_id(request_token)


class CommerceMaintenanceTaskRunner:
    def __init__(
        self,
        db_path: Path | None = None,
        order_service: OrderService | None = None,
        owner_id: str | None = None,
    ) -> None:
        self.db_path = db_path
        self.store = RuntimeTaskStore(db_path)
        self.order_service = order_service or OrderService(db_path or DEFAULT_SQLITE_PATH)
        self.owner_id = owner_id or f"commerce-{secrets.token_hex(12)}"

    @staticmethod
    def interval_seconds() -> int:
        return max(60, int(os.getenv("COMMERCE_MAINTENANCE_INTERVAL_SECONDS", "300")))

    @classmethod
    def lease_seconds(cls) -> int:
        configured = int(os.getenv("COMMERCE_MAINTENANCE_LEASE_SECONDS", "900"))
        return max(cls.interval_seconds() * 2, configured, 120)

    @staticmethod
    def batch_size() -> int:
        return max(1, min(int(os.getenv("COMMERCE_MAINTENANCE_BATCH_SIZE", "100")), 1000))

    def run_once(self) -> dict[str, Any]:
        if not commerce_maintenance_enabled():
            return {"status": "disabled", "executed": False}
        started_at = utc_now()
        run_id = f"cmr_{secrets.token_hex(16)}"
        if not self.store.acquire(COMMERCE_TASK_NAME, self.owner_id, self.lease_seconds(), started_at):
            log_event(LOGGER, "commerce.maintenance.skipped_locked", result="skipped")
            return {"status": "skipped_locked", "executed": False}
        request_token = bind_request_id(run_id)
        run_recorded = False
        try:
            self.store.start_run(run_id, COMMERCE_TASK_NAME, self.owner_id, started_at)
            run_recorded = True
            payments = self.order_service.reconcile_processing_payments(limit=self.batch_size())
            expired = self.order_service.release_expired_reservations(limit=self.batch_size())
            checked = int(expired.get("processed_orders") or 0) + int(payments.get("checked") or 0)
            deferred_processing = int(expired.get("deferred_processing") or 0)
            reconciliation_blocked = deferred_processing > 0 and not payments.get("configured", False)
            failed = int(payments.get("failed") or 0) + int(reconciliation_blocked)
            status = "completed" if failed == 0 else "partial_failed"
            self.store.finish_run(
                run_id,
                status=status,
                attempts=1,
                checked=checked,
                failed=failed,
            )
            log_event(
                LOGGER,
                "commerce.maintenance.finished",
                result=status,
                checked=checked,
                failed=failed,
                released_reservations=int(expired.get("released_reservations") or 0),
                deferred_processing=deferred_processing,
                reconciliation_blocked=reconciliation_blocked,
                payment_compensations=int(payments.get("compensation_required") or 0),
            )
            return {
                "status": status,
                "executed": True,
                "run_id": run_id,
                "checked": checked,
                "failed": failed,
                "expired": expired,
                "payments": payments,
            }
        except Exception as exc:
            if run_recorded:
                try:
                    self.store.finish_run(
                        run_id,
                        status="failed",
                        attempts=1,
                        checked=0,
                        failed=1,
                        error_type=type(exc).__name__,
                    )
                except Exception:
                    pass
            log_event(
                LOGGER,
                "commerce.maintenance.failed",
                level=logging.ERROR,
                result="failed",
                error_type=type(exc).__name__,
                stack=safe_exception_frames(exc),
            )
            return {"status": "failed", "executed": True, "run_id": run_id, "error_type": type(exc).__name__}
        finally:
            reset_request_id(request_token)
