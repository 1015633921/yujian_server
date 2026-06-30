from __future__ import annotations

import hashlib
import re
from typing import Any


ELEMENT_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "metal", "label": "金"},
    {"key": "wood", "label": "木"},
    {"key": "water", "label": "水"},
    {"key": "fire", "label": "火"},
    {"key": "earth", "label": "土"},
)

ELEMENT_LABEL_BY_KEY = {item["key"]: item["label"] for item in ELEMENT_OPTIONS}
ELEMENT_KEY_BY_LABEL = {item["label"]: item["key"] for item in ELEMENT_OPTIONS}
ELEMENT_ALIASES = {
    **ELEMENT_KEY_BY_LABEL,
    **{key: key for key in ELEMENT_LABEL_BY_KEY},
    "gold": "metal",
    "jin": "metal",
    "mu": "wood",
    "shui": "water",
    "huo": "fire",
    "tu": "earth",
}

WISH_POOL_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "wealth", "label": "招财"},
    {"key": "career", "label": "事业"},
    {"key": "love", "label": "桃花"},
    {"key": "relationship", "label": "人缘"},
    {"key": "protection", "label": "守护"},
    {"key": "calm", "label": "安定"},
    {"key": "health", "label": "健康"},
    {"key": "focus", "label": "专注"},
    {"key": "communication", "label": "表达沟通"},
    {"key": "study", "label": "学习考试"},
    {"key": "sleep", "label": "睡眠修复"},
    {"key": "emotion", "label": "情绪柔和"},
    {"key": "inspiration", "label": "灵感创作"},
)

WISH_POOL_ALIASES = {
    **{item["key"]: item["key"] for item in WISH_POOL_OPTIONS},
    "招财": "wealth",
    "财运": "wealth",
    "一心搞钱": "wealth",
    "事业": "career",
    "事业运": "career",
    "搞事业": "career",
    "桃花": "love",
    "招桃花": "love",
    "人缘": "relationship",
    "贵人": "relationship",
    "守护": "protection",
    "防小人": "protection",
    "辟邪": "protection",
    "安定": "calm",
    "稳定": "calm",
    "健康": "health",
    "护身": "health",
    "专注": "focus",
    "学习": "study",
    "考试": "study",
    "沟通": "communication",
    "表达": "communication",
    "睡眠": "sleep",
    "疗愈": "sleep",
    "情绪": "emotion",
    "灵感": "inspiration",
    "创作": "inspiration",
}

CHAKRA_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "root", "label": "海底轮"},
    {"key": "sacral", "label": "脐轮"},
    {"key": "solar_plexus", "label": "太阳轮"},
    {"key": "heart", "label": "心轮"},
    {"key": "throat", "label": "喉轮"},
    {"key": "third_eye", "label": "眉心轮"},
    {"key": "crown", "label": "顶轮"},
)

CHAKRA_ALIASES = {
    **{item["key"]: item["key"] for item in CHAKRA_OPTIONS},
    "海底轮": "root",
    "根轮": "root",
    "脐轮": "sacral",
    "太阳轮": "solar_plexus",
    "心轮": "heart",
    "喉轮": "throat",
    "眉心轮": "third_eye",
    "第三眼": "third_eye",
    "顶轮": "crown",
}

COLOR_FAMILY_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "clear", "label": "清透"},
    {"key": "white", "label": "白色"},
    {"key": "pink", "label": "粉色"},
    {"key": "blue", "label": "蓝色"},
    {"key": "green", "label": "绿色"},
    {"key": "purple", "label": "紫色"},
    {"key": "gold", "label": "金色"},
    {"key": "red", "label": "红色"},
    {"key": "brown", "label": "棕色"},
    {"key": "black", "label": "黑色"},
)

COLOR_FAMILY_ALIASES = {
    **{item["key"]: item["key"] for item in COLOR_FAMILY_OPTIONS},
    **{item["label"]: item["key"] for item in COLOR_FAMILY_OPTIONS},
    "透明": "clear",
}

