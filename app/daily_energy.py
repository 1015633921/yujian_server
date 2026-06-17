from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from .energy import ELEMENTS, WISH_MAPPING, normalized_profile
from .recommendation import CRYSTAL_CATALOG, SUPPORTING_BY_ELEMENT

SEASON_ELEMENT = {
    1: "水", 2: "木", 3: "木", 4: "木",
    5: "火", 6: "火", 7: "火", 8: "土",
    9: "金", 10: "金", 11: "水", 12: "水",
}

ELEMENT_CONTENT = {
    "金": {
        "theme": "清晰整理的一天",
        "color": "月雾白",
        "best_time": "15:00-17:00",
        "actions": ["整理一个长期搁置的清单", "为今天最重要的决定设置明确边界", "给桌面留出一块干净空间"],
        "avoid": ["反复纠结已经做出的决定"],
    },
    "木": {
        "theme": "向前生长的一天",
        "color": "松针绿",
        "best_time": "07:00-09:00",
        "actions": ["推进一件需要持续积累的事情", "到户外散步十分钟", "主动开启一次温和沟通"],
        "avoid": ["一次给自己安排过多新目标"],
    },
    "水": {
        "theme": "稳定流动的一天",
        "color": "海盐蓝",
        "best_time": "21:00-23:00",
        "actions": ["给自己十分钟不被打扰的安静时间", "记录今天最真实的一种感受", "适度补水并放慢节奏"],
        "avoid": ["在情绪波动时立即做重大决定"],
    },
    "火": {
        "theme": "表达与推进的一天",
        "color": "石榴红",
        "best_time": "11:00-13:00",
        "actions": ["完成一件拖延中的小事", "主动表达一次真实需求", "用短时运动唤醒状态"],
        "avoid": ["情绪上头时过度承诺"],
    },
    "土": {
        "theme": "稳定积蓄的一天",
        "color": "麦芽金",
        "best_time": "13:00-15:00",
        "actions": ["整理一处经常使用的空间", "写下今天最重要的一件事", "按计划完成一顿规律饮食"],
        "avoid": ["因为追求完美而迟迟不开始"],
    },
}


