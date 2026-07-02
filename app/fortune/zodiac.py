from __future__ import annotations

from datetime import date, datetime
from typing import Any


ZODIAC_SIGNS = [
    {
        "key": "capricorn",
        "name": "摩羯座",
        "english_name": "Capricorn",
        "start": (12, 22),
        "end": (1, 19),
        "date_range": "12.22 - 01.19",
        "element": "土象",
        "modality": "开创",
        "traits": ["秩序感", "长期主义", "责任心"],
        "focus": "适合把愿望拆成可执行的小目标，用稳定节奏累积结果。",
    },
    {
        "key": "aquarius",
        "name": "水瓶座",
        "english_name": "Aquarius",
        "start": (1, 20),
        "end": (2, 18),
        "date_range": "01.20 - 02.18",
        "element": "风象",
        "modality": "固定",
        "traits": ["独立思考", "灵感跳跃", "保持距离"],
        "focus": "适合保留清晰边界，同时给新想法一点实验空间。",
    },
    {
        "key": "pisces",
        "name": "双鱼座",
        "english_name": "Pisces",
        "start": (2, 19),
        "end": (3, 20),
        "date_range": "02.19 - 03.20",
        "element": "水象",
        "modality": "变动",
        "traits": ["感受力", "共情", "想象力"],
        "focus": "适合先照顾情绪和睡眠，再把灵感落到具体行动里。",
    },
    {
        "key": "aries",
        "name": "白羊座",
        "english_name": "Aries",
        "start": (3, 21),
        "end": (4, 19),
        "date_range": "03.21 - 04.19",
        "element": "火象",
        "modality": "开创",
        "traits": ["行动力", "直接", "启动感"],
        "focus": "适合把冲劲用在最重要的一件事上，少让热度被杂事分散。",
    },
    {
        "key": "taurus",
        "name": "金牛座",
        "english_name": "Taurus",
        "start": (4, 20),
        "end": (5, 20),
        "date_range": "04.20 - 05.20",
        "element": "土象",
        "modality": "固定",
        "traits": ["稳定", "审美", "身体感"],
        "focus": "适合用可触摸的仪式感稳定状态，也要给变化留一点余地。",
    },
    {
        "key": "gemini",
        "name": "双子座",
        "english_name": "Gemini",
        "start": (5, 21),
        "end": (6, 21),
        "date_range": "05.21 - 06.21",
        "element": "风象",
        "modality": "变动",
        "traits": ["沟通", "好奇", "轻快转换"],
        "focus": "适合用清晰表达梳理信息，避免同时开启太多方向。",
    },
    {
        "key": "cancer",
        "name": "巨蟹座",
        "english_name": "Cancer",
        "start": (6, 22),
        "end": (7, 22),
        "date_range": "06.22 - 07.22",
        "element": "水象",
        "modality": "开创",
        "traits": ["照顾力", "安全感", "情绪记忆"],
        "focus": "适合先建立安全边界，再把照顾力留给真正重要的人和事。",
    },
    {
        "key": "leo",
        "name": "狮子座",
        "english_name": "Leo",
        "start": (7, 23),
        "end": (8, 22),
        "date_range": "07.23 - 08.22",
        "element": "火象",
        "modality": "固定",
        "traits": ["表达力", "创造力", "自信感"],
        "focus": "适合把存在感放到作品和成果里，减少被临时情绪牵动。",
    },
    {
        "key": "virgo",
        "name": "处女座",
        "english_name": "Virgo",
        "start": (8, 23),
        "end": (9, 22),
        "date_range": "08.23 - 09.22",
        "element": "土象",
        "modality": "变动",
        "traits": ["整理", "细节", "修正力"],
        "focus": "适合用清单和秩序减轻内耗，不必把每一步都做到完美。",
    },
    {
        "key": "libra",
        "name": "天秤座",
        "english_name": "Libra",
        "start": (9, 23),
        "end": (10, 23),
        "date_range": "09.23 - 10.23",
        "element": "风象",
        "modality": "开创",
        "traits": ["平衡", "审美", "关系协调"],
        "focus": "适合在关系里保留自己的尺度，避免为了和谐过度让步。",
    },
    {
        "key": "scorpio",
        "name": "天蝎座",
        "english_name": "Scorpio",
        "start": (10, 24),
        "end": (11, 22),
        "date_range": "10.24 - 11.22",
        "element": "水象",
        "modality": "固定",
        "traits": ["洞察", "专注", "深度转化"],
        "focus": "适合把敏锐感用于看清核心问题，同时放下不必要的防备。",
    },
    {
        "key": "sagittarius",
        "name": "射手座",
        "english_name": "Sagittarius",
        "start": (11, 23),
        "end": (12, 21),
        "date_range": "11.23 - 12.21",
        "element": "火象",
        "modality": "变动",
        "traits": ["探索", "乐观", "扩张感"],
        "focus": "适合把探索欲落到明确路径上，避免热情过快分散。",
    },
]

ELEMENT_TO_WUXING = {
    "火象": "火气外放，适合用水与金的清凉、边界感做温柔平衡。",
    "土象": "土气稳重，适合用木的生发感和水的流动感减轻停滞。",
    "风象": "风象重沟通与思考，适合借木的条理和金的边界让灵感成形。",
    "水象": "水象重感受与共情，适合用土的安定和火的明亮托住情绪。",
}


def parse_birth_date(value: date | str | None) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def is_in_date_range(birthday: date, start: tuple[int, int], end: tuple[int, int]) -> bool:
    current = (birthday.month, birthday.day)
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def zodiac_sign_for_date(birthday: date | str | None) -> dict[str, Any]:
    parsed = parse_birth_date(birthday)
    if not parsed:
        return {}
    for sign in ZODIAC_SIGNS:
        if is_in_date_range(parsed, sign["start"], sign["end"]):
            return sign
    return {}


def calculate_zodiac_analysis(
    birthday: date | str | None,
    strongest_element: str | None = None,
    weakest_element: str | None = None,
) -> dict[str, Any]:
    sign = zodiac_sign_for_date(birthday)
    if not sign:
        return {}
    element = sign["element"]
    traits = list(sign["traits"])
    strongest = strongest_element or "优势"
    weakest = weakest_element or "待补"
    return {
        "key": sign["key"],
        "name": sign["name"],
        "english_name": sign["english_name"],
        "date_range": sign["date_range"],
        "element": element,
        "modality": sign["modality"],
        "traits": traits,
        "keywords": traits,
        "summary": f"{sign['name']}带有{element}的{sign['modality']}气质，关键词是{'、'.join(traits)}。",
        "wuxing_hint": ELEMENT_TO_WUXING.get(element, "星座气质会作为五行报告外的性格侧写参考。"),
        "integration": f"结合你的五行画像，当前偏强的{strongest}适合被看见，{weakest}则适合用更温和的节奏补足。",
        "suggestion": sign["focus"],
    }
