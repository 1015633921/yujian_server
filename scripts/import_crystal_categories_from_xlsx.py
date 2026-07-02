from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.admin_service import AdminService
from app.material_knowledge import knowledge_to_db_item
from app.materials import invalidate_material_cache


BEAD_SIZES = tuple(range(8, 16))
ACCESSORY_SIZES_BY_SHAPE = {
    "随型": (8, 10, 12, 14),
    "方糖": (6, 8, 10, 12),
    "三角牌": (10, 12, 14, 16),
    "魔盒": (8, 10, 12),
    "圆桶型": (8, 10, 12, 14),
}

GRADE_VARIANTS = (
    {"prefix": "", "grade": "", "price_multiplier": 1.0, "stock": 99},
    {"prefix": "高品", "grade": "高品", "price_multiplier": 2.0, "stock": 60},
)

TOP_CODE = {"bead": "10", "accessory": "20", "pendant": "30"}
ELEMENT_LABEL = {
    "metal": "金",
    "wood": "木",
    "water": "水",
    "fire": "火",
    "earth": "土",
}

SHAPE_PARAMS = {
    "bead": {"bead_shape": "round", "surface_finish": "glossy"},
    "随型": {"bead_shape": "special", "surface_finish": "glossy"},
    "方糖": {"bead_shape": "special", "surface_finish": "glossy"},
    "三角牌": {"bead_shape": "special", "surface_finish": "glossy"},
    "魔盒": {"bead_shape": "special", "surface_finish": "glossy"},
    "圆桶型": {"bead_shape": "barrel", "surface_finish": "glossy"},
}


@dataclass(frozen=True)
class SourceRow:
    row_number: int
    category: str
    series: str


def read_xlsx_rows(path: Path) -> list[SourceRow]:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(path) as workbook:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", ns):
                shared_strings.append(
                    "".join(
                        node.text or ""
                        for node in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                    )
                )

        workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
        rel_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
        rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rel_root}
        sheet = workbook_root.find("a:sheets/a:sheet", ns)
        if sheet is None:
            raise ValueError("Excel 文件没有工作表")
        rel_id = sheet.attrib[f"{{{rel_ns}}}id"]
        target = rel_map[rel_id]
        sheet_path = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
        sheet_root = ET.fromstring(workbook.read(sheet_path))

    rows: list[SourceRow] = []
    for row in sheet_root.findall("a:sheetData/a:row", ns):
        values: list[str] = []
        for cell in row.findall("a:c", ns):
            ref = cell.attrib.get("r", "")
            match = re.match(r"([A-Z]+)(\d+)", ref)
            if match:
                column = column_index(match.group(1))
                while len(values) < column - 1:
                    values.append("")
            cell_type = cell.attrib.get("t")
            value_node = cell.find("a:v", ns)
            inline_node = cell.find("a:is", ns)
            value = ""
            if cell_type == "s" and value_node is not None:
                value = shared_strings[int(value_node.text or 0)]
            elif cell_type == "inlineStr" and inline_node is not None:
                value = "".join(
                    node.text or ""
                    for node in inline_node.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                )
            elif value_node is not None:
                value = value_node.text or ""
            values.append(value.strip())
        if len(values) < 2:
            continue
        row_number = int(row.attrib.get("r", len(rows) + 1))
        if row_number == 1 and values[:2] == ["一级分类", "二级分类"]:
            continue
        category, series = values[0].strip(), values[1].strip()
        if category and series:
            rows.append(SourceRow(row_number=row_number, category=category, series=series))
    return rows


def column_index(letters: str) -> int:
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - 64
    return value


def classify_row(row: SourceRow, accessory_mode: bool) -> tuple[str, str, str]:
    if not accessory_mode:
        return "bead", row.category, "bead"
    return "accessory", row.category, row.category


