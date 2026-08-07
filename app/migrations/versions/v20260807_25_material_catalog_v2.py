from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


VERSION = "20260807_25_material_catalog_v2"


def _table_exists(connection, backend: str, database: str, table: str) -> bool:
    if backend == "mysql":
        return bool(
            connection.execute(
                "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=? AND TABLE_NAME=?",
                (database, table),
            ).fetchone()
        )
    return bool(
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
    )


def _rows(connection, table: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table}").fetchall()]


def _slug_id(prefix: str, *parts: Any) -> str:
    source = "|".join(str(part or "").strip() for part in parts)
    return f"{prefix}_{hashlib.sha1(source.encode('utf-8')).hexdigest()[:24]}"


def _cost_cents(value: Any) -> int:
    try:
        amount = Decimal(str(value or 0))
    except Exception:
        amount = Decimal(0)
    return max(0, int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _create_tables(connection, backend: str) -> None:
    if backend == "mysql":
        statements = [
            """
            CREATE TABLE IF NOT EXISTS material_categories_v2 (
                category_id VARCHAR(120) PRIMARY KEY,
                type_code VARCHAR(40) NOT NULL,
                name VARCHAR(160) NOT NULL,
                description VARCHAR(500) NOT NULL DEFAULT '',
                sort_order INT NOT NULL DEFAULT 0,
                enabled TINYINT NOT NULL DEFAULT 1,
                created_at VARCHAR(40) NOT NULL,
                updated_at VARCHAR(40) NOT NULL,
                UNIQUE KEY uq_material_categories_v2_type_name (type_code, name),
                INDEX idx_material_categories_v2_type (type_code, enabled, sort_order),
                CONSTRAINT fk_material_categories_v2_type FOREIGN KEY (type_code)
                    REFERENCES material_types(type_code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS material_series_v2 (
                series_id VARCHAR(120) PRIMARY KEY,
                category_id VARCHAR(120) NOT NULL,
                material_code VARCHAR(160) NOT NULL,
                name VARCHAR(160) NOT NULL,
                color VARCHAR(40) NOT NULL DEFAULT '',
                shine VARCHAR(40) NOT NULL DEFAULT '',
                asset_version INT NOT NULL DEFAULT 1,
                sort_order INT NOT NULL DEFAULT 0,
                enabled TINYINT NOT NULL DEFAULT 1,
                created_at VARCHAR(40) NOT NULL,
                updated_at VARCHAR(40) NOT NULL,
                UNIQUE KEY uq_material_series_v2_code (material_code),
                UNIQUE KEY uq_material_series_v2_category_name (category_id, name),
                INDEX idx_material_series_v2_category (category_id, enabled, sort_order),
                CONSTRAINT fk_material_series_v2_category FOREIGN KEY (category_id)
                    REFERENCES material_categories_v2(category_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS material_series_profiles_v2 (
                series_id VARCHAR(120) PRIMARY KEY,
                profile_json LONGTEXT NOT NULL,
                created_at VARCHAR(40) NOT NULL,
                updated_at VARCHAR(40) NOT NULL,
                CONSTRAINT fk_material_profiles_v2_series FOREIGN KEY (series_id)
                    REFERENCES material_series_v2(series_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS material_series_assets_v2 (
                asset_id VARCHAR(120) PRIMARY KEY,
                series_id VARCHAR(120) NOT NULL,
                asset_role VARCHAR(30) NOT NULL DEFAULT 'gallery',
                image_url VARCHAR(2000) NOT NULL DEFAULT '',
                image_path VARCHAR(1000) NOT NULL DEFAULT '',
                sort_order INT NOT NULL DEFAULT 0,
                enabled TINYINT NOT NULL DEFAULT 1,
                created_at VARCHAR(40) NOT NULL,
                updated_at VARCHAR(40) NOT NULL,
                UNIQUE KEY uq_material_assets_v2_series_sort (series_id, sort_order),
                INDEX idx_material_assets_v2_series (series_id, enabled, sort_order),
                CONSTRAINT fk_material_assets_v2_series FOREIGN KEY (series_id)
                    REFERENCES material_series_v2(series_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS material_skus_v2 (
                sku_id VARCHAR(160) PRIMARY KEY,
                series_id VARCHAR(120) NOT NULL,
                sku_code VARCHAR(160) NOT NULL,
                name VARCHAR(160) NOT NULL,
                grade VARCHAR(40) NOT NULL DEFAULT '',
                price_cents BIGINT NOT NULL DEFAULT 0,
                cost_cents BIGINT NOT NULL DEFAULT 0,
                size_mm DECIMAL(12,4) NOT NULL DEFAULT 0,
                weight_g DECIMAL(12,4) NOT NULL DEFAULT 0,
                physical_specs_json LONGTEXT NOT NULL,
                supplier_name VARCHAR(255) NOT NULL DEFAULT '',
                purchase_note TEXT,
                enabled TINYINT NOT NULL DEFAULT 1,
                sort_order INT NOT NULL DEFAULT 0,
                revision INT NOT NULL DEFAULT 1,
                created_at VARCHAR(40) NOT NULL,
                updated_at VARCHAR(40) NOT NULL,
                UNIQUE KEY uq_material_skus_v2_code (sku_code),
                INDEX idx_material_skus_v2_series (series_id, enabled, sort_order),
                CONSTRAINT fk_material_skus_v2_series FOREIGN KEY (series_id)
                    REFERENCES material_series_v2(series_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS material_inventory_v2 (
                sku_id VARCHAR(160) PRIMARY KEY,
                stock INT NOT NULL DEFAULT 0,
                reserved_stock INT NOT NULL DEFAULT 0,
                safety_stock INT NOT NULL DEFAULT 0,
                revision INT NOT NULL DEFAULT 1,
                updated_at VARCHAR(40) NOT NULL,
                CONSTRAINT fk_material_inventory_v2_sku FOREIGN KEY (sku_id)
                    REFERENCES material_skus_v2(sku_id) ON DELETE CASCADE,
                CONSTRAINT chk_material_inventory_v2_nonnegative
                    CHECK (stock >= 0 AND reserved_stock >= 0 AND safety_stock >= 0 AND reserved_stock <= stock)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
    else:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS material_categories_v2 (
                category_id TEXT PRIMARY KEY, type_code TEXT NOT NULL, name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(type_code, name), FOREIGN KEY(type_code) REFERENCES material_types(type_code)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS material_series_v2 (
                series_id TEXT PRIMARY KEY, category_id TEXT NOT NULL, material_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '', shine TEXT NOT NULL DEFAULT '',
                asset_version INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(category_id, name), FOREIGN KEY(category_id) REFERENCES material_categories_v2(category_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS material_series_profiles_v2 (
                series_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(series_id) REFERENCES material_series_v2(series_id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS material_series_assets_v2 (
                asset_id TEXT PRIMARY KEY, series_id TEXT NOT NULL, asset_role TEXT NOT NULL DEFAULT 'gallery',
                image_url TEXT NOT NULL DEFAULT '', image_path TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(series_id, sort_order),
                FOREIGN KEY(series_id) REFERENCES material_series_v2(series_id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS material_skus_v2 (
                sku_id TEXT PRIMARY KEY, series_id TEXT NOT NULL, sku_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL, grade TEXT NOT NULL DEFAULT '', price_cents INTEGER NOT NULL DEFAULT 0,
                cost_cents INTEGER NOT NULL DEFAULT 0, size_mm NUMERIC NOT NULL DEFAULT 0,
                weight_g NUMERIC NOT NULL DEFAULT 0, physical_specs_json TEXT NOT NULL,
                supplier_name TEXT NOT NULL DEFAULT '', purchase_note TEXT,
                enabled INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(series_id) REFERENCES material_series_v2(series_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS material_inventory_v2 (
                sku_id TEXT PRIMARY KEY, stock INTEGER NOT NULL DEFAULT 0,
                reserved_stock INTEGER NOT NULL DEFAULT 0, safety_stock INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL,
                CHECK(stock >= 0 AND reserved_stock >= 0 AND safety_stock >= 0 AND reserved_stock <= stock),
                FOREIGN KEY(sku_id) REFERENCES material_skus_v2(sku_id) ON DELETE CASCADE
            )
            """,
        ]
    for statement in statements:
        connection.execute(statement)
    indexes = (
        ("idx_material_categories_v2_type", "material_categories_v2(type_code, enabled, sort_order)"),
        ("idx_material_series_v2_category", "material_series_v2(category_id, enabled, sort_order)"),
        ("idx_material_assets_v2_series", "material_series_assets_v2(series_id, enabled, sort_order)"),
        ("idx_material_skus_v2_series", "material_skus_v2(series_id, enabled, sort_order)"),
    )
    if backend != "mysql":
        for name, target in indexes:
            connection.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {target}")


def _insert_if_missing(connection, table: str, key: str, value: Any, columns: list[str], values: list[Any]) -> None:
    if connection.execute(f"SELECT 1 FROM {table} WHERE {key}=?", (value,)).fetchone():
        return
    marks = ", ".join("?" for _ in values)
    connection.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({marks})", values
    )


