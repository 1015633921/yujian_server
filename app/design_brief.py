"""Deterministic translation from an assessment snapshot to a designer brief.

This module intentionally produces design language and constraints, not an
automatic bracelet or a claim about a material's effect.  It is safe to use on
the admin and customer service surfaces because it only accepts the already
sanitised report projection.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


BRIEF_SCHEMA_VERSION = 1
BRIEF_RULE_VERSION = "design-brief-2026-08-v1"


COLOR_LIBRARY = {
    "clear": {"label": "清透", "hex": "#EAF2F2"},
    "white": {"label": "月光白", "hex": "#F2F1EA"},
    "gray": {"label": "银灰", "hex": "#BFC5C6"},
    "blue": {"label": "雾蓝", "hex": "#A8C2D1"},
    "green": {"label": "雾绿", "hex": "#A8C5AE"},
    "pink": {"label": "柔粉", "hex": "#E8BDC4"},
    "purple": {"label": "浅紫", "hex": "#BDAED1"},
    "gold": {"label": "柔金", "hex": "#D5B36B"},
    "red": {"label": "暖红", "hex": "#C97767"},
    "orange": {"label": "蜜橙", "hex": "#DE9A62"},
    "yellow": {"label": "浅黄", "hex": "#E0CF98"},
    "brown": {"label": "暖棕", "hex": "#A77B5C"},
    "black": {"label": "深色", "hex": "#343735"},
}

ELEMENT_VISUALS = {
    "木": {"baseline": "舒展自然", "colors": ["green", "blue", "white"], "texture": ["清透", "自然内含", "低饱和"], "structure": "留白、疏密有序、线条舒展"},
    "火": {"baseline": "明亮有焦点", "colors": ["red", "orange", "gold"], "texture": ["温润", "适度光泽"], "structure": "一个焦点、节奏利落、少量提亮"},
    "土": {"baseline": "稳定温润", "colors": ["white", "yellow", "brown"], "texture": ["温润", "柔和", "有质感"], "structure": "重心稳定、排列有序、圆润过渡"},
    "金": {"baseline": "干净利落", "colors": ["white", "gray", "clear"], "texture": ["通透", "干净", "细腻"], "structure": "比例清晰、适度规整、少量留白"},
    "水": {"baseline": "安静流动", "colors": ["blue", "white", "gray"], "texture": ["清透", "柔和", "流动光泽"], "structure": "圆润过渡、层次柔和、节奏舒缓"},
}

STYLE_PROFILES = {
    "清透自然": {
        "colors": ["clear", "white", "blue", "green"],
        "texture": ["清透", "低饱和", "自然内含"],
        "structure": "一个视觉主角，稳定对称或柔和渐变，保留呼吸感",
        "max_materials": 3,
        "max_accessories": 2,
    },
    "高级极简": {
        "colors": ["white", "gray", "clear"],
        "texture": ["干净", "通透", "低对比"],
        "structure": "一个视觉主角，邻近色或单色，避免复杂隔片",
        "max_materials": 2,
        "max_accessories": 1,
    },
    "温柔治愈": {
        "colors": ["pink", "white", "purple"],
        "texture": ["柔和", "温润", "低对比"],
        "structure": "圆润、低对比、柔和过渡，避免多个强焦点",
        "max_materials": 3,
        "max_accessories": 2,
    },
    "东方禅意": {
        "colors": ["white", "brown", "green"],
        "texture": ["温润", "自然纹理", "克制"],
        "structure": "稳定重心、分段有序、少量点缀",
        "max_materials": 3,
        "max_accessories": 2,
    },
}

COLOR_ALIASES = {
    "透明": "clear", "清透": "clear", "冰透": "clear", "蓝": "blue", "雾蓝": "blue", "蓝白": "blue",
    "白": "white", "月光白": "white", "米白": "white", "银": "gray", "灰": "gray", "银灰": "gray",
    "绿": "green", "雾绿": "green", "粉": "pink", "紫": "purple", "金": "gold", "黄": "yellow",
    "棕": "brown", "红": "red", "橙": "orange", "黑": "black", "深色": "black",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        clean = _text(value)
        if clean and clean not in result:
            result.append(clean)
    return result


def _string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            if isinstance(item, dict):
                result.append(_text(item.get("label") or item.get("name") or item.get("value")))
            else:
                result.append(_text(item))
        return _unique(result)
    return _unique(re.split(r"[、,，/;；|]+", _text(value)))


def _measure(value: Any, unit: str) -> str:
    if value in (None, ""):
        return "待确认"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return f"{_text(value)} {unit}".strip()
    number = str(int(numeric)) if numeric.is_integer() else f"{numeric:.1f}".rstrip("0").rstrip(".")
    return f"{number} {unit}"


def _colors(keys: list[str], *, reason: str, source: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for key in _unique(keys):
        color = COLOR_LIBRARY.get(key)
        if color:
            result.append({"key": key, **color, "reason": reason, "source": source})
    return result


def _color_keys_from_text(value: Any) -> list[str]:
    text = _text(value).lower()
    if not text:
        return []
    matches: list[str] = []
    for token, key in COLOR_ALIASES.items():
        if token in text:
            matches.append(key)
    return _unique(matches)


def _balance_intervention(score: Any) -> dict[str, str | int]:
    try:
        normalized = max(0, min(100, round(float(score))))
    except (TypeError, ValueError):
        normalized = 0
    if normalized >= 85:
        return {
            "level": "aesthetic_first",
            "label": "审美优先",
            "score": normalized,
            "reason": "元素分布接近，以用户审美、佩戴场景和预算优先，不强行补某一方向。",
        }
    if normalized >= 70:
        return {
            "level": "light",
            "label": "轻度调和",
            "score": normalized,
            "reason": "第一调整方向用于辅材或过渡，保持整体自然克制。",
        }
    if normalized >= 55:
        return {
            "level": "moderate",
            "label": "明确调和",
            "score": normalized,
            "reason": "第一调整方向可承担重要辅材；用中性材料维持整体统一。",
        }
    return {
        "level": "focused",
        "label": "重点调和",
        "score": normalized,
        "reason": "先以清透或中性色建立基底，再有节制地体现主要调整方向，避免堆叠成多色串。",
    }


def _adjustment_directions(report: dict[str, Any]) -> list[dict[str, str]]:
    directions: list[dict[str, str]] = []
    for item in report.get("adjustment_strategy") or []:
        if not isinstance(item, dict):
            continue
        element = _text(item.get("element"))
        if element:
            directions.append({"element": element, "source_role": _text(item.get("role"))})
    if not directions:
        directions = [{"element": item, "source_role": ""} for item in _string_list(report.get("useful_elements"))]
    if not directions:
        lowest = _text((report.get("ranking") or {}).get("lowest"))
        if lowest:
            directions.append({"element": lowest, "source_role": "观察方向"})
    return directions[:3]


def _is_explicit_exclusion(text: str, key: str) -> bool:
    if not text:
        return False
    aliases = [token for token, value in COLOR_ALIASES.items() if value == key]
    exclusion_phrases = re.findall(r"(?:不要|避免|不想|别用|禁用)[^、，,；;。]{0,12}", text)
    return any(token in phrase for phrase in exclusion_phrases for token in aliases)


def _fingerprint(report: dict[str, Any], request: dict[str, Any]) -> str:
    safe_input = {
        "report": report,
        "request": {
            key: request.get(key)
            for key in (
                "wrist_size_cm", "bead_size_mm", "budget", "style_preference", "color_preference",
                "accessory_preference", "wear_scene", "preference_confirmed", "note",
            )
        },
    }
    canonical = json.dumps(safe_input, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_design_brief(
    report_summary: dict[str, Any] | None,
    request: dict[str, Any] | None,
    *,
    report_id: str = "",
    report_code: str = "",
    report_version: int | None = None,
) -> dict[str, Any]:
    """Build a stable, explainable brief from an already-sanitised report.

    ``report_summary`` must not contain raw birth, name or location data.  The
    returned brief deliberately exposes only translated design constraints and
    traceable evidence for designers.
    """

    report = report_summary if isinstance(report_summary, dict) else {}
    service_request = request if isinstance(request, dict) else {}
    ranking = report.get("ranking") if isinstance(report.get("ranking"), dict) else {}
    balance = report.get("balance") if isinstance(report.get("balance"), dict) else {}
    conclusion = report.get("core_conclusion") if isinstance(report.get("core_conclusion"), dict) else {}
    style_guidance = report.get("style_guidance") if isinstance(report.get("style_guidance"), dict) else {}
    dominant = _text(ranking.get("dominant") or report.get("strongest_element"))
    style_choice = _text(service_request.get("style_preference"))
    # “由设计师判断” is an explicit preference, but it must not masquerade as
    # a visual style or make a fabricated style claim in the brief.
    style = "" if style_choice in {"由设计师判断", "交给设计师"} else style_choice
    style_profile = STYLE_PROFILES.get(style, STYLE_PROFILES["清透自然"])
    adjustments = _adjustment_directions(report)
    intervention = _balance_intervention(balance.get("score"))
    user_color_text = _text(service_request.get("color_preference"))
    user_note = _text(service_request.get("note"))
    explicit_color_keys = _color_keys_from_text(user_color_text)

    base_keys = explicit_color_keys or list(style_profile["colors"][:2])
    adjustment_color_keys = [
        key
        for direction in adjustments
        for key in ELEMENT_VISUALS.get(direction["element"], {}).get("colors", [])
    ]
    support_keys = [key for key in adjustment_color_keys if key not in base_keys][:2]
    if not support_keys:
        support_keys = [key for key in style_profile["colors"] if key not in base_keys][:2]
    accent_keys = [
        key for key in adjustment_color_keys if key not in base_keys and key not in support_keys
    ][:1]

    avoid_keys: list[str] = []
    for key in COLOR_LIBRARY:
        if _is_explicit_exclusion(user_color_text, key) or _is_explicit_exclusion(user_note, key):
            avoid_keys.append(key)
    if "深色" in _text(style_guidance.get("reduce")):
        avoid_keys.append("black")
    avoid_keys = _unique(avoid_keys)
    base_keys = [key for key in base_keys if key not in avoid_keys]
    support_keys = [key for key in support_keys if key not in avoid_keys]
    accent_keys = [key for key in accent_keys if key not in avoid_keys]

    hard_constraints = [
        {
            "key": "wrist_size_cm",
            "label": "手围",
            "value": _measure(service_request.get("wrist_size_cm"), "cm"),
            "source": "用户申请",
        },
        {
            "key": "bead_size_mm",
            "label": "珠径",
            "value": _measure(service_request.get("bead_size_mm"), "mm"),
            "source": "用户申请",
        },
        {
            "key": "budget",
            "label": "预算",
            "value": _text(service_request.get("budget")) or "待确认",
            "source": "用户申请",
        },
    ]
    if user_color_text:
        hard_constraints.append({"key": "color_preference", "label": "色彩偏好", "value": user_color_text, "source": "用户申请"})
    if user_note:
        hard_constraints.append({"key": "note", "label": "设计备注", "value": user_note, "source": "用户申请"})

    accessory = _text(service_request.get("accessory_preference"))
    scene = _text(service_request.get("wear_scene"))
    preferences_confirmed = bool(service_request.get("preference_confirmed"))
    preference_source = "用户已确认"
    if not preferences_confirmed:
        preference_source = "旧服务单或未确认记录，发布前请确认"

    roles = []
    role_labels = (("primary", "主材", "承接用户风格与主要愿景"), ("support", "辅材", "承担主要调和与过渡"), ("accent", "点缀", "只作少量视觉提亮"))
    for index, (key, label, purpose) in enumerate(role_labels):
        direction = adjustments[index] if index < len(adjustments) else None
        element = direction["element"] if direction else ""
        roles.append({
            "key": key,
            "label": label,
            "element": element,
            "purpose": purpose,
            "reason": (
                f"{direction.get('source_role') or '调整方向'}：{element}。具体石种由风格、库存和预算共同决定。"
                if direction else "未指定元素方向，以用户审美、库存与预算共同决定。"
            ),
        })

    baseline = ELEMENT_VISUALS.get(dominant, {})
    objective_parts = []
    if style:
        objective_parts.append(style)
    if dominant:
        objective_parts.append(f"保留{dominant}的{baseline.get('baseline', '既有气质')}")
    if adjustments:
        objective_parts.append(f"以{adjustments[0]['element']}方向做{intervention['label']}")
    title = " · ".join(objective_parts) or "以用户偏好为核心完成日常佩戴设计"
    summary = _text(conclusion.get("summary")) or _text(conclusion.get("title"))
    if summary:
        summary = f"{summary}。{intervention['reason']}"
    else:
        summary = str(intervention["reason"])

    texture = _unique([*_string_list(style_profile.get("texture")), *_string_list(style_guidance.get("recommended_texture"))])
    structure_direction = _text(style_profile.get("structure"))
    if intervention["level"] == "focused":
        structure_direction += "；采用中性基底与渐进过渡，避免把多个方向同时做成主角"
    reduce_text = _text(style_guidance.get("reduce"))
    warnings: list[dict[str, str]] = []
    if dominant and adjustments and dominant not in [item["element"] for item in adjustments]:
        warnings.append({
            "level": "info",
            "label": "主导元素与调整方向不同",
            "message": f"{dominant}只用于识别已有气质和避免过量堆叠；实际选材优先按调整方向与用户偏好处理。",
        })
    if not preferences_confirmed:
        warnings.append({
            "level": "attention",
            "label": "配饰或场景待确认",
            "message": "该项来自旧服务单或尚未确认的记录，发布前请确认是否为用户真实偏好。",
        })
    if not adjustments:
        warnings.append({"level": "attention", "label": "调整方向不完整", "message": "本次仅按用户审美与物理约束生成基础设计指引。"})
    if not report:
        warnings.append({"level": "attention", "label": "测算依据不完整", "message": "请核对报告快照后再发布设计方案。"})

    mood = report.get("mood_analysis") if isinstance(report.get("mood_analysis"), dict) else {}
    chakra = report.get("chakra_analysis") if isinstance(report.get("chakra_analysis"), dict) else {}
    mbti = report.get("mbti_analysis") if isinstance(report.get("mbti_analysis"), dict) else {}
    zodiac = report.get("zodiac_analysis") if isinstance(report.get("zodiac_analysis"), dict) else {}
    evidence = [
        {
            "source": "元素分布均衡度",
            "level": "设计强度",
            "value": f"{intervention['score']} 分 · {intervention['label']}",
            "effect": str(intervention["reason"]),
        },
        {
            "source": "调整方向",
            "level": "核心参考",
            "value": "、".join(item["element"] for item in adjustments) or "未提供",
            "effect": "决定主材、辅材、点缀的候选方向，不直接等同某一种水晶。",
        },
    ]
    if style:
        evidence.append({"source": "用户风格", "level": "高优先级", "value": style, "effect": "决定材料数量、视觉节奏和配饰克制程度。"})
    if user_color_text:
        evidence.append({"source": "用户色彩偏好", "level": "高优先级", "value": user_color_text, "effect": "优先于泛化元素配色。"})
    if mood.get("name") or mood.get("palette_name"):
        evidence.append({"source": "情绪色板", "level": "审美微调", "value": _text(mood.get("name") or mood.get("palette_name")), "effect": "用于辅助色、明暗和通透度，不单独决定材料。"})
    if chakra.get("primary_chakra_name") or chakra.get("primary_chakra"):
        evidence.append({"source": "脉轮状态", "level": "审美微调", "value": _text(chakra.get("primary_chakra_name") or chakra.get("primary_chakra")), "effect": "用于色彩与情绪氛围参考，不作功效承诺。"})
    if mbti.get("selected"):
        evidence.append({"source": "MBTI", "level": "低权重", "value": _text(mbti.get("type")), "effect": "只用于结构节奏的同分择优。"})
    if zodiac.get("name"):
        evidence.append({"source": "星座", "level": "叙事参考", "value": _text(zodiac.get("name")), "effect": "只用于方案命名或故事表达，不参与主材筛选。"})

    return {
        "schema_version": BRIEF_SCHEMA_VERSION,
        "rule_version": BRIEF_RULE_VERSION,
        "status": "ready" if report else "partial",
        "lineage": {
            "report_id": _text(report_id),
            "report_code": _text(report_code),
            "report_version": int(report_version or 1),
            "input_fingerprint": _fingerprint(report, service_request),
        },
        "design_goal": {"title": title, "summary": summary},
        "intervention": intervention,
        "hard_constraints": hard_constraints,
        "preferences": {
            "style": style_choice,
            "accessory": accessory,
            "wear_scene": scene,
            "confirmed": preferences_confirmed,
            "source": preference_source,
        },
        "palette": {
            "base": _colors(base_keys, reason="用户偏好或风格基底", source="用户偏好 / 风格"),
            "support": _colors(support_keys, reason="主要调整方向的辅助表达", source="调整方向"),
            "accent": _colors(accent_keys, reason="少量提亮，不形成第二主角", source="辅助调整"),
            "avoid": _colors(avoid_keys, reason="用户明确限制或报告减少项", source="用户偏好 / 测算参考"),
        },
        "optics": {"tags": texture, "existing_baseline": baseline.get("baseline", "")},
        "material_roles": roles,
        "structure": {
            "direction": structure_direction,
            "max_bead_materials": style_profile["max_materials"],
            "max_accessories": style_profile["max_accessories"],
            "reduce": reduce_text,
            "dominant_element": dominant,
            "dominant_note": (
                f"{dominant}代表已有的{baseline.get('baseline', '视觉气质')}；不作为继续堆叠同类材料的指令。"
                if dominant else "主导元素信息不足，以用户风格为主。"
            ),
        },
        "supplementary_context": {
            "core_wishes": _string_list(report.get("core_wishes")),
            "keywords": _string_list(report.get("keywords")),
            "mood": _text(mood.get("name") or mood.get("palette_name")),
            "mbti": _text(mbti.get("type")),
            "zodiac": _text(zodiac.get("name")),
        },
        "source_evidence": evidence,
        "warnings": warnings,
    }