def profile_for(category: str, series: str, top: str) -> dict[str, Any]:
    text = f"{category}{series}"
    rules: list[tuple[tuple[str, ...], dict[str, Any]]] = [
        (("白", "奶白", "月光"), {"element": "metal", "secondary": ["water"], "color": "#dfe4e4", "shine": "#ffffff", "family": "white", "effects": ["净化与放大"], "wish": ["focus", "calm"], "chakra": ["crown"], "mood": ["clarity"], "visual": ["icy", "transparent"]}),
        (("蓝", "海蓝", "堇青", "托帕", "青金", "磷灰", "鹰眼"), {"element": "water", "secondary": ["metal"], "color": "#6f9eb8", "shine": "#e9f8ff", "family": "blue", "effects": ["沟通与平静"], "wish": ["communication", "calm"], "chakra": ["throat"], "mood": ["calming", "clarity"], "visual": ["icy", "transparent"]}),
        (("绿", "葡萄", "孔雀", "岫玉", "药王"), {"element": "wood", "secondary": ["water"], "color": "#6b9f78", "shine": "#e5f4e8", "family": "green", "effects": ["生长与复原"], "wish": ["health", "career"], "chakra": ["heart"], "mood": ["calming", "softness"], "visual": ["soft_color", "texture"]}),
        (("粉", "草莓", "摩根"), {"element": "fire", "secondary": ["wood"], "color": "#d98d96", "shine": "#fff0f2", "family": "pink", "effects": ["亲密与吸引"], "wish": ["love", "relationship"], "chakra": ["heart"], "mood": ["softness", "companionship"], "visual": ["soft_color", "sparkling"]}),
        (("红", "南红", "石榴", "胶花", "橙"), {"element": "fire", "secondary": ["earth"], "color": "#b85d57", "shine": "#ffe3df", "family": "red", "effects": ["活力与自信"], "wish": ["love", "career"], "chakra": ["root", "sacral"], "mood": ["vitality", "confidence"], "visual": ["warm", "texture"]}),
        (("紫", "超七", "紫晶"), {"element": "fire", "secondary": ["water"], "color": "#8b70a8", "shine": "#f1e8ff", "family": "purple", "effects": ["灵感与觉察"], "wish": ["inspiration", "sleep"], "chakra": ["third_eye", "crown"], "mood": ["clarity"], "visual": ["soft_color", "sparkling"]}),
        (("黄", "金", "钛晶", "虎眼", "太阳"), {"element": "earth", "secondary": ["fire"], "color": "#c89b4b", "shine": "#fff0b8", "family": "gold", "effects": ["财富与行动"], "wish": ["wealth", "career"], "chakra": ["solar_plexus"], "mood": ["confidence", "vitality"], "visual": ["warm", "sparkling"]}),
        (("黑", "墨", "茶", "曜", "耀", "骨干", "闪灵"), {"element": "water", "secondary": ["metal"], "color": "#323238", "shine": "#c7ccd0", "family": "black", "effects": ["守护与稳定"], "wish": ["protection", "calm"], "chakra": ["root"], "mood": ["boundary", "calming"], "visual": ["dark", "texture"]}),
        (("发晶", "兔毛"), {"element": "metal", "secondary": ["fire"], "color": "#9a8062", "shine": "#fff2d7", "family": "gold", "effects": ["决断与聚焦"], "wish": ["career", "focus"], "chakra": ["solar_plexus"], "mood": ["confidence", "focus"], "visual": ["sparkling", "texture"]}),
        (("玛瑙", "玉石", "碧玺", "彼得"), {"element": "earth", "secondary": ["fire"], "color": "#9b7d68", "shine": "#fff1df", "family": "brown", "effects": ["平衡与守护"], "wish": ["protection", "health"], "chakra": ["root"], "mood": ["boundary", "calming"], "visual": ["texture", "warm"]}),
    ]
    for keywords, profile in rules:
        if any(keyword in text for keyword in keywords):
            return normalize_profile(profile, top)
    return normalize_profile(
        {"element": "earth", "secondary": ["metal"], "color": "#9f8d7a", "shine": "#fff5e8", "family": "brown", "effects": ["平衡与守护"], "wish": ["calm", "protection"], "chakra": ["root"], "mood": ["calming"], "visual": ["texture"]},
        top,
    )


