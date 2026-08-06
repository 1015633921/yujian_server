from __future__ import annotations


VERSION = "20260806_18_custom_design_queue_indexes"


QUEUE_INDEXES = (
    ("idx_custom_design_requests_queue_updated", "updated_at, request_id"),
    ("idx_custom_design_requests_queue_status_updated", "status, updated_at, request_id"),
)


def _mysql_indexes(connection, database: str) -> set[str]:
    return {
        str(row["INDEX_NAME"])
        for row in connection.execute(
            "SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS "
            "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'custom_design_requests'",
            (database,),
        ).fetchall()
    }


def upgrade(connection, backend: str, database: str = "") -> None:
    """Add queue-order indexes used by the limited admin work-order list."""
    if backend == "mysql":
        existing = _mysql_indexes(connection, database)
        for name, columns in QUEUE_INDEXES:
            if name not in existing:
                connection.execute(
                    f"CREATE INDEX {name} ON custom_design_requests ({columns})"
                )
        return

    for name, columns in QUEUE_INDEXES:
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {name} ON custom_design_requests ({columns})"
        )


def downgrade(connection, backend: str, database: str = "") -> None:
    """Rollback only the queue-order indexes; service-order data is retained."""
    if backend == "mysql":
        existing = _mysql_indexes(connection, database)
        for name, _columns in QUEUE_INDEXES:
            if name in existing:
                connection.execute(f"DROP INDEX {name} ON custom_design_requests")
        return

    for name, _columns in QUEUE_INDEXES:
        connection.execute(f"DROP INDEX IF EXISTS {name}")
