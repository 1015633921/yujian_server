from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .daily_energy import DailyEnergyCalculator
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
        force_recalculate: bool = False,
    ) -> tuple[dict, bool]:
        if not force_recalculate:
            existing = self.repository.get_daily_energy(user_id, target_date.isoformat())
            if existing:
                return existing, True

        assessment = self.repository.latest_for_user(user_id)
        checkins = self.repository.recent_checkins(
            user_id,
            (target_date - timedelta(days=6)).isoformat(),
            limit=7,
        )
        calculated = self.calculator.calculate(user_id, target_date, assessment, checkins, initial_wish)
        result = {
            "user_id": user_id,
            "date": target_date.isoformat(),
            "calculated_at": datetime.now(CHINA_TZ).isoformat(),
            "cache_hit": False,
            **calculated,
        }
        self.repository.save_daily_energy(result)
        return result, False

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
            "message": "今日状态已记录，将用于后续每日能量建议。",
        }
