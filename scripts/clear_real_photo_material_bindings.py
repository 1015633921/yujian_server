from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import connect_database
from scripts.upload_real_bead_photo_assets_to_cos_and_db import load_local_env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clear or disable previously imported real-photo material bindings.")
    parser.add_argument("--app-env", default="test")
    parser.add_argument("--mysql-database", default="yujian_test")
    parser.add_argument("--prefix", default="real-photos")
    parser.add_argument("--apply", action="store_true", help="Actually write changes. Default is dry-run.")
    parser.add_argument(
        "--mode",
        choices=("disable-created", "clear-images", "both"),
        default="disable-created",
        help="disable-created only disables deterministic real_* rows; clear-images clears image fields from matching rows.",
    )
    return parser.parse_args()


def main() -> None:
    load_local_env(ROOT / ".env")
    load_local_env(ROOT / ".env.local")
    load_local_env(ROOT / ".env.test")
    args = parse_args()
    os.environ["APP_ENV"] = args.app_env
    os.environ["MYSQL_DATABASE"] = args.mysql_database
    if os.getenv("APP_ENV", "").lower() not in {"test", "testing", "staging"}:
        raise SystemExit("Refusing to modify non-test environment.")
    pattern = f"%{args.prefix}%"
    with connect_database() as connection:
        total = connection.execute(
            "SELECT COUNT(*) AS c FROM managed_materials WHERE image_url LIKE ? OR image_urls_json LIKE ?",
            (pattern, pattern),
        ).fetchone()["c"]
        created = connection.execute(
            "SELECT COUNT(*) AS c FROM managed_materials WHERE id LIKE 'real\\_%' AND (image_url LIKE ? OR image_urls_json LIKE ?)",
            (pattern, pattern),
        ).fetchone()["c"]
        print(f"matching_rows={total} created_real_rows={created} mode={args.mode} apply={args.apply}")
        if not args.apply:
            return
        if args.mode in {"disable-created", "both"}:
            connection.execute(
                "UPDATE managed_materials SET enabled=0, updated_at=UTC_TIMESTAMP() WHERE id LIKE 'real\\_%' AND (image_url LIKE ? OR image_urls_json LIKE ?)",
                (pattern, pattern),
            )
        if args.mode in {"clear-images", "both"}:
            connection.execute(
                "UPDATE managed_materials SET image_path='', image_url='', image_urls_json='[]', updated_at=UTC_TIMESTAMP() WHERE image_url LIKE ? OR image_urls_json LIKE ?",
                (pattern, pattern),
            )
        try:
            from app.materials import invalidate_material_cache

            invalidate_material_cache()
        except Exception:
            pass


if __name__ == "__main__":
    main()
