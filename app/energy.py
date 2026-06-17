from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, time, timedelta

from .schemas import AssessmentRequest

ELEMENTS = ("金", "木", "水", "火", "土")

# Explicit 16-type mapping. Every profile totals 15 points.
MBTI_MAPPING: dict[str, dict[str, float]] = {
    "INTJ": {"金": 4, "木": 1, "水": 5, "火": 1, "土": 4},
    "INTP": {"金": 4, "木": 2, "水": 6, "火": 1, "土": 2},
    "ENTJ": {"金": 5, "木": 2, "水": 2, "火": 3, "土": 3},
    "ENTP": {"金": 3, "木": 3, "水": 3, "火": 5, "土": 1},
    "INFJ": {"金": 2, "木": 4, "水": 5, "火": 2, "土": 2},
    "INFP": {"金": 1, "木": 5, "水": 5, "火": 3, "土": 1},
    "ENFJ": {"金": 1, "木": 5, "水": 2, "火": 5, "土": 2},
    "ENFP": {"金": 1, "木": 5, "水": 2, "火": 6, "土": 1},
    "ISTJ": {"金": 4, "木": 1, "水": 3, "火": 1, "土": 6},
    "ISFJ": {"金": 2, "木": 3, "水": 3, "火": 2, "土": 5},
    "ESTJ": {"金": 4, "木": 1, "水": 1, "火": 3, "土": 6},
    "ESFJ": {"金": 1, "木": 3, "水": 1, "火": 5, "土": 5},
    "ISTP": {"金": 5, "木": 1, "水": 5, "火": 1, "土": 3},
    "ISFP": {"金": 2, "木": 4, "水": 4, "火": 3, "土": 2},
    "ESTP": {"金": 3, "木": 2, "水": 2, "火": 6, "土": 2},
    "ESFP": {"金": 1, "木": 4, "水": 1, "火": 7, "土": 2},
}
NEUTRAL_MBTI_PROFILE = {element: 3.0 for element in ELEMENTS}

WISH_MAPPING = {
    "招财进宝/事业腾飞": ("金", "土"),
    "正缘桃花/人际和合": ("火", "木"),
    "辟邪防小人/消除焦虑": ("水", "金"),
    "健康护身/保持专注": ("木", "土"),
}

# Common place fallback for longitude correction. Production can replace this with geocoding.
PLACE_COORDINATES = {
    "北京": (116.4074, 39.9042),
    "上海": (121.4737, 31.2304),
    "广州": (113.2644, 23.1291),
    "深圳": (114.0579, 22.5431),
    "成都": (104.0665, 30.5723),
    "四川省成都市": (104.0665, 30.5723),
    "重庆": (106.5516, 29.5630),
    "杭州": (120.1551, 30.2741),
    "武汉": (114.3054, 30.5931),
    "西安": (108.9398, 34.3416),
    "南京": (118.7969, 32.0603),
    "兰州": (103.8343, 36.0611),
    "甘肃省兰州市": (103.8343, 36.0611),
}

NAME_ELEMENT_CHARS = {
    "金": set("金鑫锋铭钰锦锐银钟铠鉴辛白"),
    "木": set("木林森楠松柏柳桐梓荣芳花竹禾"),
    "水": set("水海洋江河湖雨雪冰清涵泽涛淼"),
    "火": set("火炎焱烨煜炜灿晴明昕晖光"),
    "土": set("土坤垚城山岩峰岳宇安辰田"),
}


def empty_profile() -> dict[str, float]:
    return {element: 0.0 for element in ELEMENTS}


def normalized_profile(raw: dict[str, float], total: float) -> dict[str, float]:
    raw_total = sum(raw.values()) or 1
    result = {element: round(raw.get(element, 0) / raw_total * total, 2) for element in ELEMENTS}
    drift = round(total - sum(result.values()), 2)
    result[max(result, key=result.get)] = round(result[max(result, key=result.get)] + drift, 2)
    return result


