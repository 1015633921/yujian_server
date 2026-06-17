from __future__ import annotations

import sqlite3

CDN_BASE_URL = "https://cdn.yustream.cn/materials"


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
    {"key": "incense", "label": "合香珠"},
    {"key": "pendant", "label": "花托"},
]


def with_cdn_url(item: dict) -> dict:
    return {**item, "image_url": f"{CDN_BASE_URL}/{item['image_path']}"}


def list_materials(top: str | None = None, keyword: str | None = None) -> dict:
    db_materials = list_db_materials(top=top, keyword=keyword)
    if db_materials is not None:
        return build_material_payload(db_materials)

    return build_material_payload(filter_static_materials(top=top, keyword=keyword))


def filter_static_materials(top: str | None = None, keyword: str | None = None) -> list[dict]:
    keyword_normalized = (keyword or "").strip().lower()
    materials = []
    for item in MATERIAL_CATALOG:
        if top and item["top"] != top:
            continue
        haystack = " ".join(
            str(item.get(key, ""))
            for key in ["id", "skuId", "category", "series", "grade", "name", "effect", "element"]
        ).lower()
        if keyword_normalized and keyword_normalized not in haystack:
            continue
        materials.append(with_cdn_url(item))
    return materials


def build_material_payload(materials: list[dict]) -> dict:
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
        "cdn_base_url": CDN_BASE_URL,
        "top_tabs": TOP_TABS,
        "categories_by_top": categories_by_top,
        "series_by_category": {
            key: ["全部", *sorted(values)]
            for key, values in series_by_category.items()
        },
        "materials": materials,
    }


def list_db_materials(top: str | None = None, keyword: str | None = None) -> list[dict] | None:
    try:
        from .repository import DB_PATH
    except Exception:
        return None
    if not DB_PATH.exists():
        return None
    clauses = ["enabled = 1"]
    params: list[str] = []
    if top:
        clauses.append("top = ?")
        params.append(top)
    if (keyword or "").strip():
        value = f"%{keyword.strip()}%"
        clauses.append("(name LIKE ? OR category LIKE ? OR series LIKE ? OR grade LIKE ? OR effect LIKE ? OR element LIKE ? OR skuId LIKE ?)")
        params.extend([value, value, value, value, value, value, value])
    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"SELECT * FROM managed_materials WHERE {' AND '.join(clauses)} ORDER BY sort_order ASC, updated_at DESC",
                params,
            ).fetchall()
    except sqlite3.Error:
        return None
    return [normalize_db_material(dict(row)) for row in rows]


def normalize_db_material(row: dict) -> dict:
    image_url = row.get("image_url") or ""
    image_path = row.get("image_path") or ""
    if not image_url and image_path:
        image_url = f"{CDN_BASE_URL}/{image_path}"
    return {
        **row,
        "enabled": bool(row.get("enabled", 1)),
        "series": row.get("series") or row.get("name") or "",
        "grade": row.get("grade") or "",
        "image_url": image_url,
    }