def _unique_sku_code(connection, sku_id: str, preferred: str) -> str:
    base = preferred or sku_id
    row = connection.execute(
        "SELECT sku_id FROM material_skus_v2 WHERE sku_code=?", (base,)
    ).fetchone()
    if not row or str(row["sku_id"]) == sku_id:
        return base
    return f"{base}-{hashlib.sha1(sku_id.encode('utf-8')).hexdigest()[:8]}"


def _ensure_category(
    connection,
    *,
    category_id: str,
    type_code: str,
    name: str,
    sort_order: int,
    enabled: int,
    created_at: str,
    updated_at: str,
) -> str:
    existing = connection.execute(
        "SELECT category_id FROM material_categories_v2 "
        "WHERE category_id=? OR (type_code=? AND name=?) "
        "ORDER BY CASE WHEN category_id=? THEN 0 ELSE 1 END, category_id LIMIT 1",
        (category_id, type_code, name, category_id),
    ).fetchone()
    if existing:
        return str(existing["category_id"])
    _insert_if_missing(
        connection,
        "material_categories_v2",
        "category_id",
        category_id,
        ["category_id", "type_code", "name", "description", "sort_order", "enabled", "created_at", "updated_at"],
        [category_id, type_code, name, "", sort_order, enabled, created_at, updated_at],
    )
    return category_id


