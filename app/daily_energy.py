from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from .energy import ELEMENTS, WISH_MAPPING, normalized_profile
from .recommendation import CRYSTAL_CATALOG, SUPPORTING_BY_ELEMENT

WORKBENCH_CRYSTAL_CODES = {
    "citrine",
    "rose_quartz",
    "blue_rutilated_quartz",
    "obsidian",
    "black_rutilated_quartz",
    "green_phantom",
    "clear_quartz",
    "aquamarine",
    "turquoise",
    "garnet",
    "smoky_quartz",
    "hematite",
}

DAILY_ENERGY_CONTENT_VERSION = 2

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

ELEMENT_KEYWORDS = {
    "金": ["清晰", "秩序", "边界"],
    "木": ["生长", "舒展", "更新"],
    "水": ["清透", "沟通", "柔和"],
    "火": ["表达", "热度", "行动"],
    "土": ["稳定", "承接", "落地"],
}

ELEMENT_WEARING = {
    "金": {
        "colors": ["月雾白", "银灰", "透明"],
        "avoid": "过于复杂的混搭与高饱和撞色",
        "scenes": ["整理计划", "做决策", "处理边界"],
    },
    "木": {
        "colors": ["松针绿", "浅青", "奶白"],
        "avoid": "沉闷厚重的大面积黑色",
        "scenes": ["学习成长", "轻运动", "启动新计划"],
    },
    "水": {
        "colors": ["冰蓝", "透明", "浅灰"],
        "avoid": "强烈红色与过多金属感",
        "scenes": ["上班沟通", "直播表达", "轻社交"],
    },
    "火": {
        "colors": ["石榴红", "暖白", "淡粉"],
        "avoid": "连续高压对抗与情绪化承诺",
        "scenes": ["表达展示", "推进任务", "约见沟通"],
    },
    "土": {
        "colors": ["麦芽金", "茶褐", "奶油白"],
        "avoid": "临时改变太多计划",
        "scenes": ["执行落地", "整理收纳", "稳定节奏"],
    },
}

