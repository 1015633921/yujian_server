from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


DEFAULT_DB = Path("/opt/yujian_server/data/yujian_fastapi.db")
DEFAULT_SOURCE = Path(r"C:\Users\10156\Pictures\水晶珠子\珠子抠图\WPS图片批量处理")
DEFAULT_BASE_URL = "https://yujian-1258267288.cos.ap-guangzhou.myqcloud.com"
DEFAULT_PREFIX = "materials/beads/wps"

WPS_BEAD_NAMES = [
    "黑晶石", "油画蓝晶", "蓝晶石", "玉化蓝晶", "透体蓝晶",
    "喜马拉雅白水晶", "奶白水晶", "白阿塞水晶", "白水晶", "双A白水",
    "乌拉圭紫晶", "巴西紫晶", "薰衣草紫晶", "紫黄晶", "玻利维亚紫水晶",
    "巴西黄水晶", "柠檬黄水晶", "黄塔晶", "莫桑比克粉晶", "马达加斯加粉晶",
    "老矿粉晶", "果冻粉", "冰种粉晶", "六芒星光粉晶", "浅茶",
    "深茶", "墨晶", "黑茶晶", "烟墨晶", "绿水晶",
    "绿阿塞", "金发晶", "钛晶", "红铜发", "黑发晶",
    "绿发晶", "银发晶", "彩发晶", "绿幽灵", "满天星",
    "抹茶幽灵", "墨绿幽灵", "翠绿幽灵", "红幽灵", "白幽灵",
    "四季幽灵", "黄幽灵", "紫幽灵", "意境幽灵", "千层幽灵",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="将 WPS 珠子 COS 地址增量同步到材料数据库。")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--source", type=Path, default=None, help="可选：从本地目录读取文件名")
    parser.add_argument("--manifest", type=Path, default=None, help="可选：从图片 manifest.json 读取珠子名称")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.manifest:
        names = names_from_manifest(args.manifest)
    elif args.source:
        names = names_from_source(args.source)
    else:
        names = WPS_BEAD_NAMES
    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")

    with sqlite3.connect(args.db) as connection:
        counts = {
            name: connection.execute(
                """
                SELECT COUNT(*) FROM managed_materials
                WHERE top = 'bead' AND (series = ? OR name = ?)
                """,
                (name, name),
            ).fetchone()[0]
            for name in names
        }
        unmatched = [name for name, count in counts.items() if not count]
        matched_rows = sum(counts.values())
        print(f"names={len(names)} matched_rows={matched_rows} unmatched={len(unmatched)}")
        for name in unmatched:
            print(f"[SKIP] {name}")
        if args.dry_run:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = args.db.with_name(f"{args.db.stem}.before_wps_sync_{timestamp}{args.db.suffix}")
        shutil.copy2(args.db, backup)

        updated = 0
        prefix = args.prefix.strip("/")
        for name, count in counts.items():
            if not count:
                continue
            key = f"{prefix}/{name}.png" if prefix else f"{name}.png"
            image_url = f"{args.base_url.rstrip('/')}/{quote(key)}"
            cursor = connection.execute(
                """
                UPDATE managed_materials
                SET image_path = ?, image_url = ?, updated_at = datetime('now')
                WHERE top = 'bead' AND (series = ? OR name = ?)
                """,
                (key, image_url, name, name),
            )
            updated += cursor.rowcount
        connection.commit()

    print(f"updated_rows={updated}")
    print(f"backup={backup}")


def names_from_source(source: Path) -> list[str]:
    if not source.exists():
        raise SystemExit(f"Source directory not found: {source}")
    return [
        re.sub(r"^\d+[_\-\s]*", "", path.stem).strip()
        for path in sorted(source.iterdir())
        if path.is_file() and path.suffix.lower() == ".png"
    ]


def names_from_manifest(manifest: Path) -> list[str]:
    if not manifest.exists():
        raise SystemExit(f"Manifest not found: {manifest}")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return [str(item["name"]).strip() for item in payload if item.get("name")]


if __name__ == "__main__":
    main()
