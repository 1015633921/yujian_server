from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any


ELEMENT_ORDER = ("木", "火", "土", "金", "水")
# A report snapshot must identify the true-solar-time rule and location dataset
# generation it was built with. Historical snapshots remain immutable.
REPORT_ALGORITHM_VERSION = "energy-assessment-2026-08-06-location-calibration-v2"
REPORT_SCHEMA_VERSION = 3

ELEMENT_STYLE_GUIDANCE = {
    "木": {
        "keyword": "清新舒展",
        "colors": "青绿、雾蓝、米白",
        "texture": "清透、自然、轻盈",
        "structure": "线条舒展、适当留白、疏密有序",
        "reduce": "过多同类绿色、过于松散的结构",
    },
    "火": {
        "keyword": "明亮有活力",
        "colors": "暖红、蜜橙、柔金",
        "texture": "明亮、温润、有光泽",
        "structure": "重点明确、节奏利落、适量点缀",
        "reduce": "大面积高饱和暖色、过强视觉对比",
    },
    "土": {
        "keyword": "沉稳可靠",
        "colors": "米白、浅黄、暖棕",
        "texture": "温润、柔和、有质感",
        "structure": "圆润线条、重心稳定、排列有序",
        "reduce": "大面积黄棕、过密排列与厚重堆叠",
    },
    "金": {
        "keyword": "利落克制",
        "colors": "白色、银灰、冷调浅色",
        "texture": "通透、干净、细腻",
        "structure": "轮廓清晰、比例规整、少量留白",
        "reduce": "过多冷白灰、过于规整的重复",
    },
    "水": {
        "keyword": "安静细腻",
        "colors": "雾蓝、月光白、浅灰蓝",
        "texture": "清透、柔和、有流动光泽",
        "structure": "圆润过渡、层次柔和、节奏舒缓",
        "reduce": "大面积深色、过度沉静的组合",
    },
}


def normalized_input_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


def stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        normalized_input_payload(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")
    return max(Decimal("0"), result) if result.is_finite() else Decimal("0")


def display_percentages(raw_profile: dict[str, Any]) -> dict[str, int]:
    values = [_decimal(raw_profile.get(element, 0)) for element in ELEMENT_ORDER]
    total = sum(values, Decimal("0"))
    if total <= 0:
        return {element: 0 for element in ELEMENT_ORDER}
    exact = [value * Decimal("100") / total for value in values]
    floors = [int(value) for value in exact]
    remaining = 100 - sum(floors)
    allocation = sorted(
        range(len(ELEMENT_ORDER)),
        key=lambda index: (-(exact[index] - floors[index]), index),
    )
    for cursor in range(remaining):
        floors[allocation[cursor % len(allocation)]] += 1
    return {element: floors[index] for index, element in enumerate(ELEMENT_ORDER)}


def stable_element_ranking(percentages: dict[str, int]) -> list[str]:
    order_index = {element: index for index, element in enumerate(ELEMENT_ORDER)}
    return sorted(ELEMENT_ORDER, key=lambda element: (-int(percentages.get(element, 0)), order_index[element]))


def balance_level(score: Any) -> dict[str, Any]:
    try:
        normalized = max(0, min(100, round(float(score))))
    except (TypeError, ValueError):
        normalized = 0
    if normalized >= 85:
        label = "分布接近"
    elif normalized >= 70:
        label = "轻微侧重"
    elif normalized >= 55:
        label = "侧重明显"
    else:
        label = "倾向明显"
    return {"score": normalized, "label": label}


def build_report_projection(result: dict[str, Any]) -> dict[str, Any]:
    raw_profile = {
        element: float(_decimal((result.get("final_energy_profile") or {}).get(element, 0)))
        for element in ELEMENT_ORDER
    }
    percentages = display_percentages(raw_profile)
    ranking = stable_element_ranking(percentages)
    interpretation = result.get("interpretation") or {}
    balance = balance_level(interpretation.get("balance_index"))
    dominant = ranking[0]
    secondary = ranking[1]
    lowest = sorted(
        ELEMENT_ORDER,
        key=lambda element: (int(percentages.get(element, 0)), ELEMENT_ORDER.index(element)),
    )[0]
    style = ELEMENT_STYLE_GUIDANCE[dominant]
    useful = [element for element in result.get("useful_elements") or [] if element in ELEMENT_ORDER]
    adjustment = useful[:3] or [lowest]
    return {
        "elements": [
            {
                "name": element,
                "raw_value": raw_profile[element],
                "percent": percentages[element],
                "rank": ranking.index(element) + 1,
            }
            for element in ELEMENT_ORDER
        ],
        "ranking": {
            "dominant": dominant,
            "secondary": secondary,
            "lowest": lowest,
            "tie_break_order": list(ELEMENT_ORDER),
        },
        "balance": balance,
        "core_conclusion": {
            "title": str(interpretation.get("headline") or f"{style['keyword']}，适合有序调和"),
            "summary": str(interpretation.get("summary") or interpretation.get("overview") or ""),
        },
        "style_guidance": {
            "recommended_colors": style["colors"],
            "recommended_texture": style["texture"],
            "structure_direction": style["structure"],
            "reduce": style["reduce"],
        },
        "adjustment_strategy": [
            {
                "element": element,
                "role": "主要调整" if index == 0 else ("辅助调整" if index == 1 else "少量点缀"),
            }
            for index, element in enumerate(adjustment)
        ],
        "keywords": [item for item in result.get("energy_keywords") or [] if isinstance(item, dict)],
    }


def report_context(input_snapshot: dict[str, Any]) -> dict[str, Any]:
    name = str(input_snapshot.get("name") or "")
    return {
        "name_initial": name[:1],
        "core_wishes": list(input_snapshot.get("core_wishes") or []),
        "has_mbti_input": bool(input_snapshot.get("mbti")),
        "has_chakra_input": bool(input_snapshot.get("chakra_answers")),
        "has_mood_input": bool(input_snapshot.get("mood_palette_id")),
    }


def sanitized_output_snapshot(result: dict[str, Any], input_snapshot: dict[str, Any]) -> dict[str, Any]:
    output = {key: value for key, value in result.items() if key != "input_summary"}
    output["report_projection"] = build_report_projection(result)
    output["report_context"] = report_context(input_snapshot)
    return output
