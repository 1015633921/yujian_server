from __future__ import annotations


VERSION = "20260727_16_custom_design_workbench"


def _sqlite_columns(connection, table: str) -> set[str]:
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}


def _mysql_columns(connection, database: str, table: str) -> set[str]:
    return {
        row["COLUMN_NAME"]
        for row in connection.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?",
            (database, table),
        ).fetchall()
    }


def _mysql_indexes(connection, database: str, table: str) -> set[str]:
    return {
        row["INDEX_NAME"]
        for row in connection.execute(
            "SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS "
            "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?",
            (database, table),
        ).fetchall()
    }


def upgrade(connection, backend: str, database: str = "") -> None:
    text = "LONGTEXT" if backend == "mysql" else "TEXT"
    suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if backend == "mysql" else ""

    proposal_columns = (
        _mysql_columns(connection, database, "custom_design_proposals")
        if backend == "mysql"
        else _sqlite_columns(connection, "custom_design_proposals")
    )
    if "workbench_json" not in proposal_columns:
        connection.execute(
            f"ALTER TABLE custom_design_proposals ADD COLUMN workbench_json {text}"
        )
    if "order_id" not in proposal_columns:
        connection.execute(
            "ALTER TABLE custom_design_proposals ADD COLUMN order_id VARCHAR(80)"
            if backend == "mysql"
            else "ALTER TABLE custom_design_proposals ADD COLUMN order_id TEXT"
        )
    if "confirmed_at" not in proposal_columns:
        connection.execute(
            "ALTER TABLE custom_design_proposals ADD COLUMN confirmed_at VARCHAR(40)"
            if backend == "mysql"
            else "ALTER TABLE custom_design_proposals ADD COLUMN confirmed_at TEXT"
        )

    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS custom_design_drafts (
        draft_id VARCHAR(80) PRIMARY KEY,
        request_id VARCHAR(80) NOT NULL,
        draft_version INT NOT NULL,
        workbench_json {text} NOT NULL,
        created_by VARCHAR(100) NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        UNIQUE(request_id)
        ){suffix}"""
    )

    if backend == "mysql":
        indexes = _mysql_indexes(connection, database, "custom_design_proposals")
        if "idx_custom_design_proposals_order" not in indexes:
            connection.execute(
                "CREATE INDEX idx_custom_design_proposals_order "
                "ON custom_design_proposals(order_id)"
            )
        draft_indexes = _mysql_indexes(connection, database, "custom_design_drafts")
        if "idx_custom_design_drafts_updated" not in draft_indexes:
            connection.execute(
                "CREATE INDEX idx_custom_design_drafts_updated "
                "ON custom_design_drafts(updated_at)"
            )
    else:
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_custom_design_proposals_order "
            "ON custom_design_proposals(order_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_custom_design_drafts_updated "
            "ON custom_design_drafts(updated_at DESC)"
        )


def downgrade(connection, backend: str, database: str = "") -> None:
    del database
    connection.execute("DROP TABLE IF EXISTS custom_design_drafts")
    if backend == "mysql":
        connection.execute(
            "DROP INDEX idx_custom_design_proposals_order ON custom_design_proposals"
        )
    else:
        connection.execute("DROP INDEX IF EXISTS idx_custom_design_proposals_order")
    connection.execute("ALTER TABLE custom_design_proposals DROP COLUMN confirmed_at")
    connection.execute("ALTER TABLE custom_design_proposals DROP COLUMN order_id")
    connection.execute("ALTER TABLE custom_design_proposals DROP COLUMN workbench_json")
