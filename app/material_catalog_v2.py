from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import hashlib
from typing import Any


V2_TABLES = (
    "material_categories_v2",
    "material_series_v2",
    "material_series_profiles_v2",
    "material_series_assets_v2",
    "material_skus_v2",
    "material_inventory_v2",
)


def _upsert(connection, table: str, key: str, values: dict[str, Any]) -> None:
    identity = values[key]
    exists = connection.execute(
        f"SELECT 1 FROM {table} WHERE {key}=?", (identity,)
    ).fetchone()
    if exists:
        changes = [column for column in values if column != key]
        connection.execute(
            f"UPDATE {table} SET {', '.join(f'{column}=?' for column in changes)} WHERE {key}=?",
            [*(values[column] for column in changes), identity],
        )
        return
    connection.execute(
        f"INSERT INTO {table} ({', '.join(values)}) VALUES ({', '.join('?' for _ in values)})",
        list(values.values()),
    )


def catalog_v2_available(connection) -> bool:
    try:
        connection.execute("SELECT 1 FROM material_skus_v2 WHERE 1=0")
    except Exception:
        return False
    return True


def sync_legacy_category_to_v2(connection, category_id: str) -> str:
    if not catalog_v2_available(connection):
        return category_id
    row = connection.execute(
        "SELECT * FROM material_taxonomy WHERE item_id=? AND kind='category'", (category_id,)
    ).fetchone()
    if not row:
        return category_id
    item = dict(row)
    type_code = str(item.get("top") or "bead")
    name = str(item.get("name") or "未分类")
    canonical = connection.execute(
        "SELECT category_id FROM material_categories_v2 "
        "WHERE type_code=? AND name=? ORDER BY category_id LIMIT 1",
        (type_code, name),
    ).fetchone()
    if canonical and str(canonical["category_id"]) != category_id:
        return str(canonical["category_id"])
    _upsert(connection, "material_categories_v2", "category_id", {
        "category_id": str(item["item_id"]),
        "type_code": type_code,
        "name": name,
        "description": "",
        "sort_order": int(item.get("sort_order") or 0),
        "enabled": int(bool(item.get("enabled", 1))),
        "created_at": str(item.get("created_at") or item.get("updated_at") or ""),
        "updated_at": str(item.get("updated_at") or ""),
    })
    return category_id


