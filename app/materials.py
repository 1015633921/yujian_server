from __future__ import annotations

import json
import os
import time
from urllib.parse import quote, urlsplit, urlunsplit

from .database import connect_database, use_mysql
from .material_knowledge import enrich_materials_with_knowledge, material_code_from_payload
from .material_options import normalize_sku_physical_specs
from .money import cents_to_text, stored_cents


class MaterialCatalogUnavailable(RuntimeError):
    pass


def production_material_catalog_required() -> bool:
    return os.getenv("APP_ENV", "").strip().lower() in {"production", "prod"}


def material_cdn_base_url() -> str:
    cdn_base = os.getenv("TENCENT_COS_CDN_BASE_URL", "").strip().rstrip("/")
    if cdn_base:
        return cdn_base if cdn_base.endswith("/materials") else f"{cdn_base}/materials"
    app_env = os.getenv("APP_ENV", "").lower()
    if app_env in {"test", "testing", "staging"}:
        return "https://cdn-test.yustream.cn/materials"
    if app_env in {"production", "prod"}:
        return "https://cdn-prod.yustream.cn/materials"
    return "https://cdn-test.yustream.cn/materials"


CDN_BASE_URL = material_cdn_base_url()
MATERIAL_CACHE_TTL_SECONDS = 60
_MATERIAL_PAYLOAD_CACHE: dict[tuple, dict] = {}
# The material grid is paginated on the server.  Keep the version in the
# catalog cache key so a change to its ordering reaches clients immediately.
MATERIAL_SORT_POLICY_VERSION = "style-size-v1"

INTERNAL_MATERIAL_FIELDS = {
    "cost_price",
    "cost",
    "safety_stock",
    "stock_warning",
    "supplier_name",
    "supplier",
    "purchase_note",
    "purchase_remark",
    "price_cents",
    "physical_specs_json",
    "image_urls_json",
}


FEATURED_MATERIAL_PRIORITY_KEYWORDS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (0, ("粉水晶", "粉晶", "粉兔毛", "粉幽灵", "粉萤石", "粉色", "粉")),
    (1, ("白水晶", "白晶", "奶白水晶", "白阿塞", "双A白水", "净体白水晶", "白兔毛", "白幽灵", "白月光", "白色", "透明", "冰种")),
    (2, ("海蓝宝", "海蓝", "蓝水晶", "蓝发晶", "蓝兔毛", "蓝月光", "蓝虎眼", "蓝纹石", "天河石", "蓝色", "冰蓝")),
    (3, ("发晶", "金发晶", "银发晶", "彩发晶", "钛晶", "铜发", "黑发晶", "绿发晶")),
    (4, ("兔毛", "红兔毛", "黄兔毛", "白兔毛", "彩兔毛", "紫兔毛", "蓝兔毛", "灰兔毛", "绿兔毛")),
    (5, ("幽灵", "满天星", "四季幽灵", "绿幽灵", "白幽灵", "彩幽灵", "红幽灵", "黄幽灵", "紫幽灵", "千层幽灵")),
)


def material_display_text(item: dict) -> str:
    return "".join(
        str(item.get(key, "") or "")
        for key in ("category", "series", "name", "skuId", "id", "effect")
    )


