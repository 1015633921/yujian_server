from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload reviewed accessory assets and bind them only to yujian_test."
    )
    parser.add_argument("--assets-root", type=Path, required=True)
    parser.add_argument("--manifest-root", type=Path, required=True)
    parser.add_argument("--cos-prefix", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region", default=os.getenv("TENCENT_COS_REGION", ""))
    parser.add_argument("--secret-id", default=os.getenv("TENCENT_COS_SECRET_ID", ""))
    parser.add_argument("--secret-key", default=os.getenv("TENCENT_COS_SECRET_KEY", ""))
    parser.add_argument("--cdn-base-url", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def require_test_environment() -> None:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    database = os.getenv("MYSQL_DATABASE", "").strip()
    if app_env not in {"test", "testing", "staging"} or database != "yujian_test":
        raise SystemExit(
            f"Refusing import outside yujian_test: APP_ENV={app_env or '<empty>'} MYSQL_DATABASE={database or '<empty>'}"
        )


def read_groups(args: argparse.Namespace) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    for manifest_path in sorted(args.manifest_root.glob("*/manifest.json")):
        rows = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise SystemExit(f"Expected one reviewed item in {manifest_path}")
        row = rows[0]
        top = str(row.get("top") or "").strip().lower()
        code = str(row.get("material_code") or "").strip()
        series = str(row.get("final_series") or row.get("name") or "").strip()
        category = str(row.get("final_category") or row.get("category") or "").strip()
        if top != "accessory" or not code or not series or not category:
            raise SystemExit(f"Invalid reviewed accessory manifest: {manifest_path}")
        files = sorted(
            path
            for path in (args.assets_root / code).glob("*.webp")
            if not path.name.startswith("._")
        )
        if not files:
            raise SystemExit(f"Missing processed WebP for {code}")
        groups.append({"row": row, "code": code, "series": series, "category": category, "files": files})
    if not groups:
        raise SystemExit("No reviewed accessory manifests found.")
    return groups


def deterministic_id(code: str, series: str) -> str:
    digest = hashlib.sha1(f"accessory|{code}|{series}|0".encode("utf-8")).hexdigest()[:18]
    return f"real_{digest}"


def deterministic_sku(code: str, series: str) -> str:
    value = int(hashlib.sha1(f"sku|accessory|{code}|{series}|0".encode("utf-8")).hexdigest()[:13], 16)
    return f"{value % 10_000_000_000_000:013d}"


def public_url(base_url: str, key: str) -> str:
    return f"{base_url.rstrip('/')}/{quote(key)}"


def upload_assets(args: argparse.Namespace, groups: list[dict[str, object]]) -> None:
    if not args.region or not args.secret_id or not args.secret_key:
        raise SystemExit("Missing COS region or credentials.")
    from qcloud_cos import CosConfig, CosS3Client

    client = CosS3Client(
        CosConfig(Region=args.region, SecretId=args.secret_id, SecretKey=args.secret_key, Scheme="https")
    )
    prefix = args.cos_prefix.strip("/")
    for group in groups:
        files = list(group["files"])
        keys = [f"{prefix}/{group['code']}/{index:02d}-{path.name}" for index, path in enumerate(files, start=1)]
        for path, key in zip(files, keys, strict=True):
            client.put_object_from_local_file(Bucket=args.bucket, LocalFilePath=str(path), Key=key)
        group["keys"] = keys
        group["urls"] = [public_url(args.cdn_base_url, key) for key in keys]


def connect_mysql():
    import pymysql

    return pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        charset="utf8mb4",
        autocommit=False,
    )


def bind_database(args: argparse.Namespace, groups: list[dict[str, object]]) -> tuple[int, int]:
    required_columns = {
        "id", "skuId", "top", "category", "series", "material_code", "grade", "name", "effect", "element",
        "price", "size", "weight", "color", "shine", "image_path", "image_url", "image_urls_json", "stock",
        "enabled", "sort_order", "created_at", "updated_at",
    }
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    created = 0
    updated = 0
    with connect_mysql() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM managed_materials")
            columns = {row[0] for row in cursor.fetchall()}
            missing = sorted(required_columns - columns)
            if missing:
                raise RuntimeError("managed_materials is missing required columns: " + ", ".join(missing))
            for offset, group in enumerate(groups, start=1):
                row = dict(group["row"])
                urls = list(group["urls"])
                keys = list(group["keys"])
                price = float(row.get("price") or 0)
                stock = int(row.get("stock") or 0)
                if price <= 0 or stock <= 0:
                    raise RuntimeError(f"Invalid sellable price or stock for {group['code']}")
                cursor.execute(
                    "SELECT id FROM managed_materials WHERE top=%s AND series=%s LIMIT 1",
                    ("accessory", group["series"]),
                )
                existing = cursor.fetchone()
                values = {
                    "skuId": deterministic_sku(str(group["code"]), str(group["series"])),
                    "category": group["category"],
                    "material_code": group["code"],
                    "grade": "配件",
                    "name": group["series"],
                    "effect": "focus",
                    "element": str(row.get("element") or "metal"),
                    "price": price,
                    "size": 0,
                    "weight": 0,
                    "color": str(row.get("color") or "#9da1a8"),
                    "shine": str(row.get("shine") or "#ffffff"),
                    "image_path": str(keys[0])[len("materials/"):] if str(keys[0]).startswith("materials/") else str(keys[0]),
                    "image_url": urls[0],
                    "image_urls_json": json.dumps(urls, ensure_ascii=False),
                    "stock": stock,
                    "enabled": 1,
                    "sort_order": 900 + offset,
                    "updated_at": now,
                }
                if existing:
                    values["id"] = existing[0]
                    cursor.execute(
                        """
                        UPDATE managed_materials SET skuId=%(skuId)s, category=%(category)s, material_code=%(material_code)s,
                        grade=%(grade)s, name=%(name)s, effect=%(effect)s, element=%(element)s, price=%(price)s,
                        size=%(size)s, weight=%(weight)s, color=%(color)s, shine=%(shine)s, image_path=%(image_path)s,
                        image_url=%(image_url)s, image_urls_json=%(image_urls_json)s, stock=%(stock)s, enabled=%(enabled)s,
                        sort_order=%(sort_order)s, updated_at=%(updated_at)s WHERE id=%(id)s
                        """,
                        values,
                    )
                    updated += 1
                else:
                    values["id"] = deterministic_id(str(group["code"]), str(group["series"]))
                    values["top"] = "accessory"
                    values["created_at"] = now
                    cursor.execute(
                        """
                        INSERT INTO managed_materials
                        (id, skuId, top, category, series, material_code, grade, name, effect, element, price, size, weight,
                         color, shine, image_path, image_url, image_urls_json, stock, enabled, sort_order, created_at, updated_at)
                        VALUES (%(id)s, %(skuId)s, %(top)s, %(category)s, %(name)s, %(material_code)s, %(grade)s, %(name)s,
                                %(effect)s, %(element)s, %(price)s, %(size)s, %(weight)s, %(color)s, %(shine)s,
                                %(image_path)s, %(image_url)s, %(image_urls_json)s, %(stock)s, %(enabled)s, %(sort_order)s,
                                %(created_at)s, %(updated_at)s)
                        """,
                        values,
                    )
                    created += 1
        connection.commit()
    return created, updated


def main() -> None:
    args = parse_args()
    require_test_environment()
    groups = read_groups(args)
    print(f"groups={len(groups)} assets={sum(len(group['files']) for group in groups)} dry_run={args.dry_run}")
    if args.dry_run:
        return
    upload_assets(args, groups)
    created, updated = bind_database(args, groups)
    print(f"created={created} updated={updated}")


if __name__ == "__main__":
    main()
