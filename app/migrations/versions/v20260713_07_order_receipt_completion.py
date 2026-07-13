from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone


VERSION = "20260713_07_order_receipt_completion"
AUTO_COMPLETE_DAYS = 7


def _sqlite_columns(connection, table: str) -> set[str]:
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}


def _mysql_columns(connection, database: str, table: str) -> set[str]:
    rows = connection.execute(
        """
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        """,
        (database, table),
    ).fetchall()
    return {row["COLUMN_NAME"] for row in rows}


def _mysql_indexes(connection, database: str, table: str) -> set[str]:
    rows = connection.execute(
        """
        SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        """,
        (database, table),
    ).fetchall()
    return {row["INDEX_NAME"] for row in rows}


def _parse_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone(timedelta(hours=8)))
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _signed_at(logistics: dict) -> datetime | None:
    explicit = _parse_time(logistics.get("signed_at"))
    if explicit is not None:
        return explicit
    latest_event = _parse_time(logistics.get("latest_event_time"))
    if latest_event is not None:
        return latest_event
    trace_times = [
        parsed
        for parsed in (_parse_time(item.get("time")) for item in logistics.get("traces") or [] if isinstance(item, dict))
        if parsed is not None
    ]
    return max(trace_times) if trace_times else _parse_time(logistics.get("updated_at"))


def _backfill_signed_orders(connection) -> None:
    rows = connection.execute(
        """
        SELECT order_id, logistics_json FROM orders
        WHERE status = 'shipped' AND logistics_json IS NOT NULL
        """
    ).fetchall()
    for row in rows:
        try:
            logistics = json.loads(row["logistics_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(logistics, dict) or logistics.get("status") != "signed":
            continue
        signed_at = _signed_at(logistics)
        if signed_at is None:
            continue
        signed_at = signed_at.replace(microsecond=0)
        auto_complete_at = signed_at + timedelta(days=AUTO_COMPLETE_DAYS)
        signed_text = signed_at.isoformat()
        deadline_text = auto_complete_at.isoformat()
        logistics["signed_at"] = signed_text
        logistics["auto_complete_at"] = deadline_text
        connection.execute(
            """
            UPDATE orders
            SET logistics_json = ?, logistics_signed_at = ?, auto_complete_at = ?
            WHERE order_id = ?
            """,
            (json.dumps(logistics, ensure_ascii=False), signed_text, deadline_text, row["order_id"]),
        )


def upgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        columns = _mysql_columns(connection, database, "orders")
        if "logistics_signed_at" not in columns:
            connection.execute(
                "ALTER TABLE orders ADD COLUMN logistics_signed_at VARCHAR(40) NULL AFTER logistics_json"
            )
        if "auto_complete_at" not in columns:
            connection.execute(
                "ALTER TABLE orders ADD COLUMN auto_complete_at VARCHAR(40) NULL AFTER logistics_signed_at"
            )
        _backfill_signed_orders(connection)
        if "idx_orders_auto_complete" not in _mysql_indexes(connection, database, "orders"):
            connection.execute(
                "CREATE INDEX idx_orders_auto_complete ON orders(status, auto_complete_at)"
            )
        return

    columns = _sqlite_columns(connection, "orders")
    if "logistics_signed_at" not in columns:
        connection.execute("ALTER TABLE orders ADD COLUMN logistics_signed_at TEXT")
    if "auto_complete_at" not in columns:
        connection.execute("ALTER TABLE orders ADD COLUMN auto_complete_at TEXT")
    _backfill_signed_orders(connection)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_orders_auto_complete ON orders(status, auto_complete_at)"
    )


def downgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        if "idx_orders_auto_complete" in _mysql_indexes(connection, database, "orders"):
            connection.execute("DROP INDEX idx_orders_auto_complete ON orders")
        columns = _mysql_columns(connection, database, "orders")
        if "auto_complete_at" in columns:
            connection.execute("ALTER TABLE orders DROP COLUMN auto_complete_at")
        if "logistics_signed_at" in columns:
            connection.execute("ALTER TABLE orders DROP COLUMN logistics_signed_at")
        return

    connection.execute("DROP INDEX IF EXISTS idx_orders_auto_complete")
    columns = _sqlite_columns(connection, "orders")
    if "auto_complete_at" in columns:
        connection.execute("ALTER TABLE orders DROP COLUMN auto_complete_at")
    if "logistics_signed_at" in columns:
        connection.execute("ALTER TABLE orders DROP COLUMN logistics_signed_at")