def parse_hex_color(value: str | None) -> tuple[int, int, int] | None:
    text = str(value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return None
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return None


def material_color_priority(item: dict) -> int:
    rgb = parse_hex_color(item.get("color"))
    if not rgb:
        return 99
    red, green, blue = rgb
    brightness = (red + green + blue) / 3
    spread = max(rgb) - min(rgb)
    if brightness >= 220 and spread <= 36:
        return 11
    if red >= 190 and blue >= 145 and green >= 105 and red >= green + 18:
        return 10
    if blue >= 165 and green >= 120 and blue >= red + 16:
        return 12
    return 99


def featured_material_rank(item: dict) -> int:
    text = material_display_text(item)
    for rank, keywords in FEATURED_MATERIAL_PRIORITY_KEYWORDS:
        if any(keyword and keyword in text for keyword in keywords):
            return rank
    return material_color_priority(item)


def material_customer_sort_key(item: dict) -> tuple:
    """Keep SKU variants next to one another, ordered by their diameter.

    ``series`` is the operator-maintained variety/style.  Some legacy rows do
    not have one, in which case the display name is the best available group
    key.  When a style has multiple material codes, diameter still takes
    priority: every 8 mm option is shown before every 10 mm option.
    """
    top = str(item.get("top") or (item.get("sku") or {}).get("top") or "")
    category = str(item.get("category") or (item.get("sku") or {}).get("category") or "")
    series = str(item.get("series") or (item.get("sku") or {}).get("series") or item.get("name") or "")
    material_code = str(item.get("material_code") or item.get("materialCode") or item.get("skuId") or "")
    sort_order = int(float(item.get("sort_order") or item.get("sortOrder") or 0))
    try:
        size = float(item.get("size") or (item.get("sku") or {}).get("size_mm") or 0)
    except (TypeError, ValueError):
        size = 0
    item_id = str(item.get("id") or item.get("skuId") or "")
    return (top, category, series, size, material_code, sort_order, item_id)


def sort_materials_for_customer(materials: list[dict]) -> list[dict]:
    return sorted(materials, key=material_customer_sort_key)


MATERIAL_CATALOG: list[dict] = [
    {"id": "clearQuartz8", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "白水晶", "effect": "清爽与干净感", "element": "金", "price": 5, "size": 8, "weight": 1.2, "color": "#dfe3e5", "shine": "#ffffff", "image_path": "beads/clear-quartz-8.png"},
    {"id": "clearQuartz10", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "白水晶", "effect": "清爽与干净感", "element": "金", "price": 10, "size": 10, "weight": 1.6, "color": "#d6dbde", "shine": "#ffffff", "image_path": "beads/clear-quartz-10.png"},
    {"id": "clearQuartz12", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "白水晶", "effect": "清爽与干净感", "element": "金", "price": 15, "size": 12, "weight": 2.1, "color": "#cfd5d8", "shine": "#ffffff", "image_path": "beads/clear-quartz-12.png"},
    {"id": "clearQuartz14", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "白水晶", "effect": "清爽与干净感", "element": "金", "price": 18, "size": 14, "weight": 2.8, "color": "#c8ced1", "shine": "#ffffff", "image_path": "beads/clear-quartz-14.png"},
    {"id": "amethyst8", "skuId": "amethyst", "top": "bead", "category": "紫水晶", "name": "乌拉圭紫水晶", "effect": "灵感与睡眠", "element": "火", "price": 12, "size": 8, "weight": 1.4, "color": "#8b6aa5", "shine": "#efe8ff", "image_path": "beads/amethyst-8.png"},
    {"id": "amethyst10", "skuId": "amethyst", "top": "bead", "category": "紫水晶", "name": "乌拉圭紫水晶", "effect": "灵感与睡眠", "element": "火", "price": 18, "size": 10, "weight": 1.8, "color": "#76508f", "shine": "#efe8ff", "image_path": "beads/amethyst-10.png"},
    {"id": "citrine8", "skuId": "citrine", "top": "bead", "category": "黄水晶", "name": "巴西黄水晶", "effect": "财富与行动", "element": "土", "price": 16, "size": 8, "weight": 1.5, "color": "#d6ad50", "shine": "#fff0b7", "image_path": "beads/citrine-8.png"},
    {"id": "citrine10", "skuId": "citrine", "top": "bead", "category": "黄水晶", "name": "巴西黄水晶", "effect": "财富与行动", "element": "土", "price": 22, "size": 10, "weight": 1.9, "color": "#c79838", "shine": "#fff0b7", "image_path": "beads/citrine-10.png"},
    {"id": "obsidian10", "skuId": "obsidian", "top": "bead", "category": "曜石", "name": "冰种黑曜石", "effect": "边界与守护", "element": "金", "price": 14, "size": 10, "weight": 1.8, "color": "#262529", "shine": "#aeb2b5", "image_path": "beads/obsidian-10.png"},
    {"id": "tigerEye8", "skuId": "tigerEye", "top": "bead", "category": "虎眼石", "name": "南非虎眼石", "effect": "执行与稳定", "element": "土", "price": 13, "size": 8, "weight": 1.5, "color": "#9b6a2e", "shine": "#f1c06b", "image_path": "beads/tiger-eye-8.png"},
    {"id": "moonstone8", "skuId": "moonstone", "top": "bead", "category": "月光石", "name": "雪花幽灵", "effect": "情绪舒缓", "element": "水", "price": 8, "size": 8, "weight": 1.2, "color": "#bdc2c1", "shine": "#ffffff", "image_path": "beads/moonstone-8.png"},
    {"id": "aquamarine8", "skuId": "aquamarine", "top": "bead", "category": "海蓝宝", "name": "巴西海蓝宝", "effect": "沟通与平静", "element": "水", "price": 25, "size": 8, "weight": 1.4, "color": "#80b8c5", "shine": "#e8fbff", "image_path": "beads/aquamarine-8.png"},
    {"id": "blueRutilatedQuartz10", "skuId": "blueRutilatedQuartz", "top": "bead", "category": "蓝发晶", "name": "蓝发晶", "effect": "冷静与洞察", "element": "水", "price": 38, "size": 10, "weight": 1.9, "color": "#4f789b", "shine": "#dcecf3", "image_path": "beads/blue-rutilated-quartz-10.png"},
    {"id": "garnet8", "skuId": "garnet", "top": "bead", "category": "石榴石", "name": "石榴石", "effect": "活力与自信", "element": "火", "price": 18, "size": 8, "weight": 1.5, "color": "#8e2635", "shine": "#e7a1aa", "image_path": "beads/garnet-8.png"},
    {"id": "turquoise6", "skuId": "turquoise", "top": "bead", "category": "绿松石", "name": "绿松石", "effect": "生机与恢复", "element": "木", "price": 16, "size": 6, "weight": 0.9, "color": "#56a6a2", "shine": "#d7f1ef", "image_path": "beads/turquoise-6.png"},
    {"id": "greenPhantom8", "skuId": "greenPhantom", "top": "bead", "category": "绿幽灵", "name": "绿幽灵", "effect": "生长与专注", "element": "木", "price": 24, "size": 8, "weight": 1.4, "color": "#4a825f", "shine": "#d7eadc", "image_path": "beads/green-phantom-8.png"},
    {"id": "roseQuartz8", "skuId": "roseQuartz", "top": "bead", "category": "粉水晶", "name": "马达加斯加粉晶", "effect": "人缘与亲密", "element": "木", "price": 11, "size": 8, "weight": 1.3, "color": "#e0a3a8", "shine": "#fff1f3", "image_path": "beads/rose-quartz-8.png"},
    {"id": "silverSpacer", "skuId": "silverSpacer", "top": "accessory", "category": "隔片", "name": "925 银隔片", "effect": "结构与光泽", "element": "金", "price": 18, "size": 3, "weight": 0.4, "color": "#b9bdc2", "shine": "#ffffff", "image_path": "accessories/silver-spacer.png"},
    {"id": "goldSpacer", "skuId": "goldSpacer", "top": "accessory", "category": "隔片", "name": "鎏金隔片", "effect": "礼物感", "element": "土", "price": 16, "size": 3, "weight": 0.4, "color": "#c99d4d", "shine": "#fff0b7", "image_path": "accessories/gold-spacer.png"},
    {"id": "calmIncense8", "skuId": "calmIncense", "top": "incense", "category": "沉香调", "name": "静心合香珠", "effect": "安定与冥想", "element": "土", "price": 28, "size": 8, "weight": 0.8, "color": "#8a6b52", "shine": "#e2c7a8", "image_path": "incense/calm-incense-8.png"},
    {"id": "roseIncense8", "skuId": "roseIncense", "top": "incense", "category": "花香调", "name": "玫瑰合香珠", "effect": "柔和与关系", "element": "木", "price": 26, "size": 8, "weight": 0.8, "color": "#b9787b", "shine": "#ffe3e6", "image_path": "incense/rose-incense-8.png"},
    {"id": "lotusCap", "skuId": "lotusCap", "top": "pendant", "category": "花托", "name": "莲纹花托", "effect": "收束主石", "element": "金", "price": 22, "size": 6, "weight": 0.6, "color": "#c4b29a", "shine": "#fff8eb", "image_path": "findings/lotus-cap.png"},
    {"id": "foxPendant", "skuId": "foxPendant", "top": "pendant", "category": "吊坠", "name": "粉晶狐狸吊坠", "effect": "亲和与礼物", "element": "木", "price": 88, "size": 12, "weight": 2.2, "color": "#d88b91", "shine": "#fff1f3", "image_path": "findings/fox-pendant.png"},
]


TOP_TABS = [
    {"key": "bead", "label": "珠珠"},
    {"key": "accessory", "label": "配饰"},
    {"key": "pendant", "label": "花托"},
]

SEARCH_ALIASES = {
    "紫水晶": ["紫水晶", "紫晶", "紫"],
    "紫色": ["紫水晶", "紫晶", "紫"],
    "黄水晶": ["黄水晶", "黄晶", "黄"],
    "粉水晶": ["粉水晶", "粉晶", "粉"],
    "粉晶": ["粉水晶", "粉晶", "粉"],
    "白水晶": ["白水晶", "白晶", "白"],
    "黑曜石": ["黑曜石", "黑耀石", "曜石", "耀石"],
    "目标感": ["目标", "黄水晶", "黄晶", "金发晶", "钛晶"],
    "助眠": ["睡眠", "月光石", "紫晶"],
}

# The historical fallback catalog above may contain mojibake in older working
# copies. Keep a clean override here so the public materials API never falls
# back to unreadable Chinese when managed_materials is empty or unavailable.
MATERIAL_CATALOG = [
    {"id": "clearQuartz8", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "白水晶", "effect": "清爽与干净感", "element": "金", "price": 5, "size": 8, "weight": 1.2, "color": "#dfe3e5", "shine": "#ffffff", "image_path": "beads/clear-quartz-8.png"},
    {"id": "clearQuartz10", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "白水晶", "effect": "清爽与干净感", "element": "金", "price": 10, "size": 10, "weight": 1.6, "color": "#d6dbde", "shine": "#ffffff", "image_path": "beads/clear-quartz-10.png"},
    {"id": "clearQuartz12", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "白水晶", "effect": "清爽与干净感", "element": "金", "price": 15, "size": 12, "weight": 2.1, "color": "#cfd5d8", "shine": "#ffffff", "image_path": "beads/clear-quartz-12.png"},
    {"id": "clearQuartz14", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "白水晶", "effect": "清爽与干净感", "element": "金", "price": 18, "size": 14, "weight": 2.8, "color": "#c8ced1", "shine": "#ffffff", "image_path": "beads/clear-quartz-14.png"},
    {"id": "amethyst8", "skuId": "amethyst", "top": "bead", "category": "紫水晶", "name": "乌拉圭紫水晶", "effect": "灵感与睡眠", "element": "火", "price": 12, "size": 8, "weight": 1.4, "color": "#8b6aa5", "shine": "#efe8ff", "image_path": "beads/amethyst-8.png"},
    {"id": "amethyst10", "skuId": "amethyst", "top": "bead", "category": "紫水晶", "name": "乌拉圭紫水晶", "effect": "灵感与睡眠", "element": "火", "price": 18, "size": 10, "weight": 1.8, "color": "#76508f", "shine": "#efe8ff", "image_path": "beads/amethyst-10.png"},
    {"id": "citrine8", "skuId": "citrine", "top": "bead", "category": "黄水晶", "name": "巴西黄水晶", "effect": "财富与行动", "element": "土", "price": 16, "size": 8, "weight": 1.5, "color": "#d6ad50", "shine": "#fff0b7", "image_path": "beads/citrine-8.png"},
    {"id": "citrine10", "skuId": "citrine", "top": "bead", "category": "黄水晶", "name": "巴西黄水晶", "effect": "财富与行动", "element": "土", "price": 22, "size": 10, "weight": 1.9, "color": "#c79838", "shine": "#fff0b7", "image_path": "beads/citrine-10.png"},
    {"id": "obsidian10", "skuId": "obsidian", "top": "bead", "category": "曜石", "name": "冰种黑曜石", "effect": "边界与守护", "element": "金", "price": 14, "size": 10, "weight": 1.8, "color": "#262529", "shine": "#aeb2b5", "image_path": "beads/obsidian-10.png"},
    {"id": "tigerEye8", "skuId": "tigerEye", "top": "bead", "category": "虎眼石", "name": "南非虎眼石", "effect": "执行与稳定", "element": "土", "price": 13, "size": 8, "weight": 1.5, "color": "#9b6a2e", "shine": "#f1c06b", "image_path": "beads/tiger-eye-8.png"},
    {"id": "moonstone8", "skuId": "moonstone", "top": "bead", "category": "月光石", "name": "雪花幽灵", "effect": "情绪舒缓", "element": "水", "price": 8, "size": 8, "weight": 1.2, "color": "#bdc2c1", "shine": "#ffffff", "image_path": "beads/moonstone-8.png"},
    {"id": "aquamarine8", "skuId": "aquamarine", "top": "bead", "category": "海蓝宝", "name": "巴西海蓝宝", "effect": "沟通与平静", "element": "水", "price": 25, "size": 8, "weight": 1.4, "color": "#80b8c5", "shine": "#e8fbff", "image_path": "beads/aquamarine-8.png"},
    {"id": "blueRutilatedQuartz10", "skuId": "blueRutilatedQuartz", "top": "bead", "category": "蓝发晶", "name": "蓝发晶", "effect": "冷静与洞察", "element": "水", "price": 38, "size": 10, "weight": 1.9, "color": "#4f789b", "shine": "#dcecf3", "image_path": "beads/blue-rutilated-quartz-10.png"},
    {"id": "garnet8", "skuId": "garnet", "top": "bead", "category": "石榴石", "name": "石榴石", "effect": "活力与自信", "element": "火", "price": 18, "size": 8, "weight": 1.5, "color": "#8e2635", "shine": "#e7a1aa", "image_path": "beads/garnet-8.png"},
    {"id": "turquoise6", "skuId": "turquoise", "top": "bead", "category": "绿松石", "name": "绿松石", "effect": "生机与恢复", "element": "木", "price": 16, "size": 6, "weight": 0.9, "color": "#56a6a2", "shine": "#d7f1ef", "image_path": "beads/turquoise-6.png"},
    {"id": "greenPhantom8", "skuId": "greenPhantom", "top": "bead", "category": "绿幽灵", "name": "绿幽灵", "effect": "生长与专注", "element": "木", "price": 24, "size": 8, "weight": 1.4, "color": "#4a825f", "shine": "#d7eadc", "image_path": "beads/green-phantom-8.png"},
    {"id": "roseQuartz8", "skuId": "roseQuartz", "top": "bead", "category": "粉水晶", "name": "马达加斯加粉晶", "effect": "人缘与亲密", "element": "木", "price": 11, "size": 8, "weight": 1.3, "color": "#e0a3a8", "shine": "#fff1f3", "image_path": "beads/rose-quartz-8.png"},
    {"id": "silverSpacer", "skuId": "silverSpacer", "top": "accessory", "category": "隔片", "name": "925 银隔片", "effect": "结构与光泽", "element": "金", "price": 18, "size": 3, "weight": 0.4, "color": "#b9bdc2", "shine": "#ffffff", "image_path": "accessories/silver-spacer.png"},
    {"id": "goldSpacer", "skuId": "goldSpacer", "top": "accessory", "category": "隔片", "name": "鎏金隔片", "effect": "礼物感", "element": "土", "price": 16, "size": 3, "weight": 0.4, "color": "#c99d4d", "shine": "#fff0b7", "image_path": "accessories/gold-spacer.png"},
    {"id": "lotusCap", "skuId": "lotusCap", "top": "pendant", "category": "花托", "name": "莲纹花托", "effect": "收束主石", "element": "金", "price": 22, "size": 6, "weight": 0.6, "color": "#c4b29a", "shine": "#fff8eb", "image_path": "findings/lotus-cap.png"},
    {"id": "foxPendant", "skuId": "foxPendant", "top": "pendant", "category": "吊坠", "name": "粉晶狐狸吊坠", "effect": "亲和与礼物", "element": "木", "price": 88, "size": 12, "weight": 2.2, "color": "#d88b91", "shine": "#fff1f3", "image_path": "findings/fox-pendant.png"},
]

TOP_TABS = [
    {"key": "bead", "label": "珠珠"},
    {"key": "accessory", "label": "配饰"},
    {"key": "pendant", "label": "花托"},
]

SEARCH_ALIASES = {
    "紫水晶": ["紫水晶", "紫晶", "紫"],
    "紫色": ["紫水晶", "紫晶", "紫"],
    "黄水晶": ["黄水晶", "黄晶", "黄"],
    "粉水晶": ["粉水晶", "粉晶", "粉"],
    "粉晶": ["粉水晶", "粉晶", "粉"],
    "白水晶": ["白水晶", "白晶", "白"],
    "黑曜石": ["黑曜石", "黑耀石", "曜石"],
    "目标感": ["目标", "黄水晶", "黄晶", "金发晶", "钛晶"],
    "助眠": ["睡眠", "月光石", "紫晶"],
}


def expand_search_terms(keyword: str | None) -> list[str]:
    value = (keyword or "").strip()
    if not value:
        return []
    return list(dict.fromkeys(SEARCH_ALIASES.get(value, [value])))


def normalize_material_image_path(image_path: str | None) -> str:
    path = str(image_path or "").strip().lstrip("/")
    while path.startswith("materials/"):
        path = path[len("materials/"):]
    return path


def normalize_material_image_url(url: str | None) -> str:
    value = str(url or "").strip()
    while "/materials/materials/" in value:
        value = value.replace("/materials/materials/", "/materials/")
    if ".cos." in value and "/materials/" in value:
        _, path = value.split("/materials/", 1)
        path, separator, query = path.partition("?")
        normalized = material_url_from_path(path)
        value = f"{normalized}?{query}" if separator and query else normalized
    if value.startswith(("http://", "https://")):
        parts = urlsplit(value)
        value = urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%"), parts.query, parts.fragment))
    return value


def material_url_from_path(image_path: str | None) -> str:
    path = normalize_material_image_path(image_path)
    if not path:
        return ""
    return f"{material_cdn_base_url()}/{quote(path, safe='/%')}"


def clean_image_urls(value, primary_url: str = "", image_path: str = "") -> list[str]:
    candidates: list[str] = []
    if isinstance(value, list):
        candidates.extend(str(item).strip() for item in value)
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    candidates.extend(str(item).strip() for item in parsed)
            except json.JSONDecodeError:
                candidates.append(text)
        else:
            candidates.extend(part.strip() for part in text.replace("\r", "\n").replace(",", "\n").split("\n"))
    if primary_url:
        candidates.append(primary_url.strip())
    path_url = material_url_from_path(image_path)
    if path_url:
        candidates.append(path_url)
    result: list[str] = []
    seen: set[str] = set()
    for url in candidates:
        url = normalize_material_image_url(url)
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(url)
    return result


def material_image_identity(url: str | None) -> str:
    """Compare material assets without cache-busting query strings."""
    normalized = normalize_material_image_url(url)
    if not normalized:
        return ""
    parts = urlsplit(normalized)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def clean_gallery_image_urls(value, primary_url: str = "", *, top: str = "") -> list[str]:
    """Normalize only gallery entries; the primary image is a separate field."""
    # 主图仅用于目录和材料详情展示，不能参与工作台的随机抽图。用去掉
    # query string 的 identity 比较，避免同一 COS 文件因版本参数不同而绕过
    # 校验；图库本身也以相同规则去重，保证每张图的随机概率一致。
    primary_identity = material_image_identity(primary_url)
    result: list[str] = []
    seen: set[str] = set()
    for url in clean_image_urls(value):
        identity = material_image_identity(url)
        if not identity or identity == primary_identity or identity in seen:
            continue
        seen.add(identity)
        result.append(url)
    return result


def with_cdn_url(item: dict) -> dict:
    image_url = normalize_material_image_url(item.get("image_url")) or material_url_from_path(item.get("image_path"))
    if item.get("top") == "accessory":
        image_urls = clean_gallery_image_urls(item.get("image_urls"), image_url, top="accessory")
    else:
        image_urls = clean_image_urls(item.get("image_urls"), image_url, item.get("image_path") or "")
    return {
        **item,
        "image_url": image_url or (image_urls[0] if image_urls else ""),
        "image_urls": image_urls,
        "image_pool": image_urls,
    }


ALL_OPTION_LABEL = "\u5168\u90e8"


def normalize_material_id_list(ids: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if not ids:
        return []
    values: list[str] = []
    if isinstance(ids, str):
        raw_values = ids.replace("\r", ",").replace("\n", ",").split(",")
    else:
        raw_values = []
        for value in ids:
            raw_values.extend(str(value or "").split(","))
    for value in raw_values:
        text = str(value or "").strip()
        if text and text not in values:
            values.append(text)
    return values


def is_all_option(value: str | None) -> bool:
    return not value or str(value).strip() == ALL_OPTION_LABEL


def slim_material(item: dict) -> dict:
    sku = item.get("sku") or {}
    energy = item.get("energy") or {}
    visual = item.get("visual") or {}
    image_url = (
        visual.get("thumbnail_url")
        or visual.get("image_url")
        or item.get("thumbnail_url")
        or item.get("image_url")
        or ""
    )
    image_urls = clean_gallery_image_urls(
        visual.get("image_urls") or item.get("image_urls") or item.get("image_pool"),
        image_url,
        top=sku.get("top") or item.get("top") or "",
    )
    effects = energy.get("effects") or item.get("effects") or []
    if isinstance(effects, str):
        effects = [effects]
    top = sku.get("top") or item.get("top") or ""
    primary_element = "" if top == "pendant" else (
        energy.get("primary_element") or item.get("primary_element") or item.get("element") or ""
    )
    price = sku.get("price_per_bead") if sku else None
    size = sku.get("size_mm") if sku else None
    weight = sku.get("weight_g") if sku else None
    physical_specs = normalize_sku_physical_specs(item.get("physical_specs"))
    material_params = {
        **(visual.get("material_params") or item.get("material_params") or {}),
        **physical_specs,
    }
    return {
        "id": sku.get("id") or item.get("id") or "",
        "skuId": sku.get("sku_id") or item.get("skuId") or item.get("sku_id") or "",
        "sku_id": sku.get("sku_id") or item.get("sku_id") or item.get("skuId") or "",
        "material_code": sku.get("material_code") or item.get("material_code") or "",
        "top": top,
        "category": sku.get("category") or item.get("category") or "",
        "series": sku.get("series") or item.get("series") or item.get("name") or "",
        "grade": sku.get("grade") or item.get("grade") or "",
        "name": sku.get("name") or item.get("name") or "",
        "price": float(price if price not in (None, "") else item.get("price") or 0),
        "size": float(size if size not in (None, "") else item.get("size") or 0),
        "weight": float(weight if weight not in (None, "") else item.get("weight") or 0),
        "stock": int(float(sku.get("stock") if sku else item.get("stock") or 0)),
        "enabled": bool(sku.get("enabled") if sku and "enabled" in sku else item.get("enabled", True)),
        "sort_order": int(float(sku.get("sort_order") if sku else item.get("sort_order") or item.get("sortOrder") or 0)),
        "element": primary_element,
        "primary_element": primary_element,
        "effects": effects,
        "effect": " / ".join(str(value) for value in effects if value) or item.get("effect") or "",
        "color": visual.get("color_hex") or item.get("color") or "",
        "shine": visual.get("shine_hex") or item.get("shine") or "",
        # Legacy varieties can have only gallery data.  Use its first image as
        # a display fallback, but keep it in the gallery: it was never a real
        # primary image and must remain eligible for workspace randomization.
        "image_url": image_url or (image_urls[0] if image_urls else ""),
        "image_urls": image_urls,
        "thumbnail_url": image_url,
        "material_params": material_params,
        "physical_specs": physical_specs,
    }


def paginate_materials(materials: list[dict], page: int | None, page_size: int | None) -> tuple[list[dict], dict]:
    current_page = max(1, int(page or 1))
    size = max(1, min(60, int(page_size or 24)))
    total = len(materials)
    start = (current_page - 1) * size
    end = start + size
    return materials[start:end], {
        "page": current_page,
        "page_size": size,
        "total": total,
        "has_more": end < total,
    }


def list_materials(
    top: str | None = None,
    keyword: str | None = None,
    compact: bool = False,
    limit: int | None = None,
    category: str | None = None,
    series: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    slim: bool = False,
    ids: str | list[str] | tuple[str, ...] | None = None,
) -> dict:
    version = material_catalog_version()
    material_ids = normalize_material_id_list(ids)
    use_pagination = page is not None or page_size is not None
    cache_key = (
        top or "",
        keyword or "",
        category or "",
        series or "",
        tuple(material_ids),
        bool(compact),
        bool(slim),
        int(limit or 0),
        int(page or 0),
        int(page_size or 0),
        version.get("version", ""),
    )
    cached = _MATERIAL_PAYLOAD_CACHE.get(cache_key)
    if cached and time.time() - cached.get("_cached_at", 0) < MATERIAL_CACHE_TTL_SECONDS:
        return {k: v for k, v in cached.items() if k != "_cached_at"}

    if use_pagination and slim and not material_ids:
        db_page = list_db_materials_page(
            top=top,
            keyword=keyword,
            category=category,
            series=series,
            page=page,
            page_size=page_size,
        )
        if db_page is not None:
            materials, pagination = db_page
            materials = enrich_materials_with_knowledge(materials)
            payload = {"materials": [slim_material(item) for item in materials], "pagination": pagination}
            if not compact:
                payload = {**build_material_payload(payload["materials"], version), "pagination": pagination}
            _MATERIAL_PAYLOAD_CACHE[cache_key] = {**payload, "_cached_at": time.time()}
            return payload

    db_materials = list_db_materials(
        top=top,
        keyword=keyword,
        limit=None if use_pagination else limit,
        category=category,
        series=series,
        ids=material_ids,
        enrich=True,
    )
    if db_materials is not None:
        materials = db_materials
        pagination = None
        if use_pagination:
            materials, pagination = paginate_materials(materials, page, page_size)
        if slim:
            materials = [slim_material(item) for item in materials]
        if compact:
            payload = {"materials": materials}
            if pagination:
                payload["pagination"] = pagination
            return payload
        payload = build_material_payload(materials, version)
        if pagination:
            payload["pagination"] = pagination
        _MATERIAL_PAYLOAD_CACHE[cache_key] = {**payload, "_cached_at": time.time()}
        return payload

    if production_material_catalog_required():
        raise MaterialCatalogUnavailable("材料库暂时不可用，请稍后重试")

    materials = filter_static_materials(top=top, keyword=keyword, category=category, series=series, ids=material_ids)
    pagination = None
    if use_pagination:
        materials, pagination = paginate_materials(materials, page, page_size)
    elif limit:
        materials = materials[:limit]
    if slim:
        materials = [slim_material(item) for item in materials]
    if compact:
        payload = {"materials": materials}
        if pagination:
            payload["pagination"] = pagination
        return payload
    payload = build_material_payload(materials, version)
    if pagination:
        payload["pagination"] = pagination
    _MATERIAL_PAYLOAD_CACHE[cache_key] = {**payload, "_cached_at": time.time()}
    return payload


def filter_static_materials(
    top: str | None = None,
    keyword: str | None = None,
    category: str | None = None,
    series: str | None = None,
    ids: list[str] | None = None,
) -> list[dict]:
    search_terms = [item.lower() for item in expand_search_terms(keyword)]
    id_set = set(ids or [])
    materials = []
    for item in MATERIAL_CATALOG:
        item_identifiers = {
            str(item.get("id") or ""),
            str(item.get("skuId") or ""),
            str(item.get("sku_id") or ""),
            str(item.get("material_code") or ""),
        }
        if top and item["top"] != top:
            continue
        if id_set and not (id_set & item_identifiers):
            continue
        if not is_all_option(category) and item.get("category") != category:
            continue
        item_series = item.get("series") or item.get("name") or ""
        if not is_all_option(series) and item_series != series:
            continue
        haystack = " ".join(
            str(item.get(key, ""))
            for key in ["id", "skuId", "category", "series", "grade", "name", "effect", "element"]
        ).lower()
        if search_terms and not any(term in haystack for term in search_terms):
            continue
        materials.append(with_cdn_url(item))
    return enrich_materials_with_knowledge(sort_materials_for_customer(materials))


def build_material_payload(materials: list[dict], version: dict | None = None) -> dict:
    categories_by_top = {}
    series_by_category = {}
    db_facets = list_db_material_facets()
    for tab in TOP_TABS:
        pool = db_facets if db_facets is not None else MATERIAL_CATALOG
        pool = [item for item in pool if item.get("top") == tab["key"]]
        category_sort_orders: dict[str, int] = {}
        for item in pool:
            category = str(item.get("category") or "").strip()
            if not category:
                continue
            try:
                sort_order = int(item.get("category_sort_order") or 0)
            except (TypeError, ValueError):
                sort_order = 0
            category_sort_orders[category] = min(category_sort_orders.get(category, sort_order), sort_order)
        ordered_categories = sorted(category_sort_orders, key=lambda name: (category_sort_orders[name], name))
        categories_by_top[tab["key"]] = [ALL_OPTION_LABEL, *ordered_categories]
        for item in pool:
            category_key = f"{tab['key']}::{item.get('category', '')}"
            series = item.get("series") or item.get("name") or ""
            if series:
                series_by_category.setdefault(category_key, set()).add(series)

    return {
        "cdn_base_url": material_cdn_base_url(),
        "version": (version or material_catalog_version()).get("version", ""),
        "updated_at": (version or material_catalog_version()).get("updated_at", ""),
        "top_tabs": TOP_TABS,
        "categories_by_top": categories_by_top,
        "series_by_category": {
            key: [ALL_OPTION_LABEL, *sorted(values)]
            for key, values in series_by_category.items()
        },
        "materials": materials,
    }


def invalidate_material_cache() -> None:
    _MATERIAL_PAYLOAD_CACHE.clear()


def material_catalog_version() -> dict:
    try:
        from .repository import DB_PATH
    except Exception:
        DB_PATH = None
    if not use_mysql() and (not DB_PATH or not DB_PATH.exists()):
        return {"version": f"static-v1:{MATERIAL_SORT_POLICY_VERSION}", "updated_at": ""}
    try:
        with connect_database() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total, COALESCE(MAX(updated_at), '') AS updated_at
                FROM managed_materials
                """
            ).fetchone()
            taxonomy = connection.execute(
                """
                SELECT COALESCE(MAX(updated_at), '') AS updated_at
                FROM material_taxonomy
                """
            ).fetchone()
            knowledge = connection.execute(
                """
                SELECT COALESCE(MAX(updated_at), '') AS updated_at
                FROM material_knowledge
                """
            ).fetchone()
    except Exception:
        return {"version": f"static-v1:{MATERIAL_SORT_POLICY_VERSION}", "updated_at": ""}
    total = int(row["total"] or 0)
    updated_at = max(
        str(row["updated_at"] or ""),
        str(taxonomy["updated_at"] if taxonomy else ""),
        str(knowledge["updated_at"] if knowledge else ""),
    )
    return {"version": f"{total}:{updated_at}:{MATERIAL_SORT_POLICY_VERSION}", "updated_at": updated_at}


def list_db_material_facets() -> list[dict] | None:
    try:
        from .repository import DB_PATH
    except Exception:
        return None
    if not use_mysql() and not DB_PATH.exists():
        return None
    try:
        with connect_database() as connection:
            try:
                rows = connection.execute(
                    """
                    SELECT m.top, m.category, m.series, m.name,
                           COALESCE(c.sort_order, 0) AS category_sort_order
                    FROM managed_materials m
                    LEFT JOIN material_taxonomy c
                      ON c.kind='category' AND c.top=m.top AND c.name=m.category
                    WHERE m.enabled = 1
                    """
                ).fetchall()
            except Exception:
                # Keep older deployments usable until their taxonomy table is
                # initialized; their legacy category order remains unchanged.
                rows = connection.execute(
                    """
                    SELECT top, category, series, name, 0 AS category_sort_order
                    FROM managed_materials
                    WHERE enabled = 1
                    """
                ).fetchall()
    except Exception:
        return None
    return [dict(row) for row in rows]


def build_db_material_filters(
    top: str | None = None,
    keyword: str | None = None,
    category: str | None = None,
    series: str | None = None,
    ids: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    clauses = ["enabled = 1"]
    params: list[str] = []
    if top:
        clauses.append("top = ?")
        params.append(top)
    if ids:
        placeholders = ",".join("?" for _ in ids)
        clauses.append(f"(id IN ({placeholders}) OR skuId IN ({placeholders}) OR material_code IN ({placeholders}))")
        params.extend([*ids, *ids, *ids])
    if not is_all_option(category):
        clauses.append("category = ?")
        params.append(category or "")
    if not is_all_option(series):
        clauses.append("COALESCE(NULLIF(series, ''), name) = ?")
        params.append(series or "")
    search_terms = expand_search_terms(keyword)
    if search_terms:
        fields = ["name", "category", "series", "grade", "effect", "element", "skuId"]
        term_clauses = []
        for term in search_terms:
            term_clauses.append("(" + " OR ".join(f"{field} LIKE ?" for field in fields) + ")")
            params.extend([f"%{term}%"] * len(fields))
        clauses.append("(" + " OR ".join(term_clauses) + ")")
    return clauses, params


def list_db_materials_page(
    top: str | None = None,
    keyword: str | None = None,
    category: str | None = None,
    series: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> tuple[list[dict], dict] | None:
    try:
        from .repository import DB_PATH
    except Exception:
        return None
    if not use_mysql() and not DB_PATH.exists():
        return None
    current_page = max(1, int(page or 1))
    size = max(1, min(60, int(page_size or 24)))
    offset = (current_page - 1) * size
    clauses, params = build_db_material_filters(top=top, keyword=keyword, category=category, series=series)
    where = " AND ".join(clauses)
    try:
        with connect_database() as connection:
            total_row = connection.execute(f"SELECT COUNT(*) AS total FROM managed_materials WHERE {where}", params).fetchone()
            rows = connection.execute(
                f"""
                SELECT *
                FROM managed_materials
                WHERE {where}
                ORDER BY
                    COALESCE(top, '') ASC,
                    COALESCE(category, '') ASC,
                    COALESCE(NULLIF(series, ''), name, '') ASC,
                    size ASC,
                    COALESCE(material_code, '') ASC,
                    sort_order ASC,
                    id ASC
                LIMIT ? OFFSET ?
                """,
                [*params, size, offset],
            ).fetchall()
            row_dicts = [dict(row) for row in rows]
            series_assets = fetch_db_series_assets(connection, row_dicts)
    except Exception:
        return None
    total = int(total_row["total"] or 0)
    return [normalize_db_material(row, series_assets) for row in row_dicts], {
        "page": current_page,
        "page_size": size,
        "total": total,
        "has_more": offset + size < total,
    }


def list_db_materials(
    top: str | None = None,
    keyword: str | None = None,
    limit: int | None = None,
    category: str | None = None,
    series: str | None = None,
    ids: list[str] | None = None,
    enrich: bool = True,
) -> list[dict] | None:
    try:
        from .repository import DB_PATH
    except Exception:
        return None
    if not use_mysql() and not DB_PATH.exists():
        return None
    clauses, params = build_db_material_filters(top=top, keyword=keyword, category=category, series=series, ids=ids)
    try:
        with connect_database() as connection:
            sql = f"SELECT * FROM managed_materials WHERE {' AND '.join(clauses)} ORDER BY sort_order ASC, updated_at DESC"
            rows = connection.execute(sql, params).fetchall()
            row_dicts = [dict(row) for row in rows]
            series_assets = fetch_db_series_assets(connection, row_dicts)
    except Exception:
        return None
    materials = [normalize_db_material(row, series_assets) for row in row_dicts]
    if enrich:
        materials = enrich_materials_with_knowledge(sort_materials_for_customer(materials))
    if limit:
        materials = materials[:limit]
    return materials


def series_asset_key(row: dict) -> tuple[str, str, str]:
    series_id = str(row.get("series_id") or "").strip()
    if series_id:
        return ("series_id", series_id, "")
    return (
        str(row.get("top") or "bead"),
        str(row.get("category") or ""),
        str(row.get("series") or row.get("name") or ""),
    )


def fetch_db_series_assets(connection, rows: list[dict]) -> dict[tuple[str, str, str], dict]:
    if not rows:
        return {}
    # `series_asset_key` starts with the literal ``series_id`` once a SKU has
    # been migrated.  The taxonomy query must still be constrained by the
    # material type, not by that key marker; otherwise every linked SKU misses
    # its shared images and recommendation/workspace previews turn blank.
    tops = sorted({str(row.get("top") or "").strip() for row in rows if str(row.get("top") or "").strip()})
    if not tops:
        return {}
    placeholders = ", ".join(["?"] * len(tops))
    try:
        taxonomy_rows = connection.execute(
            f"""
            SELECT s.*, c.name AS category_name
            FROM material_taxonomy s, material_taxonomy c
            WHERE s.kind='series'
              AND c.kind='category'
              AND s.parent_id=c.item_id
              AND s.enabled=1
              AND c.enabled=1
              AND s.top IN ({placeholders})
            """,
            tops,
        ).fetchall()
    except Exception:
        return {}
    result: dict[tuple[str, str, str], dict] = {}
    for raw in taxonomy_rows:
        row = dict(raw)
        image_path = row.get("image_path") or ""
        image_url = normalize_material_image_url(row.get("image_url") or "") or material_url_from_path(image_path)
        image_urls = clean_gallery_image_urls(
            row.get("image_urls_json") or row.get("image_urls"),
            image_url,
            top=row.get("top") or "bead",
        )
        result[("series_id", row.get("item_id") or "", "")] = {
            "series_id": row.get("item_id") or "",
            "material_code": row.get("material_code") or "",
            "color": row.get("color") or "",
            "shine": row.get("shine") or "",
            "image_path": image_path,
            "image_url": image_url,
            "image_urls": image_urls,
        }
        # The editable name/category key remains a compatibility fallback for
        # legacy SKU rows that have not yet been linked by the migration.
        result[(row.get("top") or "bead", row.get("category_name") or "", row.get("name") or "")] = {
            "series_id": row.get("item_id") or "",
            "material_code": row.get("material_code") or "",
            "color": row.get("color") or "",
            "shine": row.get("shine") or "",
            "image_path": image_path,
            "image_url": image_url,
            "image_urls": image_urls,
        }
    return result


def normalize_db_material(row: dict, series_assets: dict[tuple[str, str, str], dict] | None = None) -> dict:
    public_row = {key: value for key, value in row.items() if key not in INTERNAL_MATERIAL_FIELDS}
    series_asset = (series_assets or {}).get(series_asset_key(row), {})
    image_path = series_asset.get("image_path") or ""
    image_url = series_asset.get("image_url") or ""
    if image_path:
        normalized_path = normalize_material_image_path(image_path)
        old_suffix = f"/materials/{normalized_path}"
        if not image_url or "cdn.yustream.cn/materials/" in image_url or image_url.endswith(old_suffix):
            image_url = material_url_from_path(image_path)
    image_urls = clean_gallery_image_urls(
        series_asset.get("image_urls") or [],
        image_url,
        top=row.get("top") or "bead",
    )
    try:
        display_price = float(cents_to_text(stored_cents(row.get("price_cents"), field_name="材料价格")))
    except ValueError:
        display_price = float(row.get("price") or 0)
    raw_physical_specs = row.get("physical_specs_json")
    if isinstance(raw_physical_specs, str):
        try:
            raw_physical_specs = json.loads(raw_physical_specs or "{}")
        except json.JSONDecodeError:
            raw_physical_specs = {}
    physical_specs = normalize_sku_physical_specs(raw_physical_specs)
    return {
        **public_row,
        "price": display_price,
        "material_code": row.get("material_code") or series_asset.get("material_code") or material_code_from_payload(row),
        "enabled": bool(row.get("enabled", 1)),
        "series": row.get("series") or row.get("name") or "",
        "grade": row.get("grade") or "",
        "color": series_asset.get("color") or row.get("color") or "",
        "shine": series_asset.get("shine") or row.get("shine") or "",
        "image_path": image_path,
        # Keep old gallery-only records usable for display until an operator
        # sets a real primary image.  `image_urls` intentionally stays intact
        # so the fallback image is not silently removed from the random pool.
        "image_url": image_url or (image_urls[0] if image_urls else ""),
        "image_urls": image_urls,
        "image_pool": image_urls,
        "physical_specs": physical_specs,
    }