def normalize_profile(profile: dict[str, Any], top: str) -> dict[str, Any]:
    if top == "accessory":
        profile = {
            **profile,
            "effects": ["结构与点睛"],
            "wish": list(dict.fromkeys([*profile.get("wish", []), "focus"])),
            "roles": ["spacer", "accent"],
            "match_rules": ["spacer_only", "pair_symmetry"],
        }
    else:
        profile = {
            **profile,
            "roles": ["primary", "support", "accent"],
            "match_rules": ["no_limit"],
        }
    return profile


def material_code_for(top: str, category: str, series: str) -> str:
    digest = hashlib.sha1(f"{top}|{category}|{series}".encode("utf-8")).hexdigest()[:16]
    return f"mat_{digest}"


def make_sku(top: str, code: str, category: str, series: str, grade: str, size: int, used: set[str]) -> str:
    digest = hashlib.sha1(f"{top}|{code}|{category}|{series}|{grade}".encode("utf-8")).hexdigest()
    material_no = int(digest[:10], 16) % 10_000_000
    size_code = max(0, min(999, int(round(size * 10))))
    check_digit = int(digest[-2:], 16) % 10
    base = f"{TOP_CODE.get(top, '90')}{material_no:07d}{size_code:03d}{check_digit}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}{suffix:02d}"
        suffix += 1
    used.add(candidate)
    return candidate


def size_token(size: int | float) -> str:
    value = float(size)
    return f"{int(value)}mm" if value.is_integer() else f"{str(value).replace('.', 'p')}mm"


