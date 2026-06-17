from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from .energy import ELEMENTS, EnergyCalculator, MBTI_MAPPING, PLACE_COORDINATES, WISH_MAPPING
from .recommendation import CRYSTAL_CATALOG, PRIMARY_POOLS, RecommendationEngine, interpretation
from .repository import AssessmentRepository
from .schemas import AssessmentRequest, DIYRecommendationRequest

CHINA_TZ = ZoneInfo("Asia/Shanghai")


class AssessmentService:
    def __init__(self):
        self.energy_calculator = EnergyCalculator()
        self.recommendation_engine = RecommendationEngine()
        self.repository = AssessmentRepository()

    def calculate(self, request: AssessmentRequest) -> tuple[dict, bool]:
        fingerprint = self.fingerprint(request)
        if not request.force_recalculate:
            existing = self.repository.find_by_fingerprint(fingerprint)
            if existing:
                return existing, True

        energy = self.energy_calculator.calculate(request)
        recommendation = self.recommendation_engine.recommend(request, energy)
        created_at = datetime.now(CHINA_TZ).isoformat()
        result = {
            "assessment_id": uuid.uuid4().hex,
            "created_at": created_at,
            "input_summary": {
                "user_id": request.user_id,
                "name": request.name,
                "birthday": request.birthday.isoformat(),
                "birth_time": request.birth_time.strftime("%H:%M"),
                "birth_place": request.birth_place,
                "mbti": request.mbti,
                "core_wish": request.primary_core_wish,
                "core_wishes": request.core_wishes,
                "wrist_size_cm": request.wrist_size_cm,
                "bead_size_mm": request.bead_size_mm,
            },
            "solar_time": energy["solar_time"],
            "final_energy_profile": energy["final"],
            "energy_breakdown": energy["breakdown"],
            "chart": {
                "type": "radar",
                "indicator": [
                    {
                        "name": element,
                        "max": max(30, math.ceil(max(energy["final"].values()) / 5) * 5),
                    }
                    for element in ELEMENTS
                ],
                "values": [energy["final"][element] for element in ELEMENTS],
                "colors": {
                    "金": "#C8A95B",
                    "木": "#548B62",
                    "水": "#4E7893",
                    "火": "#C75B4B",
                    "土": "#9B7653",
                },
            },
            "strongest_element": energy["strongest"],
            "weakest_element": energy["weakest"],
            "interpretation": interpretation(energy["final"], energy["strongest"], energy["weakest"]),
            "primary_crystal": recommendation["primary"],
            "supporting_crystals": recommendation["supporting"],
            "bracelet_plan": recommendation["bracelet_plan"],
            "recommendation_copy": recommendation["copy"],
            "care_tips": [
                "首次佩戴前用柔软干布轻拭，保持珠体洁净。",
                "把手串作为愿望提醒工具，不替代医疗、心理或财务建议。",
                "洗澡、运动和睡眠时建议取下，避免磕碰与化学清洁剂。",
            ],
            "disclaimer": "本测算用于文化体验与个性化 DIY 推荐，不构成命理、医疗或投资建议。",
        }
        self.repository.save(result, fingerprint)
        return result, False

    def calculate_energy(self, request: AssessmentRequest) -> tuple[dict, bool]:
        fingerprint = self.energy_fingerprint(request)
        if not request.force_recalculate:
            existing = self.repository.find_by_fingerprint(fingerprint)
            if existing:
                return existing, True

        energy = self.energy_calculator.calculate(request)
        result = {
            "assessment_id": uuid.uuid4().hex,
            "created_at": datetime.now(CHINA_TZ).isoformat(),
            "status": "energy_ready",
            "input_summary": self.input_summary(request, include_wrist=False),
            "solar_time": energy["solar_time"],
            "final_energy_profile": energy["final"],
            "energy_breakdown": energy["breakdown"],
            "chart": self.chart(energy),
            "strongest_element": energy["strongest"],
            "weakest_element": energy["weakest"],
            "interpretation": interpretation(energy["final"], energy["strongest"], energy["weakest"]),
            "next_step": {
                "status": "waiting_for_wrist_size",
                "button_text": "生成我的专属手串",
                "description": "填写手腕周长后，为你生成适配尺寸的推荐手串。",
                "action": "open_wrist_size_form",
                "submit_api": "/api/v1/assessment/{assessment_id}/diy-recommendation",
                "fields": {
                    "wrist_size_cm": {"label": "手腕周长", "unit": "cm", "min": 10, "max": 30, "step": 0.5},
                    "bead_size_mm": {"label": "偏好珠径", "unit": "mm", "options": [6, 8, 10, 12], "default": 8},
                },
            },
            "disclaimer": "本测算用于文化体验与个性化 DIY 推荐，不构成命理、医疗或投资建议。",
        }
        self.repository.save(result, fingerprint)
        return result, False

    def create_diy_recommendation(
        self,
        assessment_id: str,
        payload: DIYRecommendationRequest,
    ) -> dict | None:
        assessment = self.repository.get(assessment_id)
        if not assessment:
            return None

        request_data = {
            **assessment["input_summary"],
            "wrist_size_cm": payload.wrist_size_cm,
            "bead_size_mm": payload.bead_size_mm,
        }
        request = AssessmentRequest.model_validate(request_data)
        energy = {
            "final": assessment["final_energy_profile"],
            "breakdown": assessment["energy_breakdown"],
            "solar_time": assessment["solar_time"],
            "strongest": assessment["strongest_element"],
            "weakest": assessment["weakest_element"],
        }
        recommendation = self.recommendation_engine.recommend(request, energy)
        workbench_payload = {
            "source": "energy_assessment",
            "assessment_id": assessment_id,
            "name": f"{request.name}的专属能量手串",
            "core_wish": request.primary_core_wish,
            "core_wishes": request.core_wishes,
            "wrist_size_cm": payload.wrist_size_cm,
            "bead_size_mm": payload.bead_size_mm,
            "primary_crystal": recommendation["primary"],
            "supporting_crystals": recommendation["supporting"],
            "bracelet_plan": recommendation["bracelet_plan"],
            "recommendation_copy": recommendation["copy"],
            "editable": True,
            "save_api": "/api/diy-plans/save/",
        }
        assessment.update(
            {
                "status": "diy_ready",
                "primary_crystal": recommendation["primary"],
                "supporting_crystals": recommendation["supporting"],
                "bracelet_plan": recommendation["bracelet_plan"],
                "recommendation_copy": recommendation["copy"],
                "workbench_payload": workbench_payload,
                "next_step": {
                    "status": "diy_ready",
                    "button_text": "进入 DIY 工作台",
                    "action": "navigate_to_diy_workbench",
                    "route": "/pages/diy-workbench/index",
                },
            }
        )
        self.repository.update(assessment)
        return assessment

    @staticmethod
    def fingerprint(request: AssessmentRequest) -> str:
        payload = request.model_dump(mode="json", exclude={"force_recalculate"})
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def energy_fingerprint(request: AssessmentRequest) -> str:
        payload = request.model_dump(
            mode="json",
            exclude={"force_recalculate", "wrist_size_cm", "bead_size_mm"},
        )
        raw = f"energy:{json.dumps(payload, ensure_ascii=False, sort_keys=True)}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def input_summary(request: AssessmentRequest, include_wrist: bool = True) -> dict:
        summary = {
            "user_id": request.user_id,
            "name": request.name,
            "birthday": request.birthday.isoformat(),
            "birth_time": request.birth_time.strftime("%H:%M"),
            "birth_place": request.birth_place,
            "lng": request.lng,
            "lat": request.lat,
            "mbti": request.mbti,
            "core_wish": request.primary_core_wish,
            "core_wishes": request.core_wishes,
        }
        if include_wrist:
            summary.update({"wrist_size_cm": request.wrist_size_cm, "bead_size_mm": request.bead_size_mm})
        return summary

    @staticmethod
    def chart(energy: dict) -> dict:
        chart_max = max(30, math.ceil(max(energy["final"].values()) / 5) * 5)
        return {
            "type": "radar",
            "indicator": [{"name": element, "max": chart_max} for element in ELEMENTS],
            "values": [energy["final"][element] for element in ELEMENTS],
            "colors": {
                "金": "#C8A95B",
                "木": "#548B62",
                "水": "#4E7893",
                "火": "#C75B4B",
                "土": "#9B7653",
            },
        }

    def get(self, assessment_id: str) -> dict | None:
        return self.repository.get(assessment_id)

    def history(self, user_id: str, limit: int) -> list[dict]:
        return self.repository.history(user_id, limit)

    @staticmethod
    def options() -> dict:
        return {
            "mbti_options": sorted(MBTI_MAPPING),
            "mbti_optional": True,
            "core_wish_options": [
                {
                    "value": wish,
                    "label": wish,
                    "target_elements": list(elements),
                    "primary_crystals": [CRYSTAL_CATALOG[code]["name"] for code in PRIMARY_POOLS[wish]],
                }
                for wish, elements in WISH_MAPPING.items()
            ],
            "core_wish_selection": {"min": 1, "max": 3, "primary_rule": "第一个愿望用于锁定主石"},
            "birth_place_presets": [
                {"label": place, "lng": coordinates[0], "lat": coordinates[1]}
                for place, coordinates in PLACE_COORDINATES.items()
            ],
            "wrist_size": {"min": 10, "max": 30, "default": 15.5, "step": 0.5},
            "bead_size_options": [6, 8, 10, 12],
            "calculation_weights": {"bazi": 55, "mbti": 15, "name": 10, "wish": 20},
        }