GRADE_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "entry", "label": "入门级"},
    {"key": "A", "label": "A"},
    {"key": "AA", "label": "AA"},
    {"key": "AAA", "label": "AAA"},
    {"key": "AAAA", "label": "AAAA"},
    {"key": "premium", "label": "精选级"},
    {"key": "collector", "label": "收藏级"},
)

EFFECT_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "wealth", "label": "招财"},
    {"key": "career", "label": "事业推进"},
    {"key": "love", "label": "桃花人缘"},
    {"key": "protection", "label": "守护避煞"},
    {"key": "calm", "label": "稳定安定"},
    {"key": "focus", "label": "专注清晰"},
    {"key": "communication", "label": "表达沟通"},
    {"key": "emotion", "label": "情绪柔和"},
    {"key": "sleep", "label": "睡眠修复"},
    {"key": "inspiration", "label": "灵感创作"},
    {"key": "vitality", "label": "活力自信"},
)

MOOD_TAG_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "calming", "label": "舒缓"},
    {"key": "confidence", "label": "自信"},
    {"key": "clarity", "label": "清晰"},
    {"key": "focus", "label": "专注"},
    {"key": "vitality", "label": "活力"},
    {"key": "softness", "label": "柔和"},
    {"key": "boundary", "label": "边界"},
    {"key": "companionship", "label": "陪伴"},
)

MOOD_TAG_ALIASES = {
    **{item["key"]: item["key"] for item in MOOD_TAG_OPTIONS},
    **{item["label"]: item["key"] for item in MOOD_TAG_OPTIONS},
}

VISUAL_TAG_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "transparent", "label": "透明感"},
    {"key": "milky", "label": "奶白感"},
    {"key": "icy", "label": "冰透"},
    {"key": "sparkling", "label": "闪光"},
    {"key": "soft_color", "label": "低饱和"},
    {"key": "texture", "label": "纹理感"},
    {"key": "dark", "label": "深色"},
    {"key": "warm", "label": "暖调"},
)

VISUAL_TAG_ALIASES = {
    **{item["key"]: item["key"] for item in VISUAL_TAG_OPTIONS},
    **{item["label"]: item["key"] for item in VISUAL_TAG_OPTIONS},
}

ROLE_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "primary", "label": "主石"},
    {"key": "support", "label": "辅石"},
    {"key": "accent", "label": "点缀"},
    {"key": "spacer", "label": "隔珠/隔片"},
    {"key": "pendant", "label": "吊坠/花托"},
)

ROLE_ALIASES = {
    **{item["key"]: item["key"] for item in ROLE_OPTIONS},
    **{item["label"]: item["key"] for item in ROLE_OPTIONS},
    "隔珠": "spacer",
    "隔片": "spacer",
    "花托": "pendant",
    "吊坠": "pendant",
}

MATCH_RULE_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "no_limit", "label": "不限搭配"},
    {"key": "best_as_primary", "label": "适合作主石"},
    {"key": "best_as_support", "label": "适合作辅石"},
    {"key": "accent_only", "label": "建议少量点缀"},
    {"key": "spacer_only", "label": "仅作隔珠/隔片"},
    {"key": "pair_symmetry", "label": "建议成对对称"},
    {"key": "avoid_dense", "label": "避免高密度使用"},
    {"key": "needs_color_balance", "label": "需搭配平衡色"},
)

MATCH_RULE_ALIASES = {
    **{item["key"]: item["key"] for item in MATCH_RULE_OPTIONS},
    **{item["label"]: item["key"] for item in MATCH_RULE_OPTIONS},
    "不限": "no_limit",
    "主石": "best_as_primary",
    "辅石": "best_as_support",
    "点缀": "accent_only",
    "少量": "accent_only",
    "隔珠": "spacer_only",
    "隔片": "spacer_only",
}

CARE_TAG_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "avoid_water", "label": "避免长期泡水"},
    {"key": "avoid_sun", "label": "避免暴晒"},
    {"key": "avoid_sweat", "label": "避免汗液久沾"},
    {"key": "fragile", "label": "易磕碰"},
    {"key": "metal_sensitive", "label": "金属敏感提醒"},
    {"key": "clean_regularly", "label": "建议定期清洁"},
    {"key": "storage_separate", "label": "建议分开收纳"},
)

