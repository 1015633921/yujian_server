from __future__ import annotations

import argparse
import os
import sqlite3
import uuid
from pathlib import Path

from app.database import DEFAULT_SQLITE_PATH, MySQLConnection
from app.migrations.versions import v20260712_01_p0a_security
from app.migrations.versions import v20260712_02_p0b_order_integrity
from app.migrations.versions import v20260712_03_p1a_payment_events
from app.migrations.versions import v20260712_04_p1b_report_snapshots
from app.migrations.versions import v20260712_05_p1c_runtime_tasks
from app.migrations.versions import v20260712_06_p1_material_price_cents
from app.migrations.versions import v20260713_07_order_receipt_completion
from app.migrations.versions import v20260713_08_after_sale_cases
from app.migrations.versions import v20260714_09_after_sale_return_flow
from app.migrations.versions import v20260714_10_material_physical_specs
from app.migrations.versions import v20260715_11_material_types
from app.migrations.versions import v20260723_12_ai_material_annotations
from app.migrations.versions import v20260724_13_web_login_pairing
from app.migrations.versions import v20260727_14_custom_design_service
from app.migrations.versions import v20260727_15_report_codes
from app.migrations.versions import v20260727_16_custom_design_workbench
from app.migrations.versions import v20260806_17_custom_design_deposits
from app.migrations.versions import v20260806_18_custom_design_queue_indexes
from app.migrations.versions import v20260806_19_material_series_identity
from app.migrations.versions import v20260806_20_material_asset_versions
from app.migrations.versions import v20260806_21_material_sku_revisions
from app.migrations.versions import v20260806_22_material_catalog_indexes
from app.migrations.versions import v20260807_23_community_post_image_gallery

MIGRATIONS = [
    v20260712_01_p0a_security,
    v20260712_02_p0b_order_integrity,
    v20260712_03_p1a_payment_events,
    v20260712_04_p1b_report_snapshots,
    v20260712_05_p1c_runtime_tasks,
    v20260712_06_p1_material_price_cents,
    v20260713_07_order_receipt_completion,
    v20260713_08_after_sale_cases,
    v20260714_09_after_sale_return_flow,
    v20260714_10_material_physical_specs,
    v20260715_11_material_types,
    v20260723_12_ai_material_annotations,
    v20260724_13_web_login_pairing,
    v20260727_14_custom_design_service,
    v20260727_15_report_codes,
    v20260727_16_custom_design_workbench,
    v20260806_17_custom_design_deposits,
    v20260806_18_custom_design_queue_indexes,
    v20260806_19_material_series_identity,
    v20260806_20_material_asset_versions,
    v20260806_21_material_sku_revisions,
    v20260806_22_material_catalog_indexes,
    v20260807_23_community_post_image_gallery,
]


def _connect(backend: str, sqlite_path: Path | None = None):
    if backend == "mysql":
        return MySQLConnection()
    path = Path(sqlite_path or DEFAULT_SQLITE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_version_table(connection, backend: str) -> None:
    suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if backend == "mysql" else ""
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version VARCHAR(100) PRIMARY KEY, applied_at VARCHAR(40) NOT NULL, "
        "applied_by VARCHAR(160) NOT NULL DEFAULT 'unknown', "
        "release_version VARCHAR(100) NOT NULL DEFAULT 'unversioned'"
        f"){suffix}"
    )
    if backend == "mysql":
        database = os.environ["MYSQL_DATABASE"]
        columns = {
            row["COLUMN_NAME"]
            for row in connection.execute(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'schema_migrations'",
                (database,),
            ).fetchall()
        }
    else:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(schema_migrations)").fetchall()}
    if "applied_by" not in columns:
        connection.execute(
            "ALTER TABLE schema_migrations ADD COLUMN applied_by VARCHAR(160) NOT NULL DEFAULT 'unknown'"
        )
    if "release_version" not in columns:
        connection.execute(
            "ALTER TABLE schema_migrations ADD COLUMN release_version VARCHAR(100) NOT NULL DEFAULT 'unversioned'"
        )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migration_history ("
        "event_id VARCHAR(64) PRIMARY KEY, version VARCHAR(100) NOT NULL, "
        "action VARCHAR(20) NOT NULL, recorded_at VARCHAR(40) NOT NULL, "
        "operator_name VARCHAR(160) NOT NULL, release_version VARCHAR(100) NOT NULL"
        f"){suffix}"
    )


