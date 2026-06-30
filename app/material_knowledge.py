from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from .database import connect_database
from .fortune.crystal_taxonomy import taxonomy_for
from .material_options import (
    normalize_chakra_list,
    normalize_care_tag_list,
    normalize_color_family,
    normalize_element_key,
    normalize_element_list,
    normalize_match_rule_list,
    normalize_material_params,
    normalize_mood_tag_list,
    normalize_role_list,
    normalize_visual_tag_list,
    normalize_wish_pool_list,
)


JSON_LIST_FIELDS = {
    "secondary_elements": "secondary_elements_json",
    "chakras": "chakras_json",
    "effects": "effects_json",
    "wish_pools": "wish_pools_json",
    "mood_tags": "mood_tags_json",
    "visual_tags": "visual_tags_json",
    "allowed_roles": "allowed_roles_json",
    "conflict_codes": "conflict_codes_json",
    "match_rules": "match_rules_json",
    "care_tags": "care_tags_json",
}

JSON_DICT_FIELDS = {
    "chakra_weights": "chakra_weights_json",
    "material_params": "material_params_json",
    "asset": "asset_json",
}


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def json_text(value: Any, default: Any = None) -> str:
    if value is None:
        value = [] if default is None else default
    return json.dumps(value, ensure_ascii=False)


def json_value(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return [] if default is None else default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [] if default is None else default


def unique_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        if value.strip().startswith("["):
            value = json_value(value, [])
        else:
            value = re.split(r"[,，、\n\r]+", value)
    if not isinstance(value, list):
        value = [value]
    result: list[Any] = []
    seen: set[str] = set()
    for item in value:
        if item in (None, ""):
            continue
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(item if isinstance(item, dict) else normalized)
    return result


def clean_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json_value(value, {})
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items() if item not in (None, "")}


def camel_to_kebab(value: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"-\1", value).lower()


CRYSTAL_CODE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("titanium_quartz", ("钛晶发", "钛晶")),
    ("gold_rutilated_quartz", ("维纳斯金发晶", "金发晶")),
    ("silver_rutilated_quartz", ("银发晶",)),
    ("black_rutilated_quartz", ("黑发晶",)),
    ("red_rutilated_quartz", ("红铜发晶", "铜发晶")),
    ("green_rutilated_quartz", ("绿发猫眼", "绿钢丝发", "绿发晶")),
    ("blue_rutilated_quartz", ("蓝发晶",)),
    ("rabbit_hair_quartz", ("兔毛水晶", "兔毛", "钢丝")),
    ("white_phantom", ("白幽灵", "雪花白幽灵")),
    ("green_phantom", ("绿幽灵",)),
    ("red_phantom", ("红幽灵",)),
    ("yellow_phantom", ("黄幽灵",)),
    ("pink_phantom", ("粉幽灵",)),
    ("purple_phantom", ("紫幽灵",)),
    ("four_seasons_phantom", ("四季幽灵",)),
    ("colorful_phantom", ("彩幽灵", "幽灵水晶各种形态", "幽灵水晶")),
    ("rose_quartz", ("马达加斯加粉晶", "莫桑比亚粉水晶", "粉水晶马粉", "粉水晶", "粉水品种", "粉晶")),
    ("strawberry_quartz", ("草莓晶", "红草莓晶", "金草莓晶", "白水草莓晶", "车厘子草莓晶")),
    ("rhodochrosite", ("红纹石",)),
    ("flower_agate", ("樱花玛瑙",)),
    ("south_red_agate", ("南红玛瑙", "南虹玛瑙")),
    ("salt_source_agate", ("盐源玛瑙",)),
    ("alashan_agate", ("阿拉善玛瑙", "阿拉善")),
    ("banded_agate", ("条纹玛瑙", "缠丝玛瑙")),
    ("black_agate", ("黑玛瑙",)),
    ("blue_lace_agate", ("蓝纹玛瑙",)),
    ("red_agate", ("红玛瑙",)),
    ("quartz_inclusion", ("胶花水晶", "胶花", "锦鲤胶花")),
    ("clear_quartz", ("喜马拉雅白水晶", "白水晶", "白阿塞水晶")),
    ("milky_quartz", ("奶白晶",)),
    ("citrine", ("柠檬黄水晶", "巴西黄水晶", "黄水晶", "黄阿塞水晶")),
    ("ametrine", ("紫黄晶",)),
    ("amethyst", ("玻利维亚紫水晶", "薰衣草紫水晶", "紫水晶")),
    ("lepidolite", ("紫锂辉",)),
    ("garnet", ("紫牙乌石榴石", "红石榴石", "石榴石")),
    ("moonstone", ("白月光石", "灰月光", "月光石")),
    ("labradorite", ("拉长石",)),
    ("aquamarine", ("海蓝宝",)),
    ("larimar", ("海纹石",)),
    ("amazonite", ("天河石",)),
    ("blue_topaz", ("蓝托帕石",)),
    ("kyanite", ("玉化蓝晶石", "蓝晶石")),
    ("iolite", ("堇青石",)),
    ("lapis_lazuli", ("青金石",)),
    ("blue_fluorite", ("拉丝蓝萤石",)),
    ("yellow_fluorite", ("拉丝黄萤石",)),
    ("purple_fluorite", ("紫拉丝萤石",)),
    ("fluorite", ("彩萤石", "拉丝萤石", "萤石")),
    ("prehnite", ("葡萄石",)),
    ("tourmaline", ("碧玺",)),
    ("blue_tiger_eye", ("蓝虎眼石", "鹰眼石")),
    ("tiger_eye", ("金虎眼石", "黄虎眼石", "虎眼石")),
    ("golden_obsidian", ("金曜石",)),
    ("silver_obsidian", ("银曜石",)),
    ("obsidian", ("毒液黑超七", "彩耀石", "黑曜石", "陨石曜", "曜石")),
    ("smoky_quartz", ("茶晶",)),
)


