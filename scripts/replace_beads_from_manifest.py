from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


SIZES = tuple(range(8, 16))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replace every bead material with entries generated from an image manifest."
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base-url", default="https://yujian-1258267288.cos.ap-guangzhou.myqcloud.com")
    parser.add_argument("--prefix", default="materials/beads/wps-transparent")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    names = load_names(args.manifest)
    if len(names) != 100:
        raise SystemExit(f"Expected 100 unique bead names, found {len(names)}")
    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")

    with sqlite3.connect(args.db) as connection:
        previous = connection.execute(
            "SELECT COUNT(*) FROM managed_materials WHERE top = 'bead'"
        ).fetchone()[0]
        other = connection.execute(
            "SELECT COUNT(*) FROM managed_materials WHERE top <> 'bead'"
        ).fetchone()[0]

    print(
        f"bead_names={len(names)} sizes={len(SIZES)} "
        f"new_rows={len(names) * len(SIZES)} previous_bead_rows={previous} preserved_other_rows={other}"
    )
    if args.dry_run:
        print("dry_run=true")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = args.db.with_name(f"{args.db.stem}.before_bead_replace_{timestamp}{args.db.suffix}")
    shutil.copy2(args.db, backup)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    prefix = args.prefix.strip("/")
    rows = []
    for index, name in enumerate(names, start=1):
        profile = infer_profile(name)
        token = hashlib.sha1(name.encode("utf-8")).hexdigest()[:12]
        sku_id = f"bead_{token}"
        key = f"{prefix}/{name}.png"
        image_url = f"{args.base_url.rstrip('/')}/{quote(key)}"
        for size_offset, size in enumerate(SIZES):
            rows.append(
                (
                    f"{sku_id}_{size}mm",
                    sku_id,
                    "bead",
                    profile["category"],
                    name,
                    "",
                    name,
                    profile["effect"],
                    profile["element"],
                    estimate_price(size),
                    size,
                    round((size / 8) ** 3 * 1.2, 2),
                    profile["color"],
                    profile["shine"],
                    key,
                    image_url,
                    1,
                    index * 10 + size_offset,
                    now,
                    now,
                )
            )

    with sqlite3.connect(args.db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM managed_materials WHERE top = 'bead'")
        connection.executemany(
            """
            INSERT INTO managed_materials
            (id, skuId, top, category, series, grade, name, effect, element, price, size, weight,
             color, shine, image_path, image_url, enabled, sort_order, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()
        final_count = connection.execute(
            "SELECT COUNT(*) FROM managed_materials WHERE top = 'bead'"
        ).fetchone()[0]
        distinct_names = connection.execute(
            "SELECT COUNT(DISTINCT series) FROM managed_materials WHERE top = 'bead'"
        ).fetchone()[0]

    print(f"inserted_rows={final_count} distinct_beads={distinct_names}")
    print(f"backup={backup}")


def load_names(manifest: Path) -> list[str]:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    names = [str(item["name"]).strip() for item in payload if item.get("name")]
    return list(dict.fromkeys(names))


def infer_profile(name: str) -> dict[str, str]:
    rules = [
        (["幽灵"], "幽灵水晶", "木", "生长与复原", "#5f9a72", "#e1f2e7"),
        (["兔毛"], "兔毛水晶", "火", "热情与行动", "#c96f78", "#ffe7ea"),
        (["草莓", "粉晶", "粉水晶", "红纹", "樱花"], "粉红晶石", "火", "亲密与吸引", "#d98d96", "#fff0f2"),
        (["黄水晶", "金发", "钛晶", "金太阳", "虎眼"], "财富晶石", "土", "财富与行动", "#d4a548", "#fff0b8"),
        (["蓝", "海纹", "天河", "青金", "堇青"], "蓝色晶石", "水", "沟通与平静", "#6faec5", "#e9f8ff"),
        (["紫", "极光"], "紫色晶石", "火", "灵感与觉察", "#8a69a8", "#f1e8ff"),
        (["白", "月光", "奶白"], "白色晶石", "金", "净化与放大", "#dfe3e5", "#ffffff"),
        (["黑", "墨", "曜", "陨石", "茶晶"], "守护晶石", "水", "守护与稳定", "#333238", "#bfc3c7"),
        (["绿", "葡萄"], "绿色晶石", "木", "成长与平衡", "#5f9a72", "#e1f2e7"),
        (["红", "南红", "玛瑙", "石榴"], "红色晶石", "火", "活力与自信", "#b95858", "#ffe1df"),
        (["萤石"], "萤石", "水", "专注与秩序", "#7895aa", "#ecf7ff"),
        (["发晶"], "发晶", "金", "决断与聚焦", "#8e7a63", "#fff1d8"),
        (["胶花"], "胶花水晶", "火", "创造与热情", "#d27762", "#fff0e8"),
    ]
    for keywords, category, element, effect, color, shine in rules:
        if any(keyword in name for keyword in keywords):
            return {
                "category": category,
                "element": element,
                "effect": effect,
                "color": color,
                "shine": shine,
            }
    return {
        "category": crystal_category(name),
        "element": "土",
        "effect": "平衡与守护",
        "color": "#9f8d7a",
        "shine": "#fff5e8",
    }


def crystal_category(name: str) -> str:
    for suffix in ("水晶", "玛瑙", "萤石", "石", "晶"):
        if suffix in name:
            return suffix
    return "天然晶石"


def estimate_price(size: int) -> int:
    return int(round(12 * (size / 8) ** 1.35))


if __name__ == "__main__":
    main()
