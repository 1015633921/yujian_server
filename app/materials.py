from __future__ import annotations

import json
import os
import time
from urllib.parse import quote, urlsplit, urlunsplit

from .database import connect_database, use_mysql


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
MATERIAL_SORT_POLICY_VERSION = "featured-v1"


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
    rank = featured_material_rank(item)
    sort_order = int(float(item.get("sort_order") or item.get("sortOrder") or 0))
    size = float(item.get("size") or 0)
    name = str(item.get("series") or item.get("name") or item.get("category") or "")
    item_id = str(item.get("id") or item.get("skuId") or "")
    return (rank, sort_order, name, size, item_id)


def sort_materials_for_customer(materials: list[dict]) -> list[dict]:
    return sorted(materials, key=material_customer_sort_key)


MATERIAL_CATALOG: list[dict] = [
    {"id": "clearQuartz8", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "喜马拉雅白水晶", "effect": "净化与放大", "element": "金", "price": 5, "size": 8, "weight": 1.2, "color": "#dfe3e5", "shine": "#ffffff", "image_path": "beads/clear-quartz-8.png"},
    {"id": "clearQuartz10", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "喜马拉雅白水晶", "effect": "净化与放大", "element": "金", "price": 10, "size": 10, "weight": 1.6, "color": "#d6dbde", "shine": "#ffffff", "image_path": "beads/clear-quartz-10.png"},
    {"id": "clearQuartz12", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "喜马拉雅白水晶", "effect": "净化与放大", "element": "金", "price": 15, "size": 12, "weight": 2.1, "color": "#cfd5d8", "shine": "#ffffff", "image_path": "beads/clear-quartz-12.png"},
    {"id": "clearQuartz14", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "喜马拉雅白水晶", "effect": "净化与放大", "element": "金", "price": 18, "size": 14, "weight": 2.8, "color": "#c8ced1", "shine": "#ffffff", "image_path": "beads/clear-quartz-14.png"},
    {"id": "amethyst8", "skuId": "amethyst", "top": "bead", "category": "紫水晶", "name": "乌拉圭紫水晶", "effect": "灵感与睡眠", "element": "火", "price": 12, "size": 8, "weight": 1.4, "color": "#8b6aa5", "shine": "#efe8ff", "image_path": "beads/amethyst-8.png"},
    {"id": "amethyst10", "skuId": "amethyst", "top": "bead", "category": "紫水晶", "name": "乌拉圭紫水晶", "effect": "灵感与睡眠", "element": "火", "price": 18, "size": 10, "weight": 1.8, "color": "#76508f", "shine": "#efe8ff", "image_path": "beads/amethyst-10.png"},
    {"id": "citrine8", "skuId": "citrine", "top": "bead", "category": "黄水晶", "name": "巴西黄水晶", "effect": "财富与行动", "element": "土", "price": 16, "size": 8, "weight": 1.5, "color": "#d6ad50", "shine": "#fff0b7", "image_path": "beads/citrine-8.png"},
    {"id": "citrine10", "skuId": "citrine", "top": "bead", "category": "黄水晶", "name": "巴西黄水晶", "effect": "财富与行动", "element": "土", "price": 22, "size": 10, "weight": 1.9, "color": "#c79838", "shine": "#fff0b7", "image_path": "beads/citrine-10.png"},
    {"id": "obsidian10", "skuId": "obsidian", "top": "bead", "category": "曜石", "name": "冰种黑曜石", "effect": "边界与守护", "element": "金", "price": 14, "size": 10, "weight": 1.8, "color": "#262529", "shine": "#aeb2b5", "image_path": "beads/obsidian-10.png"},
    {"id": "tigerEye8", "skuId": "tigerEye", "top": "bead", "category": "虎眼石", "name": "南非虎眼石", "effect": "执行与稳定", "element": "土", "price": 13, "size": 8, "weight": 1.5, "color": "#9b6a2e", "shine": "#f1c06b", "image_path": "beads/tiger-eye-8.png"},
    {"id": "moonstone8", "skuId": "moonstone", "top": "bead", "category": "月光石", "name": "雪花幽灵", "effect": "情绪修复", "element": "水", "price": 8, "size": 8, "weight": 1.2, "color": "#bdc2c1", "shine": "#ffffff", "image_path": "beads/moonstone-8.png"},
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
    {"id": "foxPendant", "skuId": "foxPendant", "top": "pendant", "category": "吊坠", "name": "粉晶狐狸吊坠", "effect": "桃花与礼物", "element": "木", "price": 88, "size": 12, "weight": 2.2, "color": "#d88b91", "shine": "#fff1f3", "image_path": "findings/fox-pendant.png"},
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
    "招财": ["财富", "黄水晶", "黄晶", "金发晶", "钛晶"],
    "助眠": ["睡眠", "月光石", "紫晶"],
}

