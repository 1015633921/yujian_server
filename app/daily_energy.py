from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from .daily_rules import daily_rules_version, normalize_daily_energy_rules
from .energy import ELEMENTS, WISH_MAPPING, normalized_profile
from .materials import list_materials
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

DAILY_ENERGY_CONTENT_VERSION = 4

CRYSTAL_MATERIAL_SKUS = {
    "titanium_quartz": ["titaniumQuartz", "goldRutilatedQuartz", "citrine"],
    "citrine": ["citrine", "goldRutilatedQuartz"],
    "gold_rutilated_quartz": ["goldRutilatedQuartz", "titaniumQuartz", "citrine"],
    "rhodochrosite": ["rhodochrosite", "roseQuartz", "garnet"],
    "strawberry_quartz": ["strawberryQuartz", "roseQuartz", "garnet"],
    "rose_quartz": ["roseQuartz", "strawberryQuartz", "rhodochrosite"],
    "blue_rutilated_quartz": ["blueRutilatedQuartz", "aquamarine"],
    "obsidian": ["obsidian", "blackAgate", "blackRutilatedQuartz"],
    "black_rutilated_quartz": ["blackRutilatedQuartz", "obsidian"],
    "green_phantom": ["greenPhantom", "greenRutilatedQuartz"],
    "clear_quartz": ["clearQuartz", "whiteQuartz", "milkyQuartz", "doubleAClearQuartz"],
    "aquamarine": ["aquamarine", "blueRutilatedQuartz"],
    "turquoise": ["turquoise", "greenPhantom"],
    "garnet": ["garnet"],
    "smoky_quartz": ["smokyQuartz", "citrine"],
    "hematite": ["hematite", "silverRutilatedQuartz"],
}

CRYSTAL_MATERIAL_ALIASES = {
    "titanium_quartz": ["钛晶", "金发晶", "黄水晶", "黄晶"],
    "citrine": ["黄水晶", "黄晶", "金发晶", "钛晶"],
    "gold_rutilated_quartz": ["金发晶", "钛晶", "黄水晶", "黄晶"],
    "rhodochrosite": ["红纹石", "粉晶", "粉水晶", "南红玛瑙", "红玛瑙"],
    "strawberry_quartz": ["草莓晶", "粉晶", "粉水晶", "南红玛瑙", "红玛瑙"],
    "rose_quartz": ["粉晶", "粉水晶", "红纹石", "草莓晶"],
    "blue_rutilated_quartz": ["蓝发晶", "海蓝宝", "蓝晶石", "青金石"],
    "obsidian": ["黑曜石", "黑耀石", "曜石", "黑发晶", "黑玛瑙"],
    "black_rutilated_quartz": ["黑发晶", "黑曜石", "黑耀石", "曜石", "黑玛瑙"],
    "green_phantom": ["绿幽灵", "绿发晶", "东陵玉", "橄榄石"],
    "clear_quartz": ["白水晶", "白晶", "透明水晶", "水晶"],
    "aquamarine": ["海蓝宝", "蓝发晶", "蓝晶石"],
    "turquoise": ["绿松石", "绿幽灵", "东陵玉"],
    "garnet": ["石榴石", "南红玛瑙", "红玛瑙", "红发晶"],
    "smoky_quartz": ["茶晶", "烟晶", "黄水晶"],
    "hematite": ["赤铁矿", "银发晶", "白水晶", "黑曜石"],
}

ELEMENT_TO_MATERIAL_KEY = {
    "金": "metal",
    "木": "wood",
    "水": "water",
    "火": "fire",
    "土": "earth",
    "metal": "metal",
    "wood": "wood",
    "water": "water",
    "fire": "fire",
    "earth": "earth",
}

SEASON_ELEMENT = {
    1: "水", 2: "木", 3: "木", 4: "木",
    5: "火", 6: "火", 7: "火", 8: "土",
    9: "金", 10: "金", 11: "水", 12: "水",
}

HEAVENLY_STEMS = ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸")
STEM_ELEMENT = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}
EARTHLY_BRANCHES = ("子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥")
BRANCH_ELEMENT = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}
GANZHI_REFERENCE = date(1984, 2, 2)  # 甲子日参考点，用于稳定生成日柱节律。