CARE_TAG_ALIASES = {
    **{item["key"]: item["key"] for item in CARE_TAG_OPTIONS},
    **{item["label"]: item["key"] for item in CARE_TAG_OPTIONS},
    "怕水": "avoid_water",
    "怕晒": "avoid_sun",
    "易碎": "fragile",
    "定期清洁": "clean_regularly",
}

BEAD_SHAPE_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "round", "label": "圆珠"},
    {"key": "faceted_round", "label": "切面圆珠"},
    {"key": "rondelle", "label": "算盘珠"},
    {"key": "barrel", "label": "桶珠"},
    {"key": "disc", "label": "隔片"},
    {"key": "special", "label": "异形"},
)

SURFACE_FINISH_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "glossy", "label": "亮面抛光"},
    {"key": "matte", "label": "哑光"},
    {"key": "frosted", "label": "磨砂"},
    {"key": "faceted", "label": "切面"},
    {"key": "carved", "label": "雕刻"},
)

TRANSPARENCY_LEVEL_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "transparent", "label": "通透"},
    {"key": "semi_transparent", "label": "半透"},
    {"key": "translucent", "label": "微透"},
    {"key": "opaque", "label": "不透"},
)

TEXTURE_FEATURE_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "clean", "label": "净体"},
    {"key": "cloud", "label": "棉絮"},
    {"key": "crack", "label": "冰裂"},
    {"key": "rutile", "label": "发丝"},
    {"key": "phantom", "label": "幽灵"},
    {"key": "cat_eye", "label": "猫眼"},
    {"key": "color_band", "label": "色带"},
    {"key": "mineral_inclusion", "label": "矿物内含"},
)

BATCH_VARIATION_OPTIONS: tuple[dict[str, str], ...] = (
    {"key": "low", "label": "批次差异小"},
    {"key": "medium", "label": "批次差异中"},
    {"key": "high", "label": "批次差异大"},
)

BEAD_SHAPE_ALIASES = {
    **{item["key"]: item["key"] for item in BEAD_SHAPE_OPTIONS},
    **{item["label"]: item["key"] for item in BEAD_SHAPE_OPTIONS},
    "圆形": "round",
    "切面": "faceted_round",
}

SURFACE_FINISH_ALIASES = {
    **{item["key"]: item["key"] for item in SURFACE_FINISH_OPTIONS},
    **{item["label"]: item["key"] for item in SURFACE_FINISH_OPTIONS},
    "亮面": "glossy",
    "抛光": "glossy",
}

TRANSPARENCY_LEVEL_ALIASES = {
    **{item["key"]: item["key"] for item in TRANSPARENCY_LEVEL_OPTIONS},
    **{item["label"]: item["key"] for item in TRANSPARENCY_LEVEL_OPTIONS},
    "透明": "transparent",
    "冰透": "transparent",
    "奶白": "translucent",
}

TEXTURE_FEATURE_ALIASES = {
    **{item["key"]: item["key"] for item in TEXTURE_FEATURE_OPTIONS},
    **{item["label"]: item["key"] for item in TEXTURE_FEATURE_OPTIONS},
    "发晶": "rutile",
    "内含物": "mineral_inclusion",
}

BATCH_VARIATION_ALIASES = {
    **{item["key"]: item["key"] for item in BATCH_VARIATION_OPTIONS},
    **{item["label"]: item["key"] for item in BATCH_VARIATION_OPTIONS},
    "小": "low",
    "中": "medium",
    "大": "high",
}