def build_records(source_rows: list[SourceRow]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    materials: list[dict[str, Any]] = []
    knowledge_by_code: dict[str, dict[str, Any]] = {}
    used_skus: set[str] = set()
    accessory_mode = False
    sort_order = 0

    for row in source_rows:
        top, category, shape_key = classify_row(row, accessory_mode)
        if row.category == "彼得石":
            accessory_mode = True
        sizes = BEAD_SIZES if top == "bead" else ACCESSORY_SIZES_BY_SHAPE.get(category, (8, 10, 12))
        base_code = material_code_for(top, category, row.series)
        profile = profile_for(category, row.series, top)
        shape_params = SHAPE_PARAMS.get(shape_key, SHAPE_PARAMS["随型"])
        material_params = {
            **shape_params,
            "transparency_level": "semi_transparent",
            "texture_features": infer_texture_features(category, row.series, shape_key),
            "batch_variation": "high",
            "hole_diameter_mm": 1.0,
            "size_tolerance_mm": 0.3,
        }
        if base_code not in knowledge_by_code:
            knowledge_by_code[base_code] = {
                "material_code": base_code,
                "name": row.series,
                "knowledge_name": row.series,
                "top": top,
                "category": category,
                "series": row.series,
                "primary_element": profile["element"],
                "secondary_elements": profile.get("secondary", []),
                "effects": profile["effects"],
                "wish_pools": profile["wish"],
                "chakras": profile.get("chakra", []),
                "color_family": profile["family"],
                "mood_tags": profile.get("mood", []),
                "visual_tags": profile.get("visual", []),
                "allowed_roles": profile["roles"],
                "match_rules": profile["match_rules"],
                "care_tags": ["clean_regularly", "storage_separate"],
                "material_params": material_params,
                "story": f"{row.series}用于{'圆珠主材与配珠' if top == 'bead' else '配饰点睛与结构搭配'}，后续可在运营后台补充产地、品级与实拍说明。",
            }
        for grade_index, grade in enumerate(GRADE_VARIANTS):
            display_series = f"{grade['prefix']}{row.series}"
            for size in sizes:
                sort_order += 10
                sku_id = make_sku(top, base_code, category, row.series, grade["grade"], size, used_skus)
                material_id = f"mat_{sku_id}"
                price = round(0.01 * float(grade["price_multiplier"]), 2)
                weight = estimate_weight(size, top, shape_key)
                materials.append(
                    {
                        "id": material_id,
                        "skuId": sku_id,
                        "top": top,
                        "category": category,
                        "series": display_series,
                        "material_code": base_code,
                        "grade": grade["grade"],
                        "name": display_series,
                        "effect": profile["effects"][0],
                        "element": ELEMENT_LABEL[profile["element"]],
                        "price": price,
                        "size": float(size),
                        "weight": weight,
                        "cost_price": round(price * 0.45, 2),
                        "safety_stock": 10,
                        "supplier_name": "",
                        "purchase_note": "",
                        "color": profile["color"],
                        "shine": profile["shine"],
                        "image_path": "",
                        "image_url": "",
                        "image_urls_json": "[]",
                        "stock": int(grade["stock"]),
                        "enabled": 1,
                        "sort_order": sort_order + grade_index,
                        "knowledge": knowledge_by_code[base_code],
                    }
                )
    return materials, knowledge_by_code


def infer_texture_features(category: str, series: str, shape_key: str) -> list[str]:
    text = f"{category}{series}{shape_key}"
    features: list[str] = []
    if any(keyword in text for keyword in ("发晶", "兔毛")):
        features.append("rutile")
    if "幽灵" in text:
        features.append("phantom")
    if "猫眼" in text:
        features.append("cat_eye")
    if any(keyword in text for keyword in ("彩", "虎眼", "玛瑙")):
        features.append("color_band")
    if shape_key != "bead":
        features.append("mineral_inclusion")
    return features or ["mineral_inclusion"]


def estimate_weight(size: int | float, top: str, shape_key: str) -> float:
    size = float(size)
    base = 1.2 * (size / 8) ** 3
    if top == "accessory":
        if shape_key == "三角牌":
            base *= 0.65
        elif shape_key == "圆桶型":
            base *= 0.85
        else:
            base *= 0.75
    return round(base, 2)


def table_exists(connection: Any, table_name: str) -> bool:
    try:
        connection.execute(f"SELECT 1 FROM {table_name} LIMIT 1").fetchone()
        return True
    except Exception:
        return False


def write_records(materials: list[dict[str, Any]], knowledge_by_code: dict[str, dict[str, Any]], apply: bool) -> dict[str, Any]:
    service = AdminService()
    if not apply:
        return summarize(service, materials, knowledge_by_code, dry_run=True)

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with service.connect() as connection:
        before = {
            "managed_materials": count_rows(connection, "managed_materials"),
            "material_knowledge": count_rows(connection, "material_knowledge"),
            "material_taxonomy": count_rows(connection, "material_taxonomy"),
        }
        connection.execute("DELETE FROM managed_materials")
        if table_exists(connection, "material_knowledge"):
            connection.execute("DELETE FROM material_knowledge")
        if table_exists(connection, "material_taxonomy"):
            connection.execute("DELETE FROM material_taxonomy")
        if table_exists(connection, "material_audit_logs"):
            connection.execute(
                "DELETE FROM material_audit_logs WHERE target_type IN ('material', 'material_taxonomy')"
            )

        for item in materials:
            connection.execute(
                """
                INSERT INTO managed_materials
                (id, skuId, top, category, series, material_code, grade, name, effect, element, price, size, weight,
                 cost_price, safety_stock, supplier_name, purchase_note, color, shine, image_path, image_url,
                 image_urls_json, stock, enabled, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    item["skuId"],
                    item["top"],
                    item["category"],
                    item["series"],
                    item["material_code"],
                    item["grade"],
                    item["name"],
                    item["effect"],
                    item["element"],
                    item["price"],
                    item["size"],
                    item["weight"],
                    item["cost_price"],
                    item["safety_stock"],
                    item["supplier_name"],
                    item["purchase_note"],
                    item["color"],
                    item["shine"],
                    item["image_path"],
                    item["image_url"],
                    item["image_urls_json"],
                    item["stock"],
                    item["enabled"],
                    item["sort_order"],
                    timestamp,
                    timestamp,
                ),
            )
        for knowledge in knowledge_by_code.values():
            insert_material_knowledge(connection, knowledge, timestamp)
        service._sync_material_taxonomy_from_materials(connection)
        after = {
            "managed_materials": count_rows(connection, "managed_materials"),
            "material_knowledge": count_rows(connection, "material_knowledge"),
            "material_taxonomy": count_rows(connection, "material_taxonomy"),
        }
        by_top = count_by(connection, "managed_materials", "top")
        category_by_top = count_distinct_by(connection, "managed_materials", "top", "category")
        incense_count = connection.execute(
            "SELECT COUNT(*) AS c FROM managed_materials WHERE top = 'incense'"
        ).fetchone()["c"]
    invalidate_material_cache()
    summary = summarize(service, materials, knowledge_by_code, dry_run=False)
    summary.update(
        {
            "before": before,
            "after": after,
            "by_top": by_top,
            "category_by_top": category_by_top,
            "incense_count": int(incense_count or 0),
        }
    )
    return summary


def count_rows(connection: Any, table_name: str) -> int:
    if not table_exists(connection, table_name):
        return 0
    return int(connection.execute(f"SELECT COUNT(*) AS c FROM {table_name}").fetchone()["c"] or 0)


def insert_material_knowledge(connection: Any, knowledge: dict[str, Any], timestamp: str) -> None:
    item = knowledge_to_db_item(
        {
            **knowledge,
            "code": knowledge["material_code"],
        }
    )
    connection.execute(
        """
        INSERT INTO material_knowledge
        (code, name, primary_element, secondary_elements_json, chakras_json, chakra_weights_json,
         effects_json, wish_pools_json, color_family, mood_tags_json, visual_tags_json, story,
         allowed_roles_json, conflict_codes_json, match_rules_json, care_tags_json,
         material_params_json, asset_json, enabled, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item["code"],
            item["name"],
            item["primary_element"],
            item["secondary_elements_json"],
            item["chakras_json"],
            item["chakra_weights_json"],
            item["effects_json"],
            item["wish_pools_json"],
            item["color_family"],
            item["mood_tags_json"],
            item["visual_tags_json"],
            item["story"],
            item["allowed_roles_json"],
            item["conflict_codes_json"],
            item["match_rules_json"],
            item["care_tags_json"],
            item["material_params_json"],
            item["asset_json"],
            item["enabled"],
            timestamp,
            timestamp,
        ),
    )


def count_by(connection: Any, table_name: str, field: str) -> dict[str, int]:
    rows = connection.execute(
        f"SELECT {field} AS k, COUNT(*) AS c FROM {table_name} GROUP BY {field} ORDER BY {field}"
    ).fetchall()
    return {str(row["k"]): int(row["c"] or 0) for row in rows}


def count_distinct_by(connection: Any, table_name: str, field: str, distinct_field: str) -> dict[str, int]:
    rows = connection.execute(
        f"SELECT {field} AS k, COUNT(DISTINCT {distinct_field}) AS c FROM {table_name} GROUP BY {field} ORDER BY {field}"
    ).fetchall()
    return {str(row["k"]): int(row["c"] or 0) for row in rows}


def summarize(service: AdminService, materials: list[dict[str, Any]], knowledge_by_code: dict[str, dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    series_keys = {
        (item["top"], item["category"], item["series"], item["grade"])
        for item in materials
    }
    return {
        "dry_run": dry_run,
        "material_rows": len(materials),
        "knowledge_rows": len(knowledge_by_code),
        "spu_variants": len(series_keys),
        "by_top_planned": count_items(materials, "top"),
        "categories_planned": {
            top: len({item["category"] for item in materials if item["top"] == top})
            for top in sorted({item["top"] for item in materials})
        },
        "sample": [
            {key: item[key] for key in ("top", "category", "series", "grade", "size", "price")}
            for item in materials[:8]
        ],
    }


def count_items(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in items:
        result[str(item.get(key) or "")] = result.get(str(item.get(key) or ""), 0) + 1
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Import crystal material categories from a two-column XLSX file.")
    parser.add_argument("--xlsx", type=Path, required=True, help="Excel file with 一级分类/二级分类 columns.")
    parser.add_argument("--apply", action="store_true", help="Clear and rewrite material tables.")
    parser.add_argument("--summary-json", type=Path, help="Optional path to write the import summary JSON.")
    args = parser.parse_args()

    rows = read_xlsx_rows(args.xlsx)
    materials, knowledge_by_code = build_records(rows)
    summary = write_records(materials, knowledge_by_code, apply=args.apply)
    summary["source_rows"] = len(rows)
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(text)
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
