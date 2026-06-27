from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repository import DB_PATH
from scripts.make_wps_beads_transparent import make_transparent


DEFAULT_SOURCE_DIR = Path(r"C:\Users\10156\Pictures\水晶珠子\珠子抠图\WPS图片批量处理")
DEFAULT_BUCKET = "yujian-1258267288"
DEFAULT_REGION = "ap-guangzhou"
DEFAULT_PREFIX = "materials/beads/wps"


@dataclass(frozen=True)
class BeadImage:
    path: Path
    bead_name: str


def main() -> None:
    load_local_env(ROOT / ".env")
    parser = argparse.ArgumentParser(description="上传 WPS 抠图珠子到 COS，并按名称绑定数据库。")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--bucket", default=os.getenv("TENCENT_COS_BUCKET", DEFAULT_BUCKET))
    parser.add_argument("--region", default=os.getenv("TENCENT_COS_REGION", DEFAULT_REGION))
    parser.add_argument("--prefix", default=os.getenv("TENCENT_COS_PREFIX", DEFAULT_PREFIX))
    parser.add_argument("--secret-id", default=os.getenv("TENCENT_COS_SECRET_ID"))
    parser.add_argument("--secret-key", default=os.getenv("TENCENT_COS_SECRET_KEY"))
    parser.add_argument("--cdn-base-url", default=os.getenv("TENCENT_COS_CDN_BASE_URL", ""))
    parser.add_argument("--feather", type=float, default=2.0)
    parser.add_argument("--inset", type=float, default=8.0)
    parser.add_argument("--size", type=int, default=640)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    images = load_images(args.source)
    matches, unmatched = preview_matches(images)
    print(f"images={len(images)} matched_images={len(matches)} unmatched_images={len(unmatched)}")
    for image, row_count in matches:
        print(f"[MATCH] {image.path.name} -> {image.bead_name} ({row_count} rows)")
    for image in unmatched:
        print(f"[SKIP]  {image.path.name} -> {image.bead_name}")

    if args.dry_run:
        print("dry_run=true")
        return
    if not args.secret_id or not args.secret_key:
        raise SystemExit(
            "Missing TENCENT_COS_SECRET_ID / TENCENT_COS_SECRET_KEY. "
            "Set them as environment variables, then rerun."
        )

    from qcloud_cos import CosConfig, CosS3Client

    client = CosS3Client(
        CosConfig(
            Region=args.region,
            SecretId=args.secret_id,
            SecretKey=args.secret_key,
            Scheme="https",
        )
    )
    uploaded: list[tuple[BeadImage, str, str]] = []
    prefix = args.prefix.strip("/")
    with tempfile.TemporaryDirectory(prefix="yujian-wps-beads-") as temp_dir:
        prepared_dir = Path(temp_dir)
        for image, _ in matches:
            prepared_path = prepared_dir / f"{image.bead_name}.png"
            make_transparent(
                image.path,
                prepared_path,
                feather=args.feather,
                inset=args.inset,
                output_size=args.size,
            )
            object_name = f"{image.bead_name}.png"
            key = f"{prefix}/{object_name}" if prefix else object_name
            client.upload_file(
                Bucket=args.bucket,
                LocalFilePath=str(prepared_path),
                Key=key,
                PartSize=10,
                MAXThread=4,
                EnableMD5=False,
            )
            uploaded.append((image, key, public_url(args, key)))

    backup = DB_PATH.with_suffix(".before_wps_cos_images.db")
    shutil.copy2(DB_PATH, backup)
    updated = update_database(uploaded)
    print(f"uploaded={len(uploaded)} updated_material_rows={updated}")
    print(f"database_backup={backup}")


def load_images(source: Path) -> list[BeadImage]:
    if not source.exists():
        raise SystemExit(f"Source directory not found: {source}")
    images = []
    for path in sorted(source.iterdir()):
        if path.is_file() and path.suffix.lower() == ".png":
            images.append(BeadImage(path=path, bead_name=strip_number_prefix(path.stem)))
    return images


def preview_matches(images: list[BeadImage]) -> tuple[list[tuple[BeadImage, int]], list[BeadImage]]:
    matches = []
    unmatched = []
    with sqlite3.connect(DB_PATH) as connection:
        for image in images:
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM managed_materials
                WHERE top = 'bead' AND (series = ? OR name = ?)
                """,
                (image.bead_name, image.bead_name),
            ).fetchone()[0]
            if count:
                matches.append((image, count))
            else:
                unmatched.append(image)
    return matches, unmatched


def update_database(uploaded: list[tuple[BeadImage, str, str]]) -> int:
    updated = 0
    with sqlite3.connect(DB_PATH) as connection:
        for image, key, image_url in uploaded:
            cursor = connection.execute(
                """
                UPDATE managed_materials
                SET image_path = ?, image_url = ?, updated_at = datetime('now')
                WHERE top = 'bead' AND (series = ? OR name = ?)
                """,
                (key, image_url, image.bead_name, image.bead_name),
            )
            updated += cursor.rowcount
    return updated


def public_url(args: argparse.Namespace, key: str) -> str:
    if args.cdn_base_url:
        return f"{args.cdn_base_url.rstrip('/')}/{quote(key)}"
    return f"https://{args.bucket}.cos.{args.region}.myqcloud.com/{quote(key)}"


def strip_number_prefix(value: str) -> str:
    return re.sub(r"^\d+[_\-\s]*", "", value).strip()


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
