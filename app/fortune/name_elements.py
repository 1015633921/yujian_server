from __future__ import annotations

from .common import ELEMENTS, empty_profile, neutral_profile, normalized_profile

DIRECT_CHAR_ELEMENTS = {
    "金": set("金鑫铭锋钧锦银钟铎锐镇铮鉴钰钦铠铂铄铜铁镜铃锡钥"),
    "木": set("木林森楚松柏柳桐梓楠荣芳花竹禾苗英茵茹荷莲梅桂榕桦榆"),
    "水": set("水海洋江河湖雨雪冰清涵泽涛沐汐淼沁泉润溪澜澈渊"),
    "火": set("火炎焱炜煜烨灿炫明昕晖晟晓晴照熙灵煊煌"),
    "土": set("土坤垚城垣培基堂山岩峰岳宇安辰田均垚垠垒峻"),
}

RADICAL_ELEMENTS = {
    "金": ("钅", "釒"),
    "木": ("木", "艹", "竹", "禾"),
    "水": ("氵", "水", "雨", "冫"),
    "火": ("火", "灬", "日"),
    "土": ("土", "山", "石", "田", "宀"),
}


def analyze_name(name: str, total: float = 8) -> tuple[dict[str, float], dict]:
    raw = empty_profile()
    details = []
    unknown = []
    for char in name:
        element = resolve_char_element(char)
        if element:
            raw[element] += 1.0
            details.append({"char": char, "element": element, "source": "字库/偏旁"})
        elif char.strip():
            unknown.append(char)
            details.append({"char": char, "element": "", "source": "未收录"})
    if not any(raw.values()):
        profile = neutral_profile(total)
    else:
        if unknown:
            neutral_share = 0.2 * len(unknown)
            for element in ELEMENTS:
                raw[element] += neutral_share / len(ELEMENTS)
        profile = normalized_profile(raw, total)
    return profile, {
        "chars": details,
        "unknown_chars": unknown,
        "fallback": "unlisted_chars_distributed_neutrally" if unknown else "direct_match",
    }


def resolve_char_element(char: str) -> str | None:
    for element, chars in DIRECT_CHAR_ELEMENTS.items():
        if char in chars:
            return element
    for element, radicals in RADICAL_ELEMENTS.items():
        if any(radical in char for radical in radicals):
            return element
    return None
