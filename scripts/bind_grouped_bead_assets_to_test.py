from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import connect_database, use_mysql


DEFAULT_BUCKET = "yujian-test-1258267288"
DEFAULT_REGION = "ap-guangzhou"
DEFAULT_CDN_BASE_URL = "https://cdn-test.yustream.cn"
DEFAULT_COS_PREFIX = "materials/beads/20260716-grouped"


@dataclass(frozen=True)
class AssetGroup:
    series: str
    category: str
    material_code: str
    slug: str
    files: tuple[Path, ...]
    keys: tuple[str, ...]
    urls: tuple[str, ...]


@dataclass(frozen=True)
class CatalogTarget:
    group: AssetGroup
    sku_ids: tuple[str, ...]
    sizes: tuple[float, ...]
    enabled_values: tuple[int, ...]
    taxonomy_id: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload grouped bead assets and bind only existing test catalog rows."
    )
    parser.add_argument("--manifest-root", type=Path, required=True)
    parser.add_argument(
        "--assets-root",
        type=Path,
        help="Optional relocated asset root; each manifest folder must have a matching asset folder.",
    )
    parser.add_argument("--cos-prefix", default=DEFAULT_COS_PREFIX)
    parser.add_argument("--bucket", default=os.getenv("TENCENT_COS_BUCKET") or DEFAULT_BUCKET)
    parser.add_argument("--region", default=os.getenv("TENCENT_COS_REGION") or DEFAULT_REGION)
    parser.add_argument(
        "--cdn-base-url",
        default=os.getenv("TENCENT_COS_CDN_BASE_URL") or DEFAULT_CDN_BASE_URL,
    )
    parser.add_argument("--secret-id", default=os.getenv("TENCENT_COS_SECRET_ID"))
    parser.add_argument("--secret-key", default=os.getenv("TENCENT_COS_SECRET_KEY"))
    parser.add_argument("--app-env", default=os.getenv("APP_ENV") or "test")
    parser.add_argument("--mysql-database", default=os.getenv("MYSQL_DATABASE") or "yujian_test")
    parser.add_argument("--expected-groups", type=int, default=33)
    parser.add_argument("--assets-per-group", type=int, default=9)
    parser.add_argument("--expected-skus", type=int, default=8)
    parser.add_argument(
        "--operation-id",
        default=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
    )
    parser.add_argument(
        "--url-version",
        default="",
        help="Optional query version. Content-hashed object keys do not require one.",
    )
    parser.add_argument("--result-path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    return parser.parse_args()


def validate_operation_id(value: str) -> str:
    operation_id = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{8,32}", operation_id):
        raise SystemExit("operation-id must contain only 8-32 letters, digits, or underscores")
    return operation_id


def validate_runtime(args: argparse.Namespace) -> None:
    os.environ["APP_ENV"] = str(args.app_env)
    os.environ["MYSQL_DATABASE"] = str(args.mysql_database)
    os.environ["DATABASE_BACKEND"] = "mysql"
    app_env = str(args.app_env).strip().lower()
    database = str(args.mysql_database).strip().lower()
    if app_env not in {"test", "testing", "staging"} or "test" not in database:
        raise SystemExit(
            f"Refusing non-test bind: APP_ENV={app_env or '<empty>'} "
            f"MYSQL_DATABASE={database or '<empty>'}"
        )
    if str(args.bucket) != DEFAULT_BUCKET:
        raise SystemExit(f"Refusing non-test bucket: {args.bucket}")
    if str(args.cdn_base_url).rstrip("/") != DEFAULT_CDN_BASE_URL:
        raise SystemExit(f"Refusing non-test CDN: {args.cdn_base_url}")
    if not use_mysql():
        raise SystemExit("Grouped material binding requires MySQL")


def public_url(cdn_base_url: str, key: str, version: str = "") -> str:
    base = cdn_base_url.rstrip("/")
    url = f"{base}/{quote(key, safe='/')}"
    return f"{url}?v={quote(version)}" if version else url


def object_key(prefix: str, material_code: str, index: int, path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"{prefix.strip('/')}/{material_code}/{index:02d}-{digest}.webp"


def material_image_path(key: str) -> str:
    return key[len("materials/") :] if key.startswith("materials/") else key


def load_asset_groups(args: argparse.Namespace) -> list[AssetGroup]:
    groups: list[AssetGroup] = []
    manifest_paths = sorted(args.manifest_root.glob("*/manifest.json"))
    for manifest_path in manifest_paths:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list) or not raw:
            raise SystemExit(f"Empty or invalid manifest: {manifest_path}")
        rows = sorted(raw, key=lambda row: int(row.get("index") or 0))
        series_values = {str(row.get("final_series") or row.get("series") or "").strip() for row in rows}
        category_values = {str(row.get("final_category") or row.get("category") or "").strip() for row in rows}
        code_values = {str(row.get("material_code") or "").strip() for row in rows}
        top_values = {str(row.get("top") or "bead").strip() for row in rows}
        if len(series_values) != 1 or len(category_values) != 1 or len(code_values) != 1:
            raise SystemExit(f"Mixed catalog metadata in manifest: {manifest_path}")
        if top_values != {"bead"}:
            raise SystemExit(f"Non-bead manifest rejected: {manifest_path}")
        if len(rows) != args.assets_per_group:
            raise SystemExit(
                f"Expected {args.assets_per_group} assets in {manifest_path}, found {len(rows)}"
            )
        warnings = [str(row.get("warning_text") or "") for row in rows if row.get("warning_text")]
        if warnings:
            raise SystemExit(f"Unresolved asset warnings in {manifest_path}: {warnings}")
        if args.assets_root:
            files = tuple(
                (args.assets_root / manifest_path.parent.name / Path(str(row["app_webp"])).name).resolve()
                for row in rows
            )
        else:
            files = tuple(Path(str(row["app_webp"])).resolve() for row in rows)
        missing = [str(path) for path in files if not path.is_file()]
        if missing:
            raise SystemExit(f"Missing processed assets: {', '.join(missing)}")
        series = next(iter(series_values))
        category = next(iter(category_values))
        material_code = next(iter(code_values))
        slug = str(rows[0].get("slug") or material_code).strip()
        keys = tuple(
            object_key(args.cos_prefix, material_code, index, path)
            for index, path in enumerate(files, start=1)
        )
        urls = tuple(public_url(args.cdn_base_url, key, args.url_version) for key in keys)
        groups.append(
            AssetGroup(
                series=series,
                category=category,
                material_code=material_code,
                slug=slug,
                files=files,
                keys=keys,
                urls=urls,
            )
        )
    if len(groups) != args.expected_groups:
        raise SystemExit(f"Expected {args.expected_groups} groups, found {len(groups)}")
    series_names = [group.series for group in groups]
    material_codes = [group.material_code for group in groups]
    if len(series_names) != len(set(series_names)):
        raise SystemExit("Duplicate series in grouped manifests")
    if len(material_codes) != len(set(material_codes)):
        raise SystemExit("Duplicate material_code in grouped manifests")
    return groups


def preflight_catalog(groups: list[AssetGroup], expected_skus: int) -> list[CatalogTarget]:
    targets: list[CatalogTarget] = []
    with connect_database() as connection:
        for group in groups:
            sku_rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT id, category, series, material_code, size, enabled
                    FROM managed_materials
                    WHERE top=? AND series=?
                    ORDER BY size, id
                    """,
                    ("bead", group.series),
                ).fetchall()
            ]
            taxonomy_rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT s.item_id, s.name, s.material_code, s.enabled, c.name AS category_name
                    FROM material_taxonomy s
                    JOIN material_taxonomy c ON c.item_id=s.parent_id
                    WHERE s.kind='series' AND s.top=? AND s.name=?
                    """,
                    ("bead", group.series),
                ).fetchall()
            ]
            if expected_skus > 0 and len(sku_rows) != expected_skus:
                raise SystemExit(
                    f"Catalog preflight failed for {group.series}: expected {expected_skus} SKUs, "
                    f"found {len(sku_rows)}"
                )
            if not sku_rows or len(taxonomy_rows) != 1:
                raise SystemExit(
                    f"Catalog preflight failed for {group.series}: "
                    f"skus={len(sku_rows)} taxonomy={len(taxonomy_rows)}"
                )
            categories = {str(row.get("category") or "") for row in sku_rows}
            codes = {str(row.get("material_code") or "") for row in sku_rows}
            taxonomy = taxonomy_rows[0]
            if categories != {group.category} or str(taxonomy.get("category_name") or "") != group.category:
                raise SystemExit(f"Category mismatch for {group.series}: manifest={group.category}")
            if codes != {group.material_code} or str(taxonomy.get("material_code") or "") != group.material_code:
                raise SystemExit(f"Material code mismatch for {group.series}: manifest={group.material_code}")
            targets.append(
                CatalogTarget(
                    group=group,
                    sku_ids=tuple(str(row["id"]) for row in sku_rows),
                    sizes=tuple(float(row.get("size") or 0) for row in sku_rows),
                    enabled_values=tuple(int(row.get("enabled") or 0) for row in sku_rows),
                    taxonomy_id=str(taxonomy["item_id"]),
                )
            )
    return targets


