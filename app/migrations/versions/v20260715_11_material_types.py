from __future__ import annotations

from datetime import datetime, timezone


VERSION = "20260715_11_material_types"

DEFAULT_TYPES = (
    ("bead", "珠子", "常规圆珠及按珠径管理的珠材", 10),
    ("accessory", "配饰", "异形水晶、隔珠、花托、吊坠等配饰", 20),
    ("incense", "合香珠", "历史合香珠目录", 30),
    ("pendant", "花托/吊坠", "历史花托与吊坠目录，后续可归入配饰", 40),
)


def _table_exists(connection, backend: str, database: str, table: str) -> bool:
    if backend == "mysql":
        row = connection.execute(
            """
            SELECT COUNT(*) AS c FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
            """,
            (database, table),
        ).fetchone()
        return bool(row and row["c"])
    return bool(
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
    )


def _existing_type_codes(connection, backend: str, database: str) -> set[str]:
    result: set[str] = set()
    for table in ("managed_materials", "material_taxonomy"):
        if not _table_exists(connection, backend, database, table):
            continue
        rows = connection.execute(
            f"SELECT DISTINCT top FROM {table} WHERE COALESCE(top, '') <> ''"
        ).fetchall()
        result.update(str(row["top"] or "").strip() for row in rows)
    return {code for code in result if code}


def upgrade(connection, backend: str, database: str = "") -> None:
    suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if backend == "mysql" else ""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS material_types (
            type_code VARCHAR(40) PRIMARY KEY,
            name VARCHAR(160) NOT NULL,
            description VARCHAR(500) NOT NULL DEFAULT '',
            sort_order INT NOT NULL DEFAULT 0,
            enabled TINYINT NOT NULL DEFAULT 1,
            created_at VARCHAR(40) NOT NULL,
            updated_at VARCHAR(40) NOT NULL
        )
        """ + suffix
    )
    if backend == "mysql":
        indexes = {
            row["INDEX_NAME"]
            for row in connection.execute(
                """
                SELECT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'material_types'
                """,
                (database,),
            ).fetchall()
        }
        if "idx_material_types_enabled_sort" not in indexes:
            connection.execute(
                "CREATE INDEX idx_material_types_enabled_sort ON material_types (enabled, sort_order)"
            )
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    defaults = {code: (name, description, sort_order) for code, name, description, sort_order in DEFAULT_TYPES}
    codes = set(defaults) | _existing_type_codes(connection, backend, database)
    for index, code in enumerate(sorted(codes)):
        existing = connection.execute(
            "SELECT type_code FROM material_types WHERE type_code = ?",
            (code,),
        ).fetchone()
        if existing:
            continue
        name, description, sort_order = defaults.get(code, (code, "由现有材料目录迁移", 100 + index))
        connection.execute(
            """
            INSERT INTO material_types
            (type_code, name, description, sort_order, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (code, name, description, sort_order, timestamp, timestamp),
        )


def downgrade(connection, backend: str, database: str = "") -> None:
    if _table_exists(connection, backend, database, "material_types"):
        connection.execute("DROP TABLE material_types")
