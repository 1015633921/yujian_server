from __future__ import annotations

import hashlib
import json
import logging
import math
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .energy import ELEMENTS, ENERGY_WEIGHTS, EnergyCalculator, MBTI_MAPPING, PLACE_COORDINATES, WISH_MAPPING
from .fortune.chakra import public_chakra_options
from .fortune.mood_palette import public_mood_palettes
from .fortune.zodiac import calculate_zodiac_analysis
from .copy_safety import safe_display_text
from .recommendation import RecommendationEngine, interpretation
from .repository import AssessmentRepository
from .report_repository import ReportConflictError, ReportRepository
from .reporting import REPORT_ALGORITHM_VERSION, REPORT_SCHEMA_VERSION, sanitized_output_snapshot, stable_hash
from .observability import log_event, safe_exception_frames
from .schemas import AssessmentRequest, DIYRecommendationRequest

CHINA_TZ = ZoneInfo("Asia/Shanghai")
DIY_RECOMMENDATION_CACHE_VERSION = "2026-07-12-mbti-v2"
LOGGER = logging.getLogger(__name__)

ELEMENT_ZEN_WORDS = {
    "金": ["澄心", "清骨", "守界", "素光"],
    "木": ["青岚", "生发", "舒枝", "含章"],
    "水": ["静澜", "涵养", "听雨", "归流"],
    "火": ["明照", "暖阳", "照心", "赤诚"],
    "土": ["厚载", "安住", "归根", "静守"],
}

MONTH_ENERGY_CONTEXT = {
    1: ("小寒至大寒", "水", "寒水收敛，适合蓄力与复盘"),
    2: ("立春至雨水", "木", "木气初生，适合启动新计划"),
    3: ("惊蛰至春分", "木", "木气渐盛，行动欲与表达欲上升"),
    4: ("清明至谷雨", "土", "春土承接，适合整理关系与秩序"),
    5: ("立夏至小满", "火", "火气升腾，注意情绪消耗与睡眠节律"),
    6: ("芒种至夏至", "火", "夏季火旺，容易心神外散与精力透支"),
    7: ("小暑至大暑", "火", "暑火最盛，注意急躁、节奏偏急与过度社交"),
    8: ("立秋至处暑", "金", "金气初显，适合收束计划与建立边界"),
    9: ("白露至秋分", "金", "秋金清肃，适合断舍离与回到重点"),
    10: ("寒露至霜降", "土", "燥土承金，注意脾胃、焦虑与思虑过重"),
    11: ("立冬至小雪", "水", "水气渐旺，适合沉淀、休息与储备"),
    12: ("大雪至冬至", "水", "冬水深藏，适合减少消耗、养精蓄能"),
}

ELEMENT_DRAIN_POINTS = {
    "金": "容易在规则、边界与判断上过度用力，形成紧绷感。",
    "木": "容易同时开启太多计划，精力被分散在生长与变化里。",
    "水": "容易思绪过深、睡眠变浅，情绪在暗处反复流动。",
    "火": "容易外放过度、急于回应，心神和耐心被快速消耗。",
    "土": "容易陷入责任感和反复权衡，身体与情绪都变得沉重。",
}

ELEMENT_SEASON_ADVICE = {
    "金": "用清晰边界守住节奏，少做临时承诺。",
    "木": "把新想法拆成小步执行，避免一口气铺太开。",
    "水": "给睡眠、独处和慢节奏留出空间，先稳住内在流动。",
    "火": "减少情绪性决策，重要沟通尽量放慢半拍。",
    "土": "把杂事归类落地，先处理最能减负的一件事。",
}