MATERIAL_OPTION_FIELD_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "wish_pools",
        "label": "适用愿景池",
        "control": "multi_select",
        "value_kind": "tag_key",
        "cardinality": "many",
        "mutable": True,
        "description": "用于测算、推荐和运营筛选，属于可扩展标签池，不建议让运营自由输入。",
    },
    {
        "key": "effects",
        "label": "核心功效标签",
        "control": "multi_select",
        "value_kind": "tag_key",
        "cardinality": "many",
        "mutable": True,
        "description": "用于前台卖点、搜索和推荐解释，适合做成标签池。",
    },
    {
        "key": "grades",
        "label": "品质等级",
        "control": "single_select",
        "value_kind": "enum_key",
        "cardinality": "one",
        "mutable": True,
        "description": "A、AA、AAA 等等级需要统一口径，避免同义词污染。",
    },
    {
        "key": "chakras",
        "label": "对应脉轮",
        "control": "multi_select",
        "value_kind": "enum_key",
        "cardinality": "many",
        "mutable": True,
        "description": "用于能量解释和推荐权重，通常多选。",
    },
    {
        "key": "color_families",
        "label": "色彩倾向",
        "control": "single_select",
        "value_kind": "enum_key",
        "cardinality": "one",
        "mutable": True,
        "description": "用于前台排序、推荐色系和筛选，单选主色系即可。",
    },
    {
        "key": "mood_tags",
        "label": "情绪标签",
        "control": "multi_select",
        "value_kind": "tag_key",
        "cardinality": "many",
        "mutable": True,
        "description": "用于今日能量、测算结果和用户共鸣表达，适合动态维护。",
    },
    {
        "key": "visual_tags",
        "label": "视觉标签",
        "control": "multi_select",
        "value_kind": "tag_key",
        "cardinality": "many",
        "mutable": True,
        "description": "用于风格筛选，例如冰透、奶白、闪光、低饱和。",
    },
    {
        "key": "roles",
        "label": "材料角色",
        "control": "multi_select",
        "value_kind": "enum_key",
        "cardinality": "many",
        "mutable": True,
        "description": "决定材料能否作为主石、辅石、点缀或隔珠使用。",
    },
    {
        "key": "match_rules",
        "label": "搭配规则",
        "control": "multi_select",
        "value_kind": "rule_key",
        "cardinality": "many",
        "mutable": True,
        "description": "用于约束自动成串和方案推荐，不应手写自然语言。",
    },
    {
        "key": "care_tags",
        "label": "佩戴养护",
        "control": "multi_select",
        "value_kind": "tag_key",
        "cardinality": "many",
        "mutable": True,
        "description": "用于商品详情和售后提示，例如怕水、怕晒、易磕碰。",
    },
    {
        "key": "bead_shapes",
        "label": "珠体形制",
        "control": "single_select",
        "value_kind": "enum_key",
        "cardinality": "one",
        "mutable": True,
        "description": "圆珠、切面珠、桶珠、隔片等形制需要统一枚举。",
    },
    {
        "key": "surface_finishes",
        "label": "表面工艺",
        "control": "single_select",
        "value_kind": "enum_key",
        "cardinality": "one",
        "mutable": True,
        "description": "亮面、哑光、磨砂、雕刻等工艺适合下拉选择。",
    },
    {
        "key": "transparency_levels",
        "label": "通透度",
        "control": "single_select",
        "value_kind": "enum_key",
        "cardinality": "one",
        "mutable": True,
        "description": "用于区分通透、半透、微透、不透，适合统一口径。",
    },
    {
        "key": "texture_features",
        "label": "纹理/内含特征",
        "control": "multi_select",
        "value_kind": "tag_key",
        "cardinality": "many",
        "mutable": True,
        "description": "棉絮、发丝、幽灵、猫眼等特征通常多选。",
    },
    {
        "key": "batch_variation_levels",
        "label": "批次差异",
        "control": "single_select",
        "value_kind": "enum_key",
        "cardinality": "one",
        "mutable": True,
        "description": "用于提醒同款不同批次的色差和纹理差异。",
    },
)