def _migration_identity() -> tuple[str, str]:
    operator = os.getenv("MIGRATION_OPERATOR", "local-operator").strip() or "local-operator"
    release = os.getenv("RELEASE_VERSION", "unversioned").strip() or "unversioned"
    return operator[:160], release[:100]


def _record_history(connection, version: str, action: str, operator: str, release: str) -> None:
    connection.execute(
        "INSERT INTO schema_migration_history"
        "(event_id, version, action, recorded_at, operator_name, release_version) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?)",
        (uuid.uuid4().hex, version, action, operator, release),
    )


def _applied_versions(connection) -> set[str]:
    return {row["version"] for row in connection.execute("SELECT version FROM schema_migrations").fetchall()}


def pending(backend: str | None = None, sqlite_path: Path | None = None) -> list[str]:
    target = (backend or os.getenv("DATABASE_BACKEND", "sqlite")).lower()
    connection = _connect(target, sqlite_path)
    try:
        _ensure_version_table(connection, target)
        existing = _applied_versions(connection)
        return [migration.VERSION for migration in MIGRATIONS if migration.VERSION not in existing]
    finally:
        if target == "mysql":
            connection.raw.close()
        else:
            connection.close()


def upgrade(backend: str | None = None, sqlite_path: Path | None = None) -> list[str]:
    target = (backend or os.getenv("DATABASE_BACKEND", "sqlite")).lower()
    connection = _connect(target, sqlite_path)
    applied: list[str] = []
    try:
        _ensure_version_table(connection, target)
        existing = _applied_versions(connection)
        operator, release = _migration_identity()
        for migration in MIGRATIONS:
            if migration.VERSION in existing:
                continue
            migration.upgrade(connection, target, os.getenv("MYSQL_DATABASE", ""))
            connection.execute(
                "INSERT INTO schema_migrations"
                "(version, applied_at, applied_by, release_version) "
                "VALUES (?, CURRENT_TIMESTAMP, ?, ?)",
                (migration.VERSION, operator, release),
            )
            _record_history(connection, migration.VERSION, "upgrade", operator, release)
            applied.append(migration.VERSION)
        if target == "mysql":
            connection.raw.commit()
        else:
            connection.commit()
        return applied
    except Exception:
        if target == "mysql":
            connection.raw.rollback()
        else:
            connection.rollback()
        raise
    finally:
        if target == "mysql":
            connection.raw.close()
        else:
            connection.close()


def downgrade(
    backend: str | None = None,
    sqlite_path: Path | None = None,
    steps: int | None = None,
) -> list[str]:
    target = (backend or os.getenv("DATABASE_BACKEND", "sqlite")).lower()
    connection = _connect(target, sqlite_path)
    reverted: list[str] = []
    try:
        _ensure_version_table(connection, target)
        existing = _applied_versions(connection)
        operator, release = _migration_identity()
        for migration in reversed(MIGRATIONS):
            if migration.VERSION not in existing:
                continue
            migration.downgrade(connection, target, os.getenv("MYSQL_DATABASE", ""))
            connection.execute("DELETE FROM schema_migrations WHERE version = ?", (migration.VERSION,))
            _record_history(connection, migration.VERSION, "downgrade", operator, release)
            reverted.append(migration.VERSION)
            if steps is not None and len(reverted) >= max(1, steps):
                break
        if target == "mysql":
            connection.raw.commit()
        else:
            connection.commit()
        return reverted
    except Exception:
        if target == "mysql":
            connection.raw.rollback()
        else:
            connection.rollback()
        raise
    finally:
        if target == "mysql":
            connection.raw.close()
        else:
            connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run explicit Yujian database migrations")
    parser.add_argument("direction", choices=("pending", "upgrade", "downgrade"))
    parser.add_argument("--backend", choices=("sqlite", "mysql"), default=None)
    parser.add_argument("--sqlite-path", type=Path, default=None)
    parser.add_argument("--steps", type=int, default=None, help="downgrade only the latest N migrations")
    args = parser.parse_args()
    if args.direction == "pending":
        versions = pending(args.backend, args.sqlite_path)
    elif args.direction == "upgrade":
        versions = upgrade(args.backend, args.sqlite_path)
    else:
        versions = downgrade(args.backend, args.sqlite_path, args.steps)
    print(f"{args.direction}: {', '.join(versions) if versions else 'no changes'}")


if __name__ == "__main__":
    main()
