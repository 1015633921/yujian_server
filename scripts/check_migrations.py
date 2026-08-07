from __future__ import annotations

import argparse
import gc
from contextlib import closing
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.admin_service import AdminService
from app.migrations.runner import MIGRATIONS, downgrade, upgrade
from app.order_service import OrderService
from app.repository import AssessmentRepository


def check_sqlite() -> None:
    with tempfile.TemporaryDirectory(prefix="yujian-migration-check-") as directory:
        root = Path(directory)
        database = root / "migration.db"
        restored = root / "restored.db"
        repository = AssessmentRepository(database)
        order_service = OrderService(database)
        admin_service = AdminService(database)
        expected = [migration.VERSION for migration in MIGRATIONS]
        if upgrade("sqlite", database) != expected:
            raise RuntimeError("clean upgrade did not apply every migration")
        if upgrade("sqlite", database):
            raise RuntimeError("second upgrade was not idempotent")
        shutil.copy2(database, restored)
        with closing(sqlite3.connect(restored)) as connection:
            active = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
            history = connection.execute("SELECT COUNT(*) FROM schema_migration_history").fetchone()[0]
        if active != len(expected) or history != len(expected):
            raise RuntimeError("migration audit record is incomplete")
        if downgrade("sqlite", database) != list(reversed(expected)):
            raise RuntimeError("downgrade order mismatch")
        if upgrade("sqlite", database) != expected:
            raise RuntimeError("upgrade after downgrade failed")
        # Some Windows SQLite drivers keep finalizer-owned file handles alive
        # until collection, which otherwise makes TemporaryDirectory cleanup fail.
        del repository, order_service, admin_service
        gc.collect()


def check_mysql() -> None:
    database = os.getenv("MYSQL_DATABASE", "").lower()
    if "test" not in database and "ci" not in database:
        raise RuntimeError("MySQL migration check requires an isolated test/ci database")
    os.environ["ALLOW_RUNTIME_SCHEMA_MUTATION"] = "true"
    AssessmentRepository()
    OrderService()
    AdminService()
    expected = [migration.VERSION for migration in MIGRATIONS]
    applied = upgrade("mysql")
    if applied not in ([], expected):
        raise RuntimeError("unexpected MySQL migration state")
    if downgrade("mysql") != list(reversed(expected)):
        raise RuntimeError("MySQL downgrade order mismatch")
    if upgrade("mysql") != expected:
        raise RuntimeError("MySQL re-upgrade failed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercise migration upgrade, audit, backup and rollback")
    parser.add_argument("--backend", choices=("sqlite", "mysql"), default="sqlite")
    args = parser.parse_args()
    check_mysql() if args.backend == "mysql" else check_sqlite()
    print(f"{args.backend} migration round trip passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