def sync_legacy_series_to_v2(connection, series_id: str) -> str:
    if not catalog_v2_available(connection):
        return series_id
    row = connection.execute(
        "SELECT * FROM material_taxonomy WHERE item_id=? AND kind='series'", (series_id,)
    ).fetchone()
    if not row:
        return series_id
    item = dict(row)
    category_id = sync_legacy_category_to_v2(
        connection, str(item.get("parent_id") or "")
    )
    name = str(item.get("name") or "未命名品种")
    canonical = connection.execute(
        "SELECT series_id FROM material_series_v2 "
        "WHERE category_id=? AND name=? ORDER BY series_id LIMIT 1",
        (category_id, name),
    ).fetchone()
    if canonical and str(canonical["series_id"]) != series_id:
        return str(canonical["series_id"])
    code = str(item.get("material_code") or f"legacy-{series_id}")
    code_owner = connection.execute(
        "SELECT series_id FROM material_series_v2 WHERE material_code=?",
        (code,),
    ).fetchone()
    if code_owner and str(code_owner["series_id"]) != series_id:
        code = f"legacy-{series_id}"
    _upsert(connection, "material_series_v2", "series_id", {
        "series_id": series_id,
        "category_id": category_id,
        "material_code": code,
        "name": name,
        "color": str(item.get("color") or ""),
        "shine": str(item.get("shine") or ""),
        "asset_version": max(1, int(item.get("asset_version") or 1)),
        "sort_order": int(item.get("sort_order") or 0),
        "enabled": int(bool(item.get("enabled", 1))),
        "created_at": str(item.get("created_at") or item.get("updated_at") or ""),
        "updated_at": str(item.get("updated_at") or ""),
    })
    knowledge = connection.execute(
        "SELECT * FROM material_knowledge WHERE code=?", (code,)
    ).fetchone()
    profile = dict(knowledge) if knowledge else {}
    for key in ("code", "name", "created_at", "updated_at"):
        profile.pop(key, None)
    _upsert(connection, "material_series_profiles_v2", "series_id", {
        "series_id": series_id,
        "profile_json": json.dumps(profile, ensure_ascii=False, separators=(",", ":")),
        "created_at": str(item.get("created_at") or item.get("updated_at") or ""),
        "updated_at": str(item.get("updated_at") or ""),
    })
    connection.execute("DELETE FROM material_series_assets_v2 WHERE series_id=?", (series_id,))
    urls = _json_list(item.get("image_urls_json"))
    primary = str(item.get("image_url") or "").strip()
    if primary and primary not in urls:
        urls.insert(0, primary)
    for index, raw_url in enumerate(urls):
        url = str(raw_url or "").strip()
        if not url:
            continue
        asset_id = f"asset_{hashlib.sha1(f'{series_id}|{index}|{url}'.encode('utf-8')).hexdigest()[:24]}"
        _upsert(connection, "material_series_assets_v2", "asset_id", {
            "asset_id": asset_id,
            "series_id": series_id,
            "asset_role": "cover" if index == 0 else "gallery",
            "image_url": url,
            "image_path": str(item.get("image_path") or "") if index == 0 else "",
            "sort_order": index,
            "enabled": 1,
            "created_at": str(item.get("created_at") or item.get("updated_at") or ""),
            "updated_at": str(item.get("updated_at") or ""),
        })
    return series_id


def sync_legacy_sku_to_v2(connection, sku_id: str) -> None:
    if not catalog_v2_available(connection):
        return
    row = connection.execute("SELECT * FROM managed_materials WHERE id=?", (sku_id,)).fetchone()
    if not row:
        connection.execute("DELETE FROM material_inventory_v2 WHERE sku_id=?", (sku_id,))
        connection.execute("DELETE FROM material_skus_v2 WHERE sku_id=?", (sku_id,))
        return
    item = dict(row)
    series_id = str(item.get("series_id") or "")
    if not series_id:
        # Direct legacy imports may still bypass the catalog service.  Do not
        # break their original write; the readiness validator will report the
        # missing V2 SKU and block cutover until the import is repaired.
        return
    series_id = sync_legacy_series_to_v2(connection, series_id)
    _upsert(connection, "material_skus_v2", "sku_id", {
        "sku_id": sku_id,
        "series_id": series_id,
        "sku_code": str(item.get("skuId") or sku_id),
        "name": str(item.get("name") or ""),
        "grade": str(item.get("grade") or ""),
        "price_cents": _price_cents(item),
        "cost_cents": int((_decimal(item.get("cost_price")) * 100).quantize(Decimal("1"))),
        "size_mm": item.get("size") or 0,
        "weight_g": item.get("weight") or 0,
        "physical_specs_json": json.dumps(
            _json_object(item.get("physical_specs_json")), ensure_ascii=False, separators=(",", ":")
        ),
        "supplier_name": str(item.get("supplier_name") or ""),
        "purchase_note": str(item.get("purchase_note") or ""),
        "enabled": int(bool(item.get("enabled", 1))),
        "sort_order": int(item.get("sort_order") or 0),
        "revision": max(1, int(item.get("revision") or 1)),
        "created_at": str(item.get("created_at") or item.get("updated_at") or ""),
        "updated_at": str(item.get("updated_at") or ""),
    })
    stock = max(0, int(item.get("stock") or 0))
    reserved = max(0, int(item.get("reserved_stock") or 0))
    if reserved > stock:
        raise ValueError(f"SKU {sku_id} reserved_stock exceeds stock")
    _upsert(connection, "material_inventory_v2", "sku_id", {
        "sku_id": sku_id,
        "stock": stock,
        "reserved_stock": reserved,
        "safety_stock": max(0, int(item.get("safety_stock") or 0)),
        "revision": max(1, int(item.get("revision") or 1)),
        "updated_at": str(item.get("updated_at") or ""),
    })


