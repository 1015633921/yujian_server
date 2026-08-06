from __future__ import annotations


VERSION = "20260806_22_material_catalog_indexes"

INDEXES = {
    "idx_managed_materials_catalog_group": (
        "top, category, series_id, sort_order, updated_at"
    ),
    "idx_managed_materials_material_code_sizes": (
        "material_code, enabled, size"
    ),
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
    """Keep SPU grouping and batched size hydration index-backed as the catalog grows."""
    if backend == "mysql":
        existing = _mysql_indexes(connection, database)
        for name, columns in INDEXES.items():
            if name not in existing:
                connection.execute(f"CREATE INDEX {name} ON managed_materials({columns})")
        return
    for name, columns in INDEXES.items():
        connection.execute(f"CREATE INDEX IF NOT EXISTS {name} ON managed_materials({columns})")


def downgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        existing = _mysql_indexes(connection, database)
        for name in INDEXES:
            if name in existing:
                connection.execute(f"DROP INDEX {name} ON managed_materials")
        return
    for name in INDEXES:
        connection.execute(f"DROP INDEX IF EXISTS {name}")