def infer_material_code_from_text(payload: dict[str, Any]) -> str:
    text = " ".join(
        str(payload.get(key) or "")
        for key in (
            "series",
            "name",
            "category",
            "effect",
            "image_path",
            "image_url",
            "thumbnail_url",
        )
    ).lower()
    if not text.strip():
        return ""
    for code, keywords in CRYSTAL_CODE_KEYWORDS:
        if any(keyword.lower() in text for keyword in keywords):
            return code
    return ""


def material_code_token(value: Any) -> str:
    text = camel_to_kebab(str(value or "").strip())
    text = re.sub(r"\.(png|jpg|jpeg|webp|gif)$", "", text, flags=re.I)
    text = re.sub(r"[_\s]+", "-", text)
    text = re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")
    text = re.sub(r"(^|-)materials?(-|$)", "-", text)
    text = re.sub(r"(^|-)beads?(-|$)", "-", text)
    text = re.sub(r"(^|-)sku(-|$)", "-", text)
    text = re.sub(r"(^|-)mat(-|$)", "-", text)
    text = re.sub(r"[-_]*\d+(?:p\d+)?mm$", "", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text.replace("-", "_")


def material_code_from_payload(payload: dict[str, Any]) -> str:
    inferred = infer_material_code_from_text(payload)
    for key in ("material_code", "code"):
        token = material_code_token(payload.get(key))
        if token:
            # 后台编辑时 material_code 是历史只读字段，分类/品种才是当前事实来源。
            # 如果运营把品种从 A 改为 B，必须优先使用文本重新推断出的编码，
            # 否则旧编码会继续把 SKU 聚合到错误 SPU 下。
            if inferred and inferred != token:
                return inferred
            return token
    if inferred:
        return inferred
    for key in ("skuId", "sku_id", "id"):
        token = material_code_token(payload.get(key))
        if token:
            return token
    digest_source = f"{payload.get('top', '')}:{payload.get('category', '')}:{payload.get('name', '')}"
    return material_code_token(digest_source) or "material"


def list_from_payload(payload: dict[str, Any], key: str, *aliases: str) -> list[Any]:
    for candidate in (key, *aliases):
        if candidate in payload:
            return unique_list(payload.get(candidate))
    return []


def dict_from_payload(payload: dict[str, Any], key: str, *aliases: str) -> dict[str, Any]:
    for candidate in (key, *aliases):
        if candidate in payload:
            return clean_dict(payload.get(candidate))
    return {}


def normalize_knowledge_payload(payload: dict[str, Any], material: dict[str, Any] | None = None) -> dict[str, Any]:
    material = material or {}
    nested = clean_dict(payload.get("knowledge") or payload.get("material_knowledge"))
    source = {**nested, **payload}
    code = material_code_from_payload({**material, **source})
    taxonomy = taxonomy_for(code)
    taxonomy_elements = normalize_element_list(taxonomy.get("elements"))
    primary_element = normalize_element_key(
        source.get("primary_element")
        or source.get("element")
        or material.get("primary_element")
        or material.get("element")
        or (taxonomy_elements[0] if taxonomy_elements else "")
    )
    secondary_elements = normalize_element_list(list_from_payload(source, "secondary_elements", "secondary_element"))
    if not secondary_elements:
        secondary_elements = [item for item in taxonomy_elements if item != primary_element]
    effects = list_from_payload(source, "effects", "effect_tags")
    if not effects and source.get("effect") and source.get("_legacy_effect_is_structured", True):
        effects = unique_list(source.get("effect"))
    if not effects and material.get("effect"):
        effects = unique_list(material.get("effect"))
    if not effects:
        effects = unique_list(taxonomy.get("effects"))
    chakras = normalize_chakra_list(list_from_payload(source, "chakras", "chakra"))
    if not chakras:
        chakras = normalize_chakra_list(taxonomy.get("chakras"))
    wish_pools = normalize_wish_pool_list(list_from_payload(source, "wish_pools", "wish_tags"))
    if not wish_pools:
        wish_pools = normalize_wish_pool_list(taxonomy.get("wish_tags"))
    mood_tags = normalize_mood_tag_list(list_from_payload(source, "mood_tags"))
    if not mood_tags:
        mood_tags = normalize_mood_tag_list(taxonomy.get("mood_tags"))
    visual_tags = normalize_visual_tag_list(list_from_payload(source, "visual_tags"))
    if not visual_tags:
        visual_tags = normalize_visual_tag_list(taxonomy.get("visual_tags"))
    allowed_roles = normalize_role_list(list_from_payload(source, "allowed_roles", "roles"))
    if not allowed_roles:
        allowed_roles = normalize_role_list(taxonomy.get("allowed_roles") or taxonomy.get("roles"))
    if not allowed_roles:
        top = str(material.get("top") or source.get("top") or "bead")
        allowed_roles = ["spacer", "accent"] if top in {"accessory", "pendant"} else ["primary", "support", "accent"]
    match_rules = normalize_match_rule_list(list_from_payload(source, "match_rules", "rule_tags", "rules_tags"))
    if not match_rules:
        match_rules = normalize_match_rule_list(taxonomy.get("match_rules"))
    if not match_rules:
        match_rules = ["spacer_only"] if str(material.get("top") or source.get("top") or "") in {"accessory", "pendant"} else ["no_limit"]
    care_tags = normalize_care_tag_list(list_from_payload(source, "care_tags", "care_rules"))
    if not care_tags:
        care_tags = normalize_care_tag_list(taxonomy.get("care_tags"))
    asset = {**clean_dict(taxonomy.get("asset")), **dict_from_payload(source, "asset", "assets")}
    for source_key, asset_key in {
        "thumbnail_url": "thumbnail_url",
        "diffuse_map_url": "diffuse_map_url",
        "normal_map_url": "normal_map_url",
        "glb_model_url": "glb_model_url",
        "preview_render_url": "preview_render_url",
    }.items():
        if source.get(source_key):
            asset[asset_key] = source[source_key]
    material_params = {**clean_dict(taxonomy.get("material_params")), **dict_from_payload(source, "material_params")}
    for key in (
        "bead_shape",
        "surface_finish",
        "transparency_level",
        "texture_features",
        "batch_variation",
        "hole_diameter_mm",
        "size_tolerance_mm",
    ):
        if source.get(key) not in (None, ""):
            material_params[key] = source.get(key)
    material_params = normalize_material_params(material_params)
    return {
        "code": code,
        "name": str(source.get("knowledge_name") or source.get("name") or material.get("series") or material.get("name") or code).strip(),
        "primary_element": primary_element,
        "secondary_elements": secondary_elements,
        "chakras": chakras,
        "chakra_weights": dict_from_payload(source, "chakra_weights"),
        "effects": effects,
        "wish_pools": wish_pools,
        "color_family": str(
            source.get("color_family")
            or (taxonomy.get("color_families") or [""])[0]
            or ""
        ).strip(),
        "mood_tags": mood_tags,
        "visual_tags": visual_tags,
        "story": str(source.get("story") or taxonomy.get("story") or "").strip(),
        "allowed_roles": allowed_roles,
        "conflict_codes": list_from_payload(source, "conflict_codes"),
        "match_rules": match_rules,
        "care_tags": care_tags,
        "material_params": material_params,
        "asset": asset,
        "enabled": bool(source.get("knowledge_enabled", source.get("enabled", True))),
    }


def has_explicit_knowledge(payload: dict[str, Any]) -> bool:
    keys = {
        "knowledge",
        "material_knowledge",
        "primary_element",
        "secondary_elements",
        "chakras",
        "chakra",
        "chakra_weights",
        "effects",
        "effect_tags",
        "wish_pools",
        "wish_tags",
        "color_family",
        "mood_tags",
        "visual_tags",
        "story",
        "allowed_roles",
        "roles",
        "conflict_codes",
        "match_rules",
        "rule_tags",
        "care_tags",
        "care_rules",
        "material_params",
        "bead_shape",
        "surface_finish",
        "transparency_level",
        "texture_features",
        "batch_variation",
        "hole_diameter_mm",
        "size_tolerance_mm",
        "asset",
        "assets",
        "thumbnail_url",
        "diffuse_map_url",
        "normal_map_url",
        "glb_model_url",
        "preview_render_url",
    }
    return any(key in payload and payload.get(key) not in (None, "", [], {}) for key in keys)


def public_knowledge(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    result = {
        "code": row.get("code") or "",
        "name": row.get("name") or "",
        "primary_element": normalize_element_key(row.get("primary_element")) or "",
        "color_family": row.get("color_family") or "",
        "story": row.get("story") or "",
        "enabled": bool(row.get("enabled", 1)),
    }
    for public_key, column in JSON_LIST_FIELDS.items():
        result[public_key] = unique_list(json_value(row.get(column), []))
    for public_key, column in JSON_DICT_FIELDS.items():
        result[public_key] = clean_dict(json_value(row.get(column), {}))
    result["secondary_elements"] = normalize_element_list(result.get("secondary_elements"))
    result["chakras"] = normalize_chakra_list(result.get("chakras"))
    result["wish_pools"] = normalize_wish_pool_list(result.get("wish_pools"))
    result["mood_tags"] = normalize_mood_tag_list(result.get("mood_tags"))
    result["visual_tags"] = normalize_visual_tag_list(result.get("visual_tags"))
    result["allowed_roles"] = normalize_role_list(result.get("allowed_roles"))
    result["match_rules"] = normalize_match_rule_list(result.get("match_rules"))
    result["care_tags"] = normalize_care_tag_list(result.get("care_tags"))
    result["color_family"] = normalize_color_family(result.get("color_family")) or ""
    result["material_params"] = normalize_material_params(result.get("material_params"))
    return result


def knowledge_to_db_item(knowledge: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing_public = public_knowledge(existing) if existing else {}
    merged = {**existing_public, **knowledge}
    return {
        "code": merged["code"],
        "name": merged.get("name") or merged["code"],
        "primary_element": normalize_element_key(merged.get("primary_element")) or "",
        "secondary_elements_json": json_text(normalize_element_list(merged.get("secondary_elements"))),
        "chakras_json": json_text(normalize_chakra_list(merged.get("chakras"))),
        "chakra_weights_json": json_text(clean_dict(merged.get("chakra_weights")), {}),
        "effects_json": json_text(unique_list(merged.get("effects"))),
        "wish_pools_json": json_text(normalize_wish_pool_list(merged.get("wish_pools"))),
        "color_family": normalize_color_family(merged.get("color_family")) or "",
        "mood_tags_json": json_text(normalize_mood_tag_list(merged.get("mood_tags"))),
        "visual_tags_json": json_text(normalize_visual_tag_list(merged.get("visual_tags"))),
        "story": merged.get("story") or "",
        "allowed_roles_json": json_text(normalize_role_list(merged.get("allowed_roles")) or ["primary", "support", "accent"]),
        "conflict_codes_json": json_text(unique_list(merged.get("conflict_codes"))),
        "match_rules_json": json_text(normalize_match_rule_list(merged.get("match_rules")) or ["no_limit"]),
        "care_tags_json": json_text(normalize_care_tag_list(merged.get("care_tags"))),
        "material_params_json": json_text(clean_dict(merged.get("material_params")), {}),
        "asset_json": json_text(clean_dict(merged.get("asset")), {}),
        "enabled": 1 if merged.get("enabled", True) else 0,
    }


def table_exists(connection: Any, table_name: str) -> bool:
    try:
        row = connection.execute("SELECT 1 FROM " + table_name + " LIMIT 1").fetchone()
        return row is not None or row is None
    except Exception:
        return False


def fetch_knowledge_map(codes: list[str], connection: Any | None = None) -> dict[str, dict[str, Any]]:
    clean_codes = [code for code in dict.fromkeys(codes) if code]
    if not clean_codes:
        return {}

    def run(conn: Any) -> dict[str, dict[str, Any]]:
        if not table_exists(conn, "material_knowledge"):
            return {}
        placeholders = ", ".join(["?"] * len(clean_codes))
        rows = conn.execute(
            f"SELECT * FROM material_knowledge WHERE enabled = 1 AND code IN ({placeholders})",
            clean_codes,
        ).fetchall()
        return {row["code"]: public_knowledge(dict(row)) for row in rows}

    if connection is not None:
        return run(connection)
    try:
        with connect_database() as conn:
            return run(conn)
    except Exception:
        return {}


def fetch_size_map(codes: list[str], connection: Any | None = None) -> dict[str, list[float]]:
    clean_codes = [code for code in dict.fromkeys(codes) if code]
    if not clean_codes:
        return {}

    def run(conn: Any) -> dict[str, list[float]]:
        placeholders = ", ".join(["?"] * len(clean_codes))
        rows = conn.execute(
            f"""
            SELECT material_code, size
            FROM managed_materials
            WHERE enabled = 1 AND material_code IN ({placeholders})
            """,
            clean_codes,
        ).fetchall()
        result: dict[str, set[float]] = {}
        for row in rows:
            code = row["material_code"]
            if not code:
                continue
            result.setdefault(code, set()).add(float(row["size"] or 0))
        return {code: sorted(value for value in sizes if value > 0) for code, sizes in result.items()}

    if connection is not None:
        try:
            return run(connection)
        except Exception:
            return {}
    try:
        with connect_database() as conn:
            return run(conn)
    except Exception:
        return {}


def fallback_knowledge_for_material(material: dict[str, Any]) -> dict[str, Any]:
    return normalize_knowledge_payload(material, material)


def enrich_materials_with_knowledge(
    materials: list[dict[str, Any]],
    connection: Any | None = None,
) -> list[dict[str, Any]]:
    codes = []
    normalized = []
    for material in materials:
        item = dict(material)
        code = item.get("material_code") or material_code_from_payload(item)
        item["material_code"] = code
        codes.append(code)
        normalized.append(item)
    knowledge_map = fetch_knowledge_map(codes, connection)
    size_map = fetch_size_map(codes, connection)
    enriched = []
    for item in normalized:
        code = item["material_code"]
        knowledge = knowledge_map.get(code) or fallback_knowledge_for_material(item)
        asset = clean_dict(knowledge.get("asset"))
        thumbnail_url = asset.get("thumbnail_url") or item.get("image_url") or ""
        material_params = clean_dict(knowledge.get("material_params"))
        sizes = size_map.get(code) or unique_list([item.get("size")])
        energy = {
            "primary_element": normalize_element_key(knowledge.get("primary_element") or item.get("element")) or "",
            "secondary_elements": normalize_element_list(knowledge.get("secondary_elements")),
            "chakras": normalize_chakra_list(knowledge.get("chakras")),
            "chakra_weights": clean_dict(knowledge.get("chakra_weights")),
            "effects": unique_list(knowledge.get("effects")) or unique_list(item.get("effect")),
            "wish_pools": normalize_wish_pool_list(knowledge.get("wish_pools")),
            "color_family": normalize_color_family(knowledge.get("color_family")) or "",
            "mood_tags": normalize_mood_tag_list(knowledge.get("mood_tags")),
            "visual_tags": normalize_visual_tag_list(knowledge.get("visual_tags")),
        }
        visual = {
            "color_hex": item.get("color") or "",
            "shine_hex": item.get("shine") or "",
            "thumbnail_url": thumbnail_url,
            "image_url": item.get("image_url") or "",
            "image_urls": unique_list(item.get("image_urls") or item.get("image_pool")),
            "asset": {
                **asset,
                "thumbnail_url": thumbnail_url,
            },
            "material_params": material_params,
        }
        rules = {
            "allowed_roles": normalize_role_list(knowledge.get("allowed_roles")),
            "conflict_codes": unique_list(knowledge.get("conflict_codes")),
            "match_rules": normalize_match_rule_list(knowledge.get("match_rules")),
            "care_tags": normalize_care_tag_list(knowledge.get("care_tags")),
        }
        sku = {
            "id": item.get("id") or "",
            "sku_id": item.get("sku_id") or item.get("skuId") or "",
            "material_code": code,
            "top": item.get("top") or "",
            "category": item.get("category") or "",
            "series": item.get("series") or item.get("name") or "",
            "grade": item.get("grade") or "",
            "name": item.get("name") or knowledge.get("name") or "",
            "price_per_bead": float(item.get("price") or item.get("price_per_bead") or 0),
            "size_mm": float(item.get("size") or item.get("size_mm") or 0),
            "weight_g": float(item.get("weight") or item.get("weight_g") or 0),
            "stock": int(float(item.get("stock") or 0)),
            "enabled": bool(item.get("enabled", 1)),
            "sort_order": int(float(item.get("sort_order") or item.get("sortOrder") or 0)),
            "available_sizes_mm": sizes,
        }
        enriched.append(
            {
                **item,
                "material_code": code,
                "sku": sku,
                "energy": energy,
                "visual": visual,
                "rules": rules,
                "primary_element": energy["primary_element"],
                "secondary_elements": energy["secondary_elements"],
                "chakras": energy["chakras"],
                "chakra_weights": energy["chakra_weights"],
                "effects": energy["effects"],
                "wish_pools": energy["wish_pools"],
                "color_family": energy["color_family"],
                "mood_tags": energy["mood_tags"],
                "visual_tags": energy["visual_tags"],
                "story": knowledge.get("story") or "",
                "allowed_roles": rules["allowed_roles"],
                "conflict_codes": rules["conflict_codes"],
                "match_rules": rules["match_rules"],
                "care_tags": rules["care_tags"],
                "available_sizes_mm": sizes,
                "thumbnail_url": thumbnail_url,
                "asset": visual["asset"],
                "material_params": material_params,
                "knowledge": knowledge,
            }
        )
    return enriched


def enrich_material_with_knowledge(material: dict[str, Any], connection: Any | None = None) -> dict[str, Any]:
    return enrich_materials_with_knowledge([material], connection)[0]


def upsert_material_knowledge(
    payload: dict[str, Any],
    material: dict[str, Any] | None = None,
    connection: Any | None = None,
    force_update: bool = False,
) -> dict[str, Any]:
    knowledge = normalize_knowledge_payload(payload, material)
    if not knowledge.get("code"):
        return {}

    def run(conn: Any) -> dict[str, Any]:
        if not table_exists(conn, "material_knowledge"):
            return knowledge
        existing = conn.execute(
            "SELECT * FROM material_knowledge WHERE code = ?",
            (knowledge["code"],),
        ).fetchone()
        if existing and not force_update:
            return public_knowledge(dict(existing))
        item = knowledge_to_db_item(knowledge, dict(existing) if existing else None)
        timestamp = now_iso()
        if existing:
            conn.execute(
                """
                UPDATE material_knowledge SET
                name=?, primary_element=?, secondary_elements_json=?, chakras_json=?, chakra_weights_json=?,
                effects_json=?, wish_pools_json=?, color_family=?, mood_tags_json=?, visual_tags_json=?,
                story=?, allowed_roles_json=?, conflict_codes_json=?, match_rules_json=?, care_tags_json=?,
                material_params_json=?, asset_json=?,
                enabled=?, updated_at=?
                WHERE code=?
                """,
                (
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
                    item["code"],
                ),
            )
        else:
            conn.execute(
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
        return public_knowledge(item)

    if connection is not None:
        return run(connection)
    with connect_database() as conn:
        return run(conn)


def merge_taxonomy(code: str, crystal: dict[str, Any]) -> dict[str, Any]:
    taxonomy = taxonomy_for(code)
    return {
        **taxonomy,
        "elements": unique_list([*unique_list(taxonomy.get("elements")), *unique_list(crystal.get("secondary_elements"))]),
        "chakras": unique_list([*unique_list(taxonomy.get("chakras")), *unique_list(crystal.get("chakras"))]),
        "color_families": unique_list(
            [*unique_list(taxonomy.get("color_families")), *unique_list(crystal.get("color_families"))]
        ),
        "mood_tags": unique_list([*unique_list(taxonomy.get("mood_tags")), *unique_list(crystal.get("mood_tags"))]),
        "wish_tags": unique_list([*unique_list(taxonomy.get("wish_tags")), *unique_list(crystal.get("wish_pools"))]),
        "visual_tags": unique_list(
            [*unique_list(taxonomy.get("visual_tags")), *unique_list(crystal.get("visual_tags"))]
        ),
    }


def crystal_elements(code: str, crystal: dict[str, Any]) -> set[str]:
    taxonomy = merge_taxonomy(code, crystal)
    return {
        crystal.get("element") or crystal.get("primary_element") or "",
        *unique_list(crystal.get("secondary_elements")),
        *unique_list(taxonomy.get("elements")),
    } - {""}


def build_recommendation_catalog(base_catalog: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    catalog = {code: dict(item) for code, item in base_catalog.items()}
    try:
        with connect_database() as connection:
            if not table_exists(connection, "material_knowledge"):
                return catalog
            rows = connection.execute("SELECT * FROM material_knowledge WHERE enabled = 1").fetchall()
    except Exception:
        return catalog
    for row in rows:
        knowledge = public_knowledge(dict(row))
        code = knowledge["code"]
        base = dict(catalog.get(code) or {})
        base.update(
            {
                "name": knowledge.get("name") or base.get("name") or code,
                "element": knowledge.get("primary_element") or base.get("element") or "",
                "secondary_elements": unique_list(
                    knowledge.get("secondary_elements") or base.get("secondary_elements")
                ),
                "color": base.get("color") or "#dfe3e5",
                "effects": unique_list(knowledge.get("effects") or base.get("effects")),
                "chakras": unique_list(knowledge.get("chakras")),
                "color_families": unique_list([knowledge.get("color_family"), *unique_list(base.get("color_families"))]),
                "mood_tags": unique_list(knowledge.get("mood_tags")),
                "visual_tags": unique_list(knowledge.get("visual_tags")),
                "wish_pools": unique_list(knowledge.get("wish_pools")),
                "allowed_roles": unique_list(knowledge.get("allowed_roles")),
                "conflict_codes": unique_list(knowledge.get("conflict_codes")),
                "match_rules": unique_list(knowledge.get("match_rules")),
                "care_tags": unique_list(knowledge.get("care_tags")),
                "story": knowledge.get("story") or base.get("story") or "",
                "material_params": clean_dict(knowledge.get("material_params")),
                "asset": clean_dict(knowledge.get("asset")),
            }
        )
        if base.get("element"):
            catalog[code] = base
    return catalog


def build_primary_pools(
    base_pools: dict[str, list[str]],
    catalog: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    pools = {wish: list(codes) for wish, codes in base_pools.items()}
    for code, crystal in catalog.items():
        for wish in unique_list(crystal.get("wish_pools")):
            pools.setdefault(wish, [])
            if code not in pools[wish]:
                pools[wish].append(code)
    return pools