class EnergyCalculator:
    """Combines mock Bazi, MBTI, name and wish energy into a 100-point profile."""

    def calculate(self, request: AssessmentRequest) -> dict:
        solar_time = self.calculate_true_solar_time(request)
        bazi = self.calculate_bazi_mock(request.birthday, solar_time["true_solar_datetime"])
        mbti = dict(MBTI_MAPPING[request.mbti]) if request.mbti else dict(NEUTRAL_MBTI_PROFILE)
        name = self.calculate_name_energy(request.name)
        wish = self.calculate_wish_energy(request.core_wishes)
        breakdown = {"bazi": bazi, "mbti": mbti, "name": name, "wish": wish}
        final = {
            element: round(sum(profile[element] for profile in breakdown.values()), 2)
            for element in ELEMENTS
        }
        return {
            "solar_time": {key: value for key, value in solar_time.items() if key != "true_solar_datetime"},
            "breakdown": breakdown,
            "final": final,
            "strongest": max(final, key=final.get),
            "weakest": min(final, key=final.get),
        }

    def calculate_true_solar_time(self, request: AssessmentRequest) -> dict:
        longitude, latitude, source = self.resolve_coordinates(request)
        local_datetime = datetime.combine(request.birthday, request.birth_time)
        longitude_correction = (longitude - 120.0) * 4.0
        day_of_year = request.birthday.timetuple().tm_yday
        b = math.radians((360 / 365) * (day_of_year - 81))
        equation_of_time = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
        total_correction = longitude_correction + equation_of_time
        true_solar_datetime = local_datetime + timedelta(minutes=total_correction)
        return {
            "beijing_time": local_datetime.strftime("%Y-%m-%d %H:%M"),
            "true_solar_time": true_solar_datetime.strftime("%Y-%m-%d %H:%M"),
            "longitude": round(longitude, 4),
            "latitude": round(latitude, 4) if latitude is not None else None,
            "longitude_correction_minutes": round(longitude_correction, 2),
            "equation_of_time_minutes": round(equation_of_time, 2),
            "total_correction_minutes": round(total_correction, 2),
            "location_source": source,
            "true_solar_datetime": true_solar_datetime,
        }

    @staticmethod
    def resolve_coordinates(request: AssessmentRequest) -> tuple[float, float | None, str]:
        if request.lng is not None:
            return request.lng, request.lat, "frontend_coordinates"
        for place, coordinates in PLACE_COORDINATES.items():
            if place in request.birth_place:
                return coordinates[0], coordinates[1], "built_in_place_lookup"
        return 120.0, None, "default_china_standard_meridian"

    @staticmethod
    def calculate_bazi_mock(birthday: date, true_solar_datetime: datetime) -> dict[str, float]:
        seed = f"{birthday.isoformat()}|{true_solar_datetime.strftime('%H:%M')}".encode("utf-8")
        digest = hashlib.sha256(seed).digest()
        raw = {element: float(digest[index] + 35) for index, element in enumerate(ELEMENTS)}
        # Time branch influence: night favors water, noon favors fire.
        hour = true_solar_datetime.hour
        if 21 <= hour or hour < 5:
            raw["水"] += 80
        elif 9 <= hour < 15:
            raw["火"] += 80
        elif 5 <= hour < 9:
            raw["木"] += 60
        elif 15 <= hour < 19:
            raw["金"] += 60
        else:
            raw["土"] += 60
        return normalized_profile(raw, 55)

    @staticmethod
    def calculate_name_energy(name: str) -> dict[str, float]:
        raw = empty_profile()
        for char in name:
            matched = False
            for element, chars in NAME_ELEMENT_CHARS.items():
                if char in chars:
                    raw[element] += 1
                    matched = True
                    break
            if not matched:
                raw[ELEMENTS[ord(char) % len(ELEMENTS)]] += 1
        return normalized_profile(raw, 10)

    @staticmethod
    def calculate_wish_energy(core_wishes: list[str]) -> dict[str, float]:
        profile = empty_profile()
        target_elements = {
            element
            for wish in core_wishes
            for element in WISH_MAPPING[wish]
        }
        points = 20 / len(target_elements)
        for element in target_elements:
            profile[element] += points
        drift = round(20 - sum(profile.values()), 2)
        first = next(iter(target_elements))
        profile[first] = round(profile[first] + drift, 2)
        return profile
