from __future__ import annotations

import sqlite3

from app.admin_service import AdminService
from app.migrations.runner import downgrade, upgrade
from app.migrations.versions import v20260806_18_custom_design_queue_indexes as migration
from app.order_service import OrderService
from app.repository import AssessmentRepository


def _index_columns(db_path, name: str) -> list[str]:
    with sqlite3.connect(db_path) as connection:
        return [
            row[2]
            for row in connection.execute(f"PRAGMA index_info({name})").fetchall()
        ]


def _index_names(db_path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        return {
            row[1]
            for row in connection.execute("PRAGMA index_list(custom_design_requests)").fetchall()
        }


def test_custom_design_queue_indexes_upgrade_and_rollback(tmp_path):
    db_path = tmp_path / "custom-design-queue-indexes.db"
    AssessmentRepository(db_path)
    AdminService(db_path)
    OrderService(db_path)

    applied = upgrade("sqlite", db_path)
    assert migration.VERSION in applied
    assert _index_columns(db_path, "idx_custom_design_requests_queue_updated") == [
        "updated_at",
        "request_id",
    ]
    assert _index_columns(db_path, "idx_custom_design_requests_queue_status_updated") == [
        "status",
        "updated_at",
        "request_id",
    ]

    # Newer additive migrations may exist; roll back to this migration instead
    # of assuming it is permanently the tail of the migration chain.
    rolled_back: list[str] = []
    while migration.VERSION not in rolled_back:
        rolled_back.extend(downgrade("sqlite", db_path, steps=1))
    assert migration.VERSION in rolled_back
    names = _index_names(db_path)
    assert "idx_custom_design_requests_queue_updated" not in names
    assert "idx_custom_design_requests_queue_status_updated" not in names
    assert migration.VERSION in upgrade("sqlite", db_path)


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _MySQLConnectionStub:
    def __init__(self, indexes: set[str]):
        self.indexes = indexes
        self.statements: list[tuple[str, tuple]] = []

    def execute(self, statement: str, params=()):
        self.statements.append((statement, tuple(params)))
        if "INFORMATION_SCHEMA.STATISTICS" in statement:
            return _Rows([{"INDEX_NAME": name} for name in self.indexes])
        return _Rows([])


def test_custom_design_queue_indexes_use_mysql_safe_create_and_drop_statements():
    create_connection = _MySQLConnectionStub(set())
    migration.upgrade(create_connection, "mysql", "yujian")
    created = [statement for statement, _params in create_connection.statements if statement.startswith("CREATE INDEX")]
    assert created == [
        "CREATE INDEX idx_custom_design_requests_queue_updated ON custom_design_requests (updated_at, request_id)",
        "CREATE INDEX idx_custom_design_requests_queue_status_updated ON custom_design_requests (status, updated_at, request_id)",
    ]

    drop_connection = _MySQLConnectionStub(
        {
            "idx_custom_design_requests_queue_updated",
            "idx_custom_design_requests_queue_status_updated",
        }
    )
    migration.downgrade(drop_connection, "mysql", "yujian")
    dropped = [statement for statement, _params in drop_connection.statements if statement.startswith("DROP INDEX")]
    assert dropped == [
        "DROP INDEX idx_custom_design_requests_queue_updated ON custom_design_requests",
        "DROP INDEX idx_custom_design_requests_queue_status_updated ON custom_design_requests",
    ]
