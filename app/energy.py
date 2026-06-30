from __future__ import annotations

import math
from datetime import datetime, timedelta

from .fortune.bazi import calculate_bazi
from .fortune.chakra import calculate_chakra_profile
from .fortune.common import ELEMENTS, empty_profile, normalized_profile
from .fortune.mood_palette import calculate_mood_profile
from .fortune.name_elements import analyze_name
from .schemas import AssessmentRequest

ENERGY_WEIGHTS = {
    "bazi": 50,
    "wish": 18,
    "name": 8,
    "mbti": 8,
    "chakra": 8,
    "mood": 8,
}

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

class EnergyCalculator:
    """Combines real Bazi, wish, name, MBTI and live-state inputs into 100 points."""

    def calculate(self, request: AssessmentRequest) -> dict:
        solar_time = self.calculate_true_solar_time(request)
        bazi_result = calculate_bazi(solar_time["true_solar_datetime"], ENERGY_WEIGHTS["bazi"])
        mbti = self.calculate_mbti_energy(request.mbti)
        name, name_analysis = self.calculate_name_energy(request.name)
        wish = self.calculate_wish_energy(request.core_wishes)
        chakra, chakra_analysis = calculate_chakra_profile(request.chakra_answers, ENERGY_WEIGHTS["chakra"])
        mood, mood_analysis = calculate_mood_profile(request.mood_palette_id, ENERGY_WEIGHTS["mood"])
        breakdown = {"bazi": bazi_result.profile, "wish": wish, "name": name, "mbti": mbti, "chakra": chakra, "mood": mood}
        final = {
            element: round(sum(profile[element] for profile in breakdown.values()), 2)
            for element in ELEMENTS
        }
        return {
            "solar_time": {key: value for key, value in solar_time.items() if key != "true_solar_datetime"},
            "breakdown": breakdown,
            "bazi_basis": bazi_result.basis,
            "name_analysis": name_analysis,
            "chakra_analysis": chakra_analysis,
            "mood_analysis": mood_analysis,
            "useful_elements": bazi_result.basis["useful_elements"],
            "recommendation_strategy": bazi_result.basis["strategy"],
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
    def calculate_mbti_energy(mbti: str | None) -> dict[str, float]:
        raw = MBTI_MAPPING[mbti] if mbti else NEUTRAL_MBTI_PROFILE
        return normalized_profile(raw, ENERGY_WEIGHTS["mbti"])

    @staticmethod
    def calculate_name_energy(name: str) -> tuple[dict[str, float], dict]:
        return analyze_name(name, ENERGY_WEIGHTS["name"])

    @staticmethod
    def calculate_wish_energy(core_wishes: list[str]) -> dict[str, float]:
        profile = empty_profile()
        target_elements = {
            element
            for wish in core_wishes
            for element in WISH_MAPPING[wish]
        }
        points = ENERGY_WEIGHTS["wish"] / len(target_elements)
        for element in target_elements:
            profile[element] += points
        drift = round(ENERGY_WEIGHTS["wish"] - sum(profile.values()), 2)
        first = next(iter(target_elements))
        profile[first] = round(profile[first] + drift, 2)
        return profile
