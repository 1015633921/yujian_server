from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qcloud_cos import CosConfig, CosS3Client

from app.repository import DB_PATH


DEFAULT_SOURCE_DIR = Path("static/materials/beads")


def main() -> None:
    load_local_env(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Upload bead images to Tencent Cloud COS.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--prefix", default=os.getenv("TENCENT_COS_PREFIX", "materials/beads"))
    parser.add_argument("--bucket", default=os.getenv("TENCENT_COS_BUCKET"))
    parser.add_argument("--region", default=os.getenv("TENCENT_COS_REGION"))
    parser.add_argument("--secret-id", default=os.getenv("TENCENT_COS_SECRET_ID"))
    parser.add_argument("--secret-key", default=os.getenv("TENCENT_COS_SECRET_KEY"))
    parser.add_argument("--cdn-base-url", default=os.getenv("TENCENT_COS_CDN_BASE_URL", ""))
    parser.add_argument("--update-db", action="store_true")
    parser.add_argument("--strip-number-prefix", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    validate_args(args)
    files = sorted(path for path in args.source.iterdir() if path.suffix.lower() == ".png")
    if not files:
        raise SystemExit(f"No PNG files found in {args.source}")

    preview = preview_material_matches(files, args.strip_number_prefix)
    matched = sum(1 for _, count in preview if count)
    print(f"images={len(files)} matched_images={matched} unmatched_images={len(files) - matched}")
    for path, count in preview:
        name = series_name(path, args.strip_number_prefix)
        print(f"[{'MATCH' if count else 'SKIP'}] {path.name} -> {name} ({count} rows)")
    if args.dry_run:
        print("dry_run=true")
        return

    client = build_client(args)
    uploaded: list[tuple[str, str, str]] = []
    prefix = args.prefix.strip("/")
    for path in files:
        name = series_name(path, args.strip_number_prefix)
        object_name = f"{name}{path.suffix.lower()}"
        key = f"{prefix}/{object_name}" if prefix else object_name
        client.upload_file(
            Bucket=args.bucket,
            LocalFilePath=str(path),
            Key=key,
            PartSize=10,
            MAXThread=4,
            EnableMD5=False,
        )
        uploaded.append((name, key, public_url(args, key)))

    updated = 0
    if args.update_db:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = DB_PATH.with_name(f"{DB_PATH.stem}.before_cos_upload_{timestamp}{DB_PATH.suffix}")
        shutil.copy2(DB_PATH, backup)
        updated = update_material_urls(uploaded)
        print(f"database_backup={backup}")

    print(f"uploaded={len(uploaded)} updated_materials={updated} bucket={args.bucket} prefix={args.prefix}")


def validate_args(args: argparse.Namespace) -> None:
    missing = [
        name
        for name in ["bucket", "region", "secret_id", "secret_key"]
        if not getattr(args, name, None)
    ]
    if missing:
        raise SystemExit(
            "Missing COS config: "
            + ", ".join(missing)
            + "\nSet TENCENT_COS_BUCKET, TENCENT_COS_REGION, "
            "TENCENT_COS_SECRET_ID, TENCENT_COS_SECRET_KEY."
        )
    if not args.source.exists():
        raise SystemExit(f"Source directory not found: {args.source}")


def build_client(args: argparse.Namespace) -> CosS3Client:
    return CosS3Client(
        CosConfig(
            Region=args.region,
            SecretId=args.secret_id,
            SecretKey=args.secret_key,
            Scheme="https",
        )
    )


def public_url(args: argparse.Namespace, key: str) -> str:
    if args.cdn_base_url:
        return f"{args.cdn_base_url.rstrip('/')}/{quote(key)}"
    return f"https://{args.bucket}.cos.{args.region}.myqcloud.com/{quote(key)}"


def update_material_urls(uploaded: list[tuple[str, str, str]]) -> int:
    updated = 0
    with sqlite3.connect(DB_PATH) as connection:
        for series, key, image_url in uploaded:
            cursor = connection.execute(
                """
                UPDATE managed_materials
                SET image_path = ?, image_url = ?, updated_at = datetime('now')
                WHERE top = 'bead' AND (series = ? OR name = ?)
                """,
                (key, image_url, series, series),
            )
            updated += cursor.rowcount
    return updated


def preview_material_matches(files: list[Path], strip_number_prefix: bool) -> list[tuple[Path, int]]:
    result: list[tuple[Path, int]] = []
    with sqlite3.connect(DB_PATH) as connection:
        for path in files:
            name = series_name(path, strip_number_prefix)
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM managed_materials
                WHERE top = 'bead' AND (series = ? OR name = ?)
                """,
                (name, name),
            ).fetchone()[0]
            result.append((path, count))
    return result


def series_name(path: Path, strip_number_prefix: bool) -> str:
    if strip_number_prefix:
        return re.sub(r"^\d+[_\-\s]*", "", path.stem).strip()
    return path.stem


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


if __name__ == "__main__":
    main()
