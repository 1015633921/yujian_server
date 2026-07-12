from __future__ import annotations

import math
from datetime import datetime, timedelta

from .fortune.bazi import calculate_bazi
from .fortune.chakra import calculate_chakra_profile
from .fortune.common import ELEMENTS, empty_profile, normalized_profile
from .fortune.mood_palette import calculate_mood_profile
from .fortune.name_elements import analyze_name
from .locations import CALIBRATION_VERSION, DEFAULT_TIMEZONE, LOCATION_DATA_VERSION, LOCATION_RECORDS, resolve_location
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

MBTI_DIMENSION_LABELS = {
    "I": "安静聚焦",
    "E": "开放表达",
    "N": "灵感探索",
    "S": "具体务实",
    "T": "理性清晰",
    "F": "柔和共情",
    "J": "计划有序",
    "P": "弹性自由",
}

ELEMENT_STYLE_LABELS = {
    "金": "清晰有序",
    "木": "轻盈舒展",
    "水": "清透安静",
    "火": "明亮有活力",
    "土": "温润稳重",
}

WISH_MAPPING = {
    "招财进宝/事业腾飞": ("金", "土"),
    "正缘桃花/人际和合": ("火", "木"),
    "辟邪防小人/消除焦虑": ("水", "金"),
    "健康护身/保持专注": ("木", "土"),
}

PLACE_COORDINATES = {
    alias: (record.longitude, record.latitude)
    for record in LOCATION_RECORDS
    for alias in record.aliases
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
            "mbti_analysis": self.analyze_mbti(request.mbti, mbti),
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
        local_datetime = datetime.combine(request.birthday, request.birth_time)
        resolution = self.resolve_coordinates(request)
        if resolution["status"] != "applied":
            return {
                "beijing_time": local_datetime.strftime("%Y-%m-%d %H:%M"),
                "true_solar_time": None,
                "calibrated_time": None,
                "longitude": None,
                "latitude": None,
                "longitude_correction_minutes": None,
                "equation_of_time_minutes": None,
                "total_correction_minutes": None,
                "location_source": resolution["source"],
                "resolved_location_code": resolution.get("location_code"),
                "timezone": DEFAULT_TIMEZONE,
                "calibration_status": resolution["status"],
                "calibration_source": resolution["source"],
                "calibration_version": CALIBRATION_VERSION,
                "location_data_version": LOCATION_DATA_VERSION,
                "calibration_reason_code": resolution["reason_code"],
                "true_solar_datetime": local_datetime,
            }
        longitude = float(resolution["longitude"])
        latitude = float(resolution["latitude"])
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
            "location_source": resolution["source"],
            "resolved_location_code": resolution["location_code"],
            "timezone": DEFAULT_TIMEZONE,
            "calibration_status": "applied",
            "calibration_source": resolution["source"],
            "calibration_version": CALIBRATION_VERSION,
            "location_data_version": LOCATION_DATA_VERSION,
            "calibration_reason_code": "location_resolved",
            "calibrated_time": true_solar_datetime.strftime("%Y-%m-%d %H:%M"),
            "true_solar_datetime": true_solar_datetime,
        }

    @staticmethod
    def resolve_coordinates(request: AssessmentRequest) -> dict:
        if request.birth_time_unknown:
            return {
                "status": "not_required",
                "source": "user_declared_unknown_time",
                "reason_code": "birth_time_unknown",
                "location_code": None,
            }
        record = resolve_location(request.location_code, request.birth_place)
        if not record:
            return {
                "status": "unsupported" if request.birth_place else "unavailable",
                "source": "project_location_dataset",
                "reason_code": "location_not_in_versioned_dataset",
                "location_code": request.location_code,
            }
        if request.lng is not None:
            matches = abs(request.lng - record.longitude) <= 0.01 and abs(request.lat - record.latitude) <= 0.01
            if not matches:
                return {
                    "status": "invalid_location",
                    "source": "project_location_dataset",
                    "reason_code": "client_coordinates_do_not_match_location",
                    "location_code": record.code,
                }
        return {
            "status": "applied",
            "source": "built_in_place_lookup",
            "reason_code": "location_resolved",
            "location_code": record.code,
            "longitude": record.longitude,
            "latitude": record.latitude,
        }

    @staticmethod
    def calculate_mbti_energy(mbti: str | None) -> dict[str, float]:
        raw = MBTI_MAPPING[mbti] if mbti else NEUTRAL_MBTI_PROFILE
        return normalized_profile(raw, ENERGY_WEIGHTS["mbti"])

    @staticmethod
    def analyze_mbti(mbti: str | None, profile: dict[str, float] | None = None) -> dict:
        normalized_mbti = (mbti or "").upper()
        if normalized_mbti not in MBTI_MAPPING:
            return {
                "selected": False,
                "type": "",
                "weight": ENERGY_WEIGHTS["mbti"],
                "keywords": [],
                "top_elements": [],
                "preference": "",
                "summary": "未填写 MBTI，本次不加入性格偏好方向。",
                "influence": "MBTI 只作为搭配偏好辅助，不单独决定元素结论或推荐结果。",
            }

        mbti_profile = profile or EnergyCalculator.calculate_mbti_energy(normalized_mbti)
        top_elements = [
            element
            for element, _ in sorted(mbti_profile.items(), key=lambda item: item[1], reverse=True)[:2]
        ]
        keywords = [MBTI_DIMENSION_LABELS[letter] for letter in normalized_mbti]
        preference = "、".join(ELEMENT_STYLE_LABELS[element] for element in top_elements)
        return {
            "selected": True,
            "type": normalized_mbti,
            "weight": ENERGY_WEIGHTS["mbti"],
            "keywords": keywords,
            "top_elements": top_elements,
            "preference": preference,
            "summary": (
                f"{normalized_mbti} 的偏好线索更接近{'、'.join(keywords)}，"
                f"搭配上可参考{preference}的表达。"
            ),
            "influence": (
                f"以 {ENERGY_WEIGHTS['mbti']}/100 的辅助权重参与，"
                "用于微调材质气质与推荐排序，不单独决定结果。"
            ),
        }

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
