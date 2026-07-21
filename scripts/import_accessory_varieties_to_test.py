from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.admin_service import AdminService
from app.database import connect_database, use_mysql
from app.material_knowledge import upsert_material_knowledge

TEST_BUCKET = "yujian-test-1258267288"
TEST_CDN = "https://cdn-test.yustream.cn"
DEFAULT_PREFIX = "materials/accessories/20260720-catalog"


def load_catalog_manifest(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise SystemExit("Accessory catalog manifest must be a non-empty JSON array")
    required = {"category", "name", "material_code", "sources"}
    names: set[str] = set()
    codes: set[str] = set()
    rows: list[dict[str, object]] = []
    for raw in payload:
        if not isinstance(raw, dict):
            raise SystemExit("Accessory catalog manifest rows must be objects")
        missing = sorted(key for key in required if not raw.get(key))
        if missing:
            raise SystemExit("Manifest row is missing: " + ", ".join(missing))
        sources = raw.get("sources")
        if not isinstance(sources, list) or len(sources) != 2:
            raise SystemExit(f"{raw.get('name')}: exactly two source images are required")
        name = str(raw["name"]).strip()
        code = str(raw["material_code"]).strip()
        if name in names or code in codes:
            raise SystemExit(f"Duplicate variety name or material code: {name} / {code}")
        names.add(name)
        codes.add(code)
        rows.append({**raw, "top": "accessory"})
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create accessory categories and varieties in the test catalog; no SKU is created."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--assets-root", type=Path, required=True)
    parser.add_argument("--cos-prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--bucket", default=os.getenv("TENCENT_COS_BUCKET") or TEST_BUCKET)
    parser.add_argument("--region", default=os.getenv("TENCENT_COS_REGION") or "ap-guangzhou")
    parser.add_argument("--cdn-base-url", default=os.getenv("TENCENT_COS_CDN_BASE_URL") or TEST_CDN)
    parser.add_argument("--secret-id", default=os.getenv("TENCENT_COS_SECRET_ID"))
    parser.add_argument("--secret-key", default=os.getenv("TENCENT_COS_SECRET_KEY"))
    parser.add_argument("--app-env", default=os.getenv("APP_ENV") or "test")
    parser.add_argument("--mysql-database", default=os.getenv("MYSQL_DATABASE") or "yujian_test")
    parser.add_argument(
        "--operation-id",
        default=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
    )
    parser.add_argument("--result-path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
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
        raise SystemExit(f"Refusing non-test import: APP_ENV={app_env} MYSQL_DATABASE={database}")
    if str(args.bucket) != TEST_BUCKET:
        raise SystemExit(f"Refusing non-test bucket: {args.bucket}")
    if str(args.cdn_base_url).rstrip("/") != TEST_CDN:
        raise SystemExit(f"Refusing non-test CDN: {args.cdn_base_url}")
    if not use_mysql():
        raise SystemExit("Accessory catalog import requires MySQL")


def validate_result_path(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        probe = path.parent / f".catalog-import-write-test-{secrets.token_hex(4)}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise SystemExit(f"Result path is not writable: {path} ({exc})") from exc


def object_key(prefix: str, material_code: str, index: int, path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"{prefix.strip('/')}/{material_code}/{index:02d}-{digest}.webp"


def public_url(cdn_base_url: str, key: str) -> str:
    return f"{cdn_base_url.rstrip('/')}/{quote(key, safe='/')}"


def split_display_and_gallery_urls(urls: list[str] | tuple[str, ...]) -> tuple[str, list[str]]:
    normalized = [str(url or "").strip() for url in urls if str(url or "").strip()]
    if len(normalized) < 2:
        raise ValueError("Accessory variety requires one display image and at least one gallery image")
    return normalized[0], normalized[1:]


def build_catalog(args: argparse.Namespace) -> list[dict[str, object]]:
    rows = load_catalog_manifest(args.manifest)
    catalog: list[dict[str, object]] = []
    for row in rows:
        code = str(row["material_code"])
        files = tuple(
            (args.assets_root / code / f"{code}-{index:02d}.webp").resolve()
            for index in (1, 2)
        )
        missing = [str(path) for path in files if not path.is_file()]
        if missing:
            raise SystemExit("Missing processed assets: " + ", ".join(missing))
        keys = tuple(
            object_key(args.cos_prefix, code, index, path)
            for index, path in enumerate(files, start=1)
        )
        urls = tuple(public_url(args.cdn_base_url, key) for key in keys)
        catalog.append({**row, "files": files, "keys": keys, "urls": urls})
    return catalog


def preflight_catalog(catalog: list[dict[str, object]]) -> dict[str, str]:
    categories = list(dict.fromkeys(str(row["category"]) for row in catalog))
    category_ids: dict[str, str] = {}
    names = [str(row["name"]) for row in catalog]
    codes = [str(row["material_code"]) for row in catalog]
    with connect_database() as connection:
        material_type = connection.execute(
            "SELECT type_code, enabled FROM material_types WHERE type_code='accessory'"
        ).fetchone()
        if not material_type or not bool(material_type["enabled"]):
            raise SystemExit("The accessory material type is missing or disabled")
        for category in categories:
            rows = connection.execute(
                "SELECT item_id, kind, top FROM material_taxonomy WHERE name=?",
                (category,),
            ).fetchall()
            invalid = [row for row in rows if row["kind"] != "category" or row["top"] != "accessory"]
            if invalid:
                raise SystemExit(f"Taxonomy name conflict for category: {category}")
            existing = next((row for row in rows if row["kind"] == "category"), None)
            category_ids[category] = (
                str(existing["item_id"])
                if existing
                else AdminService.material_taxonomy_id("category", "accessory", category)
            )
        placeholders = ",".join("?" for _ in names)
        existing_series = connection.execute(
            f"SELECT item_id, name, material_code FROM material_taxonomy "
            f"WHERE kind='series' AND (name IN ({placeholders}) OR material_code IN ({placeholders}))",
            (*names, *codes),
        ).fetchall()
        if existing_series:
            raise SystemExit(
                "Refusing to overwrite existing varieties: "
                + ", ".join(str(row["name"]) for row in existing_series)
            )
        existing_skus = connection.execute(
            f"SELECT id, material_code FROM managed_materials WHERE material_code IN ({placeholders})",
            codes,
        ).fetchall()
        if existing_skus:
            raise SystemExit("Refusing import because target material codes already have SKUs")
    return category_ids


def cos_client(args: argparse.Namespace):
    from qcloud_cos import CosConfig, CosS3Client

    if not args.secret_id or not args.secret_key:
        raise SystemExit("Missing test COS credentials")
    return CosS3Client(
        CosConfig(
            Region=args.region,
            SecretId=args.secret_id,
            SecretKey=args.secret_key,
            Scheme="https",
        )
    )


def upload_assets(args: argparse.Namespace, catalog: list[dict[str, object]]) -> int:
    client = cos_client(args)
    payload = [
        (path, key)
        for row in catalog
        for path, key in zip(row["files"], row["keys"], strict=True)
    ]
    for index, (path, key) in enumerate(payload, start=1):
        if not args.skip_upload:
            client.put_object_from_local_file(
                Bucket=args.bucket,
                LocalFilePath=str(path),
                Key=str(key),
            )
        client.head_object(Bucket=args.bucket, Key=str(key))
        if index == 1 or index % 20 == 0 or index == len(payload):
            print(f"cos_verified={index}/{len(payload)}", flush=True)
    return len(payload)


def verify_cdn_url(url: str) -> str | None:
    request = Request(url, method="HEAD", headers={"User-Agent": "YujianAssetVerifier/1.0"})
    try:
        with urlopen(request, timeout=15) as response:
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if response.status != 200 or "image/webp" not in content_type:
                return f"{url} status={response.status} content-type={content_type}"
    except Exception as exc:
        return f"{url} error={type(exc).__name__}:{exc}"
    return None


def verify_cdn(catalog: list[dict[str, object]]) -> int:
    urls = [str(url) for row in catalog for url in row["urls"]]
    failures: list[str] = []
    for attempt in range(1, 5):
        with ThreadPoolExecutor(max_workers=20) as executor:
            failures = [failure for failure in executor.map(verify_cdn_url, urls) if failure]
        if not failures:
            return len(urls)
        if attempt < 4:
            time.sleep(attempt * 2)
    raise SystemExit("CDN verification failed: " + "; ".join(failures[:6]))


def create_backup_tables(operation_id: str) -> tuple[str, str]:
    taxonomy_table = f"bak_acc_tax_{operation_id}"
    knowledge_table = f"bak_acc_knowledge_{operation_id}"
    with connect_database() as connection:
        existing = connection.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA=? AND TABLE_NAME IN (?, ?)",
            (os.environ["MYSQL_DATABASE"], taxonomy_table, knowledge_table),
        ).fetchall()
        if existing:
            raise SystemExit(f"Backup table already exists for operation {operation_id}")
        connection.execute(f"CREATE TABLE {taxonomy_table} LIKE material_taxonomy")
        connection.execute(
            f"INSERT INTO {taxonomy_table} SELECT * FROM material_taxonomy WHERE top='accessory'"
        )
        connection.execute(f"CREATE TABLE {knowledge_table} LIKE material_knowledge")
        code_rows = connection.execute(
            "SELECT DISTINCT material_code FROM material_taxonomy "
            "WHERE kind='series' AND top='accessory' AND COALESCE(material_code, '') <> ''"
        ).fetchall()
        codes = [str(row["material_code"]) for row in code_rows]
        if codes:
            placeholders = ",".join("?" for _ in codes)
            connection.execute(
                f"INSERT INTO {knowledge_table} SELECT * FROM material_knowledge "
                f"WHERE code IN ({placeholders})",
                codes,
            )
    return taxonomy_table, knowledge_table


def insert_taxonomy_audit(
    connection,
    *,
    item_id: str,
    material_code: str,
    summary: str,
    after: dict[str, object],
) -> None:
    connection.execute(
        "INSERT INTO material_audit_logs "
        "(log_id,action,target_type,target_id,material_id,material_code,actor_id,actor_name,"
        "summary,before_json,after_json,created_at) "
        "VALUES (?, 'taxonomy_create', 'material_taxonomy', ?, '', ?, 'catalog_import', "
        "'catalog_import', ?, '{}', ?, ?)",
        (
            f"matlog_{secrets.token_hex(12)}",
            item_id,
            material_code,
            summary,
            json.dumps(after, ensure_ascii=False),
            datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        ),
    )


def apply_catalog(
    catalog: list[dict[str, object]],
    category_ids: dict[str, str],
) -> tuple[list[str], list[str]]:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    created_categories: list[str] = []
    created_series: list[str] = []
    with connect_database() as connection:
        for sort_order, (category, category_id) in enumerate(category_ids.items(), start=100):
            existing = connection.execute(
                "SELECT item_id FROM material_taxonomy WHERE item_id=?",
                (category_id,),
            ).fetchone()
            if existing:
                continue
            after = {
                "item_id": category_id,
                "parent_id": "",
                "kind": "category",
                "top": "accessory",
                "name": category,
                "sort_order": sort_order,
                "enabled": 1,
            }
            connection.execute(
                "INSERT INTO material_taxonomy "
                "(item_id,parent_id,kind,top,name,sort_order,enabled,created_at,updated_at) "
                "VALUES (?, '', 'category', 'accessory', ?, ?, 1, ?, ?)",
                (category_id, category, sort_order, timestamp, timestamp),
            )
            insert_taxonomy_audit(
                connection,
                item_id=category_id,
                material_code="",
                summary=f"批量新增材料分类：{category}",
                after=after,
            )
            created_categories.append(category_id)

        for sort_order, row in enumerate(catalog, start=1000):
            category = str(row["category"])
            name = str(row["name"])
            code = str(row["material_code"])
            category_id = category_ids[category]
            item_id = AdminService.material_taxonomy_id("series", "accessory", name, category_id)
            color = str(row.get("color") or "#aeb4b7")
            shine = str(row.get("shine") or "#f6f8f9")
            keys = [str(value) for value in row["keys"]]
            urls = [str(value) for value in row["urls"]]
            primary_url, gallery_urls = split_display_and_gallery_urls(urls)
            image_path = keys[0][len("materials/") :] if keys[0].startswith("materials/") else keys[0]
            after = {
                "item_id": item_id,
                "parent_id": category_id,
                "kind": "series",
                "top": "accessory",
                "name": name,
                "material_code": code,
                "color": color,
                "shine": shine,
                "image_path": image_path,
                "image_url": primary_url,
                "image_urls_json": json.dumps(gallery_urls, ensure_ascii=False),
                "sort_order": sort_order,
                "enabled": 1,
            }
            connection.execute(
                "INSERT INTO material_taxonomy "
                "(item_id,parent_id,kind,top,name,material_code,color,shine,image_path,image_url,"
                "image_urls_json,sort_order,enabled,created_at,updated_at) "
                "VALUES (?, ?, 'series', 'accessory', ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (
                    item_id,
                    category_id,
                    name,
                    code,
                    color,
                    shine,
                    image_path,
                    primary_url,
                    json.dumps(gallery_urls, ensure_ascii=False),
                    sort_order,
                    timestamp,
                    timestamp,
                ),
            )
            upsert_material_knowledge(
                {
                    "code": code,
                    "material_code": code,
                    "name": name,
                    "primary_element": "metal",
                    "effects": ["结构点缀"],
                    "color_family": "金属色",
                    "visual_tags": [category, "金属配饰"],
                    "material_params": {"catalog_status": "awaiting_sku_dimensions"},
                    "asset": {"thumbnail_url": primary_url, "image_urls": gallery_urls},
                    "enabled": True,
                },
                {
                    "top": "accessory",
                    "category": category,
                    "series": name,
                    "name": name,
                    "material_code": code,
                    "color": color,
                    "shine": shine,
                },
                connection=connection,
                force_update=True,
            )
            insert_taxonomy_audit(
                connection,
                item_id=item_id,
                material_code=code,
                summary=f"批量新增材料品种：{name}",
                after=after,
            )
            created_series.append(item_id)
    return created_categories, created_series


def verify_database(catalog: list[dict[str, object]]) -> None:
    codes = [str(row["material_code"]) for row in catalog]
    placeholders = ",".join("?" for _ in codes)
    with connect_database() as connection:
        rows = connection.execute(
            f"SELECT name,material_code,image_url,image_urls_json FROM material_taxonomy "
            f"WHERE kind='series' AND top='accessory' AND material_code IN ({placeholders})",
            codes,
        ).fetchall()
        knowledge = connection.execute(
            f"SELECT code FROM material_knowledge WHERE code IN ({placeholders})",
            codes,
        ).fetchall()
        skus = connection.execute(
            f"SELECT id FROM managed_materials WHERE material_code IN ({placeholders})",
            codes,
        ).fetchall()
    if len(rows) != len(catalog) or len(knowledge) != len(catalog):
        raise RuntimeError(
            f"Catalog verification failed: series={len(rows)} knowledge={len(knowledge)}"
        )
    if skus:
        raise RuntimeError("Import unexpectedly created or reused SKU rows")
    expected = {
        str(row["material_code"]): split_display_and_gallery_urls(list(row["urls"]))
        for row in catalog
    }
    for row in rows:
        urls = json.loads(row["image_urls_json"] or "[]")
        primary_url, gallery_urls = expected[str(row["material_code"])]
        if urls != gallery_urls or row["image_url"] != primary_url:
            raise RuntimeError(f"Variety image mismatch: {row['name']}")


def main() -> None:
    args = parse_args()
    validate_runtime(args)
    catalog = build_catalog(args)
    category_ids = preflight_catalog(catalog)
    print(
        f"preflight categories={len(category_ids)} varieties={len(catalog)} "
        f"images={len(catalog) * 2} database={args.mysql_database}",
        flush=True,
    )
    if args.dry_run:
        return
    validate_result_path(args.result_path)
    uploaded = upload_assets(args, catalog)
    cdn_verified = verify_cdn(catalog)
    taxonomy_backup, knowledge_backup = create_backup_tables(args.operation_id)
    created_categories, created_series = apply_catalog(catalog, category_ids)
    verify_database(catalog)
    result = {
        "operation_id": args.operation_id,
        "environment": args.app_env,
        "database": args.mysql_database,
        "bucket": args.bucket,
        "cdn_base_url": args.cdn_base_url,
        "categories_created": len(created_categories),
        "varieties_created": len(created_series),
        "skus_created": 0,
        "images_uploaded": uploaded,
        "images_cdn_verified": cdn_verified,
        "taxonomy_backup_table": taxonomy_backup,
        "knowledge_backup_table": knowledge_backup,
        "created_category_ids": created_categories,
        "created_series_ids": created_series,
        "material_codes": [str(row["material_code"]) for row in catalog],
    }
    if args.result_path:
        args.result_path.parent.mkdir(parents=True, exist_ok=True)
        args.result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