ELEMENT_CONTENT = {
    "金": {
        "theme": "清晰整理的一天",
        "color": "月雾白",
        "best_time": "15:00-17:00",
        "actions": ["整理一个长期搁置的清单", "为今天最重要的决定设置清晰边界", "给桌面留出一块干净空间"],
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
        "avoid": ["在情绪波动时立刻做重大决定"],
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
        "actions": ["整理一处经常使用的空间", "写下今天最重要的一件事", "按计划完成一项规律饮食"],
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
        interaction: dict[str, Any] | None = None,
        rules: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rules = rules if isinstance(rules, dict) and rules.get("schema_version") else normalize_daily_energy_rules(rules)
        date_profile = self.date_profile(target_date)
        date_basis = self.date_basis(target_date)
        context = self.interaction_context(interaction or {}, rules)
        if assessment and assessment.get("final_energy_profile"):
            return self.personalized(user_id, target_date, assessment, date_profile, date_basis, context, rules)
        return self.starter(user_id, target_date, date_profile, date_basis, context, rules)

    def starter(
        self,
        user_id: str,
        target_date: date,
        date_profile: dict[str, float],
        date_basis: dict[str, Any],
        context: dict[str, Any],
        rules: dict[str, Any],
    ) -> dict[str, Any]:
        weights = rules.get("scoring", {}).get("starter_weights") or {}
        combined = self.weighted_profile({
            "date": (date_profile, weights.get("date", 0.30)),
            "status": (context["status_profile"], weights.get("status", 0.30)),
            "scene": (context["scene_profile"], weights.get("scene", 0.15)),
            "goal": (context["goal_profile"], weights.get("goal", 0.25)),
        })
        focus = max(combined, key=combined.get)
        support = self.support_element(combined)
        score = self.clamp(
            round(float(rules.get("scoring", {}).get("starter_base", 66)) + self.date_score_delta(date_profile) + context["score_delta"]),
            int(rules.get("scoring", {}).get("min_score", 42)),
            min(90, int(rules.get("scoring", {}).get("max_score", 96))),
        )
        content = ELEMENT_CONTENT[focus]
        result = {
            "mode": "starter",
            "personalized": False,
            "assessment_id": None,
            "score": score,
            "level": self.score_level(score),
            "theme": self.theme_for_context(context, content["theme"]),
            "summary": self.summary_text(focus, support, context, personalized=False),
            "energy_profile": combined,
            "dominant_element": focus,
            "supporting_element": support,
            "best_time": content["best_time"],
            "lucky_color": ELEMENT_CONTENT[support]["color"],
            "lucky_crystal": self.crystal_for_element(support, rules),
            "actions": self.actions_for_context(content, support, context),
            "avoid": content["avoid"],
            "state_context": context["public"],
            "date_basis": date_basis,
            "guide": {
                "title": "解锁你的专属每日能量",
                "description": "完成五行能量测算后，系统会结合你的个人画像、当天节律和实时选择生成建议。",
                "button_text": "开始专属测算",
                "route": "/pages/assessment/assessment",
            },
        }
        result.update(self.commercial_payload(result, target_date, focus, support, context, rules))
        return result

    def personalized(
        self,
        user_id: str,
        target_date: date,
        assessment: dict[str, Any],
        date_profile: dict[str, float],
        date_basis: dict[str, Any],
        context: dict[str, Any],
        rules: dict[str, Any],
    ) -> dict[str, Any]:
        personal = {element: float((assessment.get("final_energy_profile") or {}).get(element, 0)) for element in ELEMENTS}
        if not any(personal.values()):
            personal = {element: 20.0 for element in ELEMENTS}
        max_personal = max(personal.values()) or 20
        personal_need = normalized_profile({element: max_personal - personal[element] + 8 for element in ELEMENTS}, 100)
        weights = rules.get("scoring", {}).get("personalized_weights") or {}
        combined = self.weighted_profile({
            "personal_need": (personal_need, weights.get("personal_need", 0.35)),
            "date": (date_profile, weights.get("date", 0.20)),
            "status": (context["status_profile"], weights.get("status", 0.20)),
            "scene": (context["scene_profile"], weights.get("scene", 0.10)),
            "goal": (context["goal_profile"], weights.get("goal", 0.15)),
        })
        focus = max(combined, key=combined.get)
        support = max(personal_need, key=personal_need.get)
        date_fit = sum(date_profile[element] * personal_need[element] for element in ELEMENTS) / 100
        score = self.clamp(
            round(float(rules.get("scoring", {}).get("personalized_base", 68)) + (date_fit - 20) * 0.85 + context["score_delta"]),
            int(rules.get("scoring", {}).get("min_score", 42)),
            int(rules.get("scoring", {}).get("max_score", 96)),
        )
        content = ELEMENT_CONTENT[focus]
        result = {
            "mode": "personalized",
            "personalized": True,
            "assessment_id": assessment["assessment_id"],
            "score": score,
            "level": self.score_level(score),
            "theme": self.theme_for_context(context, content["theme"]),
            "summary": self.summary_text(focus, support, context, personalized=True),
            "energy_profile": combined,
            "personal_need_profile": personal_need,
            "dominant_element": focus,
            "supporting_element": support,
            "best_time": content["best_time"],
            "lucky_color": ELEMENT_CONTENT[support]["color"],
            "lucky_crystal": self.crystal_for_element(support, rules),
            "actions": self.actions_for_context(content, support, context),
            "avoid": content["avoid"],
            "state_context": context["public"],
            "date_basis": date_basis,
            "guide": None,
        }
        result.update(self.commercial_payload(result, target_date, focus, support, context, rules))
        return result

    @staticmethod
    def date_profile(target_date: date) -> dict[str, float]:
        basis = DailyEnergyCalculator.date_basis(target_date)
        raw = {element: 8.0 for element in ELEMENTS}
        raw[basis["seasonal_element"]] += 42
        raw[basis["stem_element"]] += 28
        raw[basis["branch_element"]] += 22
        if target_date.day in {1, 8, 15, 22, 29}:
            raw["金"] += 6
        if target_date.day in {3, 10, 17, 24, 31}:
            raw["水"] += 6
        return normalized_profile(raw, 100)

    @staticmethod
    def date_basis(target_date: date) -> dict[str, Any]:
        offset = (target_date - GANZHI_REFERENCE).days
        stem = HEAVENLY_STEMS[offset % 10]
        branch = EARTHLY_BRANCHES[offset % 12]
        seasonal_element = SEASON_ELEMENT[target_date.month]
        return {
            "period": f"{target_date.month}月流月",
            "seasonal_element": seasonal_element,
            "day_stem": stem,
            "day_branch": branch,
            "day_ganzhi": f"{stem}{branch}",
            "stem_element": STEM_ELEMENT[stem],
            "branch_element": BRANCH_ELEMENT[branch],
            "method": "month-season + day-stem-branch",
        }

    @staticmethod
    def neutral_profile() -> dict[str, float]:
        return {element: 20.0 for element in ELEMENTS}

    def interaction_context(self, interaction: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
        tag_keys = self.clean_keys(interaction.get("status_tags") or interaction.get("statusTags"))
        scene_key = (interaction.get("scene_key") or interaction.get("sceneKey") or "").strip()
        goal_keys = self.clean_keys(interaction.get("goal_keys") or interaction.get("goalKeys"))
        initial_wish = interaction.get("initial_wish") or interaction.get("initialWish")

        tags_by_key = {item["key"]: item for item in rules.get("status_tags", [])}
        scenes_by_key = {item["key"]: item for item in rules.get("scenes", [])}
        goals_by_key = {item["key"]: item for item in rules.get("goals", [])}
        selected_tags = [tags_by_key[key] for key in tag_keys if key in tags_by_key]
        selected_scene = scenes_by_key.get(scene_key) if scene_key else None
        selected_goals = [goals_by_key[key] for key in goal_keys if key in goals_by_key]

        status_raw = {element: 0.0 for element in ELEMENTS}
        scene_raw = {element: 0.0 for element in ELEMENTS}
        goal_raw = {element: 0.0 for element in ELEMENTS}
        dimension_delta: dict[str, float] = {}
        score_delta = 0.0
        crystal_codes: list[str] = []
        keywords: list[str] = []
        wearing_scenes: list[str] = []

        for item in selected_tags:
            for element in item.get("support_elements", []):
                if element in status_raw:
                    status_raw[element] += 1
            score_delta += float(item.get("score_delta") or 0)
            self.merge_delta(dimension_delta, item.get("dimension_delta") or {})
            crystal_codes.extend(item.get("crystal_codes") or [])
            keywords.extend(item.get("keywords") or [])

        if selected_scene:
            for element, value in (selected_scene.get("element_bias") or {}).items():
                if element in scene_raw:
                    scene_raw[element] += float(value or 0)
            score_delta += float(selected_scene.get("score_delta") or 0)
            self.merge_delta(dimension_delta, selected_scene.get("dimension_delta") or {})
            crystal_codes.extend(selected_scene.get("crystal_codes") or [])
            wearing_scenes.extend(selected_scene.get("wearing_scenes") or [selected_scene.get("label")])

        for item in selected_goals:
            for element in item.get("target_elements", []):
                if element in goal_raw:
                    goal_raw[element] += 1
            score_delta += float(item.get("score_delta") or 0)
            self.merge_delta(dimension_delta, item.get("dimension_delta") or {})
            crystal_codes.extend(item.get("crystal_codes") or [])
            keywords.extend(item.get("keywords") or [])

        if not selected_goals and initial_wish:
            goal_raw = self.wish_profile(initial_wish)
        else:
            goal_raw = normalized_profile(goal_raw, 100) if any(goal_raw.values()) else self.neutral_profile()

        status_profile = normalized_profile(status_raw, 100) if any(status_raw.values()) else self.neutral_profile()
        scene_profile = normalized_profile(scene_raw, 100) if any(scene_raw.values()) else self.neutral_profile()

        public = {
            "source": "live_selection",
            "selected_status_tags": [
                {"key": item.get("key"), "label": item.get("label"), "emoji": item.get("emoji") or ""}
                for item in selected_tags
            ],
            "selected_scene": (
                {"key": selected_scene.get("key"), "label": selected_scene.get("label"), "icon": selected_scene.get("icon") or ""}
                if selected_scene else None
            ),
            "selected_goals": [
                {"key": item.get("key"), "label": item.get("label")}
                for item in selected_goals
            ],
            "score_delta": round(score_delta, 1),
        }
        return {
            "status_profile": status_profile,
            "scene_profile": scene_profile,
            "goal_profile": goal_raw,
            "score_delta": max(-16, min(16, score_delta)),
            "dimension_delta": dimension_delta,
            "crystal_codes": self.unique([code for code in crystal_codes if code]),
            "keywords": self.unique([word for word in keywords if word]),
            "wearing_scenes": self.unique([scene for scene in wearing_scenes if scene]),
            "public": public,
        }

    @staticmethod
    def clean_keys(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            chunks = value.replace("，", ",").split(",")
        elif isinstance(value, (list, tuple)):
            chunks = value
        else:
            chunks = [value]
        result: list[str] = []
        for chunk in chunks:
            key = str(chunk or "").strip()
            if key and key not in result:
                result.append(key)
        return result

    @staticmethod
    def merge_delta(target: dict[str, float], source: dict[str, Any]) -> None:
        for key, value in (source or {}).items():
            try:
                target[key] = target.get(key, 0.0) + float(value)
            except (TypeError, ValueError):
                continue

    @staticmethod
    def weighted_profile(parts: dict[str, tuple[dict[str, float], float]]) -> dict[str, float]:
        raw = {element: 0.0 for element in ELEMENTS}
        total_weight = 0.0
        for profile, weight in parts.values():
            weight = float(weight or 0)
            if weight <= 0:
                continue
            total_weight += weight
            for element in ELEMENTS:
                raw[element] += float(profile.get(element, 0)) * weight
        if total_weight <= 0:
            return DailyEnergyCalculator.neutral_profile()
        return normalized_profile(raw, 100)

    @staticmethod
    def wish_profile(initial_wish: str | None) -> dict[str, float]:
        profile = {element: 20.0 for element in ELEMENTS}
        if initial_wish in WISH_MAPPING:
            for element in WISH_MAPPING[initial_wish]:
                profile[element] += 20
        return normalized_profile(profile, 100)

    @staticmethod
    def support_element(profile: dict[str, float]) -> str:
        return min(profile, key=profile.get)

    @staticmethod
    def date_score_delta(profile: dict[str, float]) -> float:
        spread = max(profile.values()) - min(profile.values())
        top = max(profile.values())
        return min(8, max(-6, (top - 20) * 0.18 - spread * 0.03))

    @staticmethod
    def crystal_for_element(element: str, rules: dict[str, Any]) -> str:
        code = DailyEnergyCalculator.first_crystal_code(element, rules)
        return CRYSTAL_CATALOG.get(code, {}).get("name") or "白水晶"

    @staticmethod
    def first_crystal_code(element: str, rules: dict[str, Any]) -> str:
        for code in (rules.get("element_crystal_pool", {}).get(element) or SUPPORTING_BY_ELEMENT.get(element) or []):
            if code in CRYSTAL_CATALOG:
                return code
        return "clear_quartz"

    @staticmethod
    def material_search_text(material: dict[str, Any]) -> str:
        return " ".join(
            str(material.get(key) or "")
            for key in ("id", "skuId", "sku", "name", "category", "series", "grade", "effect", "element")
        ).lower()

    @staticmethod
    def material_element_key(material: dict[str, Any]) -> str:
        element = str(material.get("element") or "").strip()
        normalized_element = ELEMENT_TO_MATERIAL_KEY.get(element) or ELEMENT_TO_MATERIAL_KEY.get(element.lower())
        if normalized_element:
            return normalized_element
        text = DailyEnergyCalculator.material_search_text(material)
        if any(word in text for word in ("金", "银", "白", "钛", "发晶", "铁", "曜", "耀")):
            return "metal"
        if any(word in text for word in ("绿", "木", "松", "幽灵", "东陵")):
            return "wood"
        if any(word in text for word in ("蓝", "海", "水", "黑")):
            return "water"
        if any(word in text for word in ("红", "南红", "玛瑙", "石榴", "火", "粉", "草莓")):
            return "fire"
        if any(word in text for word in ("黄", "茶", "烟", "土", "虎眼")):
            return "earth"
        return ""

    @staticmethod
    def choose_closest_material(candidates: list[dict[str, Any]], preferred_size: float = 8) -> dict[str, Any] | None:
        if not candidates:
            return None
        target_size = float(preferred_size or 8)

        def rank(material: dict[str, Any]) -> tuple[float, int, int, str]:
            try:
                size = float(material.get("size") or target_size)
            except (TypeError, ValueError):
                size = target_size
            stock = int(float(material.get("stock") or 0))
            has_image = 0 if (material.get("image_url") or material.get("image_urls") or material.get("image_pool")) else 1
            sort_order = int(float(material.get("sort_order") or material.get("sortOrder") or 0))
            return (abs(size - target_size), -stock, has_image, f"{sort_order:08d}{material.get('id') or ''}")

        return min(candidates, key=rank)

    @staticmethod
    def material_image_pool(material: dict[str, Any]) -> list[str]:
        pool: list[str] = []
        for value in (material.get("image_urls"), material.get("image_pool")):
            if isinstance(value, list):
                pool.extend(str(url) for url in value if str(url))
        if material.get("image_url"):
            pool.insert(0, str(material.get("image_url")))
        result = []
        seen = set()
        for url in pool:
            if url in seen:
                continue
            seen.add(url)
            result.append(url)
        return result

    @staticmethod
    def material_snapshot(material: dict[str, Any] | None) -> dict[str, Any]:
        if not material:
            return {}
        image_pool = DailyEnergyCalculator.material_image_pool(material)
        image_url = material.get("image_url") or (image_pool[0] if image_pool else "")
        return {
            "material_id": material.get("id") or "",
            "source_material_id": material.get("id") or "",
            "sku": material.get("skuId") or material.get("sku") or "",
            "skuId": material.get("skuId") or material.get("sku") or "",
            "top": material.get("top") or "bead",
            "category": material.get("category") or "",
            "series": material.get("series") or material.get("name") or "",
            "grade": material.get("grade") or "",
            "material_name": material.get("name") or "",
            "effect": material.get("effect") or "",
            "price": float(material.get("price") or 0),
            "size": float(material.get("size") or 8),
            "weight": float(material.get("weight") or 0),
            "color": material.get("color") or "",
            "shine": material.get("shine") or "",
            "image_url": image_url,
            "image_urls": image_pool,
            "image_pool": image_pool,
        }

    @staticmethod
    def resolve_crystal_material(code: str, crystal: dict[str, Any], preferred_size: float = 8) -> dict[str, Any] | None:
        try:
            payload = list_materials(top="bead", compact=True)
        except Exception:
            payload = {}
        catalog = [
            item for item in payload.get("materials", [])
            if str(item.get("top") or "bead") == "bead" and bool(item.get("enabled", True))
        ]
        if not catalog:
            return None
        in_stock = [item for item in catalog if int(float(item.get("stock") or 0)) > 0]
        source = in_stock or catalog

        sku_candidates = {
            str(sku).lower()
            for sku in CRYSTAL_MATERIAL_SKUS.get(code, [])
            if str(sku)
        }
        exact_matches = [
            item for item in source
            if str(item.get("skuId") or item.get("sku") or "").lower() in sku_candidates
        ]
        exact_match = DailyEnergyCalculator.choose_closest_material(exact_matches, preferred_size)
        if exact_match:
            return exact_match

        aliases = [crystal.get("name") or "", *CRYSTAL_MATERIAL_ALIASES.get(code, [])]
        alias_matches = [
            item for item in source
            if any(str(alias).lower() in DailyEnergyCalculator.material_search_text(item) for alias in aliases if str(alias))
        ]
        alias_match = DailyEnergyCalculator.choose_closest_material(alias_matches, preferred_size)
        if alias_match:
            return alias_match

        crystal_element = str(crystal.get("element") or "").strip()
        target_element = ELEMENT_TO_MATERIAL_KEY.get(crystal_element) or ELEMENT_TO_MATERIAL_KEY.get(crystal_element.lower())
        element_matches = [
            item for item in source
            if target_element and DailyEnergyCalculator.material_element_key(item) == target_element
        ]
        return DailyEnergyCalculator.choose_closest_material(element_matches, preferred_size)

    def commercial_payload(
        self,
        result: dict[str, Any],
        target_date: date,
        focus_element: str,
        support_element: str,
        context: dict[str, Any],
        rules: dict[str, Any],
    ) -> dict[str, Any]:
        codes = self.pick_crystal_codes(focus_element, support_element, context, rules)
        recommended_crystals = []
        context_codes = set(context.get("crystal_codes") or [])
        for index, code in enumerate(codes):
            item = CRYSTAL_CATALOG[code]
            material = self.resolve_crystal_material(code, item, preferred_size=8)
            material_snapshot = self.material_snapshot(material)
            display_name = material_snapshot.get("material_name") or item["name"]
            role = "今日主石" if index == 0 else ("平衡辅石" if index == 1 else "净化点缀")
            if index == 0 and code in context_codes:
                reason = "匹配你今天选择的状态与目标，适合作为主石随身佩戴"
            elif index == 0:
                reason = f"补足{support_element}能量，适合今天随身佩戴"
            elif index == 1:
                reason = f"呼应{focus_element}主题，让搭配更稳定"
            else:
                reason = "用于放大与净化整体能量"
            recommended_crystals.append({
                "crystal_code": code,
                "code": code,
                "name": display_name,
                "crystal_name": item["name"],
                "element": item["element"],
                "color": material_snapshot.get("color") or item["color"],
                "effects": item["effects"],
                "role": role,
                "reason": reason,
                **material_snapshot,
            })

        primary = recommended_crystals[0]
        secondary = recommended_crystals[1] if len(recommended_crystals) > 1 else primary
        keyword = result.get("theme") or "今日能量"
        rules_version = daily_rules_version(rules)
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
            "rules_version": rules_version,
            "state_context": result.get("state_context"),
        }
        layout = []
        for crystal in recommended_crystals:
            repeat = 8 if crystal["role"] == "今日主石" else 4
            for _ in range(repeat):
                layout.append({
                    **crystal,
                    "id": crystal.get("material_id") or crystal.get("id") or crystal["crystal_code"],
                    "position": len(layout) + 1,
                    "crystal_name": crystal.get("crystal_name") or crystal["name"],
                    "bead_size_mm": 8,
                    "repeat_hint": repeat,
                })

        return {
            "content_version": DAILY_ENERGY_CONTENT_VERSION,
            "rules_version": rules_version,
            "title": result.get("theme"),
            "daily_keyword": keyword,
            "keywords": self.build_keywords(result, focus_element, support_element, context),
            "today_status": self.today_status(result.get("score", 70)),
            "season_hint": self.build_season_hint(target_date, result.get("date_basis") or {}, focus_element, support_element),
            "dimensions": self.build_dimensions(result.get("energy_profile") or {}, result.get("score", 70), context),
            "dimension_commentary": self.build_dimension_commentary(result.get("energy_profile") or {}, focus_element, context),
            "recommended_stone": primary["name"],
            "recommended_crystals": recommended_crystals,
            "crystal_combo": self.build_crystal_combo(recommended_crystals),
            "wearing_advice": f"今天建议以{primary['name']}为主石，搭配{secondary['name']}，做成适合日常佩戴的轻量手串。",
            "wearing_guide": self.build_wearing_guide(primary, focus_element, support_element, context),
            "action_tip": (result.get("actions") or ["先完成一件小事"])[0],
            "action_advice": self.build_action_advice(result),
            "daily_plan": self.build_daily_plan(target_date, result, primary, secondary),
            "calculation_note": "按当月五行节律、当日天干地支、用户能量画像与实时状态/场景/目标标签综合计算。",
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
                    "summary": f"{primary['name']} + {secondary['name']}，围绕「{keyword}」生成。",
                    "bead_size_mm": 8,
                    "estimated_bead_count": len(layout),
                    "pattern": "今日主石 + 平衡辅石 + 净化点缀",
                    "items": self.build_workbench_items(recommended_crystals),
                    "layout": layout,
                },
            },
        }

    def pick_crystal_codes(
        self,
        focus_element: str,
        support_element: str,
        context: dict[str, Any],
        rules: dict[str, Any],
    ) -> list[str]:
        candidates = list(context.get("crystal_codes") or [])
        for element in (support_element, focus_element):
            candidates.extend(rules.get("element_crystal_pool", {}).get(element) or SUPPORTING_BY_ELEMENT.get(element) or [])
        candidates.append("clear_quartz")
        codes: list[str] = []
        for code in candidates:
            if code not in CRYSTAL_CATALOG or code not in WORKBENCH_CRYSTAL_CODES:
                continue
            if code not in codes:
                codes.append(code)
            if len(codes) >= 3:
                break
        if not codes:
            codes = ["clear_quartz"]
        while len(codes) < 3:
            for code in ("clear_quartz", "aquamarine", "smoky_quartz", "rose_quartz"):
                if code not in codes:
                    codes.append(code)
                    break
        return codes[:3]

    def build_keywords(self, result: dict[str, Any], focus_element: str, support_element: str, context: dict[str, Any]) -> list[str]:
        candidates = [
            *context.get("keywords", []),
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
    def build_season_hint(target_date: date, basis: dict[str, Any], focus_element: str, support_element: str) -> dict[str, Any]:
        seasonal_element = basis.get("seasonal_element") or SEASON_ELEMENT[target_date.month]
        day_ganzhi = basis.get("day_ganzhi") or ""
        return {
            "period": f"{target_date.month}月流月",
            "seasonal_element": seasonal_element,
            "day_ganzhi": day_ganzhi,
            "summary": (
                f"当前流月以{seasonal_element}气为主，今日{day_ganzhi}日会放大{focus_element}能量。"
                f"建议用{support_element}向晶石做轻柔调和，减少状态流失。"
            ),
            "drain_point": f"{support_element}能量不足时，容易出现注意力分散、节奏断档或表达过度解释。",
            "suggestion": "先完成一件确定的小事，再推进需要沟通、创意或临场判断的任务。",
        }

    def build_dimensions(self, profile: dict[str, float], score: int | float, context: dict[str, Any]) -> list[dict[str, Any]]:
        delta = context.get("dimension_delta") or {}
        return [
            {
                "key": key,
                "name": name,
                "value": self.clamp(self.dimension_score(profile, weights, score) + round(float(delta.get(key, 0))), 35, 98),
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
        return self.clamp(value, 35, 96)

    def build_dimension_commentary(self, profile: dict[str, float], focus_element: str, context: dict[str, Any]) -> str:
        dimensions = self.build_dimensions(profile, 70, context)
        strongest = max(dimensions, key=lambda item: item["value"])
        weakest = min(dimensions, key=lambda item: item["value"])
        scene = (context.get("public", {}).get("selected_scene") or {}).get("label")
        scene_copy = f"结合「{scene}」场景，" if scene else ""
        return (
            f"{scene_copy}今天的{strongest['name']}相对更好，适合把事情做稳。"
            f"{weakest['name']}略弱，不建议一次塞入太多临场创意或高压对抗。"
            f"{focus_element}能量当令时，保持清晰表达会比强行加速更有效。"
        )

    @staticmethod
    def build_crystal_combo(recommended_crystals: list[dict[str, Any]]) -> dict[str, Any]:
        main = recommended_crystals[0] if recommended_crystals else {}
        support = recommended_crystals[1] if len(recommended_crystals) > 1 else main
        balance = recommended_crystals[2] if len(recommended_crystals) > 2 else support

        def combo_item(source: dict[str, Any], label: str, fallback_name: str, role: str) -> dict[str, Any]:
            return {
                "label": label,
                "name": source.get("name", fallback_name),
                "crystal_name": source.get("crystal_name") or source.get("name", fallback_name),
                "role": role,
                "reason": source.get("reason", ""),
                "material_id": source.get("material_id") or "",
                "skuId": source.get("skuId") or source.get("sku") or "",
                "category": source.get("category") or "",
                "series": source.get("series") or "",
                "price": source.get("price") or 0,
                "size": source.get("size") or 8,
                "image_url": source.get("image_url") or "",
                "image_urls": source.get("image_urls") or source.get("image_pool") or [],
                "image_pool": source.get("image_pool") or source.get("image_urls") or [],
                "color": source.get("color") or "",
            }

        return {
            "main": combo_item(main, "主石", "海蓝宝", "表达、沟通、舒缓紧张感"),
            "support": combo_item(support, "辅石", "白水晶", "清透、放大整体能量、增强干净感"),
            "balance": combo_item(balance, "平衡石", "月光石", "柔和情绪、增加稳定陪伴感"),
            "accent": {
                "label": "点缀建议",
                "name": "银色隔片 / 透明隔珠 / 少量淡粉色",
                "role": "让整体更清爽，适合今日状态",
            },
        }

    @staticmethod
    def build_wearing_guide(primary: dict[str, Any], focus_element: str, support_element: str, context: dict[str, Any]) -> dict[str, Any]:
        focus = ELEMENT_WEARING.get(focus_element, ELEMENT_WEARING["水"])
        support = ELEMENT_WEARING.get(support_element, focus)
        scenes = list(dict.fromkeys([*context.get("wearing_scenes", []), *focus["scenes"], *support["scenes"]]))[:4]
        return {
            "hand": "建议左手佩戴，用更安静的方式稳定状态；如果今天需要高频表达，也可以短时间换到右手提醒自己清晰输出。",
            "colors": list(dict.fromkeys([*support["colors"], *focus["colors"]]))[:4],
            "avoid": focus["avoid"],
            "scenes": scenes,
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
            "wrist_hint": "将在 DIY 工作台选择手围后自动排布。",
            "budget_text": "第一版先按可用珠材自动生成，后续可加入预算区间。",
            "description": (
                f"以{primary.get('name')}作为今日主石，搭配{secondary.get('name')}做平衡，"
                f"围绕「{result.get('theme') or '今日能量'}」生成可继续编辑的方案。"
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
                "material_id": crystal.get("material_id") or "",
                "sku": crystal.get("sku") or crystal.get("skuId") or "",
                "skuId": crystal.get("skuId") or crystal.get("sku") or "",
                "category": crystal.get("category") or "",
                "series": crystal.get("series") or "",
                "price": crystal.get("price") or 0,
                "size": crystal.get("size") or 8,
                "weight": crystal.get("weight") or 0,
                "image_url": crystal.get("image_url") or "",
                "image_urls": crystal.get("image_urls") or crystal.get("image_pool") or [],
                "image_pool": crystal.get("image_pool") or crystal.get("image_urls") or [],
            })
        return items

    @staticmethod
    def theme_for_context(context: dict[str, Any], fallback: str) -> str:
        goals = context.get("public", {}).get("selected_goals") or []
        tags = context.get("public", {}).get("selected_status_tags") or []
        if goals:
            return f"{goals[0]['label']}的一天"
        if tags:
            return f"{tags[0]['label']}也能稳住的一天"
        return fallback

    @staticmethod
    def summary_text(focus: str, support: str, context: dict[str, Any], personalized: bool) -> str:
        scene = (context.get("public", {}).get("selected_scene") or {}).get("label")
        tags = context.get("public", {}).get("selected_status_tags") or []
        tag_text = "、".join(item["label"] for item in tags[:2])
        prefix = f"结合你今天选择的「{tag_text}」，" if tag_text else ""
        scene_text = f"在「{scene}」场景里，" if scene else ""
        personal_text = "也会照顾你的个人五行短板。" if personalized else "先用轻量方案帮你找到今日节奏。"
        return f"{prefix}{scene_text}今天适合用{support}能量托住状态，再顺着{focus}能量推进事情，{personal_text}"

    @staticmethod
    def actions_for_context(content: dict[str, Any], support: str, context: dict[str, Any]) -> list[str]:
        goals = context.get("public", {}).get("selected_goals") or []
        scene = (context.get("public", {}).get("selected_scene") or {}).get("label")
        actions = list(content.get("actions") or [])
        if goals:
            actions.insert(0, f"围绕「{goals[0]['label']}」先做一个 15 分钟内能完成的小动作")
        if scene:
            actions.insert(1, f"在「{scene}」前，先用一句话写下今天最想达成的结果")
        actions.append(f"佩戴{ELEMENT_CONTENT[support]['color']}向晶石约两小时，作为今日节奏提醒。")
        return DailyEnergyCalculator.unique(actions)[:3]

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
    def clamp(value: int | float, minimum: int, maximum: int) -> int:
        return max(minimum, min(maximum, int(value)))

    @staticmethod
    def unique(values: list[Any]) -> list[Any]:
        result: list[Any] = []
        for value in values:
            if value and value not in result:
                result.append(value)
        return result
