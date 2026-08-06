from __future__ import annotations


VERSION = "20260806_19_material_series_identity"
INDEX_NAME = "idx_managed_materials_series_id"


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
    return {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(managed_materials)").fetchall()
    }


def _mysql_indexes(connection, database: str) -> set[str]:
    return {
        str(row["INDEX_NAME"])
        for row in connection.execute(
            "SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS "
            "WHERE TABLE_SCHEMA=? AND TABLE_NAME='managed_materials'",
            (database,),
        ).fetchall()
    }


def upgrade(connection, backend: str, database: str = "") -> None:
    """Give every SKU a stable, rename-safe link to its material variety."""
    columns = _columns(connection, backend, database)
    if "series_id" not in columns:
        column_type = "VARCHAR(120) NOT NULL DEFAULT ''" if backend == "mysql" else "TEXT NOT NULL DEFAULT ''"
        connection.execute(f"ALTER TABLE managed_materials ADD COLUMN series_id {column_type}")

    if backend == "mysql":
        if INDEX_NAME not in _mysql_indexes(connection, database):
            connection.execute(f"CREATE INDEX {INDEX_NAME} ON managed_materials (series_id)")
    else:
        connection.execute(f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON managed_materials (series_id)")

    # Existing SKU rows predate series_id.  Resolve them once from the current
    # taxonomy so subsequent renames and category moves use the stable key.
    connection.execute(
        """
        UPDATE managed_materials
        SET series_id=(
            SELECT s.item_id
            FROM material_taxonomy s
            JOIN material_taxonomy c ON c.item_id=s.parent_id
            WHERE s.kind='series' AND c.kind='category'
              AND s.top=managed_materials.top
              AND c.name=managed_materials.category
              AND s.name=COALESCE(NULLIF(managed_materials.series, ''), managed_materials.name)
            ORDER BY s.created_at ASC, s.item_id ASC
            LIMIT 1
        )
        WHERE COALESCE(series_id, '')=''
          AND EXISTS(
            SELECT 1
            FROM material_taxonomy s
            JOIN material_taxonomy c ON c.item_id=s.parent_id
            WHERE s.kind='series' AND c.kind='category'
              AND s.top=managed_materials.top
              AND c.name=managed_materials.category
              AND s.name=COALESCE(NULLIF(managed_materials.series, ''), managed_materials.name)
          )
        """
    )


def downgrade(connection, backend: str, database: str = "") -> None:
    """Rollback the lookup index while intentionally retaining the stable IDs.

    Keeping `series_id` is non-destructive: older releases ignore the column,
    and a future re-upgrade does not need to reconstruct rename history.
    """
    if backend == "mysql":
        if INDEX_NAME in _mysql_indexes(connection, database):
            connection.execute(f"DROP INDEX {INDEX_NAME} ON managed_materials")
        return
    connection.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
