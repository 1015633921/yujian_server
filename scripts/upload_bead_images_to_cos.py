from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qcloud_cos import CosConfig, CosS3Client

from app.repository import DB_PATH


DEFAULT_SOURCE_DIR = Path("static/materials/beads")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload bead thumbnail images to Tencent Cloud COS.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_DIR, help="本地珠子缩略图目录")
    parser.add_argument("--prefix", default=os.getenv("TENCENT_COS_PREFIX", "materials/beads"), help="COS 对象前缀")
    parser.add_argument("--bucket", default=os.getenv("TENCENT_COS_BUCKET"), help="COS bucket，例如 yujian-1250000000")
    parser.add_argument("--region", default=os.getenv("TENCENT_COS_REGION"), help="COS region，例如 ap-guangzhou")
    parser.add_argument("--secret-id", default=os.getenv("TENCENT_COS_SECRET_ID"), help="腾讯云 SecretId")
    parser.add_argument("--secret-key", default=os.getenv("TENCENT_COS_SECRET_KEY"), help="腾讯云 SecretKey")
    parser.add_argument("--cdn-base-url", default=os.getenv("TENCENT_COS_CDN_BASE_URL", ""), help="CDN 根地址，可选")
    parser.add_argument("--update-db", action="store_true", help="上传后同步更新 managed_materials.image_url")
    args = parser.parse_args()

    validate_args(args)
    client = build_client(args)
    files = sorted(path for path in args.source.iterdir() if path.suffix.lower() == ".png")
    if not files:
        raise SystemExit(f"No PNG files found in {args.source}")

    uploaded: list[tuple[str, str, str]] = []
    for path in files:
        key = f"{args.prefix.strip('/')}/{path.name}"
        client.upload_file(
            Bucket=args.bucket,
            LocalFilePath=str(path),
            Key=key,
            PartSize=10,
            MAXThread=4,
            EnableMD5=False,
        )
        image_url = public_url(args, key)
        uploaded.append((path.stem, key, image_url))

    if args.update_db:
        updated = update_material_urls(uploaded)
    else:
        updated = 0

    print(f"uploaded={len(uploaded)} updated_materials={updated} bucket={args.bucket} prefix={args.prefix}")


def validate_args(args: argparse.Namespace) -> None:
    missing = [
        name for name in ["bucket", "region", "secret_id", "secret_key"]
        if not getattr(args, name.replace("-", "_"), None)
    ]
    if missing:
        raise SystemExit(
            "Missing COS config: "
            + ", ".join(missing)
            + "\nSet TENCENT_COS_BUCKET, TENCENT_COS_REGION, TENCENT_COS_SECRET_ID, TENCENT_COS_SECRET_KEY."
        )
    if not args.source.exists():
        raise SystemExit(f"Source directory not found: {args.source}")


def build_client(args: argparse.Namespace) -> CosS3Client:
    config = CosConfig(
        Region=args.region,
        SecretId=args.secret_id,
        SecretKey=args.secret_key,
        Scheme="https",
    )
    return CosS3Client(config)


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


if __name__ == "__main__":
    main()