def _backfill(connection, backend: str, database: str) -> None:
    if not _table_exists(connection, backend, database, "material_taxonomy"):
        return
    taxonomy = _rows(connection, "material_taxonomy")
    categories = {row["item_id"]: row for row in taxonomy if row.get("kind") == "category"}
    series_rows = [row for row in taxonomy if row.get("kind") == "series"]
    now = "1970-01-01T00:00:00+00:00"

    category_aliases: dict[str, str] = {}
    for row in sorted(
        categories.values(),
        key=lambda item: (int(item.get("sort_order") or 0), str(item["item_id"])),
    ):
        original_category_id = str(row["item_id"])
        category_aliases[original_category_id] = _ensure_category(
            connection,
            category_id=original_category_id,
            type_code=str(row.get("top") or "bead"),
            name=str(row.get("name") or "未分类"),
            sort_order=int(row.get("sort_order") or 0),
            enabled=int(bool(row.get("enabled", 1))),
            created_at=str(row.get("created_at") or now),
            updated_at=str(row.get("updated_at") or now),
        )

    legacy_skus = _rows(connection, "managed_materials") if _table_exists(connection, backend, database, "managed_materials") else []
    skus_by_series: dict[str, list[dict[str, Any]]] = {}
    for sku in legacy_skus:
        skus_by_series.setdefault(str(sku.get("series_id") or ""), []).append(sku)

    known_codes: set[str] = set()
    series_ids: set[str] = set()
    series_aliases: dict[str, str] = {}
    series_by_name: dict[tuple[str, str], str] = {}
    for row in sorted(
        series_rows,
        key=lambda item: (int(item.get("sort_order") or 0), str(item["item_id"])),
    ):
        original_series_id = str(row["item_id"])
        original_category_id = str(row.get("parent_id") or "")
        category_id = category_aliases.get(original_category_id, original_category_id)
        category = categories.get(original_category_id)
        if not category:
            type_code = str(row.get("top") or "bead")
            category_id = _slug_id("cat", type_code, "未分类")
            category_id = _ensure_category(
                connection, category_id=category_id, type_code=type_code, name="未分类",
                sort_order=0, enabled=1, created_at=str(row.get("created_at") or now),
                updated_at=str(row.get("updated_at") or now),
            )
        series_name = str(row.get("name") or "未命名品种")
        duplicate_series_id = series_by_name.get((category_id, series_name))
        if duplicate_series_id:
            series_aliases[original_series_id] = duplicate_series_id
            continue
        series_id = original_series_id
        series_aliases[original_series_id] = series_id
        series_by_name[(category_id, series_name)] = series_id
        code = str(row.get("material_code") or "").strip()
        if not code:
            candidates = skus_by_series.get(original_series_id, [])
            code = next((str(item.get("material_code") or "").strip() for item in candidates if item.get("material_code")), "")
        if not code or code in known_codes:
            code = f"legacy-{series_id}"
        known_codes.add(code)
        series_ids.add(series_id)
        _insert_if_missing(
            connection, "material_series_v2", "series_id", series_id,
            ["series_id", "category_id", "material_code", "name", "color", "shine", "asset_version", "sort_order", "enabled", "created_at", "updated_at"],
            [series_id, category_id, code, series_name, str(row.get("color") or ""),
             str(row.get("shine") or ""), max(1, int(row.get("asset_version") or 1)), int(row.get("sort_order") or 0),
             int(bool(row.get("enabled", 1))), str(row.get("created_at") or now), str(row.get("updated_at") or now)],
        )

        knowledge = None
        if _table_exists(connection, backend, database, "material_knowledge"):
            knowledge = connection.execute("SELECT * FROM material_knowledge WHERE code=?", (code,)).fetchone()
        profile = dict(knowledge) if knowledge else {}
        for key in ("code", "name", "created_at", "updated_at"):
            profile.pop(key, None)
        _insert_if_missing(
            connection, "material_series_profiles_v2", "series_id", series_id,
            ["series_id", "profile_json", "created_at", "updated_at"],
            [series_id, json.dumps(profile, ensure_ascii=False, separators=(",", ":")), str(row.get("created_at") or now), str(row.get("updated_at") or now)],
        )
        urls = _json_list(row.get("image_urls_json"))
        primary = str(row.get("image_url") or "").strip()
        if primary and primary not in urls:
            urls.insert(0, primary)
        for index, url in enumerate(str(item).strip() for item in urls if str(item).strip()):
            asset_id = _slug_id("asset", series_id, index, url)
            _insert_if_missing(
                connection, "material_series_assets_v2", "asset_id", asset_id,
                ["asset_id", "series_id", "asset_role", "image_url", "image_path", "sort_order", "enabled", "created_at", "updated_at"],
                [asset_id, series_id, "cover" if index == 0 else "gallery", url,
                 str(row.get("image_path") or "") if index == 0 else "", index, 1,
                 str(row.get("created_at") or now), str(row.get("updated_at") or now)],
            )

    # Legacy rows without a stable taxonomy link receive a deterministic fallback series.
    for sku in legacy_skus:
        original_series_id = str(sku.get("series_id") or "").strip()
        series_id = series_aliases.get(original_series_id, "")
        if not series_id or series_id not in series_ids:
            type_code = str(sku.get("top") or "bead")
            category_name = str(sku.get("category") or "未分类")
            category_id = _slug_id("cat", type_code, category_name)
            category_id = _ensure_category(
                connection, category_id=category_id, type_code=type_code, name=category_name,
                sort_order=0, enabled=1, created_at=str(sku.get("created_at") or now),
                updated_at=str(sku.get("updated_at") or now),
            )
            series_name = str(sku.get("series") or sku.get("name") or "未命名品种")
            series_id = _slug_id("series", type_code, category_name, series_name)
            code = str(sku.get("material_code") or "").strip()
            if not code or code in known_codes:
                code = f"legacy-{series_id}"
            known_codes.add(code)
            _insert_if_missing(
                connection, "material_series_v2", "series_id", series_id,
                ["series_id", "category_id", "material_code", "name", "color", "shine", "asset_version", "sort_order", "enabled", "created_at", "updated_at"],
                [series_id, category_id, code, series_name, str(sku.get("color") or ""), str(sku.get("shine") or ""),
                 1, int(sku.get("sort_order") or 0), int(bool(sku.get("enabled", 1))),
                 str(sku.get("created_at") or now), str(sku.get("updated_at") or now)],
            )
            _insert_if_missing(
                connection, "material_series_profiles_v2", "series_id", series_id,
                ["series_id", "profile_json", "created_at", "updated_at"],
                [series_id, "{}", str(sku.get("created_at") or now), str(sku.get("updated_at") or now)],
            )
            series_ids.add(series_id)

        sku_id = str(sku.get("id") or "").strip()
        sku_code = _unique_sku_code(
            connection, sku_id, str(sku.get("skuId") or sku_id).strip()
        )
        _insert_if_missing(
            connection, "material_skus_v2", "sku_id", sku_id,
            ["sku_id", "series_id", "sku_code", "name", "grade", "price_cents", "cost_cents", "size_mm", "weight_g",
             "physical_specs_json", "supplier_name", "purchase_note", "enabled", "sort_order", "revision", "created_at", "updated_at"],
            [sku_id, series_id, sku_code, str(sku.get("name") or ""), str(sku.get("grade") or ""),
             int(sku.get("price_cents") or _cost_cents(sku.get("price"))), _cost_cents(sku.get("cost_price")),
             sku.get("size") or 0, sku.get("weight") or 0,
             json.dumps(_json_object(sku.get("physical_specs_json")), ensure_ascii=False, separators=(",", ":")),
             str(sku.get("supplier_name") or ""), str(sku.get("purchase_note") or ""), int(bool(sku.get("enabled", 1))),
             int(sku.get("sort_order") or 0), max(1, int(sku.get("revision") or 1)),
             str(sku.get("created_at") or now), str(sku.get("updated_at") or now)],
        )
        stock = max(0, int(sku.get("stock") or 0))
        reserved = max(0, int(sku.get("reserved_stock") or 0))
        if reserved > stock:
            raise ValueError(f"SKU {sku_id} reserved_stock exceeds stock")
        _insert_if_missing(
            connection, "material_inventory_v2", "sku_id", sku_id,
            ["sku_id", "stock", "reserved_stock", "safety_stock", "revision", "updated_at"],
            [sku_id, stock, reserved, max(0, int(sku.get("safety_stock") or 0)), 1, str(sku.get("updated_at") or now)],
        )


def upgrade(connection, backend: str, database: str = "") -> None:
    """Create the normalized material catalog beside the legacy tables and backfill it."""
    _create_tables(connection, backend)
    _backfill(connection, backend, database)


def downgrade(connection, backend: str, database: str = "") -> None:
    """Remove only V2 tables; legacy catalog and order data remain untouched."""
    for table in (
        "material_inventory_v2",
        "material_skus_v2",
        "material_series_assets_v2",
        "material_series_profiles_v2",
        "material_series_v2",
        "material_categories_v2",
    ):
        connection.execute(f"DROP TABLE IF EXISTS {table}")