def sync_legacy_hierarchy_to_v2(
    connection,
    taxonomy_id: str,
    *,
    include_inventory: bool = True,
) -> None:
    if not catalog_v2_available(connection):
        return
    row = connection.execute(
        "SELECT * FROM material_taxonomy WHERE item_id=?", (taxonomy_id,)
    ).fetchone()
    if not row:
        return
    item = dict(row)
    if item.get("kind") == "series":
        sync_legacy_series_to_v2(connection, taxonomy_id)
        sku_rows = connection.execute(
            "SELECT id, enabled FROM managed_materials WHERE series_id=?", (taxonomy_id,)
        ).fetchall()
        for sku in sku_rows:
            if include_inventory:
                sync_legacy_sku_to_v2(connection, str(sku["id"]))
            else:
                connection.execute(
                    "UPDATE material_skus_v2 SET enabled=? WHERE sku_id=?",
                    (int(bool(sku["enabled"])), str(sku["id"])),
                )
        return
    sync_legacy_category_to_v2(connection, taxonomy_id)
    children = connection.execute(
        "SELECT item_id FROM material_taxonomy WHERE kind='series' AND parent_id=?", (taxonomy_id,)
    ).fetchall()
    for child in children:
        sync_legacy_hierarchy_to_v2(
            connection,
            str(child["item_id"]),
            include_inventory=include_inventory,
        )


def delete_taxonomy_from_v2(connection, taxonomy_id: str, kind: str) -> None:
    if not catalog_v2_available(connection):
        return
    if kind == "category":
        connection.execute("DELETE FROM material_categories_v2 WHERE category_id=?", (taxonomy_id,))
        return
    connection.execute("DELETE FROM material_series_assets_v2 WHERE series_id=?", (taxonomy_id,))
    connection.execute("DELETE FROM material_series_profiles_v2 WHERE series_id=?", (taxonomy_id,))
    connection.execute("DELETE FROM material_series_v2 WHERE series_id=?", (taxonomy_id,))


def sync_legacy_type_to_v2(
    connection,
    type_code: str,
    *,
    include_inventory: bool = True,
) -> None:
    if not catalog_v2_available(connection):
        return
    categories = connection.execute(
        "SELECT item_id FROM material_taxonomy WHERE kind='category' AND top=?",
        (type_code,),
    ).fetchall()
    for category in categories:
        sync_legacy_hierarchy_to_v2(
            connection,
            str(category["item_id"]),
            include_inventory=include_inventory,
        )


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0)


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


def _price_cents(row: dict[str, Any]) -> int:
    value = row.get("price_cents")
    if value not in (None, ""):
        return int(value)
    return int((_decimal(row.get("price")) * 100).quantize(Decimal("1")))


def _table_exists(connection, table: str, *, mysql: bool = False, database: str = "") -> bool:
    if mysql:
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


