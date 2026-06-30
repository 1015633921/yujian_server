from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.admin_service import AdminService, now_iso
from app.material_knowledge import infer_material_code_from_text, material_code_from_payload, upsert_material_knowledge


AGATE_CODES = {
    "alashan_agate",
    "banded_agate",
    "black_agate",
    "blue_lace_agate",
    "flower_agate",
    "red_agate",
    "salt_source_agate",
    "south_red_agate",
}


def canonical_material_code(row: dict[str, Any]) -> str:
    descriptive_payload = {
        key: value
        for key, value in row.items()
        if key not in {"material_code", "code", "skuId", "sku_id", "id"}
    }
    inferred = infer_material_code_from_text(descriptive_payload)
    if inferred:
        return inferred
    return material_code_from_payload(row)


def canonical_category(row: dict[str, Any], material_code: str) -> str:
    text = " ".join(str(row.get(key) or "") for key in ("category", "series", "name", "image_path", "image_url"))
    if material_code in AGATE_CODES or "玛瑙" in text:
        return "玛瑙"
    return str(row.get("category") or "").strip()


def numeric_unique(base: str, used: set[str]) -> str:
    candidate = "".join(ch for ch in str(base or "") if ch.isdigit())
    if not candidate:
        candidate = "9000000000000"
    if candidate not in used:
        used.add(candidate)
        return candidate
    suffix = 2
    while True:
        next_candidate = f"{candidate}{suffix:02d}"
        if next_candidate not in used:
            used.add(next_candidate)
            return next_candidate
        suffix += 1


def regenerate(apply: bool, force_knowledge: bool, limit: int = 0) -> dict[str, Any]:
    service = AdminService()
    timestamp = now_iso()
    with service.connect() as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM managed_materials
                ORDER BY top, category, series, size, id
                """
            ).fetchall()
        ]
        if limit > 0:
            rows = rows[:limit]
        used: set[str] = set()
        updates: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            material_code = canonical_material_code(payload)
            category = canonical_category(payload, material_code)
            payload["material_code"] = material_code
            payload["category"] = category
            base_sku = service.generate_material_sku(payload)
            sku_id = numeric_unique(base_sku, used)
            changed = (
                sku_id != str(row.get("skuId") or "")
                or material_code != str(row.get("material_code") or "")
                or category != str(row.get("category") or "")
            )
            updates.append(
                {
                    "id": row["id"],
                    "old_sku": row.get("skuId") or "",
                    "new_sku": sku_id,
                    "old_code": row.get("material_code") or "",
                    "new_code": material_code,
                    "old_category": row.get("category") or "",
                    "new_category": category,
                    "name": row.get("name") or row.get("series") or "",
                    "size": row.get("size") or "",
                    "changed": changed,
                }
            )
            if apply:
                connection.execute(
                    """
                    UPDATE managed_materials
                    SET skuId = ?, material_code = ?, category = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (sku_id, material_code, category, timestamp, row["id"]),
                )
                material = {**row, "skuId": sku_id, "material_code": material_code, "category": category}
                upsert_material_knowledge(
                    {**payload, "skuId": sku_id, "material_code": material_code},
                    material,
                    connection=connection,
                    force_update=force_knowledge,
                )
        if apply:
            service._sync_material_taxonomy_from_materials(connection)
    changed_count = sum(1 for item in updates if item["changed"])
    return {
        "apply": apply,
        "force_knowledge": force_knowledge,
        "total": len(updates),
        "changed": changed_count,
        "sample": updates[:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate numeric material SKUs and enrich material knowledge.")
    parser.add_argument("--apply", action="store_true", help="Write updates to the configured database.")
    parser.add_argument(
        "--force-knowledge",
        action="store_true",
        help="Overwrite existing material_knowledge rows with taxonomy-derived defaults.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Only process first N rows; useful for dry-run checks.")
    args = parser.parse_args()

    result = regenerate(apply=args.apply, force_knowledge=args.force_knowledge, limit=args.limit)
    print(f"apply={result['apply']} total={result['total']} changed={result['changed']} force_knowledge={result['force_knowledge']}")
    for item in result["sample"]:
        print(
            f"{item['id']} {item['name']} {item['size']}mm "
            f"{item['old_sku']} -> {item['new_sku']} "
            f"code:{item['old_code'] or '-'}->{item['new_code']} "
            f"category:{item['old_category'] or '-'}->{item['new_category'] or '-'}"
        )
    if not args.apply:
        print("dry_run=true; add --apply to write changes")


if __name__ == "__main__":
    main()