# The historical fallback catalog above may contain mojibake in older working
# copies. Keep a clean override here so the public materials API never falls
# back to unreadable Chinese when managed_materials is empty or unavailable.
MATERIAL_CATALOG = [
    {"id": "clearQuartz8", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "喜马拉雅白水晶", "effect": "净化与放大", "element": "金", "price": 5, "size": 8, "weight": 1.2, "color": "#dfe3e5", "shine": "#ffffff", "image_path": "beads/clear-quartz-8.png"},
    {"id": "clearQuartz10", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "喜马拉雅白水晶", "effect": "净化与放大", "element": "金", "price": 10, "size": 10, "weight": 1.6, "color": "#d6dbde", "shine": "#ffffff", "image_path": "beads/clear-quartz-10.png"},
    {"id": "clearQuartz12", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "喜马拉雅白水晶", "effect": "净化与放大", "element": "金", "price": 15, "size": 12, "weight": 2.1, "color": "#cfd5d8", "shine": "#ffffff", "image_path": "beads/clear-quartz-12.png"},
    {"id": "clearQuartz14", "skuId": "clearQuartz", "top": "bead", "category": "白水晶", "name": "喜马拉雅白水晶", "effect": "净化与放大", "element": "金", "price": 18, "size": 14, "weight": 2.8, "color": "#c8ced1", "shine": "#ffffff", "image_path": "beads/clear-quartz-14.png"},
    {"id": "amethyst8", "skuId": "amethyst", "top": "bead", "category": "紫水晶", "name": "乌拉圭紫水晶", "effect": "灵感与睡眠", "element": "火", "price": 12, "size": 8, "weight": 1.4, "color": "#8b6aa5", "shine": "#efe8ff", "image_path": "beads/amethyst-8.png"},
    {"id": "amethyst10", "skuId": "amethyst", "top": "bead", "category": "紫水晶", "name": "乌拉圭紫水晶", "effect": "灵感与睡眠", "element": "火", "price": 18, "size": 10, "weight": 1.8, "color": "#76508f", "shine": "#efe8ff", "image_path": "beads/amethyst-10.png"},
    {"id": "citrine8", "skuId": "citrine", "top": "bead", "category": "黄水晶", "name": "巴西黄水晶", "effect": "财富与行动", "element": "土", "price": 16, "size": 8, "weight": 1.5, "color": "#d6ad50", "shine": "#fff0b7", "image_path": "beads/citrine-8.png"},
    {"id": "citrine10", "skuId": "citrine", "top": "bead", "category": "黄水晶", "name": "巴西黄水晶", "effect": "财富与行动", "element": "土", "price": 22, "size": 10, "weight": 1.9, "color": "#c79838", "shine": "#fff0b7", "image_path": "beads/citrine-10.png"},
    {"id": "obsidian10", "skuId": "obsidian", "top": "bead", "category": "曜石", "name": "冰种黑曜石", "effect": "边界与守护", "element": "金", "price": 14, "size": 10, "weight": 1.8, "color": "#262529", "shine": "#aeb2b5", "image_path": "beads/obsidian-10.png"},
    {"id": "tigerEye8", "skuId": "tigerEye", "top": "bead", "category": "虎眼石", "name": "南非虎眼石", "effect": "执行与稳定", "element": "土", "price": 13, "size": 8, "weight": 1.5, "color": "#9b6a2e", "shine": "#f1c06b", "image_path": "beads/tiger-eye-8.png"},
    {"id": "moonstone8", "skuId": "moonstone", "top": "bead", "category": "月光石", "name": "雪花幽灵", "effect": "情绪修复", "element": "水", "price": 8, "size": 8, "weight": 1.2, "color": "#bdc2c1", "shine": "#ffffff", "image_path": "beads/moonstone-8.png"},
    {"id": "aquamarine8", "skuId": "aquamarine", "top": "bead", "category": "海蓝宝", "name": "巴西海蓝宝", "effect": "沟通与平静", "element": "水", "price": 25, "size": 8, "weight": 1.4, "color": "#80b8c5", "shine": "#e8fbff", "image_path": "beads/aquamarine-8.png"},
    {"id": "blueRutilatedQuartz10", "skuId": "blueRutilatedQuartz", "top": "bead", "category": "蓝发晶", "name": "蓝发晶", "effect": "冷静与洞察", "element": "水", "price": 38, "size": 10, "weight": 1.9, "color": "#4f789b", "shine": "#dcecf3", "image_path": "beads/blue-rutilated-quartz-10.png"},
    {"id": "garnet8", "skuId": "garnet", "top": "bead", "category": "石榴石", "name": "石榴石", "effect": "活力与自信", "element": "火", "price": 18, "size": 8, "weight": 1.5, "color": "#8e2635", "shine": "#e7a1aa", "image_path": "beads/garnet-8.png"},
    {"id": "turquoise6", "skuId": "turquoise", "top": "bead", "category": "绿松石", "name": "绿松石", "effect": "生机与恢复", "element": "木", "price": 16, "size": 6, "weight": 0.9, "color": "#56a6a2", "shine": "#d7f1ef", "image_path": "beads/turquoise-6.png"},
    {"id": "greenPhantom8", "skuId": "greenPhantom", "top": "bead", "category": "绿幽灵", "name": "绿幽灵", "effect": "生长与专注", "element": "木", "price": 24, "size": 8, "weight": 1.4, "color": "#4a825f", "shine": "#d7eadc", "image_path": "beads/green-phantom-8.png"},
    {"id": "roseQuartz8", "skuId": "roseQuartz", "top": "bead", "category": "粉水晶", "name": "马达加斯加粉晶", "effect": "人缘与亲密", "element": "木", "price": 11, "size": 8, "weight": 1.3, "color": "#e0a3a8", "shine": "#fff1f3", "image_path": "beads/rose-quartz-8.png"},
    {"id": "silverSpacer", "skuId": "silverSpacer", "top": "accessory", "category": "隔片", "name": "925 银隔片", "effect": "结构与光泽", "element": "金", "price": 18, "size": 3, "weight": 0.4, "color": "#b9bdc2", "shine": "#ffffff", "image_path": "accessories/silver-spacer.png"},
    {"id": "goldSpacer", "skuId": "goldSpacer", "top": "accessory", "category": "隔片", "name": "鎏金隔片", "effect": "礼物感", "element": "土", "price": 16, "size": 3, "weight": 0.4, "color": "#c99d4d", "shine": "#fff0b7", "image_path": "accessories/gold-spacer.png"},
    {"id": "lotusCap", "skuId": "lotusCap", "top": "pendant", "category": "花托", "name": "莲纹花托", "effect": "收束主石", "element": "金", "price": 22, "size": 6, "weight": 0.6, "color": "#c4b29a", "shine": "#fff8eb", "image_path": "findings/lotus-cap.png"},
    {"id": "foxPendant", "skuId": "foxPendant", "top": "pendant", "category": "吊坠", "name": "粉晶狐狸吊坠", "effect": "桃花与礼物", "element": "木", "price": 88, "size": 12, "weight": 2.2, "color": "#d88b91", "shine": "#fff1f3", "image_path": "findings/fox-pendant.png"},
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
    "招财": ["财富", "黄水晶", "黄晶", "金发晶", "钛晶"],
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


def with_cdn_url(item: dict) -> dict:
    image_url = normalize_material_image_url(item.get("image_url")) or material_url_from_path(item.get("image_path"))
    image_urls = clean_image_urls(item.get("image_urls"), image_url, item.get("image_path") or "")
    return {
        **item,
        "image_url": image_url or (image_urls[0] if image_urls else ""),
        "image_urls": image_urls,
        "image_pool": image_urls,
    }


def list_materials(
    top: str | None = None,
    keyword: str | None = None,
    compact: bool = False,
    limit: int | None = None,
) -> dict:
    version = material_catalog_version()
    cache_key = (top or "", keyword or "", bool(compact), int(limit or 0), version.get("version", ""))
    cached = _MATERIAL_PAYLOAD_CACHE.get(cache_key)
    if cached and time.time() - cached.get("_cached_at", 0) < MATERIAL_CACHE_TTL_SECONDS:
        return {k: v for k, v in cached.items() if k != "_cached_at"}

    db_materials = list_db_materials(top=top, keyword=keyword, limit=limit)
    if db_materials is not None:
        if compact:
            return {"materials": db_materials}
        payload = build_material_payload(db_materials, version)
        _MATERIAL_PAYLOAD_CACHE[cache_key] = {**payload, "_cached_at": time.time()}
        return payload

    materials = filter_static_materials(top=top, keyword=keyword)
    if limit:
        materials = materials[:limit]
    if compact:
        return {"materials": materials}
    payload = build_material_payload(materials, version)
    _MATERIAL_PAYLOAD_CACHE[cache_key] = {**payload, "_cached_at": time.time()}
    return payload


def filter_static_materials(top: str | None = None, keyword: str | None = None) -> list[dict]:
    search_terms = [item.lower() for item in expand_search_terms(keyword)]
    materials = []
    for item in MATERIAL_CATALOG:
        if top and item["top"] != top:
            continue
        haystack = " ".join(
            str(item.get(key, ""))
            for key in ["id", "skuId", "category", "series", "grade", "name", "effect", "element"]
        ).lower()
        if search_terms and not any(term in haystack for term in search_terms):
            continue
        materials.append(with_cdn_url(item))
    return sort_materials_for_customer(materials)


def build_material_payload(materials: list[dict], version: dict | None = None) -> dict:
    categories_by_top = {}
    series_by_category = {}
    for tab in TOP_TABS:
        db_pool = list_db_materials(top=tab["key"], keyword=None)
        pool = db_pool if db_pool is not None else [item for item in MATERIAL_CATALOG if item["top"] == tab["key"]]
        categories_by_top[tab["key"]] = ["全部", *sorted({item["category"] for item in pool})]
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
            key: ["全部", *sorted(values)]
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
    except Exception:
        return {"version": f"static-v1:{MATERIAL_SORT_POLICY_VERSION}", "updated_at": ""}
    total = int(row["total"] or 0)
    updated_at = str(row["updated_at"] or "")
    return {"version": f"{total}:{updated_at}:{MATERIAL_SORT_POLICY_VERSION}", "updated_at": updated_at}


def list_db_materials(
    top: str | None = None,
    keyword: str | None = None,
    limit: int | None = None,
) -> list[dict] | None:
    try:
        from .repository import DB_PATH
    except Exception:
        return None
    if not use_mysql() and not DB_PATH.exists():
        return None
    clauses = ["enabled = 1"]
    params: list[str] = []
    if top:
        clauses.append("top = ?")
        params.append(top)
    search_terms = expand_search_terms(keyword)
    if search_terms:
        fields = ["name", "category", "series", "grade", "effect", "element", "skuId"]
        term_clauses = []
        for term in search_terms:
            term_clauses.append("(" + " OR ".join(f"{field} LIKE ?" for field in fields) + ")")
            params.extend([f"%{term}%"] * len(fields))
        clauses.append("(" + " OR ".join(term_clauses) + ")")
    try:
        with connect_database() as connection:
            sql = f"SELECT * FROM managed_materials WHERE {' AND '.join(clauses)} ORDER BY sort_order ASC, updated_at DESC"
            rows = connection.execute(sql, params).fetchall()
    except Exception:
        return None
    materials = sort_materials_for_customer([normalize_db_material(dict(row)) for row in rows])
    if limit:
        materials = materials[:limit]
    return materials


def normalize_db_material(row: dict) -> dict:
    image_url = normalize_material_image_url(row.get("image_url") or "")
    image_path = row.get("image_path") or ""
    if image_path:
        normalized_path = normalize_material_image_path(image_path)
        old_suffix = f"/materials/{normalized_path}"
        if not image_url or "cdn.yustream.cn/materials/" in image_url or image_url.endswith(old_suffix):
            image_url = material_url_from_path(image_path)
    image_urls = clean_image_urls(
        row.get("image_urls_json") or row.get("image_urls"),
        image_url,
        image_path,
    )
    if not image_url and image_urls:
        image_url = image_urls[0]
    return {
        **row,
        "enabled": bool(row.get("enabled", 1)),
        "series": row.get("series") or row.get("name") or "",
        "grade": row.get("grade") or "",
        "image_url": image_url,
        "image_urls": image_urls,
        "image_pool": image_urls,
    }
