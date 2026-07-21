from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import connect_database, use_mysql


TARGET_TOP = "accessory"
TARGET_CATEGORY = "合金配件"
TARGET_SERIES = "合金配件"
TARGET_MATERIAL_CODE = "alloy_accessory"
TEST_DATABASE = "yujian_test"
TEST_CDN_HOST = "cdn-test.yustream.cn"
DEFAULT_EXPECTED_ASSETS = 38


@dataclass(frozen=True)
class Asset:
    key: str
    url: str

    @property
    def image_path(self) -> str:
        return self.key[len("materials/") :] if self.key.startswith("materials/") else self.key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split the legacy alloy accessory image pool into one test SKU per unique image."
    )
    parser.add_argument("--app-env", default=os.getenv("APP_ENV") or "test")
    parser.add_argument("--mysql-database", default=os.getenv("MYSQL_DATABASE") or TEST_DATABASE)
    parser.add_argument("--expected-assets", type=int, default=DEFAULT_EXPECTED_ASSETS)
    parser.add_argument(
        "--operation-id",
        default=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
    )
    parser.add_argument("--result-path", type=Path)
    parser.add_argument("--skip-cdn-check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def validate_operation_id(value: str) -> str:
    operation_id = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{8,32}", operation_id):
        raise SystemExit("operation-id must contain only 8-32 letters, digits, or underscores")
    return operation_id


def validate_runtime(app_env: str, database: str) -> None:
    clean_env = str(app_env or "").strip().lower()
    clean_database = str(database or "").strip().lower()
    if clean_env not in {"test", "testing", "staging"} or clean_database != TEST_DATABASE:
        raise SystemExit(
            f"Refusing non-test split: APP_ENV={clean_env or '<empty>'} "
            f"MYSQL_DATABASE={clean_database or '<empty>'}"
        )


def canonical_asset_key(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlsplit(text)
    path = unquote(parsed.path or text).lstrip("/")
    marker = "materials/"
    marker_index = path.find(marker)
    if marker_index >= 0:
        path = path[marker_index:]
    return path


def asset_sort_key(asset: Asset) -> tuple[int, str]:
    match = re.search(r"/(\d+)-[^/]+$", asset.key)
    return (int(match.group(1)) if match else 10**9, asset.key)


def unique_assets(values: list[str]) -> list[Asset]:
    candidates: dict[str, list[str]] = {}
    for value in values:
        text = str(value or "").strip()
        key = canonical_asset_key(text)
        if key:
            candidates.setdefault(key, []).append(text)

    assets: list[Asset] = []
    for key, urls in candidates.items():
        preferred = sorted(
            urls,
            key=lambda url: (
                0 if urlsplit(url).hostname == TEST_CDN_HOST else 1,
                0 if urlsplit(url).query else 1,
                url,
            ),
        )[0]
        if urlsplit(preferred).hostname != TEST_CDN_HOST:
            raise SystemExit(f"No test CDN URL found for asset: {key}")
        assets.append(Asset(key=key, url=f"https://{TEST_CDN_HOST}/{quote(key, safe='/')}"))
    return sorted(assets, key=asset_sort_key)


def parse_image_values(row: dict[str, object]) -> list[str]:
    raw = row.get("image_urls_json") or "[]"
    try:
        values = json.loads(str(raw)) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise SystemExit("Legacy alloy image_urls_json is invalid JSON") from exc
    if not isinstance(values, list):
        raise SystemExit("Legacy alloy image_urls_json must be a JSON array")
    return [str(row.get("image_url") or ""), *[str(value or "") for value in values]]


def deterministic_id(asset: Asset, index: int) -> str:
    digest = hashlib.sha1(asset.key.encode("utf-8")).hexdigest()[:10]
    return f"mat_alloy_accessory_{index:02d}_{digest}"


def deterministic_sku_id(asset: Asset, index: int) -> str:
    value = int(hashlib.sha1(f"alloy-sku|{index}|{asset.key}".encode("utf-8")).hexdigest()[:13], 16)
    return f"{value % 10_000_000_000_000:013d}"


def target_identity(source: dict[str, object], asset: Asset, index: int) -> tuple[str, str]:
    if index == 1:
        return str(source["id"]), str(source["skuId"])
    return deterministic_id(asset, index), deterministic_sku_id(asset, index)


def verify_cdn_asset(asset: Asset) -> tuple[str, int]:
    request = Request(asset.url, method="HEAD", headers={"User-Agent": "YujianAssetVerifier/1.0"})
    with urlopen(request, timeout=12) as response:
        status = int(getattr(response, "status", 200))
        content_type = str(response.headers.get("Content-Type") or "").lower()
    if status < 200 or status >= 400 or "image/" not in content_type:
        raise RuntimeError(f"CDN asset failed validation: {asset.url} status={status} type={content_type}")
    return asset.key, status


def verify_cdn_assets(assets: list[Asset]) -> None:
    with ThreadPoolExecutor(max_workers=min(10, len(assets))) as executor:
        list(executor.map(verify_cdn_asset, assets))


def target_where() -> tuple[str, tuple[str, str, str, str]]:
    return (
        "top=? AND category=? AND series=? AND material_code=?",
        (TARGET_TOP, TARGET_CATEGORY, TARGET_SERIES, TARGET_MATERIAL_CODE),
    )


def read_target_rows(connection, *, for_update: bool = False) -> list[dict[str, object]]:
    where, params = target_where()
    suffix = " FOR UPDATE" if for_update else ""
    rows = connection.execute(
        f"SELECT * FROM managed_materials WHERE {where} ORDER BY sort_order,id{suffix}",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def extract_assets(rows: list[dict[str, object]], expected_assets: int) -> tuple[list[Asset], str]:
    if len(rows) == 1:
        if int(rows[0].get("reserved_stock") or 0) != 0:
            raise SystemExit("Legacy alloy SKU has reserved inventory; refusing to split")
        assets = unique_assets(parse_image_values(rows[0]))
        state = "legacy"
    elif len(rows) == expected_assets:
        assets = unique_assets(
            [value for row in rows for value in parse_image_values(row)]
        )
        state = "already_split"
    else:
        raise SystemExit(
            f"Unexpected alloy SKU state: rows={len(rows)}, expected 1 or {expected_assets}"
        )
    if len(assets) != expected_assets:
        raise SystemExit(f"Expected {expected_assets} unique alloy assets, found {len(assets)}")
    return assets, state


def backup_tables(connection, operation_id: str, expected_material_rows: int) -> tuple[str, str]:
    material_backup = f"backup_alloy_mm_{operation_id}"
    taxonomy_backup = f"backup_alloy_mt_{operation_id}"
    for table in (material_backup, taxonomy_backup):
        if connection.execute("SHOW TABLES LIKE ?", (table,)).fetchone():
            raise SystemExit(f"Backup table already exists: {table}")

    where, params = target_where()
    connection.execute(f"CREATE TABLE {material_backup} LIKE managed_materials")
    connection.execute(
        f"INSERT INTO {material_backup} SELECT * FROM managed_materials WHERE {where}",
        params,
    )
    connection.execute(f"CREATE TABLE {taxonomy_backup} LIKE material_taxonomy")
    connection.execute(
        f"""
        INSERT INTO {taxonomy_backup}
        SELECT * FROM material_taxonomy
        WHERE top=? AND (
            (kind='category' AND name=?) OR
            (kind='series' AND name=? AND material_code=?)
        )
        """,
        (TARGET_TOP, TARGET_CATEGORY, TARGET_SERIES, TARGET_MATERIAL_CODE),
    )
    material_count = connection.execute(f"SELECT COUNT(*) AS c FROM {material_backup}").fetchone()["c"]
    taxonomy_count = connection.execute(f"SELECT COUNT(*) AS c FROM {taxonomy_backup}").fetchone()["c"]
    if int(material_count or 0) != expected_material_rows or int(taxonomy_count or 0) != 2:
        raise SystemExit(
            f"Backup verification failed: materials={material_count} taxonomy={taxonomy_count}"
        )
    return material_backup, taxonomy_backup


def assert_target_identities_available(connection, source: dict[str, object], assets: list[Asset]) -> None:
    target_ids = [target_identity(source, asset, index)[0] for index, asset in enumerate(assets, start=1)]
    target_skus = [target_identity(source, asset, index)[1] for index, asset in enumerate(assets, start=1)]
    if len(set(target_ids)) != len(target_ids) or len(set(target_skus)) != len(target_skus):
        raise SystemExit("Generated alloy SKU identities are not unique")
    placeholders = ",".join("?" for _ in target_ids)
    existing = connection.execute(
        f"SELECT id,skuId FROM managed_materials WHERE (id IN ({placeholders}) OR skuId IN ({placeholders})) AND id<>?",
        [*target_ids, *target_skus, str(source["id"])],
    ).fetchall()
    if existing:
        raise SystemExit("Generated alloy SKU identity collides with existing catalog data")


def split_rows(connection, source: dict[str, object], assets: list[Asset], now: str) -> None:
    columns = [row["Field"] for row in connection.execute("SHOW COLUMNS FROM managed_materials").fetchall()]
    source_values = {column: source.get(column) for column in columns}
    base_sort_order = int(source.get("sort_order") or 0)

    for index, asset in enumerate(assets, start=1):
        item = dict(source_values)
        item["id"], item["skuId"] = target_identity(source, asset, index)
        item["name"] = f"{TARGET_SERIES} {index:02d}"
        item["image_path"] = asset.image_path
        item["image_url"] = asset.url
        item["image_urls_json"] = json.dumps([asset.url], ensure_ascii=False)
        item["sort_order"] = base_sort_order + index - 1
        item["reserved_stock"] = 0
        item["updated_at"] = now
        if index == 1:
            assignments = ",".join(f"{column}=?" for column in columns if column != "id")
            params = [item[column] for column in columns if column != "id"]
            connection.execute(
                f"UPDATE managed_materials SET {assignments} WHERE id=?",
                [*params, str(source["id"])],
            )
            continue

        item["created_at"] = now
        placeholders = ",".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO managed_materials ({','.join(columns)}) VALUES ({placeholders})",
            [item[column] for column in columns],
        )


def stored_image_urls(row: dict[str, object]) -> list[str]:
    raw = row.get("image_urls_json") or "[]"
    try:
        values = json.loads(str(raw)) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"SKU {row.get('id')} has invalid image_urls_json") from exc
    if not isinstance(values, list):
        raise RuntimeError(f"SKU {row.get('id')} image_urls_json is not an array")
    return [str(value or "") for value in values]


def row_asset(row: dict[str, object]) -> Asset:
    assets = unique_assets(parse_image_values(row))
    if len(assets) != 1:
        raise RuntimeError(f"SKU {row.get('id')} does not have exactly one unique image")
    return assets[0]


def split_rows_are_canonical(rows: list[dict[str, object]], assets: list[Asset]) -> bool:
    expected = {asset.key: asset for asset in assets}
    for row in rows:
        asset = row_asset(row)
        target = expected.get(asset.key)
        if not target:
            return False
        if str(row.get("image_path") or "") != target.image_path:
            return False
        if str(row.get("image_url") or "") != target.url:
            return False
        if stored_image_urls(row) != [target.url]:
            return False
    return True


def normalize_split_row_urls(connection, rows: list[dict[str, object]], assets: list[Asset], now: str) -> None:
    expected = {asset.key: asset for asset in assets}
    for row in rows:
        current = row_asset(row)
        target = expected.get(current.key)
        if not target:
            raise RuntimeError(f"Unexpected image on SKU {row.get('id')}: {current.key}")
        connection.execute(
            """
            UPDATE managed_materials
            SET image_path=?, image_url=?, image_urls_json=?, updated_at=?
            WHERE id=?
            """,
            (
                target.image_path,
                target.url,
                json.dumps([target.url], ensure_ascii=False),
                now,
                str(row["id"]),
            ),
        )


def verify_split_rows(connection, assets: list[Asset]) -> list[dict[str, object]]:
    rows = read_target_rows(connection)
    if len(rows) != len(assets):
        raise RuntimeError(f"Split verification failed: expected {len(assets)} rows, found {len(rows)}")
    ids = {str(row.get("id") or "") for row in rows}
    sku_ids = {str(row.get("skuId") or "") for row in rows}
    names = {str(row.get("name") or "") for row in rows}
    actual_assets: list[Asset] = []
    expected = {asset.key: asset for asset in assets}
    for row in rows:
        asset = row_asset(row)
        target = expected.get(asset.key)
        if not target:
            raise RuntimeError(f"Unexpected image on SKU {row.get('id')}: {asset.key}")
        if str(row.get("image_path") or "") != target.image_path:
            raise RuntimeError(f"SKU {row.get('id')} has a non-canonical image_path")
        if str(row.get("image_url") or "") != target.url or stored_image_urls(row) != [target.url]:
            raise RuntimeError(f"SKU {row.get('id')} has non-canonical image URLs")
        actual_assets.append(asset)
    if len(ids) != len(rows) or len(sku_ids) != len(rows) or len(names) != len(rows):
        raise RuntimeError("Split verification failed: duplicate id, skuId, or display name")
    if {asset.key for asset in actual_assets} != {asset.key for asset in assets}:
        raise RuntimeError("Split verification failed: SKU images do not match the legacy image pool")
    return rows


def write_result(path: Path | None, payload: dict[str, object]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    operation_id = validate_operation_id(args.operation_id)
    validate_runtime(args.app_env, args.mysql_database)
    os.environ["APP_ENV"] = str(args.app_env)
    os.environ["MYSQL_DATABASE"] = str(args.mysql_database)
    os.environ["DATABASE_BACKEND"] = "mysql"
    if not use_mysql():
        raise SystemExit("Alloy SKU split requires MySQL")

    with connect_database() as connection:
        rows = read_target_rows(connection)
    assets, state = extract_assets(rows, args.expected_assets)
    if not args.skip_cdn_check:
        verify_cdn_assets(assets)

    result: dict[str, object] = {
        "operation_id": operation_id,
        "database": args.mysql_database,
        "state_before": state,
        "asset_count": len(assets),
        "dry_run": bool(args.dry_run),
        "assets": [{"index": index, "key": asset.key, "url": asset.url} for index, asset in enumerate(assets, start=1)],
    }
    if args.dry_run:
        result["sku_count"] = len(rows)
        result["url_normalization_required"] = state == "already_split" and not split_rows_are_canonical(rows, assets)
        write_result(args.result_path, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if state == "already_split":
        if split_rows_are_canonical(rows, assets):
            result.update({"state_after": "already_split", "sku_count": len(rows), "changed": False})
            write_result(args.result_path, result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        with connect_database() as connection:
            material_backup, taxonomy_backup = backup_tables(connection, operation_id, len(rows))
            connection.execute("START TRANSACTION")
            locked_rows = read_target_rows(connection, for_update=True)
            locked_assets, locked_state = extract_assets(locked_rows, args.expected_assets)
            if locked_state != "already_split" or [asset.key for asset in locked_assets] != [asset.key for asset in assets]:
                raise RuntimeError("Alloy catalog changed after URL preflight; refusing to continue")
            normalize_split_row_urls(connection, locked_rows, assets, now)
            verified_rows = verify_split_rows(connection, assets)
        result.update(
            {
                "state_after": "split_urls_normalized",
                "sku_count": len(verified_rows),
                "changed": True,
                "material_backup": material_backup,
                "taxonomy_backup": taxonomy_backup,
            }
        )
        write_result(args.result_path, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    with connect_database() as connection:
        material_backup, taxonomy_backup = backup_tables(connection, operation_id, 1)
        connection.execute("START TRANSACTION")
        locked_rows = read_target_rows(connection, for_update=True)
        locked_assets, locked_state = extract_assets(locked_rows, args.expected_assets)
        if locked_state != "legacy" or [asset.key for asset in locked_assets] != [asset.key for asset in assets]:
            raise RuntimeError("Alloy catalog changed after preflight; refusing to continue")
        source = locked_rows[0]
        assert_target_identities_available(connection, source, assets)
        split_rows(connection, source, assets, now)
        verified_rows = verify_split_rows(connection, assets)

    result.update(
        {
            "state_after": "split",
            "sku_count": len(verified_rows),
            "material_backup": material_backup,
            "taxonomy_backup": taxonomy_backup,
            "source_id_preserved": str(verified_rows[0]["id"]) == str(rows[0]["id"]),
        }
    )
    write_result(args.result_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
