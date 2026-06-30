from __future__ import annotations

ELEMENTS = ("金", "木", "水", "火", "土")

GENERATES = {
    "木": "火",
    "火": "土",
    "土": "金",
    "金": "水",
    "水": "木",
}

CONTROLS = {
    "木": "土",
    "土": "水",
    "水": "火",
    "火": "金",
    "金": "木",
}


def empty_profile() -> dict[str, float]:
    return {element: 0.0 for element in ELEMENTS}


def neutral_profile(total: float) -> dict[str, float]:
    return normalized_profile({element: 1.0 for element in ELEMENTS}, total)


def normalized_profile(raw: dict[str, float], total: float) -> dict[str, float]:
    raw_total = sum(max(0.0, float(value)) for value in raw.values()) or 1.0
    result = {
        element: round(max(0.0, float(raw.get(element, 0.0))) / raw_total * total, 2)
        for element in ELEMENTS
    }
    drift = round(total - sum(result.values()), 2)
    strongest = max(result, key=result.get)
    result[strongest] = round(result[strongest] + drift, 2)
    return result


def generating_element(target: str) -> str:
    return next(element for element, generated in GENERATES.items() if generated == target)


def controlling_element(target: str) -> str:
    return next(element for element, controlled in CONTROLS.items() if controlled == target)


def useful_elements_for_day_master(day_master_element: str, strength: str) -> list[str]:
    same = day_master_element
    resource = generating_element(day_master_element)
    output = GENERATES[day_master_element]
    wealth = CONTROLS[day_master_element]
    officer = controlling_element(day_master_element)
    if strength == "身弱":
        return [resource, same]
    if strength == "身强":
        return [output, wealth, officer]
    return [output, resource, wealth]