def validate_cos_args(args: argparse.Namespace) -> None:
    if args.skip_upload:
        return
    missing = [name for name in ("region", "secret_id", "secret_key") if not getattr(args, name)]
    if missing:
        raise SystemExit("Missing COS config: " + ", ".join(missing))


def cos_client(args: argparse.Namespace):
    from qcloud_cos import CosConfig, CosS3Client

    return CosS3Client(
        CosConfig(
            Region=args.region,
            SecretId=args.secret_id,
            SecretKey=args.secret_key,
            Scheme="https",
        )
    )


def upload_and_verify_cos(args: argparse.Namespace, groups: list[AssetGroup]) -> int:
    client = cos_client(args)
    payload = [
        (path, key)
        for group in groups
        for path, key in zip(group.files, group.keys, strict=True)
    ]
    for index, (path, key) in enumerate(payload, start=1):
        if not args.skip_upload:
            client.put_object_from_local_file(
                Bucket=args.bucket,
                LocalFilePath=str(path),
                Key=key,
            )
        client.head_object(Bucket=args.bucket, Key=key)
        if index == 1 or index % 50 == 0 or index == len(payload):
            print(f"cos_verified={index}/{len(payload)}", flush=True)
    return len(payload)


def verify_cdn_url(url: str) -> str | None:
    request = Request(url, method="HEAD", headers={"User-Agent": "YujianAssetVerifier/1.0"})
    try:
        with urlopen(request, timeout=15) as response:
            if response.status != 200:
                return f"{url} status={response.status}"
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if "image/webp" not in content_type:
                return f"{url} content-type={content_type or '<empty>'}"
    except Exception as exc:
        return f"{url} error={type(exc).__name__}:{exc}"
    return None


