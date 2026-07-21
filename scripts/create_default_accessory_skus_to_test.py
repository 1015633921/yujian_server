from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.admin_service import AdminService
from app.database import connect_database, use_mysql
from scripts.import_accessory_varieties_to_test import load_catalog_manifest

TARGET_PREFIX = "accessory_metal_20260720_"
EXPECTED_TARGET_COUNT = 28
DEFAULT_PRICE_CENTS = 1000
DEFAULT_PRICE = "10.00"
DEFAULT_PURCHASE_NOTE = (
    "默认 SKU：待补充珠径/外观最大尺寸、穿线方向占位、外观宽高、重量和库存后再启用"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create disabled, zero-stock default SKUs for the 2026-07-20 accessory catalog in test."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--app-env", default=os.getenv("APP_ENV") or "test")
    parser.add_argument("--mysql-database", default=os.getenv("MYSQL_DATABASE") or "yujian_test")
    parser.add_argument(
        "--operation-id",
        default=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
    )
    parser.add_argument("--result-path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def validate_runtime(args: argparse.Namespace) -> None:
    operation_id = str(args.operation_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{8,32}", operation_id):
        raise SystemExit("operation-id must contain only 8-32 letters, digits, or underscores")
    args.operation_id = operation_id
    os.environ["APP_ENV"] = str(args.app_env)
    os.environ["MYSQL_DATABASE"] = str(args.mysql_database)
    os.environ["DATABASE_BACKEND"] = "mysql"
    app_env = str(args.app_env).lower()
    database = str(args.mysql_database).lower()
    if app_env not in {"test", "testing", "staging"} or "test" not in database:
        raise SystemExit(f"Refusing non-test SKU import: APP_ENV={app_env} MYSQL_DATABASE={database}")
    if not use_mysql():
        raise SystemExit("Default accessory SKU import requires MySQL")


def validate_result_path(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        probe = path.parent / f".default-sku-write-test-{secrets.token_hex(4)}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise SystemExit(f"Result path is not writable: {path} ({exc})") from exc


def load_targets(path: Path) -> list[dict[str, object]]:
    rows = load_catalog_manifest(path)
    if len(rows) != EXPECTED_TARGET_COUNT:
        raise SystemExit(
            f"Expected {EXPECTED_TARGET_COUNT} accessory varieties, received {len(rows)}"
        )
    expected_codes = {f"{TARGET_PREFIX}{index:02d}" for index in range(1, 29)}
    actual_codes = {str(row["material_code"]) for row in rows}
    if actual_codes != expected_codes:
        missing = sorted(expected_codes - actual_codes)
        unexpected = sorted(actual_codes - expected_codes)
        raise SystemExit(f"Target material codes mismatch: missing={missing} unexpected={unexpected}")
    return rows


def default_sku_payload(series: dict[str, object], *, sort_order: int) -> dict[str, object]:
    material_code = str(series["material_code"])
    name = str(series["name"])
    base = {
        "top": "accessory",
        "category": str(series["category"]),
        "series": name,
        "material_code": material_code,
        "name": name,
        "grade": "",
        "size_mm": 0,
    }
    sku_id = AdminService.generate_material_sku(None, base)
    return {
        "id": f"mat_{material_code}_default",
        "skuId": sku_id,
        **base,
        "effect": "结构点缀",
        "element": "metal",
        "price": DEFAULT_PRICE,
        "price_cents": DEFAULT_PRICE_CENTS,
        "size": 0.0,
        "weight": 0.0,
        "cost_price": 0.0,
        "safety_stock": 0,
        "supplier_name": "",
        "purchase_note": DEFAULT_PURCHASE_NOTE,
        "color": str(series.get("color") or "#aeb4b7"),
        "shine": str(series.get("shine") or "#f6f8f9"),
        "image_path": "",
        "image_url": "",
        "image_urls_json": "[]",
        "physical_specs_json": "{}",
        "stock": 0,
        "enabled": 0,
        "sort_order": sort_order,
    }


def preflight_targets(targets: list[dict[str, object]]) -> list[dict[str, object]]:
    target_by_code = {str(row["material_code"]): row for row in targets}
    codes = list(target_by_code)
    placeholders = ",".join("?" for _ in codes)
    with connect_database() as connection:
        rows = connection.execute(
            f"SELECT name,material_code,color,shine,image_url,image_urls_json,sort_order,enabled "
            f"FROM material_taxonomy WHERE kind='series' AND top='accessory' "
            f"AND material_code IN ({placeholders})",
            codes,
        ).fetchall()
        existing_skus = connection.execute(
            f"SELECT id,skuId,material_code FROM managed_materials "
            f"WHERE material_code IN ({placeholders})",
            codes,
        ).fetchall()
        candidate_skus = [
            str(default_sku_payload({**target_by_code[str(row["material_code"])], **dict(row)}, sort_order=0)["skuId"])
            for row in rows
        ]
        sku_placeholders = ",".join("?" for _ in candidate_skus)
        sku_conflicts = connection.execute(
            f"SELECT id,skuId FROM managed_materials WHERE skuId IN ({sku_placeholders})",
            candidate_skus,
        ).fetchall()
    if len(rows) != len(targets):
        found = {str(row["material_code"]) for row in rows}
        raise SystemExit(f"Missing test catalog varieties: {sorted(set(codes) - found)}")
    if existing_skus:
        raise SystemExit(
            "Refusing to overwrite existing SKUs: "
            + ", ".join(str(row["material_code"]) for row in existing_skus)
        )
    if sku_conflicts:
        raise SystemExit(
            "Generated SKU IDs conflict with existing rows: "
            + ", ".join(str(row["skuId"]) for row in sku_conflicts)
        )

    series_rows: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        if not bool(item["enabled"]):
            raise SystemExit(f"Target variety is disabled: {item['name']}")
        try:
            image_urls = json.loads(item.get("image_urls_json") or "[]")
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid variety image JSON: {item['name']}") from exc
        if (
            not isinstance(image_urls, list)
            or len(image_urls) != 2
            or str(item.get("image_url") or "") != str(image_urls[0])
        ):
            raise SystemExit(f"Variety must have exactly two consistent images: {item['name']}")
        manifest_row = target_by_code[str(item["material_code"])]
        if str(item["name"]) != str(manifest_row["name"]):
            raise SystemExit(f"Variety name mismatch: {item['material_code']}")
        item["category"] = str(manifest_row["category"])
        series_rows.append(item)
    return sorted(series_rows, key=lambda row: str(row["material_code"]))


def create_backup_table(operation_id: str) -> tuple[str, int]:
    backup_table = f"bak_acc_sku_{operation_id}"
    with connect_database() as connection:
        existing = connection.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA=? AND TABLE_NAME=?",
            (os.environ["MYSQL_DATABASE"], backup_table),
        ).fetchone()
        if existing:
            raise SystemExit(f"Backup table already exists: {backup_table}")
        connection.execute(f"CREATE TABLE {backup_table} LIKE managed_materials")
        cursor = connection.execute(
            f"INSERT INTO {backup_table} SELECT * FROM managed_materials WHERE top='accessory'"
        )
        count = int(cursor.rowcount or 0)
    return backup_table, count


def insert_material_audit(connection: Any, sku: dict[str, object], timestamp: str) -> None:
    connection.execute(
        "INSERT INTO material_audit_logs "
        "(log_id,action,target_type,target_id,material_id,material_code,actor_id,actor_name,"
        "summary,before_json,after_json,created_at) "
        "VALUES (?, 'create', 'material', ?, ?, ?, 'default_sku_import', "
        "'default_sku_import', ?, '{}', ?, ?)",
        (
            f"matlog_{secrets.token_hex(12)}",
            sku["id"],
            sku["id"],
            sku["material_code"],
            f"新增待完善默认 SKU：{sku['name']}",
            json.dumps(sku, ensure_ascii=False),
            timestamp,
        ),
    )


def apply_default_skus(series_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    skus = [
        default_sku_payload(row, sort_order=int(row.get("sort_order") or 0))
        for row in series_rows
    ]
    with connect_database() as connection:
        for sku in skus:
            connection.execute(
                "INSERT INTO managed_materials "
                "(id,skuId,top,category,series,material_code,grade,name,effect,element,price,"
                "price_cents,size,weight,cost_price,safety_stock,supplier_name,purchase_note,"
                "color,shine,image_path,image_url,image_urls_json,physical_specs_json,stock,enabled,"
                "sort_order,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    sku["id"], sku["skuId"], sku["top"], sku["category"], sku["series"],
                    sku["material_code"], sku["grade"], sku["name"], sku["effect"],
                    sku["element"], sku["price"], sku["price_cents"], sku["size"],
                    sku["weight"], sku["cost_price"], sku["safety_stock"],
                    sku["supplier_name"], sku["purchase_note"], sku["color"], sku["shine"],
                    sku["image_path"], sku["image_url"], sku["image_urls_json"],
                    sku["physical_specs_json"], sku["stock"], sku["enabled"],
                    sku["sort_order"], timestamp, timestamp,
                ),
            )
            insert_material_audit(connection, sku, timestamp)
    return skus


def is_safe_default_sku_row(item: dict[str, Any]) -> bool:
    try:
        database_price = Decimal(str(item.get("price")))
        image_urls = json.loads(item.get("image_urls_json") or "[]")
        physical_specs = json.loads(item.get("physical_specs_json") or "{}")
    except (InvalidOperation, TypeError, ValueError, json.JSONDecodeError):
        return False
    return not (
        int(item.get("price_cents") or 0) != DEFAULT_PRICE_CENTS
        or database_price != Decimal(DEFAULT_PRICE)
        or float(item.get("size") or 0) != 0
        or float(item.get("weight") or 0) != 0
        or int(item.get("stock") or 0) != 0
        or int(item.get("reserved_stock") or 0) != 0
        or bool(item.get("enabled"))
        or str(item.get("image_path") or "") != ""
        or str(item.get("image_url") or "") != ""
        or image_urls != []
        or physical_specs != {}
    )


def verify_database(targets: list[dict[str, object]], skus: list[dict[str, object]]) -> None:
    codes = [str(row["material_code"]) for row in targets]
    placeholders = ",".join("?" for _ in codes)
    with connect_database() as connection:
        rows = connection.execute(
            f"SELECT * FROM managed_materials WHERE material_code IN ({placeholders}) "
            f"ORDER BY material_code",
            codes,
        ).fetchall()
        series = connection.execute(
            f"SELECT material_code,image_url,image_urls_json FROM material_taxonomy "
            f"WHERE kind='series' AND material_code IN ({placeholders})",
            codes,
        ).fetchall()
    expected_ids = {str(sku["id"]) for sku in skus}
    if len(rows) != len(targets) or {str(row["id"]) for row in rows} != expected_ids:
        raise RuntimeError(f"Default SKU count or identity mismatch: {len(rows)}")
    for row in rows:
        item = dict(row)
        if not is_safe_default_sku_row(item):
            raise RuntimeError(f"Unsafe default SKU values: {item['material_code']}")
    if len(series) != len(targets):
        raise RuntimeError("Variety image verification count mismatch")
    for row in series:
        urls = json.loads(row["image_urls_json"] or "[]")
        if len(urls) != 2 or row["image_url"] != urls[0]:
            raise RuntimeError(f"Variety images changed unexpectedly: {row['material_code']}")


def main() -> None:
    args = parse_args()
    validate_runtime(args)
    targets = load_targets(args.manifest)
    series_rows = preflight_targets(targets)
    print(
        f"preflight varieties={len(series_rows)} price_cents={DEFAULT_PRICE_CENTS} "
        f"stock=0 enabled=0 database={args.mysql_database}",
        flush=True,
    )
    if args.dry_run:
        return
    validate_result_path(args.result_path)
    backup_table, backup_rows = create_backup_table(args.operation_id)
    skus = apply_default_skus(series_rows)
    verify_database(targets, skus)
    result = {
        "operation_id": args.operation_id,
        "environment": args.app_env,
        "database": args.mysql_database,
        "default_skus_created": len(skus),
        "price_cents": DEFAULT_PRICE_CENTS,
        "stock": 0,
        "enabled": False,
        "dimensions_pending": True,
        "backup_table": backup_table,
        "backup_rows": backup_rows,
        "material_ids": [str(sku["id"]) for sku in skus],
        "material_codes": [str(sku["material_code"]) for sku in skus],
    }
    if args.result_path:
        args.result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