def validate_material_catalog_v2(
    connection,
    *,
    mysql: bool = False,
    database: str = "",
    issue_limit: int = 100,
    compare_legacy_inventory: bool = True,
) -> dict[str, Any]:
    """Validate the normalized catalog, optionally comparing the legacy inventory ledger."""
    missing_tables = [
        table for table in V2_TABLES if not _table_exists(connection, table, mysql=mysql, database=database)
    ]
    if missing_tables:
        return {
            "ready": False,
            "counts": {},
            "issues": [{"code": "missing_table", "table": table} for table in missing_tables],
        }

    legacy_rows = [dict(row) for row in connection.execute("SELECT * FROM managed_materials").fetchall()]
    v2_rows = {
        str(row["sku_id"]): dict(row)
        for row in connection.execute("SELECT * FROM material_skus_v2").fetchall()
    }
    inventory_rows = {
        str(row["sku_id"]): dict(row)
        for row in connection.execute("SELECT * FROM material_inventory_v2").fetchall()
    }
    hierarchy_rows = {
        str(row["sku_id"]): dict(row)
        for row in connection.execute(
            "SELECT k.sku_id, t.type_code AS top, c.name AS category, s.name AS series "
            "FROM material_skus_v2 k "
            "JOIN material_series_v2 s ON s.series_id=k.series_id "
            "JOIN material_categories_v2 c ON c.category_id=s.category_id "
            "JOIN material_types t ON t.type_code=c.type_code"
        ).fetchall()
    }
    issues: list[dict[str, Any]] = []

    def add(code: str, entity_id: str, field: str = "", legacy: Any = None, v2: Any = None) -> None:
        if len(issues) < max(1, issue_limit):
            issue = {"code": code, "entity_id": entity_id}
            if field:
                issue.update({"field": field, "legacy": legacy, "v2": v2})
            issues.append(issue)

    for legacy in legacy_rows:
        sku_id = str(legacy.get("id") or "")
        sku = v2_rows.get(sku_id)
        inventory = inventory_rows.get(sku_id)
        if not sku:
            add("missing_sku", sku_id)
            continue
        if not inventory:
            add("missing_inventory", sku_id)
            continue
        expected_fields = {
            "price_cents": _price_cents(legacy),
            "size_mm": _decimal(legacy.get("size")),
            "weight_g": _decimal(legacy.get("weight")),
            "enabled": int(bool(legacy.get("enabled"))),
        }
        for field, expected in expected_fields.items():
            actual = _decimal(sku.get(field)) if field in {"size_mm", "weight_g"} else int(sku.get(field) or 0)
            if actual != expected:
                add("sku_field_mismatch", sku_id, field, str(expected), str(actual))
        hierarchy = hierarchy_rows.get(sku_id, {})
        for field in ("top", "category", "series"):
            expected = str(legacy.get(field) or "").strip()
            actual = str(hierarchy.get(field) or "").strip()
            if expected and actual != expected:
                add("sku_field_mismatch", sku_id, field, expected, actual)
        if compare_legacy_inventory:
            for field in ("stock", "reserved_stock", "safety_stock"):
                expected = max(0, int(legacy.get(field) or 0))
                actual = int(inventory.get(field) or 0)
                if actual != expected:
                    add("inventory_field_mismatch", sku_id, field, expected, actual)

        stock = int(inventory.get("stock") or 0)
        reserved = int(inventory.get("reserved_stock") or 0)
        safety = int(inventory.get("safety_stock") or 0)
        if stock < 0 or reserved < 0 or safety < 0 or reserved > stock:
            add(
                "invalid_v2_inventory",
                sku_id,
                "stock/reserved_stock/safety_stock",
                None,
                f"{stock}/{reserved}/{safety}",
            )

    legacy_ids = {str(row.get("id") or "") for row in legacy_rows}
    for sku_id in sorted(set(v2_rows) - legacy_ids):
        add("unexpected_v2_sku", sku_id)
    for sku_id in sorted(set(inventory_rows) - set(v2_rows)):
        add("orphan_inventory", sku_id)

    orphan_skus = int(
        connection.execute(
            "SELECT COUNT(*) AS total FROM material_skus_v2 k "
            "LEFT JOIN material_series_v2 s ON s.series_id=k.series_id WHERE s.series_id IS NULL"
        ).fetchone()["total"]
    )
    orphan_series = int(
        connection.execute(
            "SELECT COUNT(*) AS total FROM material_series_v2 s "
            "LEFT JOIN material_categories_v2 c ON c.category_id=s.category_id WHERE c.category_id IS NULL"
        ).fetchone()["total"]
    )
    if orphan_skus:
        add("orphan_sku_series", str(orphan_skus))
    if orphan_series:
        add("orphan_series_category", str(orphan_series))

    counts = {
        "legacy_skus": len(legacy_rows),
        "v2_categories": int(connection.execute("SELECT COUNT(*) AS total FROM material_categories_v2").fetchone()["total"]),
        "v2_series": int(connection.execute("SELECT COUNT(*) AS total FROM material_series_v2").fetchone()["total"]),
        "v2_skus": len(v2_rows),
        "v2_inventory": len(inventory_rows),
    }
    return {"ready": not issues, "counts": counts, "issues": issues}


