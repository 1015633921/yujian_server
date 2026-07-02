from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import connect_database


DEFAULT_BUCKET = "yujian-test-1258267288"
DEFAULT_REGION = "ap-guangzhou"
DEFAULT_CDN_BASE_URL = "https://cdn-test.yustream.cn"
DEFAULT_SOURCE_ROOT = ROOT / "static" / "materials" / "beads" / "transparent-processed"
DEFAULT_COS_PREFIX = "materials/beads/transparent-processed"
POOL_BINDINGS = {
    "red-mud-skeletal-phantom": ("红泥骸骨幽灵", "高品红泥骸骨幽灵"),
    "snowflake-phantom": ("雪花幽灵", "高品雪花幽灵"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore selected phantom rows to real transparent photo pools.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--cos-prefix", default=DEFAULT_COS_PREFIX)
    parser.add_argument("--bucket", default=os.getenv("TENCENT_TEST_COS_BUCKET") or DEFAULT_BUCKET)
    parser.add_argument("--region", default=os.getenv("TENCENT_COS_REGION") or DEFAULT_REGION)
    parser.add_argument("--cdn-base-url", default=os.getenv("TENCENT_TEST_COS_CDN_BASE_URL") or DEFAULT_CDN_BASE_URL)
    parser.add_argument("--secret-id", default=os.getenv("TENCENT_COS_SECRET_ID"))
    parser.add_argument("--secret-key", default=os.getenv("TENCENT_COS_SECRET_KEY"))
    parser.add_argument("--app-env", default="test")
    parser.add_argument("--mysql-database", default="yujian_test")
    parser.add_argument("--url-version", default=datetime.now().strftime("%Y%m%d%H%M%S"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip("\"'")
        if name and value:
            os.environ.setdefault(name, value)


def configure(args: argparse.Namespace) -> None:
    load_local_env(ROOT / ".env")
    load_local_env(ROOT / ".env.local")
    args.region = args.region or os.getenv("TENCENT_COS_REGION") or DEFAULT_REGION
    args.secret_id = args.secret_id or os.getenv("TENCENT_COS_SECRET_ID")
    args.secret_key = args.secret_key or os.getenv("TENCENT_COS_SECRET_KEY")
    os.environ["DATABASE_BACKEND"] = "mysql"
    os.environ["APP_ENV"] = args.app_env
    os.environ["MYSQL_DATABASE"] = args.mysql_database
    if args.app_env.lower() not in {"test", "testing", "staging"}:
        raise SystemExit(f"Refusing to restore outside test/staging: APP_ENV={args.app_env}")
    if not args.dry_run and (not args.secret_id or not args.secret_key):
        raise SystemExit("Missing COS secret id/key.")


def public_url(args: argparse.Namespace, key: str) -> str:
    base = args.cdn_base_url.rstrip("/")
    url = f"{base}/{quote(key, safe='/%')}"
    return f"{url}?v={quote(args.url_version)}" if args.url_version else url


def material_path_from_key(key: str) -> str:
    while key.startswith("materials/"):
        key = key[len("materials/"):]
    return key


def upload(args: argparse.Namespace, payload: dict[str, list[tuple[Path, str, str]]]) -> None:
    from qcloud_cos import CosConfig, CosS3Client

    client = CosS3Client(
        CosConfig(
            Region=args.region,
            SecretId=args.secret_id,
            SecretKey=args.secret_key,
            Scheme="https",
        )
    )
    for files in payload.values():
        for path, key, _ in files:
            client.upload_file(
                Bucket=args.bucket,
                LocalFilePath=str(path),
                Key=key,
                PartSize=10,
                MAXThread=4,
                EnableMD5=False,
            )


def main() -> None:
    args = parse_args()
    configure(args)
    source_root = args.source_root.resolve()
    payload: dict[str, list[tuple[Path, str, str]]] = {}
    prefix = args.cos_prefix.strip("/")
    for slug in POOL_BINDINGS:
        directory = source_root / slug
        files = sorted(directory.glob("*.webp"))
        if not files:
            raise SystemExit(f"No webp files found: {directory}")
        payload[slug] = []
        for path in files:
            key = f"{prefix}/{slug}/{path.name}" if prefix else f"{slug}/{path.name}"
            payload[slug].append((path, key, public_url(args, key)))

    with connect_database() as connection:
        for slug, target_names in POOL_BINDINGS.items():
            placeholders = ", ".join("?" for _ in target_names)
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS row_count
                FROM managed_materials
                WHERE top = ? AND (series IN ({placeholders}) OR name IN ({placeholders}))
                """,
                ("bead", *target_names, *target_names),
            ).fetchone()
            count = int(row["row_count"] if hasattr(row, "keys") else row[0])
            print(f"[MATCH] {slug} -> rows={count} targets={','.join(target_names)} files={len(payload[slug])}")

    if args.dry_run:
        print("dry_run=true")
        return

    upload(args, payload)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    updated = 0
    with connect_database() as connection:
        for slug, target_names in POOL_BINDINGS.items():
            urls = [item[2] for item in payload[slug]]
            first_key = payload[slug][0][1]
            placeholders = ", ".join("?" for _ in target_names)
            cursor = connection.execute(
                f"""
                UPDATE managed_materials
                SET image_path = ?, image_url = ?, image_urls_json = ?, updated_at = ?
                WHERE top = ? AND (series IN ({placeholders}) OR name IN ({placeholders}))
                """,
                (
                    material_path_from_key(first_key),
                    urls[0],
                    json.dumps(urls, ensure_ascii=False),
                    now,
                    "bead",
                    *target_names,
                    *target_names,
                ),
            )
            updated += int(cursor.rowcount or 0)
    print(f"uploaded_files={sum(len(items) for items in payload.values())} updated_material_rows={updated}")


if __name__ == "__main__":
    main()