def verify_cdn(groups: list[AssetGroup], attempts: int = 4) -> int:
    urls = [url for group in groups for url in group.urls]
    failures: list[str] = []
    for attempt in range(1, attempts + 1):
        with ThreadPoolExecutor(max_workers=24) as executor:
            failures = [failure for failure in executor.map(verify_cdn_url, urls) if failure]
        if not failures:
            print(f"cdn_verified={len(urls)}/{len(urls)}", flush=True)
            return len(urls)
        if attempt < attempts:
            time.sleep(attempt * 2)
    raise SystemExit("CDN verification failed: " + "; ".join(failures[:8]))


def create_backup_tables(targets: list[CatalogTarget], operation_id: str) -> tuple[str, str]:
    managed_table = f"backup_mm_img_{operation_id}"
    taxonomy_table = f"backup_mt_img_{operation_id}"
    names = [target.group.series for target in targets]
    placeholders = ",".join("?" for _ in names)
    with connect_database() as connection:
        existing = connection.execute(
            """
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA=? AND TABLE_NAME IN (?, ?)
            """,
            (os.environ["MYSQL_DATABASE"], managed_table, taxonomy_table),
        ).fetchall()
        if existing:
            raise SystemExit(f"Backup table already exists for operation {operation_id}")
        connection.execute(f"CREATE TABLE {managed_table} LIKE managed_materials")
        connection.execute(
            f"INSERT INTO {managed_table} SELECT * FROM managed_materials "
            f"WHERE top=? AND series IN ({placeholders})",
            ("bead", *names),
        )
        connection.execute(f"CREATE TABLE {taxonomy_table} LIKE material_taxonomy")
        connection.execute(
            f"INSERT INTO {taxonomy_table} SELECT * FROM material_taxonomy "
            f"WHERE kind='series' AND top=? AND name IN ({placeholders})",
            ("bead", *names),
        )
        managed_count = int(
            connection.execute(f"SELECT COUNT(*) AS count_value FROM {managed_table}").fetchone()[
                "count_value"
            ]
        )
        taxonomy_count = int(
            connection.execute(f"SELECT COUNT(*) AS count_value FROM {taxonomy_table}").fetchone()[
                "count_value"
            ]
        )
    expected_managed = sum(len(target.sku_ids) for target in targets)
    if managed_count != expected_managed or taxonomy_count != len(targets):
        raise SystemExit(
            f"Backup validation failed: managed={managed_count}/{expected_managed} "
            f"taxonomy={taxonomy_count}/{len(targets)}"
        )
    return managed_table, taxonomy_table