MATERIAL_FORM_FIELD_SPECS: tuple[dict[str, Any], ...] = (
    {"key": "category", "label": "一级分类", "control": "taxonomy_select", "value_kind": "taxonomy_key", "required": True},
    {"key": "series", "label": "品种", "control": "taxonomy_select", "value_kind": "taxonomy_key", "required": True},
    {"key": "material_code", "label": "材料编码", "control": "readonly", "value_kind": "system_key", "required": True},
    {"key": "primary_element", "label": "主五行", "control": "single_select", "value_kind": "enum_key", "required": True},
    {"key": "secondary_elements", "label": "副五行", "control": "multi_select", "value_kind": "enum_key", "required": False},
    {"key": "effects", "label": "核心功效", "control": "multi_select", "value_kind": "tag_key", "required": True},
    {"key": "wish_pools", "label": "适用愿景", "control": "multi_select", "value_kind": "tag_key", "required": False},
    {"key": "match_rules", "label": "规则约束", "control": "multi_select", "value_kind": "rule_key", "required": False},
    {"key": "price_per_bead", "label": "单颗售价", "control": "number", "value_kind": "money", "required": True},
    {"key": "cost_price", "label": "成本价", "control": "number", "value_kind": "money", "required": False},
    {"key": "stock", "label": "库存", "control": "number", "value_kind": "quantity", "required": True},
    {"key": "safety_stock", "label": "安全库存", "control": "number", "value_kind": "quantity", "required": False},
    {"key": "supplier_name", "label": "供应商/货源", "control": "text", "value_kind": "free_text", "required": False},
    {"key": "purchase_note", "label": "采购备注", "control": "textarea", "value_kind": "free_text", "required": False},
    {"key": "story", "label": "材质故事", "control": "textarea", "value_kind": "free_text", "required": False},
    {"key": "thumbnail_url", "label": "缩略图", "control": "upload", "value_kind": "asset_url", "required": True},
    {"key": "image_urls", "label": "多图", "control": "upload_list", "value_kind": "asset_url_list", "required": False},
)


def stable_key(value: Any, fallback: str = "item") -> str:
    text = str(value or "").strip()
    latin = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if latin:
        return latin[:48]
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10] if text else fallback
    return f"{fallback}-{digest}"


CUSTOM_OPTION_KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,79}$")


def normalize_option_key(
    value: Any,
    aliases: dict[str, str],
    allowed: set[str] | None = None,
    allow_custom: bool = False,
) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = aliases.get(text) or aliases.get(text.lower()) or text.lower()
    if allowed and normalized not in allowed and not (allow_custom and CUSTOM_OPTION_KEY_RE.match(normalized)):
        return ""
    return normalized


