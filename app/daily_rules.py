from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .energy import ELEMENTS

DAILY_RULES_SETTING_KEY = "daily_energy_rules"


DEFAULT_DAILY_ENERGY_RULES: dict[str, Any] = {
    "schema_version": 1,
    "content_version": 3,
    "scoring": {
        "starter_base": 66,
        "personalized_base": 68,
        "starter_weights": {"date": 0.30, "status": 0.30, "scene": 0.15, "goal": 0.25},
        "personalized_weights": {"personal_need": 0.35, "date": 0.20, "status": 0.20, "scene": 0.10, "goal": 0.15},
        "min_score": 42,
        "max_score": 96,
    },
    "element_crystal_pool": {
        "金": ["hematite", "clear_quartz", "titanium_quartz"],
        "木": ["green_phantom", "turquoise", "rose_quartz"],
        "水": ["aquamarine", "blue_rutilated_quartz", "obsidian"],
        "火": ["garnet", "strawberry_quartz", "rhodochrosite"],
        "土": ["smoky_quartz", "citrine", "gold_rutilated_quartz"],
    },
    "status_groups": [
        {"key": "emotion", "label": "情绪与心理"},
        {"key": "energy", "label": "精力与行动"},
        {"key": "social", "label": "人际与社交"},
        {"key": "fortune", "label": "搞钱与运势"},
    ],
    "status_tags": [
        {"key": "pressure", "label": "压力山大", "emoji": "🤯", "group": "emotion", "desc": "脑子太满，需要降噪", "support_elements": ["水", "土"], "dimension_delta": {"softness": 8, "stability": 6}, "score_delta": -5, "crystal_codes": ["aquamarine", "smoky_quartz"], "keywords": ["降噪", "稳住"]},
        {"key": "emo", "label": "随时 EMO", "emoji": "🌧️", "group": "emotion", "desc": "情绪起伏，需要被接住", "support_elements": ["水", "木"], "dimension_delta": {"softness": 10, "intuition": 4}, "score_delta": -4, "crystal_codes": ["aquamarine", "rose_quartz"], "keywords": ["柔和", "抱抱自己"]},
        {"key": "calm", "label": "平静", "emoji": "🫧", "group": "emotion", "desc": "状态稳定，可以轻推进", "support_elements": ["金", "土"], "dimension_delta": {"stability": 8}, "score_delta": 5, "crystal_codes": ["clear_quartz", "smoky_quartz"], "keywords": ["清透", "稳定"]},
        {"key": "angry", "label": "暴躁", "emoji": "🔥", "group": "emotion", "desc": "火气偏强，需要柔化", "support_elements": ["水", "金"], "dimension_delta": {"softness": 9, "expression": -2}, "score_delta": -3, "crystal_codes": ["aquamarine", "clear_quartz"], "keywords": ["降火", "少硬刚"]},
        {"key": "lost", "label": "迷茫", "emoji": "🌫️", "group": "emotion", "desc": "方向感弱，先整理优先级", "support_elements": ["金", "土"], "dimension_delta": {"stability": 5, "intuition": 3}, "score_delta": -2, "crystal_codes": ["clear_quartz", "hematite"], "keywords": ["清晰", "边界"]},
        {"key": "hug", "label": "抱抱自己", "emoji": "🕊️", "group": "emotion", "desc": "需要温柔修复", "support_elements": ["木", "水"], "dimension_delta": {"softness": 8}, "score_delta": 1, "crystal_codes": ["rose_quartz", "aquamarine"], "keywords": ["修复", "陪伴"]},
        {"key": "battery_low", "label": "电量告急", "emoji": "🔋", "group": "energy", "desc": "能量偏低，先省电", "support_elements": ["土", "水"], "dimension_delta": {"stability": 6, "action": -4}, "score_delta": -6, "crystal_codes": ["smoky_quartz", "aquamarine"], "keywords": ["省电模式", "慢慢来"]},
        {"key": "internal_loss", "label": "严重内耗", "emoji": "🥱", "group": "energy", "desc": "想太多，行动太少", "support_elements": ["金", "土"], "dimension_delta": {"stability": 8, "action": 3}, "score_delta": -4, "crystal_codes": ["hematite", "clear_quartz"], "keywords": ["少纠结", "先落地"]},
        {"key": "procrastinate", "label": "拖延晚期", "emoji": "⏳", "group": "energy", "desc": "需要一点推进力", "support_elements": ["火", "土"], "dimension_delta": {"action": 9, "stability": 3}, "score_delta": -1, "crystal_codes": ["garnet", "citrine"], "keywords": ["启动", "交付"]},
        {"key": "need_focus", "label": "需要专注", "emoji": "🎯", "group": "energy", "desc": "适合减少干扰", "support_elements": ["金", "水"], "dimension_delta": {"stability": 6, "intuition": 3}, "score_delta": 2, "crystal_codes": ["clear_quartz", "obsidian"], "keywords": ["专注", "屏蔽噪音"]},
        {"key": "inspiration_low", "label": "灵感枯竭", "emoji": "💡", "group": "energy", "desc": "先输入，再输出", "support_elements": ["水", "木"], "dimension_delta": {"intuition": 8, "softness": 3}, "score_delta": -3, "crystal_codes": ["blue_rutilated_quartz", "green_phantom"], "keywords": ["灵感", "流动"]},
        {"key": "full_power", "label": "满血复活", "emoji": "🚀", "group": "energy", "desc": "适合推进关键动作", "support_elements": ["火", "木"], "dimension_delta": {"action": 10, "expression": 4}, "score_delta": 8, "crystal_codes": ["garnet", "green_phantom"], "keywords": ["冲刺", "生长"]},
        {"key": "social_anxiety", "label": "社恐发作", "emoji": "🙈", "group": "social", "desc": "保持边界，低压社交", "support_elements": ["水", "金"], "dimension_delta": {"softness": 6, "expression": -3}, "score_delta": -3, "crystal_codes": ["aquamarine", "hematite"], "keywords": ["低压社交", "边界"]},
        {"key": "charm", "label": "散发魅力", "emoji": "🧲", "group": "social", "desc": "适合展示与见面", "support_elements": ["火", "木"], "dimension_delta": {"expression": 9, "softness": 3}, "score_delta": 6, "crystal_codes": ["strawberry_quartz", "rose_quartz"], "keywords": ["好人缘", "发光"]},
        {"key": "protect", "label": "自动退散", "emoji": "🛡️", "group": "social", "desc": "不想被打扰，需要防护感", "support_elements": ["水", "金"], "dimension_delta": {"stability": 5, "softness": 4}, "score_delta": 0, "crystal_codes": ["obsidian", "hematite"], "keywords": ["防护", "退退退"]},
        {"key": "peach", "label": "桃花绝缘体", "emoji": "🌸", "group": "social", "desc": "想让关系更柔和", "support_elements": ["木", "火"], "dimension_delta": {"softness": 6, "expression": 5}, "score_delta": 2, "crystal_codes": ["rose_quartz", "rhodochrosite"], "keywords": ["桃花", "柔和"]},
        {"key": "noble", "label": "求贵人", "emoji": "🤝", "group": "social", "desc": "需要被看见与支持", "support_elements": ["木", "金"], "dimension_delta": {"expression": 5, "stability": 4}, "score_delta": 3, "crystal_codes": ["green_phantom", "clear_quartz"], "keywords": ["贵人", "协作"]},
        {"key": "money", "label": "一心搞钱", "emoji": "💰", "group": "fortune", "desc": "目标明确，适合稳步变现", "support_elements": ["土", "金"], "dimension_delta": {"action": 6, "stability": 6}, "score_delta": 5, "crystal_codes": ["citrine", "gold_rutilated_quartz"], "keywords": ["搞钱", "落袋"]},
        {"key": "career", "label": "搞事业", "emoji": "💼", "group": "fortune", "desc": "适合推进工作成果", "support_elements": ["火", "土"], "dimension_delta": {"action": 8, "stability": 4}, "score_delta": 4, "crystal_codes": ["garnet", "citrine"], "keywords": ["事业", "推进"]},
        {"key": "lucky", "label": "锦鲤本鲤", "emoji": "🐟", "group": "fortune", "desc": "想要一点好运气", "support_elements": ["水", "木"], "dimension_delta": {"intuition": 5, "softness": 3}, "score_delta": 5, "crystal_codes": ["aquamarine", "green_phantom"], "keywords": ["好运", "顺流"]},
        {"key": "exam", "label": "逢考必过", "emoji": "📚", "group": "fortune", "desc": "需要专注和稳定输出", "support_elements": ["金", "水"], "dimension_delta": {"stability": 8, "intuition": 4}, "score_delta": 3, "crystal_codes": ["clear_quartz", "blue_rutilated_quartz"], "keywords": ["考试", "清醒"]},
        {"key": "anti_mercury", "label": "水逆退散", "emoji": "🧿", "group": "fortune", "desc": "减少沟通误会与突发干扰", "support_elements": ["水", "金"], "dimension_delta": {"softness": 6, "expression": 3}, "score_delta": 1, "crystal_codes": ["obsidian", "clear_quartz"], "keywords": ["顺一点", "少踩坑"]},
    ],
    "scenes": [
        {"key": "work_comm", "label": "上班沟通", "icon": "💼", "desc": "会议、客户、协作", "element_bias": {"水": 18, "金": 10}, "dimension_delta": {"expression": 8, "stability": 3}, "score_delta": 2, "crystal_codes": ["aquamarine", "clear_quartz"], "wearing_scenes": ["上班沟通", "见客户", "直播表达"]},
        {"key": "light_social", "label": "轻社交", "icon": "👥", "desc": "见朋友、轻松互动", "element_bias": {"木": 16, "火": 10}, "dimension_delta": {"softness": 5, "expression": 7}, "score_delta": 3, "crystal_codes": ["rose_quartz", "strawberry_quartz"], "wearing_scenes": ["轻社交", "约会见面"]},
        {"key": "study_focus", "label": "学习专注", "icon": "📖", "desc": "学习、复盘、整理", "element_bias": {"金": 18, "水": 8}, "dimension_delta": {"stability": 8, "intuition": 3}, "score_delta": 2, "crystal_codes": ["clear_quartz", "blue_rutilated_quartz"], "wearing_scenes": ["学习专注", "考试复习"]},
        {"key": "rest_restore", "label": "休息修复", "icon": "🌿", "desc": "低压、补能、睡前", "element_bias": {"水": 16, "土": 12}, "dimension_delta": {"softness": 9, "stability": 4, "action": -3}, "score_delta": -1, "crystal_codes": ["aquamarine", "smoky_quartz"], "wearing_scenes": ["休息修复", "睡前整理"]},
        {"key": "live_expression", "label": "直播表达", "icon": "🎙️", "desc": "输出、展示、表达", "element_bias": {"火": 18, "水": 10}, "dimension_delta": {"expression": 10, "action": 4}, "score_delta": 4, "crystal_codes": ["garnet", "aquamarine"], "wearing_scenes": ["直播表达", "公开展示"]},
        {"key": "important_meeting", "label": "重要会议", "icon": "🧭", "desc": "结论清晰，边界稳定", "element_bias": {"金": 18, "土": 12}, "dimension_delta": {"stability": 8, "expression": 4}, "score_delta": 3, "crystal_codes": ["hematite", "clear_quartz"], "wearing_scenes": ["重要会议", "谈判沟通"]},
        {"key": "deadline", "label": "赶工交付", "icon": "⚡", "desc": "别纠结，先交付", "element_bias": {"火": 16, "土": 12}, "dimension_delta": {"action": 9, "stability": 4}, "score_delta": 2, "crystal_codes": ["garnet", "smoky_quartz"], "wearing_scenes": ["赶工交付", "推进任务"]},
        {"key": "home_clear", "label": "居家整理", "icon": "🏠", "desc": "收纳、断舍离、复位", "element_bias": {"土": 18, "金": 8}, "dimension_delta": {"stability": 9}, "score_delta": 2, "crystal_codes": ["smoky_quartz", "clear_quartz"], "wearing_scenes": ["居家整理", "空间清理"]},
    ],
    "goals": [
        {"key": "stable_expression", "label": "稳定表达", "wish": "正缘桃花/人际和合", "target_elements": ["水", "火"], "dimension_delta": {"expression": 9, "softness": 4}, "score_delta": 3, "crystal_codes": ["aquamarine", "garnet"], "keywords": ["表达", "沟通"]},
        {"key": "less_overthinking", "label": "减少内耗", "wish": "健康护身/保持专注", "target_elements": ["金", "土"], "dimension_delta": {"stability": 8, "softness": 4}, "score_delta": 1, "crystal_codes": ["clear_quartz", "smoky_quartz"], "keywords": ["少内耗", "稳住"]},
        {"key": "move_task", "label": "推进任务", "wish": "招财进宝/事业腾飞", "target_elements": ["火", "土"], "dimension_delta": {"action": 10, "stability": 3}, "score_delta": 4, "crystal_codes": ["garnet", "citrine"], "keywords": ["推进", "交付"]},
        {"key": "low_pressure_protect", "label": "低压防护", "wish": "辟邪防小人/消除焦虑", "target_elements": ["水", "金"], "dimension_delta": {"softness": 7, "stability": 5}, "score_delta": 0, "crystal_codes": ["obsidian", "hematite"], "keywords": ["防护", "低压"]},
        {"key": "wealth", "label": "招正财", "wish": "招财进宝/事业腾飞", "target_elements": ["土", "金"], "dimension_delta": {"stability": 6, "action": 5}, "score_delta": 3, "crystal_codes": ["citrine", "gold_rutilated_quartz"], "keywords": ["正财", "稳进账"]},
        {"key": "good_luck", "label": "求好运", "wish": "招财进宝/事业腾飞", "target_elements": ["水", "木"], "dimension_delta": {"intuition": 6, "softness": 3}, "score_delta": 4, "crystal_codes": ["aquamarine", "green_phantom"], "keywords": ["好运", "顺流"]},
        {"key": "relationship", "label": "提升人缘", "wish": "正缘桃花/人际和合", "target_elements": ["木", "火"], "dimension_delta": {"expression": 7, "softness": 5}, "score_delta": 3, "crystal_codes": ["rose_quartz", "strawberry_quartz"], "keywords": ["人缘", "亲和"]},
        {"key": "inspiration", "label": "提升灵感", "wish": "健康护身/保持专注", "target_elements": ["水", "木"], "dimension_delta": {"intuition": 10}, "score_delta": 2, "crystal_codes": ["blue_rutilated_quartz", "green_phantom"], "keywords": ["灵感", "创意"]},
        {"key": "sleep_restore", "label": "修复睡眠", "wish": "健康护身/保持专注", "target_elements": ["水", "土"], "dimension_delta": {"softness": 8, "stability": 3}, "score_delta": -1, "crystal_codes": ["aquamarine", "smoky_quartz"], "keywords": ["睡眠", "修复"]},
        {"key": "clear_boundary", "label": "清理边界", "wish": "辟邪防小人/消除焦虑", "target_elements": ["金", "水"], "dimension_delta": {"stability": 8, "expression": 2}, "score_delta": 2, "crystal_codes": ["hematite", "obsidian"], "keywords": ["边界", "清理"]},
    ],
}


