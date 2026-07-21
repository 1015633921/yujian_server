from __future__ import annotations


VERSION = "20260714_10_material_physical_specs"


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
        _mysql_columns(connection, database, "managed_materials")
        if backend == "mysql"
        else _sqlite_columns(connection, "managed_materials")
    )
    if "physical_specs_json" in columns:
        return
    if backend == "mysql":
        connection.execute("ALTER TABLE managed_materials ADD COLUMN physical_specs_json LONGTEXT NULL")
    else:
        connection.execute(
            "ALTER TABLE managed_materials ADD COLUMN physical_specs_json TEXT NOT NULL DEFAULT '{}'"
        )


def downgrade(connection, backend: str, database: str = "") -> None:
    columns = (
        _mysql_columns(connection, database, "managed_materials")
        if backend == "mysql"
        else _sqlite_columns(connection, "managed_materials")
    )
    if "physical_specs_json" in columns:
        connection.execute("ALTER TABLE managed_materials DROP COLUMN physical_specs_json")