def normalize_option_list(
    value: Any,
    aliases: dict[str, str],
    allowed: set[str] | None = None,
    allow_custom: bool = False,
) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        raw = re.split(r"[,，、\n\r]+", value)
    elif isinstance(value, list):
        raw = value
    else:
        raw = [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        key = normalize_option_key(item, aliases, allowed, allow_custom=allow_custom)
        if key and key not in seen:
            result.append(key)
            seen.add(key)
    return result


def normalize_element_key(value: Any) -> str:
    return normalize_option_key(value, ELEMENT_ALIASES, set(ELEMENT_LABEL_BY_KEY))


def normalize_element_list(value: Any) -> list[str]:
    return normalize_option_list(value, ELEMENT_ALIASES, set(ELEMENT_LABEL_BY_KEY))


def element_label(value: Any) -> str:
    key = normalize_element_key(value) or str(value or "")
    return ELEMENT_LABEL_BY_KEY.get(key, key)


def normalize_wish_pool_list(value: Any) -> list[str]:
    return normalize_option_list(value, WISH_POOL_ALIASES, {item["key"] for item in WISH_POOL_OPTIONS}, allow_custom=True)


def normalize_chakra_list(value: Any) -> list[str]:
    return normalize_option_list(value, CHAKRA_ALIASES, {item["key"] for item in CHAKRA_OPTIONS}, allow_custom=True)


def normalize_color_family(value: Any) -> str:
    return normalize_option_key(value, COLOR_FAMILY_ALIASES, {item["key"] for item in COLOR_FAMILY_OPTIONS}, allow_custom=True)


def normalize_mood_tag_list(value: Any) -> list[str]:
    return normalize_option_list(value, MOOD_TAG_ALIASES, {item["key"] for item in MOOD_TAG_OPTIONS}, allow_custom=True)


def normalize_visual_tag_list(value: Any) -> list[str]:
    return normalize_option_list(value, VISUAL_TAG_ALIASES, {item["key"] for item in VISUAL_TAG_OPTIONS}, allow_custom=True)


def normalize_role_list(value: Any) -> list[str]:
    return normalize_option_list(value, ROLE_ALIASES, {item["key"] for item in ROLE_OPTIONS}, allow_custom=True)


def normalize_match_rule_list(value: Any) -> list[str]:
    return normalize_option_list(value, MATCH_RULE_ALIASES, {item["key"] for item in MATCH_RULE_OPTIONS}, allow_custom=True)


def normalize_care_tag_list(value: Any) -> list[str]:
    return normalize_option_list(value, CARE_TAG_ALIASES, {item["key"] for item in CARE_TAG_OPTIONS}, allow_custom=True)


def normalize_material_param_key(value: Any, option_type: str) -> str:
    configs = {
        "bead_shapes": (BEAD_SHAPE_ALIASES, {item["key"] for item in BEAD_SHAPE_OPTIONS}),
        "surface_finishes": (SURFACE_FINISH_ALIASES, {item["key"] for item in SURFACE_FINISH_OPTIONS}),
        "transparency_levels": (TRANSPARENCY_LEVEL_ALIASES, {item["key"] for item in TRANSPARENCY_LEVEL_OPTIONS}),
        "batch_variation_levels": (BATCH_VARIATION_ALIASES, {item["key"] for item in BATCH_VARIATION_OPTIONS}),
    }
    aliases, allowed = configs.get(option_type, ({}, None))
    return normalize_option_key(value, aliases, allowed, allow_custom=True)


def normalize_texture_feature_list(value: Any) -> list[str]:
    return normalize_option_list(
        value,
        TEXTURE_FEATURE_ALIASES,
        {item["key"] for item in TEXTURE_FEATURE_OPTIONS},
        allow_custom=True,
    )


def normalize_optional_positive_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return round(number, 3)


def normalize_material_params(value: Any) -> dict[str, Any]:
    params = dict(value) if isinstance(value, dict) else {}
    for key, option_type in (
        ("bead_shape", "bead_shapes"),
        ("surface_finish", "surface_finishes"),
        ("transparency_level", "transparency_levels"),
        ("batch_variation", "batch_variation_levels"),
    ):
        normalized = normalize_material_param_key(params.get(key), option_type)
        if normalized:
            params[key] = normalized
        else:
            params.pop(key, None)
    texture_features = normalize_texture_feature_list(params.get("texture_features"))
    if texture_features:
        params["texture_features"] = texture_features
    else:
        params.pop("texture_features", None)
    for key in ("hole_diameter_mm", "size_tolerance_mm"):
        number = normalize_optional_positive_float(params.get(key))
        if number is None:
            params.pop(key, None)
        else:
            params[key] = number
    return params


def public_material_field_specs() -> dict[str, Any]:
    return {
        "option_types": list(MATERIAL_OPTION_FIELD_SPECS),
        "material_fields": list(MATERIAL_FORM_FIELD_SPECS),
        "governance": {
            "enum_first": True,
            "free_text_usage": "仅用于供应商、采购备注、材质故事、少见补充参数等不确定性强的内容。",
            "key_storage": "结构化字段统一存稳定 key，前端展示时再映射为中文 label。",
        },
    }


def public_material_options() -> dict[str, Any]:
    return {
        "elements": list(ELEMENT_OPTIONS),
        "wish_pools": list(WISH_POOL_OPTIONS),
        "chakras": list(CHAKRA_OPTIONS),
        "color_families": list(COLOR_FAMILY_OPTIONS),
        "grades": list(GRADE_OPTIONS),
        "effects": list(EFFECT_OPTIONS),
        "mood_tags": list(MOOD_TAG_OPTIONS),
        "visual_tags": list(VISUAL_TAG_OPTIONS),
        "roles": list(ROLE_OPTIONS),
        "match_rules": list(MATCH_RULE_OPTIONS),
        "care_tags": list(CARE_TAG_OPTIONS),
        "bead_shapes": list(BEAD_SHAPE_OPTIONS),
        "surface_finishes": list(SURFACE_FINISH_OPTIONS),
        "transparency_levels": list(TRANSPARENCY_LEVEL_OPTIONS),
        "texture_features": list(TEXTURE_FEATURE_OPTIONS),
        "batch_variation_levels": list(BATCH_VARIATION_OPTIONS),
    }
