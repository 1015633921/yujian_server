from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from lunar_python import Solar

from .common import (
    CONTROLS,
    ELEMENTS,
    GENERATES,
    empty_profile,
    normalized_profile,
    useful_elements_for_day_master,
)

STEM_ELEMENTS = {
    "甲": "木",
    "乙": "木",
    "丙": "火",
    "丁": "火",
    "戊": "土",
    "己": "土",
    "庚": "金",
    "辛": "金",
    "壬": "水",
    "癸": "水",
}

BRANCH_MAIN_ELEMENTS = {
    "子": "水",
    "丑": "土",
    "寅": "木",
    "卯": "木",
    "辰": "土",
    "巳": "火",
    "午": "火",
    "未": "土",
    "申": "金",
    "酉": "金",
    "戌": "土",
    "亥": "水",
}

MONTH_SEASON_ELEMENTS = {
    "寅": "木",
    "卯": "木",
    "辰": "土",
    "巳": "火",
    "午": "火",
    "未": "土",
    "申": "金",
    "酉": "金",
    "戌": "土",
    "亥": "水",
    "子": "水",
    "丑": "土",
}

PILLAR_KEYS = ("year", "month", "day", "time")


@dataclass(frozen=True)
class BaziResult:
    profile: dict[str, float]
    basis: dict


def calculate_bazi(true_solar_datetime: datetime, total: float = 50) -> BaziResult:
    solar = Solar.fromYmdHms(
        true_solar_datetime.year,
        true_solar_datetime.month,
        true_solar_datetime.day,
        true_solar_datetime.hour,
        true_solar_datetime.minute,
        true_solar_datetime.second,
    )
    eight_char = solar.getLunar().getEightChar()
    pillars = {
        "year": eight_char.getYear(),
        "month": eight_char.getMonth(),
        "day": eight_char.getDay(),
        "time": eight_char.getTime(),
    }
    stems = {
        "year": eight_char.getYearGan(),
        "month": eight_char.getMonthGan(),
        "day": eight_char.getDayGan(),
        "time": eight_char.getTimeGan(),
    }
    branches = {
        "year": eight_char.getYearZhi(),
        "month": eight_char.getMonthZhi(),
        "day": eight_char.getDayZhi(),
        "time": eight_char.getTimeZhi(),
    }
    hidden_stems = {
        "year": list(eight_char.getYearHideGan()),
        "month": list(eight_char.getMonthHideGan()),
        "day": list(eight_char.getDayHideGan()),
        "time": list(eight_char.getTimeHideGan()),
    }
    raw = empty_profile()
    support_raw = 0.0
    total_raw = 0.0
    day_master_element = STEM_ELEMENTS[stems["day"]]
    resource_element = next(element for element, generated in GENERATES.items() if generated == day_master_element)

    def add(element: str | None, weight: float) -> None:
        nonlocal support_raw, total_raw
        if element not in ELEMENTS:
            return
        raw[element] += weight
        total_raw += weight
        if element == day_master_element:
            support_raw += weight
        elif element == resource_element:
            support_raw += weight * 0.82
        elif CONTROLS.get(element) == day_master_element:
            support_raw -= weight * 0.32

    for key in PILLAR_KEYS:
        add(STEM_ELEMENTS.get(stems[key]), 8.0 if key == "day" else 6.0)
        add(BRANCH_MAIN_ELEMENTS.get(branches[key]), 4.2 if key == "month" else 3.2)
        for hidden in hidden_stems[key]:
            add(STEM_ELEMENTS.get(hidden), 1.35 if key == "month" else 1.0)

    season_element = MONTH_SEASON_ELEMENTS.get(branches["month"])
    add(season_element, 5.5)
    profile = normalized_profile(raw, total)
    support_ratio = round(max(0.0, support_raw) / (total_raw or 1.0), 3)
    if support_ratio >= 0.58:
        strength = "身强"
        strategy = "喜克、泄、耗，用能消耗或规范日主的五行来调节过旺能量。"
    elif support_ratio <= 0.42:
        strength = "身弱"
        strategy = "喜生、扶，用能滋养或支持日主的五行来补足根气。"
    else:
        strength = "中和"
        strategy = "喜顺势调和，优先在表达、滋养与落地之间保持流动。"
    useful_elements = useful_elements_for_day_master(day_master_element, strength)
    basis = {
        "pillars": pillars,
        "stems": stems,
        "branches": branches,
        "hidden_stems": hidden_stems,
        "day_master": stems["day"],
        "day_master_element": day_master_element,
        "day_master_strength": strength,
        "day_master_support_ratio": support_ratio,
        "useful_elements": useful_elements,
        "strategy": strategy,
        "season_element": season_element,
        "raw_profile": {element: round(raw[element], 2) for element in ELEMENTS},
    }
    return BaziResult(profile=profile, basis=basis)