def default_daily_energy_rules() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_DAILY_ENERGY_RULES)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _valid_elements(values: Any) -> list[str]:
    return [str(item) for item in _as_list(values) if str(item) in ELEMENTS]


def _number_map(value: Any, allowed_keys: set[str] | None = None) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key, raw in value.items():
        if allowed_keys is not None and key not in allowed_keys:
            continue
        try:
            result[str(key)] = float(raw)
        except (TypeError, ValueError):
            continue
    return result


def normalize_daily_energy_rules(raw: Any | None) -> dict[str, Any]:
    """Merge operator-maintained rules with safe defaults.

    The admin UI can edit the whole JSON. This normalizer keeps unknown optional
    fields out of the calculation path, so a typo in one rule does not break the
    daily-energy API for users.
    """
    base = copy.deepcopy(DEFAULT_DAILY_ENERGY_RULES)
    if not isinstance(raw, dict):
        raw = copy.deepcopy(DEFAULT_DAILY_ENERGY_RULES)

    merged = copy.deepcopy(base)
    if isinstance(raw.get("scoring"), dict):
        merged["scoring"].update(raw["scoring"])
    if isinstance(raw.get("element_crystal_pool"), dict):
        for element, codes in raw["element_crystal_pool"].items():
            if element in ELEMENTS:
                merged["element_crystal_pool"][element] = [str(code) for code in _as_list(codes) if str(code)]
    if isinstance(raw.get("status_groups"), list):
        merged["status_groups"] = [
            {"key": str(item.get("key") or ""), "label": str(item.get("label") or item.get("key") or "")}
            for item in raw["status_groups"]
            if isinstance(item, dict) and item.get("key")
        ] or merged["status_groups"]

    def normalize_rule(item: dict[str, Any], kind: str) -> dict[str, Any] | None:
        key = str(item.get("key") or "").strip()
        label = str(item.get("label") or "").strip()
        if not key or not label:
            return None
        result = {
            "key": key,
            "label": label,
            "emoji": str(item.get("emoji") or item.get("icon") or ""),
            "icon": str(item.get("icon") or item.get("emoji") or ""),
            "group": str(item.get("group") or ""),
            "desc": str(item.get("desc") or ""),
            "score_delta": float(item.get("score_delta") or 0),
            "dimension_delta": _number_map(item.get("dimension_delta")),
            "crystal_codes": [str(code) for code in _as_list(item.get("crystal_codes")) if str(code)],
            "keywords": [str(word) for word in _as_list(item.get("keywords")) if str(word)],
        }
        if kind == "status":
            result["support_elements"] = _valid_elements(item.get("support_elements") or item.get("target_elements"))
        elif kind == "scene":
            result["element_bias"] = _number_map(item.get("element_bias"), set(ELEMENTS))
            result["wearing_scenes"] = [str(scene) for scene in _as_list(item.get("wearing_scenes")) if str(scene)]
        else:
            result["target_elements"] = _valid_elements(item.get("target_elements") or item.get("support_elements"))
            result["wish"] = str(item.get("wish") or "")
        return result

    for source_key, kind in (("status_tags", "status"), ("scenes", "scene"), ("goals", "goal")):
        if isinstance(raw.get(source_key), list):
            normalized = [normalize_rule(item, kind) for item in raw[source_key] if isinstance(item, dict)]
            normalized = [item for item in normalized if item]
            if normalized:
                merged[source_key] = normalized
    return merged


def daily_rules_version(rules: dict[str, Any]) -> str:
    payload = json.dumps(rules, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def public_daily_rules_payload(rules: dict[str, Any]) -> dict[str, Any]:
    return {
        "content_version": int(rules.get("content_version") or 3),
        "rules_version": daily_rules_version(rules),
        "status_groups": rules.get("status_groups") or [],
        "status_tags": [
            {
                "key": item.get("key"),
                "label": item.get("label"),
                "emoji": item.get("emoji") or item.get("icon") or "",
                "group": item.get("group") or "",
                "desc": item.get("desc") or "",
            }
            for item in rules.get("status_tags", [])
        ],
        "scenes": [
            {
                "key": item.get("key"),
                "label": item.get("label"),
                "icon": item.get("icon") or item.get("emoji") or "",
                "desc": item.get("desc") or "",
            }
            for item in rules.get("scenes", [])
        ],
        "goals": [
            {
                "key": item.get("key"),
                "label": item.get("label"),
                "wish": item.get("wish") or "",
            }
            for item in rules.get("goals", [])
        ],
    }
