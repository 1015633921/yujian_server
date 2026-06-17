from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repository import DB_PATH


DEFAULT_SOURCE_DIR = Path(r"C:\Users\10156\Pictures\水晶珠子\水晶珠子图片_已命名打包")
DEFAULT_COS_BASE_URL = "https://yujian-1258267288.cos.ap-guangzhou.myqcloud.com"


def main() -> None:
    parser = argparse.ArgumentParser(description="Link managed bead materials to numbered COS image URLs.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_DIR, help="包含 01_黑晶石.png 这类文件名的目录")
    parser.add_argument("--base-url", default=DEFAULT_COS_BASE_URL, help="COS 或 CDN 根地址")
    args = parser.parse_args()

    files = sorted(
        path for path in args.source.iterdir()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    if not files:
        raise SystemExit(f"No image files found in {args.source}")

    updated = update_urls(files, args.base_url)
    print(f"linked_files={len(files)} updated_materials={updated} base_url={args.base_url.rstrip('/')}")


def update_urls(files: list[Path], base_url: str) -> int:
    updated = 0
    with sqlite3.connect(DB_PATH) as connection:
        for path in files:
            series = series_name_from_file(path)
            object_name = f"{series}{path.suffix.lower()}"
            image_url = f"{base_url.rstrip('/')}/{quote(object_name)}"
            cursor = connection.execute(
                """
                UPDATE managed_materials
                SET image_path = ?, image_url = ?, updated_at = datetime('now')
                WHERE top = 'bead' AND (series = ? OR name = ?)
                """,
                (object_name, image_url, series, series),
            )
            updated += cursor.rowcount
    return updated


def series_name_from_file(path: Path) -> str:
    return re.sub(r"^\d+[_-]*", "", path.stem).strip()


if __name__ == "__main__":
    main()
