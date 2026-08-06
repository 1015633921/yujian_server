from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_material_tagging import MaterialTaggingRepository, MaterialTaggingService
from app.migrations.runner import upgrade


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="使用千问为宇涧材料图库生成待人工审核的视觉标签"
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--top", default="")
    parser.add_argument("--material-code", action="append", default=[])
    parser.add_argument("--series", default="", help="按品种名称模糊筛选")
    parser.add_argument("--db-path", type=Path, default=None, help="仅SQLite环境使用")
    parser.add_argument("--migrate", action="store_true", help="执行包含回滚记录的显式数据库迁移")
    parser.add_argument("--force", action="store_true", help="忽略相同输入的待审核/已审核记录")
    parser.add_argument("--dry-run", action="store_true", help="只列出目标，不调用模型")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.migrate:
        backend = "sqlite" if args.db_path else os.getenv("DATABASE_BACKEND", "sqlite")
        applied = upgrade(backend=backend, sqlite_path=args.db_path)
        print(json.dumps({"migration_applied": applied}, ensure_ascii=False))

    repository = MaterialTaggingRepository(args.db_path)
    targets = repository.list_targets(
        limit=max(1, min(args.limit, 100)),
        top=args.top,
        material_codes=args.material_code,
        series_keyword=args.series,
        require_gallery=True,
    )
    preview = [
        {
            "target_id": item.target_id,
            "material_code": item.material_code,
            "top": item.top,
            "category": item.category,
            "series": item.series,
            "gallery_count": len(item.image_urls),
        }
        for item in targets
    ]
    print(json.dumps({"target_count": len(targets), "targets": preview}, ensure_ascii=False))
    if args.dry_run or not targets:
        return 0

    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        api_key = getpass.getpass("DASHSCOPE_API_KEY（不会写入文件或日志）: ").strip()
    result = MaterialTaggingService(repository=repository).analyze_targets(
        targets,
        force=args.force,
        api_key=api_key,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