def bind_catalog(targets: list[CatalogTarget]) -> tuple[int, int]:
    updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    updated_skus = 0
    updated_taxonomy = 0
    with connect_database() as connection:
        for target in targets:
            group = target.group
            image_path = material_image_path(group.keys[0])
            image_url = group.urls[0]
            image_urls_json = json.dumps(group.urls, ensure_ascii=False)
            placeholders = ",".join("?" for _ in target.sku_ids)
            cursor = connection.execute(
                f"""
                UPDATE managed_materials
                SET image_path=?, image_url=?, image_urls_json=?, updated_at=?
                WHERE id IN ({placeholders})
                """,
                (image_path, image_url, image_urls_json, updated_at, *target.sku_ids),
            )
            if int(cursor.rowcount or 0) != len(target.sku_ids):
                raise RuntimeError(
                    f"SKU update count mismatch for {group.series}: "
                    f"{cursor.rowcount}/{len(target.sku_ids)}"
                )
            updated_skus += int(cursor.rowcount or 0)
            cursor = connection.execute(
                """
                UPDATE material_taxonomy
                SET image_path=?, image_url=?, image_urls_json=?, updated_at=?
                WHERE item_id=? AND kind='series' AND top='bead'
                """,
                (image_path, image_url, image_urls_json, updated_at, target.taxonomy_id),
            )
            if int(cursor.rowcount or 0) != 1:
                raise RuntimeError(f"Taxonomy update count mismatch for {group.series}")
            updated_taxonomy += 1
    return updated_skus, updated_taxonomy


def verify_catalog(targets: list[CatalogTarget]) -> None:
    with connect_database() as connection:
        for target in targets:
            group = target.group
            placeholders = ",".join("?" for _ in target.sku_ids)
            rows = connection.execute(
                f"""
                SELECT id, enabled, image_path, image_url, image_urls_json
                FROM managed_materials WHERE id IN ({placeholders}) ORDER BY size, id
                """,
                target.sku_ids,
            ).fetchall()
            taxonomy = connection.execute(
                """
                SELECT image_path, image_url, image_urls_json
                FROM material_taxonomy WHERE item_id=?
                """,
                (target.taxonomy_id,),
            ).fetchone()
            if len(rows) != len(target.sku_ids) or taxonomy is None:
                raise RuntimeError(f"Post-bind row count mismatch for {group.series}")
            if tuple(int(row["enabled"] or 0) for row in rows) != target.enabled_values:
                raise RuntimeError(f"Enabled state changed for {group.series}")
            expected_path = material_image_path(group.keys[0])
            for row in [*rows, taxonomy]:
                urls = json.loads(row["image_urls_json"] or "[]")
                if (
                    row["image_path"] != expected_path
                    or row["image_url"] != group.urls[0]
                    or urls != list(group.urls)
                ):
                    raise RuntimeError(f"Image binding mismatch for {group.series}")


def main() -> None:
    args = parse_args()
    args.operation_id = validate_operation_id(args.operation_id)
    validate_runtime(args)
    groups = load_asset_groups(args)
    targets = preflight_catalog(groups, args.expected_skus)
    print(
        f"preflight groups={len(groups)} assets={sum(len(group.files) for group in groups)} "
        f"skus={sum(len(target.sku_ids) for target in targets)} database={args.mysql_database}",
        flush=True,
    )
    for target in targets:
        print(
            f"MATCH {target.group.series} category={target.group.category} "
            f"code={target.group.material_code} assets={len(target.group.files)} "
            f"skus={len(target.sku_ids)} enabled={sorted(set(target.enabled_values))}",
            flush=True,
        )
    if args.dry_run:
        return
    validate_cos_args(args)
    uploaded = upload_and_verify_cos(args, groups)
    cdn_verified = verify_cdn(groups)
    managed_backup, taxonomy_backup = create_backup_tables(targets, args.operation_id)
    updated_skus, updated_taxonomy = bind_catalog(targets)
    verify_catalog(targets)
    result = {
        "operation_id": args.operation_id,
        "environment": args.app_env,
        "database": args.mysql_database,
        "bucket": args.bucket,
        "cdn_base_url": args.cdn_base_url,
        "groups": len(groups),
        "assets": uploaded,
        "cdn_verified": cdn_verified,
        "updated_skus": updated_skus,
        "updated_taxonomy": updated_taxonomy,
        "managed_backup_table": managed_backup,
        "taxonomy_backup_table": taxonomy_backup,
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