class AssessmentService:
    def __init__(self, db_path: Path | None = None):
        self.energy_calculator = EnergyCalculator()
        self.recommendation_engine = RecommendationEngine()
        self.repository = AssessmentRepository(db_path) if db_path is not None else AssessmentRepository()
        self.report_repository = ReportRepository(db_path) if db_path is not None else ReportRepository()

    def calculate(self, request: AssessmentRequest) -> tuple[dict, bool]:
        fingerprint = self.fingerprint(request)
        if not request.force_recalculate:
            existing = self.repository.find_by_fingerprint(fingerprint)
            if existing:
                return self.with_energy_extras(existing), True

        energy = self.energy_calculator.calculate(request)
        recommendation = self.recommendation_engine.recommend(request, energy)
        created_at = datetime.now(CHINA_TZ).isoformat()
        energy_keywords = self.energy_keywords(energy["final"], energy["strongest"], energy["weakest"], request.core_wishes)
        seasonal_energy = self.seasonal_energy_prompt(energy["final"], energy["strongest"], energy["weakest"])
        zodiac_analysis = calculate_zodiac_analysis(request.birthday, energy["strongest"], energy["weakest"])
        result = {
            "assessment_id": uuid.uuid4().hex,
            "created_at": created_at,
            "input_summary": self.input_summary(request, include_wrist=True),
            "solar_time": energy["solar_time"],
            "bazi_basis": energy["bazi_basis"],
            "mbti_analysis": energy["mbti_analysis"],
            "name_analysis": energy["name_analysis"],
            "chakra_analysis": energy["chakra_analysis"],
            "mood_analysis": energy["mood_analysis"],
            "zodiac_analysis": zodiac_analysis,
            "useful_elements": energy["useful_elements"],
            "recommendation_strategy": energy["recommendation_strategy"],
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
            "energy_keywords": energy_keywords,
            "seasonal_energy": seasonal_energy,
            "primary_crystal": recommendation["primary"],
            "supporting_crystals": recommendation["supporting"],
            "bracelet_plan": recommendation["bracelet_plan"],
            "recommendation_copy": recommendation["copy"],
            "care_tips": [
                "首次佩戴前用柔软干布轻拭，保持珠体洁净。",
                "把手串作为愿望提醒工具，不替代医疗、心理或财务建议。",
                "洗澡、运动和睡眠时建议取下，避免磕碰与化学清洁剂。",
            ],
            "disclaimer": "本分析仅用于传统文化体验、审美搭配与个性化 DIY 推荐，不构成命理判断、医疗健康建议或效果承诺。",
        }
        self.repository.save(result, fingerprint)
        return result, False

    def calculate_energy(self, request: AssessmentRequest) -> tuple[dict, bool]:
        fingerprint = self.energy_fingerprint(request)
        if not request.force_recalculate:
            existing = self.repository.find_by_fingerprint(fingerprint)
            if existing:
                return self.with_energy_extras(existing), True

        result = self._build_energy_result(request)
        self.repository.save(result, fingerprint)
        return result, False

    def _build_energy_result(self, request: AssessmentRequest) -> dict:
        energy = self.energy_calculator.calculate(request)
        energy_keywords = self.energy_keywords(energy["final"], energy["strongest"], energy["weakest"], request.core_wishes)
        seasonal_energy = self.seasonal_energy_prompt(energy["final"], energy["strongest"], energy["weakest"])
        zodiac_analysis = calculate_zodiac_analysis(request.birthday, energy["strongest"], energy["weakest"])
        return {
            "assessment_id": uuid.uuid4().hex,
            "created_at": datetime.now(CHINA_TZ).isoformat(),
            "status": "energy_ready",
            "input_summary": self.input_summary(request, include_wrist=False),
            "solar_time": energy["solar_time"],
            "bazi_basis": energy["bazi_basis"],
            "mbti_analysis": energy["mbti_analysis"],
            "name_analysis": energy["name_analysis"],
            "chakra_analysis": energy["chakra_analysis"],
            "mood_analysis": energy["mood_analysis"],
            "zodiac_analysis": zodiac_analysis,
            "useful_elements": energy["useful_elements"],
            "recommendation_strategy": energy["recommendation_strategy"],
            "final_energy_profile": energy["final"],
            "energy_breakdown": energy["breakdown"],
            "chart": self.chart(energy),
            "strongest_element": energy["strongest"],
            "weakest_element": energy["weakest"],
            "interpretation": interpretation(energy["final"], energy["strongest"], energy["weakest"]),
            "energy_keywords": energy_keywords,
            "seasonal_energy": seasonal_energy,
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
            "disclaimer": "本分析仅用于传统文化体验、审美搭配与个性化 DIY 推荐，不构成命理判断、医疗健康建议或效果承诺。",
        }
    def calculate_energy_v2(self, request: AssessmentRequest, idempotency_key: str) -> tuple[dict, bool]:
        if not request.user_id:
            raise ValueError("报告必须绑定当前用户")
        key = self.report_repository.normalize_key(idempotency_key)
        input_snapshot = self.input_summary(request, include_wrist=False)
        source_input_hash = stable_hash(input_snapshot)
        existing_request = self.report_repository.get_request(request.user_id, key)
        if existing_request:
            if existing_request["source_input_hash"] != source_input_hash:
                raise ReportConflictError("同一 Idempotency-Key 不能用于不同的测算输入")
            if existing_request["status"] != "completed" or not existing_request.get("report_id"):
                raise ReportConflictError("报告正在生成，请使用原请求稍后重试")
            snapshot = self.report_repository.get(str(existing_request["report_id"]))
            if not snapshot:
                raise ReportConflictError("幂等记录缺少对应报告，请稍后重试")
            return self.report_repository.detail_dto(snapshot), True
        result = self._build_energy_result(request)
        solar_time = result.get("solar_time") or {}
        result["algorithm_version"] = REPORT_ALGORITHM_VERSION
        result["schema_version"] = REPORT_SCHEMA_VERSION
        result["calibration_version"] = solar_time.get("calibration_version") or "legacy_unknown"
        result["calibration_status"] = solar_time.get("calibration_status") or "legacy_unknown"
        output_snapshot = sanitized_output_snapshot(result, input_snapshot)
        snapshot, replay = self.report_repository.create_snapshot(
            user_id=request.user_id,
            idempotency_key=key,
            source_input_hash=source_input_hash,
            fingerprint=self.energy_fingerprint(request),
            input_snapshot=input_snapshot,
            output_snapshot=output_snapshot,
            assessment_id=result["assessment_id"],
            created_at=result["created_at"],
            algorithm_version=REPORT_ALGORITHM_VERSION,
            schema_version=REPORT_SCHEMA_VERSION,
            calibration_version=result["calibration_version"],
            calibration_status=result["calibration_status"],
            calibration_source=solar_time.get("calibration_source") or "unknown",
            calibration_reason_code=solar_time.get("calibration_reason_code") or "unknown",
        )
        return self.report_repository.detail_dto(snapshot), replay

    def create_diy_recommendation(
        self,
        assessment_id: str,
        payload: DIYRecommendationRequest,
    ) -> dict | None:
        cached = self.repository.get_cached_recommendation(
            assessment_id,
            payload.wrist_size_cm,
            payload.bead_size_mm,
            DIY_RECOMMENDATION_CACHE_VERSION,
        )
        if cached:
            self.repository.update(cached)
            return {**self.with_energy_extras(cached), "recommendation_cache_hit": True}

        result = self._build_diy_recommendation(assessment_id, payload)
        if not result:
            return None
        timestamp = datetime.now(CHINA_TZ).isoformat()
        self.repository.save_cached_recommendation(
            assessment_id,
            payload.wrist_size_cm,
            payload.bead_size_mm,
            DIY_RECOMMENDATION_CACHE_VERSION,
            result,
            timestamp,
        )
        self.repository.update(result)
        return {**self.with_energy_extras(result), "recommendation_cache_hit": False}

    def create_diy_recommendation_v2(
        self,
        report_id: str,
        user_id: str,
        payload: DIYRecommendationRequest,
    ) -> dict | None:
        snapshot = self.report_repository.owned(report_id, user_id, payload.expected_report_version)
        if not snapshot:
            return None
        cached = self.repository.get_cached_recommendation(
            snapshot["assessment_id"],
            payload.wrist_size_cm,
            payload.bead_size_mm,
            DIY_RECOMMENDATION_CACHE_VERSION,
            report_id=report_id,
            report_version=int(snapshot["report_version"]),
        )
        if cached:
            return {**cached, "recommendation_cache_hit": True}

        input_snapshot = snapshot["input_snapshot"]
        output_snapshot = snapshot["output_snapshot"]
        request = AssessmentRequest.model_validate(
            {
                **input_snapshot,
                "wrist_size_cm": payload.wrist_size_cm,
                "bead_size_mm": payload.bead_size_mm,
            }
        )
        energy = {
            "final": output_snapshot["final_energy_profile"],
            "breakdown": output_snapshot["energy_breakdown"],
            "solar_time": output_snapshot.get("solar_time") or {},
            "bazi_basis": output_snapshot.get("bazi_basis") or {},
            "mbti_analysis": output_snapshot.get("mbti_analysis") or {},
            "chakra_analysis": output_snapshot.get("chakra_analysis") or {},
            "mood_analysis": output_snapshot.get("mood_analysis") or {},
            "useful_elements": output_snapshot.get("useful_elements") or [],
            "recommendation_strategy": output_snapshot.get("recommendation_strategy") or "",
            "strongest": output_snapshot["strongest_element"],
            "weakest": output_snapshot["weakest_element"],
        }
        recommendation = self.recommendation_engine.recommend(request, energy)
        workbench_payload = {
            "source": "report_snapshot",
            "assessment_id": snapshot["assessment_id"],
            "report_id": report_id,
            "report_version": int(snapshot["report_version"]),
            "name": f"{request.name}的专属搭配手串",
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
        result = {
            "status": "diy_ready",
            "assessment_id": snapshot["assessment_id"],
            "report_id": report_id,
            "report_version": int(snapshot["report_version"]),
            "source_algorithm_version": snapshot["algorithm_version"],
            "primary_crystal": recommendation["primary"],
            "supporting_crystals": recommendation["supporting"],
            "bracelet_plan": recommendation["bracelet_plan"],
            "recommendation_copy": recommendation["copy"],
            "workbench_payload": workbench_payload,
        }
        timestamp = datetime.now(CHINA_TZ).isoformat()
        self.repository.save_cached_recommendation(
            snapshot["assessment_id"],
            payload.wrist_size_cm,
            payload.bead_size_mm,
            DIY_RECOMMENDATION_CACHE_VERSION,
            result,
            timestamp,
            report_id=report_id,
            report_version=int(snapshot["report_version"]),
        )
        return {**result, "recommendation_cache_hit": False}

    def pre_generate_diy_recommendation(
        self,
        assessment_id: str,
        wrist_size_cm: float = 16.0,
        bead_size_mm: int = 8,
    ) -> bool:
        try:
            return self._pre_generate_diy_recommendation(
                assessment_id,
                wrist_size_cm,
                bead_size_mm,
            )
        except Exception as exc:
            log_event(
                LOGGER,
                "report.recommendation_pre_generate.failed",
                level=logging.ERROR,
                assessment_id_hash=hashlib.sha256(assessment_id.encode("utf-8")).hexdigest()[:16],
                error_type=type(exc).__name__,
                stack=safe_exception_frames(exc),
                result="failed",
            )
            return False

    def _pre_generate_diy_recommendation(
        self,
        assessment_id: str,
        wrist_size_cm: float,
        bead_size_mm: int,
    ) -> bool:
        payload = DIYRecommendationRequest(
            wrist_size_cm=wrist_size_cm,
            bead_size_mm=bead_size_mm,
        )
        cached = self.repository.get_cached_recommendation(
            assessment_id,
            payload.wrist_size_cm,
            payload.bead_size_mm,
            DIY_RECOMMENDATION_CACHE_VERSION,
        )
        if cached:
            return True
        result = self._build_diy_recommendation(assessment_id, payload)
        if not result:
            return False
        timestamp = datetime.now(CHINA_TZ).isoformat()
        self.repository.save_cached_recommendation(
            assessment_id,
            payload.wrist_size_cm,
            payload.bead_size_mm,
            DIY_RECOMMENDATION_CACHE_VERSION,
            result,
            timestamp,
        )
        return True

    def _build_diy_recommendation(
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
            "bazi_basis": assessment.get("bazi_basis") or {},
            "mbti_analysis": assessment.get("mbti_analysis") or self.energy_calculator.analyze_mbti(
                request.mbti,
                (assessment.get("energy_breakdown") or {}).get("mbti"),
            ),
            "chakra_analysis": assessment.get("chakra_analysis") or {},
            "mood_analysis": assessment.get("mood_analysis") or {},
            "useful_elements": assessment.get("useful_elements") or [],
            "recommendation_strategy": assessment.get("recommendation_strategy") or "",
            "strongest": assessment["strongest_element"],
            "weakest": assessment["weakest_element"],
        }
        recommendation = self.recommendation_engine.recommend(request, energy)
        workbench_payload = {
            "source": "energy_assessment",
            "assessment_id": assessment_id,
            "name": f"{request.name}的专属搭配手串",
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
        return assessment

    @staticmethod
    def fingerprint(request: AssessmentRequest) -> str:
        return AssessmentService.product_fingerprint(request)

    @staticmethod
    def natal_fingerprint(request: AssessmentRequest) -> str:
        payload = request.model_dump(
            mode="json",
            include={"name", "birthday", "birth_time", "birth_place", "lng", "lat"},
        )
        raw = f"natal:{json.dumps(payload, ensure_ascii=False, sort_keys=True)}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def assessment_fingerprint(request: AssessmentRequest) -> str:
        payload = request.model_dump(
            mode="json",
            exclude={"force_recalculate", "wrist_size_cm", "bead_size_mm"},
        )
        raw = f"assessment:{json.dumps(payload, ensure_ascii=False, sort_keys=True)}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def product_fingerprint(request: AssessmentRequest) -> str:
        payload = request.model_dump(mode="json", exclude={"force_recalculate"})
        raw = f"product:{json.dumps(payload, ensure_ascii=False, sort_keys=True)}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def energy_fingerprint(request: AssessmentRequest) -> str:
        return AssessmentService.assessment_fingerprint(request)

    @staticmethod
    def input_summary(request: AssessmentRequest, include_wrist: bool = True) -> dict:
        summary = {
            "user_id": request.user_id,
            "name": request.name,
            "birthday": request.birthday.isoformat(),
            "birth_time": request.birth_time.strftime("%H:%M"),
            "birth_time_unknown": request.birth_time_unknown,
            "birth_place": request.birth_place,
            "location_code": request.location_code,
            "lng": request.lng,
            "lat": request.lat,
            "mbti": request.mbti,
            "core_wish": request.primary_core_wish,
            "core_wishes": request.core_wishes,
            "chakra_answers": request.chakra_answers,
            "mood_palette_id": request.mood_palette_id,
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

    @staticmethod
    def energy_keywords(
        final_profile: dict[str, float],
        strongest: str,
        weakest: str,
        core_wishes: list[str] | None = None,
    ) -> list[dict]:
        sorted_elements = sorted(final_profile.items(), key=lambda item: item[1], reverse=True)
        second = sorted_elements[1][0] if len(sorted_elements) > 1 else strongest
        weakest_word = ELEMENT_ZEN_WORDS.get(weakest, ["调和"])[-1]
        strongest_words = ELEMENT_ZEN_WORDS.get(strongest, ["澄明", "静守"])
        second_words = ELEMENT_ZEN_WORDS.get(second, ["含章"])
        wish_text = "愿景成形"
        wishes = core_wishes or []
        if wishes:
            if any("财" in wish or "事业" in wish for wish in wishes):
                wish_text = "目标成形"
            elif any("桃花" in wish or "人际" in wish or "正缘" in wish for wish in wishes):
                wish_text = "关系柔和"
            elif any("焦虑" in wish or "辟邪" in wish or "守护" in wish for wish in wishes):
                wish_text = "安定边界"
            elif any("健康" in wish or "专注" in wish for wish in wishes):
                wish_text = "专注平衡"
        labels = [
            {"label": strongest_words[0], "source": "主元素", "element": strongest},
            {"label": second_words[0], "source": "辅助气质", "element": second},
            {"label": weakest_word, "source": "调和方向", "element": weakest},
            {"label": wish_text, "source": "当前目标", "element": ""},
        ]
        seen = set()
        unique = []
        for item in labels:
            if item["label"] not in seen:
                seen.add(item["label"])
                unique.append(item)
        return unique

    @staticmethod
    def seasonal_energy_prompt(
        final_profile: dict[str, float],
        strongest: str,
        weakest: str,
        now: datetime | None = None,
    ) -> dict:
        current = now or datetime.now(CHINA_TZ)
        season_name, seasonal_element, seasonal_copy = MONTH_ENERGY_CONTEXT[current.month]
        seasonal_value = float(final_profile.get(seasonal_element, 0))
        weakest_value = float(final_profile.get(weakest, 0))
        strongest_value = float(final_profile.get(strongest, 0))
        is_same_as_strongest = seasonal_element == strongest
        is_same_as_weakest = seasonal_element == weakest
        if is_same_as_strongest:
            notice = f"当下{seasonal_element}元素与本身偏强方向同频，容易把优势用过头。"
            drain = ELEMENT_DRAIN_POINTS[seasonal_element]
            suggestion = ELEMENT_SEASON_ADVICE[seasonal_element]
        elif is_same_as_weakest:
            notice = f"当下{seasonal_element}元素正在呼应你的可调和方向，适合借势建立新习惯。"
            drain = f"需要注意的是，{weakest}元素刚被带起时不宜用力过猛，先从稳定的小节奏开始。"
            suggestion = ELEMENT_SEASON_ADVICE[weakest]
        elif seasonal_value >= strongest_value * 0.88:
            notice = f"当下{seasonal_element}元素较明显，也会增强你画像里相近的状态倾向。"
            drain = ELEMENT_DRAIN_POINTS[seasonal_element]
            suggestion = f"{ELEMENT_SEASON_ADVICE[seasonal_element]}同时别忘了温柔调和{weakest}。"
        else:
            notice = f"外在时令偏{seasonal_element}，你的个人画像则更适合照看{weakest}。"
            drain = ELEMENT_DRAIN_POINTS[weakest]
            suggestion = ELEMENT_SEASON_ADVICE[weakest]
        return {
            "title": "近期状态提示",
            "period": season_name,
            "seasonal_element": seasonal_element,
            "seasonal_copy": safe_display_text(seasonal_copy),
            "notice": safe_display_text(notice),
            "drain_point": safe_display_text(drain),
            "suggestion": safe_display_text(suggestion),
            "summary": safe_display_text(f"{season_name}，{seasonal_copy}。{notice}{drain}{suggestion}"),
        }

    @classmethod
    def with_energy_extras(cls, result: dict | None) -> dict | None:
        if not result:
            return result
        enriched = dict(result)
        final_profile = enriched.get("final_energy_profile") or {}
        if not final_profile:
            return enriched

        sorted_elements = sorted(final_profile.items(), key=lambda item: item[1], reverse=True)
        strongest = enriched.get("strongest_element") or (sorted_elements[0][0] if sorted_elements else ELEMENTS[0])
        weakest = enriched.get("weakest_element") or (sorted_elements[-1][0] if sorted_elements else ELEMENTS[-1])
        input_summary = enriched.get("input_summary") or {}
        core_wishes = input_summary.get("core_wishes") or []
        if not core_wishes and input_summary.get("core_wish"):
            core_wishes = [input_summary["core_wish"]]

        if not enriched.get("energy_keywords"):
            enriched["energy_keywords"] = cls.energy_keywords(final_profile, strongest, weakest, core_wishes)
        if not enriched.get("mbti_analysis"):
            enriched["mbti_analysis"] = EnergyCalculator.analyze_mbti(
                input_summary.get("mbti"),
                (enriched.get("energy_breakdown") or {}).get("mbti"),
            )
        if not enriched.get("seasonal_energy"):
            enriched["seasonal_energy"] = cls.seasonal_energy_prompt(final_profile, strongest, weakest)
        if not enriched.get("zodiac_analysis"):
            enriched["zodiac_analysis"] = calculate_zodiac_analysis(input_summary.get("birthday"), strongest, weakest)
        return enriched

    def get(self, assessment_id: str) -> dict | None:
        return self.with_energy_extras(self.repository.get(assessment_id))

    def history(self, user_id: str, limit: int) -> list[dict]:
        return [self.with_energy_extras(item) for item in self.repository.history(user_id, limit)]

    def privacy_data_summary(self, user_id: str) -> dict:
        return self.repository.privacy_data_summary(user_id)

    def delete_personalization_data(self, user_id: str) -> dict:
        return self.repository.delete_personalization_data(user_id)

    @staticmethod
    def options() -> dict:
        catalog = RecommendationEngine.catalog()
        primary_pools = RecommendationEngine.primary_pools(catalog)
        return {
            "mbti_options": sorted(MBTI_MAPPING),
            "mbti_optional": True,
            "core_wish_options": [
                {
                    "value": wish,
                    "label": wish,
                    "target_elements": list(elements),
                    "primary_crystals": [catalog[code]["name"] for code in primary_pools[wish] if code in catalog],
                }
                for wish, elements in WISH_MAPPING.items()
            ],
            "core_wish_selection": {"min": 1, "max": 3, "primary_rule": "第一个愿望用于锁定主石"},
            "chakra_questions": public_chakra_options(),
            "mood_palettes": public_mood_palettes(),
            "birth_place_presets": [
                {"label": place, "lng": coordinates[0], "lat": coordinates[1]}
                for place, coordinates in PLACE_COORDINATES.items()
            ],
            "wrist_size": {"min": 10, "max": 30, "default": 15.5, "step": 0.5},
            "bead_size_options": [6, 8, 10, 12],
            "calculation_weights": ENERGY_WEIGHTS,
        }
