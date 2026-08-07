from __future__ import annotations


VERSION = "20260807_24_material_rule_cleanup"


def _columns(connection, backend: str, database: str) -> set[str]:
    if backend == "mysql":
        return {
            str(row["COLUMN_NAME"])
            for row in connection.execute(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA=? AND TABLE_NAME='material_knowledge'",
                (database,),
            ).fetchall()
        }
    return {
        str(row["name"] if hasattr(row, "keys") else row[1])
        for row in connection.execute("PRAGMA table_info(material_knowledge)").fetchall()
    }


def upgrade(connection, backend: str, database: str = "") -> None:
    """Remove the obsolete material conflict-rule storage."""
    if "conflict_codes_json" not in _columns(connection, backend, database):
        return
    connection.execute("ALTER TABLE material_knowledge DROP COLUMN conflict_codes_json")


def downgrade(connection, backend: str, database: str = "") -> None:
    """Restore the legacy column so the preceding release can be rolled back."""
    if "conflict_codes_json" in _columns(connection, backend, database):
        return
    if backend == "mysql":
        connection.execute(
            "ALTER TABLE material_knowledge "
            "ADD COLUMN conflict_codes_json LONGTEXT NOT NULL DEFAULT ('[]') "
            "AFTER allowed_roles_json"
        )
        return
    connection.execute(
        "ALTER TABLE material_knowledge "
        "ADD COLUMN conflict_codes_json TEXT NOT NULL DEFAULT '[]'"
    )
