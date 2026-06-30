from __future__ import annotations

from .common import empty_profile, neutral_profile, normalized_profile
from .config import load_config


def mood_palettes() -> dict[str, dict]:
    return load_config("mood_palettes.json").get("palettes", {})


def calculate_mood_profile(palette_id: str | None, total: float = 8) -> tuple[dict[str, float], dict]:
    palettes = mood_palettes()
    if not palette_id or palette_id not in palettes:
        return neutral_profile(total), {
            "palette_id": "",
            "name": "未选择",
            "subtitle": "",
            "colors": [],
            "chakra": "",
            "color_families": [],
            "mood_tags": [],
            "visual_tags": [],
        }
    palette = palettes[palette_id]
    raw = empty_profile()
    for element, value in palette["element_weights"].items():
        raw[element] += value
    return normalized_profile(raw, total), {
        "palette_id": palette_id,
        "name": palette["name"],
        "subtitle": palette["subtitle"],
        "colors": palette["colors"],
        "chakra": palette["chakra"],
        "chakras": [palette["chakra"]] if palette.get("chakra") else [],
        "color_families": palette.get("color_families", []),
        "mood_tags": palette.get("mood_tags", []),
        "visual_tags": palette.get("visual_tags", []),
        "summary": f"你当下被{palette['name']}吸引，适合用{palette['subtitle']}作为配色情绪。",
    }


def public_mood_palettes() -> list[dict]:
    return [
        {"id": key, **value}
        for key, value in mood_palettes().items()
    ]
