"""Deterministic, explainable material candidates for a human design brief.

This module deliberately stops before making a bracelet.  It filters out
materials that cannot safely enter the current designer workbench and ranks
the remaining material *candidates* against the approved Design Brief.  The
designer still chooses every item, quantity and position; this result never
persists a selection, reserves stock, or changes an order.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .material_options import (
    element_label,
    normalize_color_family,
    normalize_element_key,
    normalize_match_rule_list,
    normalize_role_list,
    normalize_visual_tag_list,
)
from .recommendation import RecommendationEngine


CANDIDATE_SCHEMA_VERSION = 1
CANDIDATE_RULE_VERSION = "design-candidates-2026-08-v1"
MAX_CANDIDATES_PER_ROLE = 8

ROLE_LABELS = {
    "primary": "主材候选",
    "support": "辅材候选",
    "accent": "点缀候选",
}

VISUAL_LABELS = {
    "transparent": "透明感",
    "milky": "奶白感",
    "icy": "冰透",
    "sparkling": "闪光",
    "soft_color": "低饱和",
    "texture": "纹理感",
    "dark": "深色",
    "warm": "暖调",
}

ACCESSORY_PREFS = {
    "不使用配饰": "none",
    "少量银饰": "silver",
    "少量金饰": "gold",
    "适量点缀": "balanced",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _number(value: Any, default: float = 0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        values = re.split(r"[、,，/;；|\n\r]+", value)
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]
    result: list[str] = []
    for item in values:
        text = _text(item)
        if text and text not in result:
            result.append(text)
    return result


def _bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}
    return bool(value)


def _gallery_images(material: dict[str, Any]) -> list[str]:
    """Return gallery-only assets; primary images are deliberately excluded."""
    visual = _mapping(material.get("visual"))
    candidates = visual.get("image_urls") or material.get("image_urls") or material.get("image_pool") or []
    if isinstance(candidates, str):
        candidates = re.split(r"[,\n\r]+", candidates)
    result: list[str] = []
    for value in candidates if isinstance(candidates, (list, tuple, set)) else []:
        url = _text(value)
        if url and url not in result:
            result.append(url)
    return result


def _material_view(material: dict[str, Any]) -> dict[str, Any]:
    sku = _mapping(material.get("sku"))
    energy = _mapping(material.get("energy"))
    visual = _mapping(material.get("visual"))
    rules = _mapping(material.get("rules"))
    params = {
        **_mapping(material.get("material_params")),
        **_mapping(visual.get("material_params")),
        **_mapping(material.get("physical_specs")),
    }
    material_id = _text(sku.get("id") or material.get("id"))
    code = _text(sku.get("material_code") or material.get("material_code"))
    top = _text(sku.get("top") or material.get("top")).lower()
    price = _number(sku.get("price_per_bead") if sku else material.get("price"))
    if price <= 0:
        price = _number(material.get("price"))
    stock = _number(sku.get("stock") if sku else material.get("stock"))
    if stock <= 0:
        stock = _number(material.get("stock"))
    reserved = _number(
        material.get("reserved_stock")
        if material.get("reserved_stock") not in (None, "")
        else sku.get("reserved_stock")
    )
    size = _number(sku.get("size_mm") if sku else material.get("size"))
    if size <= 0:
        size = _number(material.get("size") or material.get("size_mm"))
    raw_elements = [
        energy.get("primary_element") or material.get("primary_element") or material.get("element"),
        *(energy.get("secondary_elements") or material.get("secondary_elements") or []),
    ]
    element_keys = [normalize_element_key(value) for value in raw_elements]
    element_keys = [value for value in element_keys if value]
    roles = normalize_role_list(rules.get("allowed_roles") or material.get("allowed_roles"))
    match_rules = normalize_match_rule_list(rules.get("match_rules") or material.get("match_rules"))
    visual_tags = normalize_visual_tag_list(energy.get("visual_tags") or material.get("visual_tags"))
    color = normalize_color_family(energy.get("color_family") or material.get("color_family"))
    return {
        "id": material_id,
        "material_code": code,
        "name": _text(sku.get("name") or material.get("name") or material.get("series")),
        "top": top,
        "enabled": _bool(sku.get("enabled") if "enabled" in sku else material.get("enabled")),
        "price": round(price, 2),
        "size_mm": size,
        "stock": int(max(0, round(stock))),
        "reserved_stock": int(max(0, round(reserved))),
        "available_stock": int(max(0, round(stock - reserved))),
        "gallery_images": _gallery_images(material),
        "color_family": color,
        "element_keys": element_keys,
        "roles": roles,
        "match_rules": match_rules,
        "visual_tags": visual_tags,
        "params": params,
    }


def _palette_keys(brief: dict[str, Any], name: str) -> list[str]:
    palette = _mapping(brief.get("palette"))
    values = palette.get(name) or []
    result: list[str] = []
    for value in values if isinstance(values, list) else []:
        key = normalize_color_family(_mapping(value).get("key") if isinstance(value, dict) else value)
        if key and key not in result:
            result.append(key)
    return result


def _role_element(brief: dict[str, Any], role: str) -> str:
    for item in brief.get("material_roles") or []:
        if isinstance(item, dict) and _text(item.get("key")) == role:
            return normalize_element_key(item.get("element"))
    return ""


def _role_is_allowed(item: dict[str, Any], role: str) -> bool:
    roles = set(item["roles"])
    rules = set(item["match_rules"])
    if role == "primary":
        return not ({"accent_only", "spacer_only"} & rules) and (not roles or "primary" in roles)
    if role == "support":
        return not ({"accent_only", "spacer_only"} & rules) and (not roles or "support" in roles)
    # A threaded accessory's normal use is a visual accent.  For beads, honor
    # the explicit role data when it exists instead of widening the semantics.
    if item["top"] == "accessory":
        return not roles or bool(roles & {"accent", "spacer"})
    return not roles or "accent" in roles or "spacer" in roles


def _material_is_supported(item: dict[str, Any], bead_size_mm: float, avoid_colors: set[str]) -> str:
    if not item["id"]:
        return "缺少材料 ID"
    if item["top"] not in {"bead", "accessory"}:
        return "当前工作台不支持该材料类型"
    if not item["enabled"]:
        return "材料已下架"
    if item["available_stock"] <= 0:
        return "无可用库存"
    if item["price"] <= 0:
        return "单颗价格无效"
    if not item["gallery_images"]:
        return "缺少图库图片"
    params = item["params"]
    if params.get("placement_mode") in {"attached_side", "hanging"} or params.get("bead_shape") in {"bead_cap", "charm"}:
        return "当前工作台暂不支持该配件安装方式"
    if item["top"] == "bead" and abs(item["size_mm"] - bead_size_mm) > 0.01:
        return "珠径与服务单不一致"
    if item["color_family"] and item["color_family"] in avoid_colors:
        return "命中用户明确避免的色彩"
    return ""


def parse_budget(value: Any) -> dict[str, Any]:
    """Parse a display budget into an advisory range without rejecting input."""
    text = _text(value)
    values = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", text)]
    minimum: float | None = None
    maximum: float | None = None
    if len(values) >= 2:
        minimum, maximum = sorted(values[:2])
    elif values:
        if any(token in text for token in ("以上", "起", "至少")):
            minimum = values[0]
        elif any(token in text for token in ("以内", "以下", "不超过", "最多")):
            maximum = values[0]
        else:
            minimum = maximum = values[0]
    return {"raw": text, "minimum": minimum, "maximum": maximum, "recognized": minimum is not None or maximum is not None}


def _brief_measure(brief: dict[str, Any], key: str, unit: str, default: float) -> float:
    constraints = {
        _text(item.get("key")): item
        for item in brief.get("hard_constraints") or []
        if isinstance(item, dict)
    }
    value = _number(_text(_mapping(constraints.get(key)).get("value")).replace(unit, ""))
    return value if value > 0 else default


def _estimate_bead_count(wrist_size_cm: float, bead_size_mm: float) -> int:
    wrist = wrist_size_cm if wrist_size_cm > 0 else 16
    bead = bead_size_mm if bead_size_mm > 0 else 8
    return RecommendationEngine.estimate_stringed_bead_count(wrist, max(1, round(bead)))


def _budget_status(estimate: float | None, budget: dict[str, Any]) -> tuple[str, str]:
    if estimate is None or not budget["recognized"]:
        return "unknown", "预算待人工核算"
    maximum = budget["maximum"]
    minimum = budget["minimum"]
    if maximum is not None and estimate > maximum:
        return "over", "单材整串估算高于用户预算；可作为少量点缀或改用组合方案"
    if minimum is not None and estimate < minimum:
        return "below", "单材整串估算低于预算；可作为基础材料并保留搭配空间"
    return "within", "单材整串估算落在预算参考内"


def _score_candidate(item: dict[str, Any], role: str, brief: dict[str, Any], budget: dict[str, Any], estimated_bead_count: int) -> dict[str, Any]:
    score = 20
    reasons: list[str] = []
    cautions: list[str] = []
    rules = set(item["match_rules"])
    roles = set(item["roles"])
    if roles:
        score += 12
        reasons.append(f"材料资料标注为{ROLE_LABELS[role].replace('候选', '')}")
    else:
        cautions.append("未设置材料角色规则，加入方案前请人工确认定位")
    if (role == "primary" and "best_as_primary" in rules) or (role == "support" and "best_as_support" in rules):
        score += 18
        reasons.append("搭配规则与当前角色一致")
    if role == "accent" and ("accent_only" in rules or "spacer_only" in rules):
        score += 16
        reasons.append("搭配规则建议少量点缀")

    role_element = _role_element(brief, role)
    intervention = _mapping(brief.get("intervention"))
    intervention_weight = {"aesthetic_first": 4, "light": 8, "moderate": 14, "focused": 20}.get(_text(intervention.get("level")), 8)
    if role_element and role_element in item["element_keys"]:
        score += intervention_weight
        reasons.append(f"贴合{element_label(role_element)}方向")

    palette_order = {
        "primary": ("base", "support"),
        "support": ("support", "base"),
        "accent": ("accent", "base", "support"),
    }[role]
    palette_keys = {key for name in palette_order for key in _palette_keys(brief, name)}
    if item["color_family"] and item["color_family"] in palette_keys:
        score += 12
        reasons.append("匹配本单色板")

    optics = _mapping(brief.get("optics"))
    desired_optics = {_text(value) for value in optics.get("tags") or []}
    if desired_optics and item["visual_tags"]:
        # Tags use different vocabularies in historical data.  Treat a known
        # Chinese label as a soft substring match, never as an exclusion.
        labels = {VISUAL_LABELS.get(tag, tag) for tag in item["visual_tags"]}
        if any(label in desired_optics or any(label in wanted for wanted in desired_optics) for label in labels):
            score += 6
            reasons.append("质感方向与 Brief 相符")

    preference = _mapping(brief.get("preferences"))
    accessory_mode = ACCESSORY_PREFS.get(_text(preference.get("accessory")), "")
    if item["top"] == "accessory":
        if accessory_mode == "silver" and item["color_family"] in {"white", "clear", "gray"}:
            score += 10
            reasons.append("符合少量银饰的偏好")
        elif accessory_mode == "gold" and item["color_family"] == "gold":
            score += 10
            reasons.append("符合少量金饰的偏好")
        elif accessory_mode == "balanced":
            score += 4
            reasons.append("可作为适量视觉点缀")

    estimate = round(item["price"] * estimated_bead_count, 2) if item["top"] == "bead" else None
    budget_status, budget_message = _budget_status(estimate, budget)
    if budget_status == "within":
        score += 6
        reasons.append("单材整串估算在预算参考内")
    elif budget_status == "over":
        cautions.append(budget_message)
    elif budget_status == "below":
        cautions.append(budget_message)
    if "avoid_dense" in rules:
        cautions.append("材料规则提示避免高密度使用")
    if "needs_color_balance" in rules:
        cautions.append("材料规则提示需搭配平衡色")
    return {
        "score": score,
        "reasons": reasons[:4] or ["满足当前工作台的基础物理与素材条件"],
        "cautions": cautions[:3],
        "single_material_string_estimate": estimate,
        "budget_status": budget_status,
        "budget_message": budget_message,
    }


def build_design_candidates(
    design_brief: dict[str, Any] | None,
    materials: list[dict[str, Any]] | None,
    *,
    selected_material_ids: list[str] | None = None,
    wrist_size_cm: float | None = None,
    bead_size_mm: float | None = None,
) -> dict[str, Any]:
    """Create material candidates from a persisted Design Brief and live catalog.

    The result is deliberately advisory: it does not include quantities, a
    layout, mutation instructions, or inventory reservations.
    """
    brief = _mapping(design_brief)
    if not brief:
        return {
            "schema_version": CANDIDATE_SCHEMA_VERSION,
            "rule_version": CANDIDATE_RULE_VERSION,
            "status": "unavailable",
            "message": "设计指引尚未生成，暂不能提供候选材料。",
            "candidate_groups": [],
        }
    selected_ids = {_text(value) for value in selected_material_ids or [] if _text(value)}
    views = [_material_view(_mapping(material)) for material in materials or []]
    avoid_colors = set(_palette_keys(brief, "avoid"))
    constraints = {
        _text(item.get("key")): item
        for item in brief.get("hard_constraints") or []
        if isinstance(item, dict)
    }
    brief_wrist_size = _brief_measure(brief, "wrist_size_cm", "cm", 16)
    brief_bead_size = _brief_measure(brief, "bead_size_mm", "mm", 8)
    active_wrist_size = _number(wrist_size_cm, brief_wrist_size)
    active_bead_size = _number(bead_size_mm, brief_bead_size)
    if active_wrist_size <= 0:
        active_wrist_size = brief_wrist_size
    if active_bead_size <= 0:
        active_bead_size = brief_bead_size
    budget = parse_budget(_mapping(constraints.get("budget")).get("value"))
    estimated_bead_count = _estimate_bead_count(active_wrist_size, active_bead_size)
    groups: list[dict[str, Any]] = []
    excluded_ids: set[str] = set()
    for role in ("primary", "support", "accent"):
        candidates: list[dict[str, Any]] = []
        for item in views:
            unsupported = _material_is_supported(item, active_bead_size, avoid_colors)
            if unsupported or not _role_is_allowed(item, role):
                if unsupported:
                    excluded_ids.add(item["id"])
                continue
            scored = _score_candidate(item, role, brief, budget, estimated_bead_count)
            candidates.append({
                "material_id": item["id"],
                "name": item["name"] or item["id"],
                "top": item["top"],
                "role": role,
                "score": scored["score"],
                "reasons": scored["reasons"],
                "cautions": scored["cautions"],
                "price": item["price"],
                "size_mm": item["size_mm"],
                "available_stock": item["available_stock"],
                "image_url": item["gallery_images"][0],
                "single_material_string_estimate": scored["single_material_string_estimate"],
                "budget_status": scored["budget_status"],
                "budget_message": scored["budget_message"],
            })
        candidates.sort(key=lambda item: (-item["score"], item["material_id"]))
        groups.append({
            "role": role,
            "label": ROLE_LABELS[role],
            "items": candidates[:MAX_CANDIDATES_PER_ROLE],
        })
    return {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "rule_version": CANDIDATE_RULE_VERSION,
        "status": "ready",
        "message": "候选仅供设计师参考；不会自动加入手串、不会锁定库存，发布时仍会进行价格与库存复核。",
        "brief_fingerprint": _mapping(brief.get("lineage")).get("input_fingerprint") or "",
        "active_constraints": {
            "wrist_size_cm": active_wrist_size,
            "bead_size_mm": active_bead_size,
        },
        "estimated_bead_count": estimated_bead_count,
        "budget": budget,
        "candidate_groups": groups,
        "catalog_material_count": len(views),
        "excluded_count": len(excluded_ids),
    }
