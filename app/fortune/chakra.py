from __future__ import annotations

from .common import ELEMENTS, empty_profile, neutral_profile, normalized_profile
from .config import load_config


def chakra_config() -> dict:
    return load_config("chakra_rules.json")


def chakra_rules() -> dict[str, dict]:
    return chakra_config().get("chakras", {})


def chakra_questions() -> list[dict]:
    return chakra_config().get("questions", [])


def answer_to_chakra() -> dict[str, str]:
    return {
        option["id"]: option["chakra"]
        for question in chakra_questions()
        for option in question.get("options", [])
    }


def calculate_chakra_profile(answer_ids: list[str], total: float = 8) -> tuple[dict[str, float], dict]:
    rules = chakra_rules()
    answer_map = answer_to_chakra()
    raw = empty_profile()
    chakra_scores = {key: 0.0 for key in rules}
    valid_answers = [answer_id for answer_id in answer_ids if answer_id in answer_map]
    if not valid_answers:
        return neutral_profile(total), {
            "selected_answers": [],
            "primary_chakra": "",
            "primary_chakra_name": "未选择",
            "keywords": [],
            "colors": [],
            "chakras": [],
            "color_families": [],
            "mood_tags": [],
            "visual_tags": [],
        }

    for answer_id in valid_answers:
        chakra_key = answer_map[answer_id]
        chakra_scores[chakra_key] += 1.0
        for element, value in rules[chakra_key]["element_weights"].items():
            raw[element] += value

    primary_chakra = max(chakra_scores, key=chakra_scores.get)
    selected_rules = [rules[key] for key, value in chakra_scores.items() if value]
    rule = rules[primary_chakra]
    return normalized_profile(raw, total), {
        "selected_answers": valid_answers,
        "scores": {key: round(value, 2) for key, value in chakra_scores.items() if value},
        "primary_chakra": primary_chakra,
        "primary_chakra_name": rule["name"],
        "keywords": rule["keywords"],
        "colors": rule["colors"],
        "chakras": [key for key, value in chakra_scores.items() if value],
        "color_families": unique_values(selected_rules, "color_families"),
        "mood_tags": unique_values(selected_rules, "mood_tags"),
        "visual_tags": unique_values(selected_rules, "visual_tags"),
        "summary": f"当下更适合照看{rule['name']}，关键词是{'、'.join(rule['keywords'])}。",
    }


def public_chakra_options() -> list[dict]:
    return chakra_questions()


def unique_values(items: list[dict], key: str) -> list[str]:
    values = []
    for item in items:
        for value in item.get(key, []):
            if value not in values:
                values.append(value)
    return values
