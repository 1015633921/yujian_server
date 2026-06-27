from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repository import DB_PATH


DEFAULT_SOURCE_DIR = Path(r"C:\Users\10156\Pictures\水晶珠子\by_name")
DEFAULT_STATIC_DIR = Path("static/materials/beads/real")
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

# 这里只放含义明确的商品简称，避免把一张图误绑定到相似但不同的水晶。
SAFE_ALIASES = {
    "黑金超": ["黑金超七"],
    "满天星绿幽灵": ["满天星"],
    "灰月光": ["灰月光石"],
    "蓝月光": ["蓝月光石"],
    "冰川蓝海蓝宝": ["冰川蓝"],
    "圣蓝海蓝宝": ["圣蓝"],
    "奶白晶": ["奶白水晶"],
    "婚纱闪白阿塞": ["白阿塞水晶"],
    "净体白水晶": ["白水晶"],
    "星光粉晶": ["六芒星光粉晶"],
    "乌拉圭紫水晶": ["乌拉圭紫晶", "乌拉圭紫水晶"],
    "巴西紫水金": ["巴西紫晶"],
    "薰衣草紫水晶": ["薰衣草紫晶"],
    "金曜石": ["金耀石"],
    "银曜石": ["银耀石"],
    "青提岫玉": ["岫玉"],
    "透体柠檬黄水晶": ["柠檬黄水晶"],
}


@dataclass(frozen=True)
class SourceImage:
    path: Path
    category: str
    product_name: str


def main() -> None:
    parser = argparse.ArgumentParser(description="按抓取图片文件名绑定 managed_materials 实拍图。")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_DIR, help="抓取图片目录")
    parser.add_argument("--static-dir", type=Path, default=DEFAULT_STATIC_DIR, help="后端静态目录")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000/static/materials/beads/real",
        help="静态图片访问根地址",
    )
    parser.add_argument("--apply", action="store_true", help="实际复制图片并更新数据库；不传时仅预览")
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"Source directory not found: {args.source}")
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    images = load_source_images(args.source)
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        material_names = load_material_names(connection)
        matches, unmatched = match_images(images, material_names)

        print(f"source_images={len(images)} matched_images={len(matches)} unmatched_images={len(unmatched)}")
        for image, targets in matches:
            print(f"[MATCH] {image.path.name} -> {', '.join(targets)}")
        for image in unmatched:
            print(f"[SKIP]  {image.path.name}")

        if not args.apply:
            print("dry_run=true; add --apply to copy files and update database")
            return

        args.static_dir.mkdir(parents=True, exist_ok=True)
        backup_path = DB_PATH.with_suffix(".before_real_bead_images.db")
        shutil.copy2(DB_PATH, backup_path)
        copied, updated = apply_matches(connection, matches, args.static_dir, args.base_url)
        connection.commit()

    print(f"copied={copied} updated_material_rows={updated}")
    print(f"database_backup={backup_path}")


def load_source_images(source_dir: Path) -> list[SourceImage]:
    images: list[SourceImage] = []
    for path in sorted(source_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        parts = path.stem.split("__")
        if len(parts) < 2:
            continue
        images.append(SourceImage(path=path, category=parts[0].strip(), product_name=parts[1].strip()))
    return images


def load_material_names(connection: sqlite3.Connection) -> dict[str, set[str]]:
    rows = connection.execute(
        """
        SELECT DISTINCT category, series, name
        FROM managed_materials
        WHERE top = 'bead'
        """
    ).fetchall()
    by_normalized: dict[str, set[str]] = {}
    for row in rows:
        for value in (row["series"], row["name"]):
            clean = str(value or "").strip()
            if clean:
                by_normalized.setdefault(normalize_name(clean), set()).add(clean)
    return by_normalized


def match_images(
    images: list[SourceImage],
    material_names: dict[str, set[str]],
) -> tuple[list[tuple[SourceImage, list[str]]], list[SourceImage]]:
    matches: list[tuple[SourceImage, list[str]]] = []
    unmatched: list[SourceImage] = []
    used_targets: set[str] = set()

    for image in images:
        candidates = [image.product_name, *SAFE_ALIASES.get(image.product_name, [])]
        targets: set[str] = set()
        for candidate in candidates:
            targets.update(material_names.get(normalize_name(candidate), set()))

        # 一种数据库品种只绑定第一张明确命中的图片，避免“随形/跑环”等后续图片覆盖圆珠图。
        available = sorted(target for target in targets if target not in used_targets)
        if not available:
            unmatched.append(image)
            continue
        used_targets.update(available)
        matches.append((image, available))

    return matches, unmatched


def apply_matches(
    connection: sqlite3.Connection,
    matches: list[tuple[SourceImage, list[str]]],
    static_dir: Path,
    base_url: str,
) -> tuple[int, int]:
    copied = 0
    updated = 0
    for image, targets in matches:
        target_name = safe_static_filename(image.product_name, image.path.suffix.lower())
        target_path = static_dir / target_name
        shutil.copy2(image.path, target_path)
        copied += 1

        relative_path = f"materials/beads/real/{target_name}"
        image_url = f"{base_url.rstrip('/')}/{quote(target_name)}"
        placeholders = ", ".join("?" for _ in targets)
        cursor = connection.execute(
            f"""
            UPDATE managed_materials
            SET image_path = ?, image_url = ?, updated_at = datetime('now')
            WHERE top = 'bead' AND (series IN ({placeholders}) OR name IN ({placeholders}))
            """,
            (relative_path, image_url, *targets, *targets),
        )
        updated += cursor.rowcount
    return copied, updated


def normalize_name(value: str) -> str:
    return re.sub(r"[\s_\-（）()·/]+", "", value).lower()


def safe_static_filename(product_name: str, suffix: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*]+', "_", product_name).strip(" .")
    return f"{clean}{suffix}"


if __name__ == "__main__":
    main()