def fetch_order_material_rows_v2(
    connection,
    references: set[str],
    *,
    lock: bool = False,
) -> list[dict[str, Any]]:
    """Return V2 rows in the stable legacy snapshot shape used by checkout."""
    marks = ", ".join(["?"] * len(references))
    lock_clause = " FOR UPDATE" if lock else ""
    rows = connection.execute(
        f"""
        SELECT k.sku_id AS id, k.sku_code AS skuId, t.type_code AS top,
               c.name AS category, s.name AS series, k.grade, k.name,
               k.price_cents, k.size_mm AS size, k.weight_g AS weight,
               k.physical_specs_json, i.stock, i.reserved_stock, k.enabled,
               k.updated_at, k.series_id, s.material_code, p.profile_json
        FROM material_skus_v2 k
        JOIN material_inventory_v2 i ON i.sku_id=k.sku_id
        JOIN material_series_v2 s ON s.series_id=k.series_id
        JOIN material_categories_v2 c ON c.category_id=s.category_id
        JOIN material_types t ON t.type_code=c.type_code
        LEFT JOIN material_series_profiles_v2 p ON p.series_id=s.series_id
        WHERE (k.sku_id IN ({marks}) OR k.sku_code IN ({marks}))
          AND k.enabled=1 AND s.enabled=1 AND c.enabled=1 AND t.enabled=1
        ORDER BY k.sku_id{lock_clause}
        """,
        [*sorted(references), *sorted(references)],
    ).fetchall()
    result: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        try:
            profile = json.loads(str(row.pop("profile_json", "") or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            profile = {}
        effects = profile.get("effects")
        if not effects:
            try:
                effects = json.loads(str(profile.get("effects_json") or "[]"))
            except (TypeError, ValueError, json.JSONDecodeError):
                effects = []
        row["effect"] = str((effects or [""])[0])
        row["element"] = str(profile.get("primary_element") or "")
        row.update({"color": "", "shine": "", "image_path": "", "image_url": "", "image_urls_json": "[]"})
        result.append(row)
    return result


def fetch_material_row_v2(connection, sku_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT k.sku_id AS id, k.sku_code AS skuId, c.type_code AS top,
               c.name AS category, s.name AS series, k.series_id, s.material_code,
               k.grade, k.name, '' AS effect, '' AS element,
               (k.price_cents / 100.0) AS price, k.price_cents,
               k.size_mm AS size, k.weight_g AS weight, (k.cost_cents / 100.0) AS cost_price,
               i.safety_stock, k.supplier_name, k.purchase_note,
               s.color, s.shine, '' AS image_path, '' AS image_url, '[]' AS image_urls_json,
               k.physical_specs_json, i.stock, i.reserved_stock, k.enabled, k.sort_order,
               k.revision, k.created_at, k.updated_at
        FROM material_skus_v2 k
        JOIN material_inventory_v2 i ON i.sku_id=k.sku_id
        JOIN material_series_v2 s ON s.series_id=k.series_id
        JOIN material_categories_v2 c ON c.category_id=s.category_id
        WHERE k.sku_id=?
        """,
        (sku_id,),
    ).fetchone()
    return dict(row) if row else None
