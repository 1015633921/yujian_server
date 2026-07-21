from __future__ import annotations


VERSION = "20260714_09_after_sale_return_flow"


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


def upgrade(connection, backend: str, database: str = "") -> None:
    columns = (
        _mysql_columns(connection, database, "after_sale_cases")
        if backend == "mysql"
        else _sqlite_columns(connection, "after_sale_cases")
    )
    definitions = {
        "return_carrier": "VARCHAR(50) NOT NULL DEFAULT ''" if backend == "mysql" else "TEXT NOT NULL DEFAULT ''",
        "return_tracking_no": "VARCHAR(80) NOT NULL DEFAULT ''" if backend == "mysql" else "TEXT NOT NULL DEFAULT ''",
        "return_submitted_at": "VARCHAR(40) NULL" if backend == "mysql" else "TEXT",
        "canceled_at": "VARCHAR(40) NULL" if backend == "mysql" else "TEXT",
    }
    for name, definition in definitions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE after_sale_cases ADD COLUMN {name} {definition}")


def downgrade(connection, backend: str, database: str = "") -> None:
    columns = (
        _mysql_columns(connection, database, "after_sale_cases")
        if backend == "mysql"
        else _sqlite_columns(connection, "after_sale_cases")
    )
    for name in ("canceled_at", "return_submitted_at", "return_tracking_no", "return_carrier"):
        if name in columns:
            connection.execute(f"ALTER TABLE after_sale_cases DROP COLUMN {name}")
