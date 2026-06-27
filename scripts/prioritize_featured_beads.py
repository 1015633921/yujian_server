from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import connect_database
from app.materials import featured_material_rank, material_customer_sort_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Move visually preferred bead materials to the front of the catalog.")
    parser.add_argument("--dry-run", action="store_true", help="Only print the planned order without updating sort_order.")
    parser.add_argument("--step", type=int, default=10, help="Sort order step between adjacent bead rows.")
    args = parser.parse_args()

    with connect_database() as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, skuId, category, series, name, effect, color, size, sort_order
                FROM managed_materials
                WHERE top = 'bead' AND enabled = 1
                """
            ).fetchall()
        ]
        ordered = sorted(rows, key=material_customer_sort_key)
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        preview = ordered[:30]
        print("top_preview:")
        for index, item in enumerate(preview, start=1):
            print(
                f"{index:02d}. rank={featured_material_rank(item):02d} "
                f"sort={item.get('sort_order')} size={item.get('size')} "
                f"{item.get('series') or item.get('name') or item.get('category')} [{item.get('id')}]"
            )

        if args.dry_run:
            print(f"dry_run=true matched_rows={len(ordered)}")
            return

        for index, item in enumerate(ordered, start=1):
            connection.execute(
                "UPDATE managed_materials SET sort_order = ?, updated_at = ? WHERE id = ?",
                (index * args.step, timestamp, item["id"]),
            )

    print(f"updated_rows={len(ordered)}")


if __name__ == "__main__":
    main()