DIMENSION_CONFIG = [
    ("stability", "稳定能量", {"土": 1.25, "金": 0.75}, "适合处理需要耐心、秩序和确定性的事情。"),
    ("action", "行动能量", {"火": 1.1, "木": 0.9}, "适合推进已明确的小任务，不必一次冲太猛。"),
    ("softness", "情绪柔和", {"水": 1.0, "土": 0.85}, "帮助把注意力从内耗里放回当下。"),
    ("expression", "表达社交", {"火": 0.85, "水": 1.1}, "适合沟通、直播、见客户或表达结论。"),
    ("intuition", "灵感直觉", {"水": 0.8, "木": 1.1}, "适合寻找灵感，但更适合先记录，不急着定案。"),
]


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
        result = {
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
        result.update(self.commercial_payload(result, target_date, focus, result["supporting_element"]))
        return result

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
        result = {
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
        result.update(self.commercial_payload(result, target_date, focus, support))
        return result

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

    def commercial_payload(
        self,
        result: dict[str, Any],
        target_date: date,
        focus_element: str,
        support_element: str,
    ) -> dict[str, Any]:
        """Build the product-facing recommendation fields for the mini program.

        The daily energy card is a lightweight commerce entry: explain why a stone
        fits today, then let the user take the generated plan into the DIY bench.
        """
        codes = []
        for element in (support_element, focus_element):
            for code in SUPPORTING_BY_ELEMENT[element]:
                if code not in WORKBENCH_CRYSTAL_CODES:
                    continue
                if code not in codes:
                    codes.append(code)
                    break
        if "clear_quartz" not in codes:
            codes.append("clear_quartz")
        codes = codes[:3]

        recommended_crystals = []
        for index, code in enumerate(codes):
            item = CRYSTAL_CATALOG[code]
            role = "今日主石" if index == 0 else ("平衡辅石" if index == 1 else "净化点缀")
            reason = (
                f"补足{support_element}能量，适合今天随身佩戴"
                if index == 0
                else f"呼应{focus_element}主题，让搭配更稳定"
                if index == 1
                else "用于放大与净化整体能量"
            )
            recommended_crystals.append({
                "crystal_code": code,
                "code": code,
                "name": item["name"],
                "element": item["element"],
                "color": item["color"],
                "effects": item["effects"],
                "role": role,
                "reason": reason,
            })

        primary = recommended_crystals[0]
        secondary = recommended_crystals[1] if len(recommended_crystals) > 1 else primary
        keyword = result.get("theme") or "今日能量"
        source_context = {
            "source": "daily_energy",
            "source_label": "今日能量",
            "date": target_date.isoformat(),
            "mode": result.get("mode"),
            "score": result.get("score"),
            "theme": result.get("theme"),
            "assessment_id": result.get("assessment_id"),
            "dominant_element": result.get("dominant_element"),
            "supporting_element": result.get("supporting_element"),
        }
        layout = []
        for crystal in recommended_crystals:
            repeat = 8 if crystal["role"] == "今日主石" else 4
            for _ in range(repeat):
                layout.append({
                    **crystal,
                    "position": len(layout) + 1,
                    "crystal_name": crystal["name"],
                    "bead_size_mm": 8,
                    "repeat_hint": repeat,
                })

        return {
            "content_version": DAILY_ENERGY_CONTENT_VERSION,
            "title": result.get("theme"),
            "daily_keyword": keyword,
            "keywords": self.build_keywords(result, focus_element, support_element),
            "today_status": self.today_status(result.get("score", 70)),
            "season_hint": self.build_season_hint(target_date, focus_element, support_element),
            "dimensions": self.build_dimensions(result.get("energy_profile") or {}, result.get("score", 70)),
            "dimension_commentary": self.build_dimension_commentary(result.get("energy_profile") or {}, focus_element),
            "recommended_stone": primary["name"],
            "recommended_crystals": recommended_crystals,
            "crystal_combo": self.build_crystal_combo(recommended_crystals),
            "wearing_advice": f"今天建议以{primary['name']}为主石，搭配{secondary['name']}，做成适合日常佩戴的轻量手串。",
            "wearing_guide": self.build_wearing_guide(primary, focus_element, support_element),
            "action_tip": (result.get("actions") or ["先完成一件小事"])[0],
            "action_advice": self.build_action_advice(result),
            "daily_plan": self.build_daily_plan(target_date, result, primary, secondary),
            "commerce_entry": {
                "source": "daily_energy",
                "title": "生成今日能量手串",
                "subtitle": f"{primary['name']}为主石 · {secondary['name']}平衡搭配",
                "button_text": "一键生成今日手串",
                "tracking": source_context,
            },
            "workbench_payload": {
                "source": "daily_energy",
                "source_label": "今日能量",
                "source_context": source_context,
                "date": target_date.isoformat(),
                "keyword": keyword,
                "wrist_size_cm": 16,
                "recommended_crystals": recommended_crystals,
                "bracelet_plan": {
                    "title": f"{target_date.strftime('%m.%d')} 今日能量手串",
                    "summary": f"{primary['name']} + {secondary['name']}，围绕{keyword}生成。",
                    "bead_size_mm": 8,
                    "estimated_bead_count": len(layout),
                    "pattern": "今日主石 + 平衡辅石 + 净化点缀",
                    "items": self.build_workbench_items(recommended_crystals),
                    "layout": layout,
                },
            },
        }

    def build_keywords(self, result: dict[str, Any], focus_element: str, support_element: str) -> list[str]:
        candidates = [
            ELEMENT_KEYWORDS.get(support_element, ["稳定"])[0],
            ELEMENT_KEYWORDS.get(focus_element, ["清透"])[1],
            "轻盈" if result.get("score", 70) >= 72 else "慢修复",
            ELEMENT_KEYWORDS.get(focus_element, ["清透"])[0],
        ]
        keywords: list[str] = []
        for item in candidates:
            if item and item not in keywords:
                keywords.append(item)
            if len(keywords) >= 3:
                break
        return keywords

    @staticmethod
    def today_status(score: int | float) -> str:
        value = int(score or 70)
        if value >= 86:
            return "顺势上扬"
        if value >= 72:
            return "温和上升"
        if value >= 60:
            return "稳定蓄能"
        return "低速修复"

    @staticmethod
    def build_season_hint(target_date: date, focus_element: str, support_element: str) -> dict[str, Any]:
        seasonal_element = SEASON_ELEMENT[target_date.month]
        return {
            "period": f"{target_date.month}月流月",
            "seasonal_element": seasonal_element,
            "summary": (
                f"当前流月以{seasonal_element}气为主，今日更容易感知到{focus_element}能量。"
                f"建议用{support_element}向的晶石做轻柔调和，减少状态流失。"
            ),
            "drain_point": f"{support_element}能量不足时，容易出现节奏断档或注意力分散。",
            "suggestion": "先完成一件确定的小事，再推进需要沟通或创意的任务。",
        }

    def build_dimensions(self, profile: dict[str, float], score: int | float) -> list[dict[str, Any]]:
        return [
            {
                "key": key,
                "name": name,
                "value": self.dimension_score(profile, weights, score),
                "description": description,
            }
            for key, name, weights, description in DIMENSION_CONFIG
        ]

    def dimension_score(
        self,
        profile: dict[str, float],
        weights: dict[str, float],
        score: int | float,
    ) -> int:
        total_weight = sum(weights.values()) or 1
        weighted = sum(float(profile.get(element, 0)) * weight for element, weight in weights.items()) / total_weight
        value = round(48 + weighted * 1.35 + (float(score or 70) - 70) * 0.18)
        return self.clamp(value, 45, 96)

    def build_dimension_commentary(self, profile: dict[str, float], focus_element: str) -> str:
        dimensions = self.build_dimensions(profile, 70)
        strongest = max(dimensions, key=lambda item: item["value"])
        weakest = min(dimensions, key=lambda item: item["value"])
        return (
            f"今天的{strongest['name']}相对更好，适合把事情做稳。"
            f"{weakest['name']}略弱，不建议一次塞入太多临场创意或高压对抗。"
            f"{focus_element}能量当令时，保持清晰表达会比强行加速更有效。"
        )

    @staticmethod
    def build_crystal_combo(recommended_crystals: list[dict[str, Any]]) -> dict[str, Any]:
        main = recommended_crystals[0] if recommended_crystals else {}
        support = recommended_crystals[1] if len(recommended_crystals) > 1 else main
        balance = recommended_crystals[2] if len(recommended_crystals) > 2 else support
        return {
            "main": {
                "label": "主石",
                "name": main.get("name", "海蓝宝"),
                "role": "表达、沟通、舒缓紧张感",
                "reason": main.get("reason", ""),
            },
            "support": {
                "label": "辅石",
                "name": support.get("name", "白水晶"),
                "role": "清透、放大整体能量、增强干净感",
                "reason": support.get("reason", ""),
            },
            "balance": {
                "label": "平衡石",
                "name": balance.get("name", "月光石"),
                "role": "柔和情绪、增加稳定陪伴感",
                "reason": balance.get("reason", ""),
            },
            "accent": {
                "label": "点缀建议",
                "name": "银色隔片 / 透明隔珠 / 少量淡粉色",
                "role": "让整体更清爽，适合今日状态",
            },
        }

    @staticmethod
    def build_wearing_guide(primary: dict[str, Any], focus_element: str, support_element: str) -> dict[str, Any]:
        focus = ELEMENT_WEARING.get(focus_element, ELEMENT_WEARING["水"])
        support = ELEMENT_WEARING.get(support_element, focus)
        return {
            "hand": "建议左手佩戴，用更安静的方式稳定状态；如今天需要高频表达，也可以短时间换到右手提醒自己清晰输出。",
            "colors": list(dict.fromkeys([*support["colors"], *focus["colors"]]))[:4],
            "avoid": focus["avoid"],
            "scenes": list(dict.fromkeys([*focus["scenes"], *support["scenes"]]))[:4],
            "not_recommended": "高压谈判、强对抗场合，或情绪很满时立刻做重大决定。",
            "primary_stone": primary.get("name", "今日主石"),
        }

    @staticmethod
    def build_action_advice(result: dict[str, Any]) -> list[str]:
        actions = list(result.get("actions") or [])
        while len(actions) < 3:
            actions.append("晚上适合整理手串、清洁水晶或保存一个新的搭配方案。")
        return actions[:3]

    @staticmethod
    def build_daily_plan(
        target_date: date,
        result: dict[str, Any],
        primary: dict[str, Any],
        secondary: dict[str, Any],
    ) -> dict[str, Any]:
        color = result.get("lucky_color") or primary.get("color") or "清透色系"
        return {
            "title": f"{target_date.strftime('%m.%d')} 今日能量手串",
            "style": "清透通勤款",
            "main_colors": [color, "透明", "奶白"],
            "bead_sizes": ["6mm", "8mm"],
            "wrist_hint": "将按你在 DIY 工作台选择的手围自动排布。",
            "budget_text": "第一版先按可用珠材自动生成，后续可加入预算区间。",
            "description": (
                f"以{primary.get('name')}作为今日主石，搭配{secondary.get('name')}做平衡，"
                f"围绕“{result.get('theme') or '今日能量'}”生成可继续编辑的方案。"
            ),
        }

    @staticmethod
    def build_workbench_items(recommended_crystals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items = []
        for index, crystal in enumerate(recommended_crystals):
            quantity = 8 if index == 0 else 4
            items.append({
                "code": crystal["crystal_code"],
                "name": crystal["name"],
                "role": crystal["role"],
                "element": crystal["element"],
                "effects": crystal["effects"],
                "quantity": quantity,
                "bead_size_mm": 8,
                "reason": crystal["reason"],
                "image_url": "",
            })
        return items

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