class DailyEnergyCalculator:
    def calculate(
        self,
        user_id: str,
        target_date: date,
        assessment: dict[str, Any] | None,
        checkins: list[dict[str, Any]],
        initial_wish: str | None = None,
    ) -> dict[str, Any]:
        date_profile = self.date_profile(target_date)
        state = self.state_score(checkins)
        if assessment and assessment.get("final_energy_profile"):
            return self.personalized(user_id, target_date, assessment, date_profile, state, checkins)
        return self.starter(user_id, target_date, date_profile, state, initial_wish)

    def starter(
        self,
        user_id: str,
        target_date: date,
        date_profile: dict[str, float],
        state: dict[str, Any],
        initial_wish: str | None,
    ) -> dict[str, Any]:
        stable = self.stable_user_profile(user_id, target_date)
        wish = self.wish_profile(initial_wish)
        combined = {
            element: date_profile[element] * 0.7 + stable[element] * 0.2 + wish[element] * 0.1
            for element in ELEMENTS
        }
        profile = normalized_profile(combined, 100)
        focus = max(profile, key=profile.get)
        content = ELEMENT_CONTENT[focus]
        score = self.clamp(round(68 + self.stable_offset(user_id, target_date, 9) + state["adjustment"]), 55, 88)
        return {
            "mode": "starter",
            "personalized": False,
            "assessment_id": None,
            "score": score,
            "level": self.score_level(score),
            "theme": content["theme"],
            "summary": f"今天的{focus}能量更容易被感知，适合先稳定节奏，再为下一步积蓄力量。",
            "energy_profile": profile,
            "dominant_element": focus,
            "supporting_element": min(profile, key=profile.get),
            "best_time": content["best_time"],
            "lucky_color": content["color"],
            "lucky_crystal": self.crystal_for_element(focus),
            "actions": content["actions"],
            "avoid": content["avoid"],
            "state_context": state,
            "guide": {
                "title": "解锁你的专属每日能量",
                "description": "完成五行能量测算后，每日建议将结合你的个人能量与近期状态生成。",
                "button_text": "开始专属测算",
                "route": "/pages/assessment/assessment",
            },
        }

    def personalized(
        self,
        user_id: str,
        target_date: date,
        assessment: dict[str, Any],
        date_profile: dict[str, float],
        state: dict[str, Any],
        checkins: list[dict[str, Any]],
    ) -> dict[str, Any]:
        personal = assessment["final_energy_profile"]
        weakest = min(personal, key=personal.get)
        strongest = max(personal, key=personal.get)
        synergy = date_profile[weakest] - date_profile[strongest]
        score = self.clamp(round(72 + synergy * 0.65 + state["adjustment"]), 48, 96)
        combined = normalized_profile(
            {element: personal[element] * 0.4 + date_profile[element] * 0.35 for element in ELEMENTS},
            100,
        )
        focus = max(date_profile, key=date_profile.get)
        support = weakest if date_profile[weakest] >= 15 else min(date_profile, key=date_profile.get)
        content = ELEMENT_CONTENT[focus]
        if date_profile[weakest] > date_profile[strongest]:
            summary = f"今日{weakest}能量能够补足你个人画像中的弱项，适合温和推进与主动表达。"
        else:
            summary = f"今日{strongest}能量会进一步放大你的天然优势，也要为{weakest}留出恢复空间。"
        return {
            "mode": "personalized",
            "personalized": True,
            "assessment_id": assessment["assessment_id"],
            "score": score,
            "level": self.score_level(score),
            "theme": content["theme"],
            "summary": summary,
            "energy_profile": combined,
            "dominant_element": focus,
            "supporting_element": support,
            "best_time": content["best_time"],
            "lucky_color": ELEMENT_CONTENT[support]["color"],
            "lucky_crystal": self.crystal_for_element(support),
            "actions": [
                content["actions"][0],
                ELEMENT_CONTENT[support]["actions"][1],
                f"佩戴{self.crystal_for_element(support)}约两小时，作为今日节奏提醒。",
            ],
            "avoid": content["avoid"],
            "state_context": {**state, "checkin_days": len(checkins)},
            "guide": None,
        }

    @staticmethod
    def date_profile(target_date: date) -> dict[str, float]:
        digest = hashlib.sha256(target_date.isoformat().encode()).digest()
        raw = {element: float(digest[index] + 80) for index, element in enumerate(ELEMENTS)}
        raw[SEASON_ELEMENT[target_date.month]] += 180
        return normalized_profile(raw, 100)

    @staticmethod
    def stable_user_profile(user_id: str, target_date: date) -> dict[str, float]:
        digest = hashlib.sha256(f"{user_id}:{target_date.isoformat()}".encode()).digest()
        return normalized_profile({element: digest[index] + 50 for index, element in enumerate(ELEMENTS)}, 100)

    @staticmethod
    def wish_profile(initial_wish: str | None) -> dict[str, float]:
        profile = {element: 20.0 for element in ELEMENTS}
        if initial_wish in WISH_MAPPING:
            for element in WISH_MAPPING[initial_wish]:
                profile[element] += 20
        return normalized_profile(profile, 100)

    @staticmethod
    def state_score(checkins: list[dict[str, Any]]) -> dict[str, Any]:
        if not checkins:
            return {"source": "neutral_default", "mood": 3.0, "sleep": 3.0, "stress": 3.0, "adjustment": 0}
        count = len(checkins)
        mood = sum(item["mood"] for item in checkins) / count
        sleep = sum(item["sleep"] for item in checkins) / count
        stress = sum(item["stress"] for item in checkins) / count
        adjustment = round((mood - 3) * 2.5 + (sleep - 3) * 2.5 - (stress - 3) * 3)
        return {"source": "recent_checkins", "mood": round(mood, 1), "sleep": round(sleep, 1), "stress": round(stress, 1), "adjustment": adjustment}

    @staticmethod
    def crystal_for_element(element: str) -> str:
        code = SUPPORTING_BY_ELEMENT[element][0]
        return CRYSTAL_CATALOG[code]["name"]

    @staticmethod
    def stable_offset(user_id: str, target_date: date, spread: int) -> int:
        digest = hashlib.sha256(f"score:{user_id}:{target_date.isoformat()}".encode()).hexdigest()
        return int(digest[:8], 16) % (spread * 2 + 1) - spread

    @staticmethod
    def score_level(score: int) -> str:
        if score >= 86:
            return "高能流动"
        if score >= 72:
            return "稳定流动"
        if score >= 60:
            return "温柔蓄能"
        return "低速修复"

    @staticmethod
    def clamp(value: int, minimum: int, maximum: int) -> int:
        return max(minimum, min(maximum, value))
