from __future__ import annotations


VERSION = "20260713_08_after_sale_cases"


def _mysql_indexes(connection, database: str, table: str) -> set[str]:
    rows = connection.execute(
        """
        SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        """,
        (database, table),
    ).fetchall()
    return {row["INDEX_NAME"] for row in rows}


def upgrade(connection, backend: str, database: str = "") -> None:
    suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if backend == "mysql" else ""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS after_sale_cases (
          case_id VARCHAR(80) PRIMARY KEY,
          order_id VARCHAR(40) NOT NULL,
          user_id VARCHAR(100) NOT NULL,
          case_type VARCHAR(40) NOT NULL,
          reason_code VARCHAR(60) NOT NULL,
          reason VARCHAR(500) NOT NULL,
          evidence_json LONGTEXT NOT NULL,
          order_snapshot_json LONGTEXT NOT NULL,
          status VARCHAR(40) NOT NULL,
          requested_refund_fee BIGINT NOT NULL DEFAULT 0,
          approved_refund_fee BIGINT NOT NULL DEFAULT 0,
          resolution_type VARCHAR(40) NOT NULL DEFAULT '',
          review_note VARCHAR(500) NOT NULL DEFAULT '',
          reviewed_by VARCHAR(100) NOT NULL DEFAULT '',
          reviewed_at VARCHAR(40),
          resolved_at VARCHAR(40),
          idempotency_key VARCHAR(128) NOT NULL,
          request_hash VARCHAR(64) NOT NULL,
          created_at VARCHAR(40) NOT NULL,
          updated_at VARCHAR(40) NOT NULL,
          UNIQUE (user_id, idempotency_key)
        )
        """ + suffix
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS after_sale_events (
          event_id VARCHAR(80) PRIMARY KEY,
          case_id VARCHAR(80) NOT NULL,
          event_type VARCHAR(40) NOT NULL,
          from_status VARCHAR(40) NOT NULL DEFAULT '',
          to_status VARCHAR(40) NOT NULL,
          operator_type VARCHAR(20) NOT NULL,
          operator_id VARCHAR(100) NOT NULL,
          note VARCHAR(500) NOT NULL DEFAULT '',
          created_at VARCHAR(40) NOT NULL
        )
        """ + suffix
    )
    if backend == "mysql":
        case_indexes = _mysql_indexes(connection, database, "after_sale_cases")
        if "idx_after_sale_order_created" not in case_indexes:
            connection.execute(
                "CREATE INDEX idx_after_sale_order_created ON after_sale_cases(order_id, created_at)"
            )
        if "idx_after_sale_status_created" not in case_indexes:
            connection.execute(
                "CREATE INDEX idx_after_sale_status_created ON after_sale_cases(status, created_at)"
            )
        event_indexes = _mysql_indexes(connection, database, "after_sale_events")
        if "idx_after_sale_events_case_created" not in event_indexes:
            connection.execute(
                "CREATE INDEX idx_after_sale_events_case_created ON after_sale_events(case_id, created_at)"
            )
        return
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_after_sale_order_created ON after_sale_cases(order_id, created_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_after_sale_status_created ON after_sale_cases(status, created_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_after_sale_events_case_created ON after_sale_events(case_id, created_at)"
    )


def downgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        connection.execute("DROP TABLE IF EXISTS after_sale_events")
        connection.execute("DROP TABLE IF EXISTS after_sale_cases")
        return
    connection.execute("DROP INDEX IF EXISTS idx_after_sale_events_case_created")
    connection.execute("DROP INDEX IF EXISTS idx_after_sale_status_created")
    connection.execute("DROP INDEX IF EXISTS idx_after_sale_order_created")
    connection.execute("DROP TABLE IF EXISTS after_sale_events")
    connection.execute("DROP TABLE IF EXISTS after_sale_cases")
