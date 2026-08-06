from __future__ import annotations


VERSION = "20260806_21_material_sku_revisions"


def _columns(connection, backend: str, database: str) -> set[str]:
    if backend == "mysql":
        return {
            str(row["COLUMN_NAME"])
            for row in connection.execute(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA=? AND TABLE_NAME='managed_materials'",
                (database,),
            ).fetchall()
        }
    return {str(row["name"]) for row in connection.execute("PRAGMA table_info(managed_materials)").fetchall()}


def upgrade(connection, backend: str, database: str = "") -> None:
    """Use a monotonic SKU revision to reject stale admin edits deterministically."""
    if "revision" not in _columns(connection, backend, database):
        column_type = "INT NOT NULL DEFAULT 1" if backend == "mysql" else "INTEGER NOT NULL DEFAULT 1"
        connection.execute(f"ALTER TABLE managed_materials ADD COLUMN revision {column_type}")
    connection.execute("UPDATE managed_materials SET revision=1 WHERE revision IS NULL OR revision < 1")


def downgrade(connection, backend: str, database: str = "") -> None:
    """The additive revision column is intentionally retained for rollback safety."""
    return None
