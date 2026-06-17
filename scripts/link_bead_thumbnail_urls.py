from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repository import DB_PATH


DEFAULT_INPUT_DIR = Path("generated/bead-thumbnails")
DEFAULT_STATIC_DIR = Path("static/materials/beads")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish bead thumbnails and link them to managed materials.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_DIR, help="裁剪后缩略图目录")
    parser.add_argument("--static-dir", type=Path, default=DEFAULT_STATIC_DIR, help="后端静态图片目录")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/static/materials/beads", help="图片访问根地址")
    args = parser.parse_args()

    args.static_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in args.input.iterdir() if path.suffix.lower() == ".png")
    copied = 0
    updated = 0

    with sqlite3.connect(DB_PATH) as connection:
        for source in files:
            target = args.static_dir / source.name
            if source.resolve() != target.resolve():
                shutil.copy2(source, target)
                copied += 1

            series = source.stem
            image_path = f"materials/beads/{source.name}"
            image_url = f"{args.base_url.rstrip('/')}/{quote(source.name)}"
            cursor = connection.execute(
                """
                UPDATE managed_materials
                SET image_path = ?, image_url = ?, updated_at = datetime('now')
                WHERE top = 'bead' AND (series = ? OR name = ?)
                """,
                (image_path, image_url, series, series),
            )
            updated += cursor.rowcount

    print(f"copied={copied} updated_materials={updated} static_dir={args.static_dir.resolve()}")


if __name__ == "__main__":
    main()
