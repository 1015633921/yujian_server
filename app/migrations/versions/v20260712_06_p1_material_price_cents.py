from __future__ import annotations


VERSION = "20260712_06_p1_material_price_cents"
MAX_LEGACY_PRICE = 999_999_999.99


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
    if backend == "mysql":
        columns = _mysql_columns(connection, database, "managed_materials")
        if "price_cents" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN price_cents BIGINT NULL AFTER price")
        connection.execute(
            """
            UPDATE managed_materials
            SET price_cents = CAST(ROUND(price * 100, 0) AS SIGNED)
            WHERE price_cents IS NULL
              AND price IS NOT NULL
              AND price > 0
              AND price <= ?
              AND ABS((price * 100) - ROUND(price * 100, 0)) < 0.000001
            """,
            (MAX_LEGACY_PRICE,),
        )
        return

    columns = _sqlite_columns(connection, "managed_materials")
    if "price_cents" not in columns:
        connection.execute("ALTER TABLE managed_materials ADD COLUMN price_cents INTEGER")
    connection.execute(
        """
        UPDATE managed_materials
        SET price_cents = CAST(ROUND(price * 100, 0) AS INTEGER)
        WHERE price_cents IS NULL
          AND typeof(price) IN ('integer', 'real')
          AND price > 0
          AND price <= ?
          AND ABS((price * 100) - ROUND(price * 100, 0)) < 0.000001
        """,
        (MAX_LEGACY_PRICE,),
    )


def downgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        if "price_cents" in _mysql_columns(connection, database, "managed_materials"):
            connection.execute("ALTER TABLE managed_materials DROP COLUMN price_cents")
        return
    if "price_cents" in _sqlite_columns(connection, "managed_materials"):
        connection.execute("ALTER TABLE managed_materials DROP COLUMN price_cents")
