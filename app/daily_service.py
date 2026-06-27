from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from .daily_energy import DAILY_ENERGY_CONTENT_VERSION, DailyEnergyCalculator
from .daily_rules import (
    DAILY_RULES_SETTING_KEY,
    daily_rules_version,
    normalize_daily_energy_rules,
    public_daily_rules_payload,
)
from .repository import AssessmentRepository
from .schemas import DailyCheckInRequest

CHINA_TZ = ZoneInfo("Asia/Shanghai")


class DailyEnergyService:
    def __init__(self):
        self.repository = AssessmentRepository()
        self.calculator = DailyEnergyCalculator()

    def get_or_calculate(
        self,
        user_id: str,
        target_date: date,
        initial_wish: str | None = None,
        status_tags: list[str] | None = None,
        scene_key: str | None = None,
        goal_keys: list[str] | None = None,
        force_recalculate: bool = False,
    ) -> tuple[dict, bool]:
        rules = normalize_daily_energy_rules(self.repository.get_setting(DAILY_RULES_SETTING_KEY))
        rules_version = daily_rules_version(rules)
        interaction = {
            "initial_wish": initial_wish,
            "status_tags": status_tags or [],
            "scene_key": scene_key or "",
            "goal_keys": goal_keys or [],
        }
        has_live_selection = bool(interaction["status_tags"] or interaction["scene_key"] or interaction["goal_keys"])

        if not force_recalculate and not has_live_selection:
            existing = self.repository.get_daily_energy(user_id, target_date.isoformat())
            if (
                existing
                and existing.get("content_version") == DAILY_ENERGY_CONTENT_VERSION
                and existing.get("rules_version") == rules_version
            ):
                return existing, True

        assessment = self.repository.latest_for_user(user_id)
        calculated = self.calculator.calculate(user_id, target_date, assessment, interaction, rules)
        result = {
            "user_id": user_id,
            "date": target_date.isoformat(),
            "calculated_at": datetime.now(CHINA_TZ).isoformat(),
            "cache_hit": False,
            **calculated,
        }
        self.repository.save_daily_energy(result)
        return result, False

    def options(self) -> dict:
        rules = normalize_daily_energy_rules(self.repository.get_setting(DAILY_RULES_SETTING_KEY))
        return public_daily_rules_payload(rules)

    def check_in(self, payload: DailyCheckInRequest, target_date: date) -> dict:
        now = datetime.now(CHINA_TZ).isoformat()
        checkin = {
            "user_id": payload.user_id,
            "date": target_date.isoformat(),
            "mood": payload.mood,
            "sleep": payload.sleep,
            "stress": payload.stress,
            "created_at": now,
        }
        self.repository.save_checkin(checkin)
        return {
            **checkin,
            "message": "今日状态已记录。新版今日能量会优先使用你本次选择的状态、场景和目标标签。",
        }
