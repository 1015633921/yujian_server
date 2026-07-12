from __future__ import annotations

import math

from .copy_safety import safe_display_text, safe_wish_label
from .energy import ELEMENTS, WISH_MAPPING
from .material_knowledge import (
    build_primary_pools,
    build_recommendation_catalog,
    crystal_elements,
    material_code_from_payload,
    material_code_token,
    merge_taxonomy,
    unique_list,
)
from .material_options import element_label
from .schemas import AssessmentRequest

STRINGED_COMFORT_ALLOWANCE_MM = 8
MIN_RECOMMENDED_BEAD_COUNT = 12
MAX_RECOMMENDED_BEAD_COUNT = 40
STRINGED_LENGTH_TOLERANCE_CM = 0.5

CRYSTAL_CATALOG = {
    "titanium_quartz": {
        "name": "钛晶", "element": "金", "secondary_elements": ["土"], "color": "#C99A2E",
        "effects": ["目标感", "行动力", "稳步推进"],
    },
    "citrine": {
        "name": "黄水晶", "element": "土", "secondary_elements": ["金"], "color": "#E4B83F",
        "effects": ["目标推进", "自信", "目标感"],
    },
    "gold_rutilated_quartz": {
        "name": "金发晶", "element": "金", "secondary_elements": ["火"], "color": "#D4A62A",
        "effects": ["决断", "协作感", "事业专注"],
    },
    "rhodochrosite": {
        "name": "红纹石", "element": "火", "secondary_elements": ["木"], "color": "#D85A72",
        "effects": ["亲和", "自我接纳", "情感流动"],
    },
    "strawberry_quartz": {
        "name": "草莓晶", "element": "火", "secondary_elements": ["木"], "color": "#E77C8E",
        "effects": ["人缘", "魅力", "温柔表达"],
    },
    "rose_quartz": {
        "name": "粉晶", "element": "木", "secondary_elements": ["火"], "color": "#ECA8B7",
        "effects": ["亲和", "关系柔和", "柔和"],
    },
    "blue_rutilated_quartz": {
        "name": "蓝发晶", "element": "水", "secondary_elements": ["金"], "color": "#4F789B",
        "effects": ["冷静", "洞察", "边界感"],
    },
    "obsidian": {
        "name": "黑曜石", "element": "水", "secondary_elements": ["金"], "color": "#23252A",
        "effects": ["安定", "边界", "稳定"],
    },
    "black_rutilated_quartz": {
        "name": "黑发晶", "element": "金", "secondary_elements": ["水"], "color": "#34343A",
        "effects": ["边界感", "清理杂念", "坚定"],
    },
    "green_phantom": {
        "name": "绿幽灵", "element": "木", "secondary_elements": ["土"], "color": "#4A825F",
        "effects": ["日常平衡", "生长", "专注"],
    },
    "clear_quartz": {
        "name": "白水晶", "element": "金", "secondary_elements": ["土"], "color": "#E8EDF0",
        "effects": ["清爽", "专注", "干净感"],
    },
    "aquamarine": {
        "name": "海蓝宝", "element": "水", "secondary_elements": [], "color": "#75B8D1",
        "effects": ["平静", "表达", "舒缓压力"],
    },
    "turquoise": {
        "name": "绿松石", "element": "木", "secondary_elements": [], "color": "#56A6A2",
        "effects": ["生机", "沟通", "恢复"],
    },
    "garnet": {
        "name": "石榴石", "element": "火", "secondary_elements": [], "color": "#8E2635",
        "effects": ["活力", "自信", "热情"],
    },
    "smoky_quartz": {
        "name": "茶晶", "element": "土", "secondary_elements": [], "color": "#766052",
        "effects": ["扎根", "稳定", "执行力"],
    },
    "hematite": {
        "name": "赤铁矿", "element": "金", "secondary_elements": [], "color": "#5A5B60",
        "effects": ["秩序", "边界", "决断"],
    },
    "sunstone": {
        "name": "太阳石", "element": "火", "secondary_elements": ["土"], "color": "#E9924E",
        "effects": ["自信", "行动力", "积极"],
    },
    "tiger_eye": {
        "name": "虎眼石", "element": "土", "secondary_elements": ["金"], "color": "#B9833C",
        "effects": ["决断", "稳定", "目标稳定"],
    },
    "rhodonite": {
        "name": "蔷薇辉石", "element": "火", "secondary_elements": ["木", "土"], "color": "#C86A78",
        "effects": ["关系柔和", "边界", "温柔坚定"],
    },
    "prehnite": {
        "name": "葡萄石", "element": "木", "secondary_elements": ["水"], "color": "#B6D89B",
        "effects": ["舒缓", "松弛", "温柔感"],
    },
    "green_aventurine": {
        "name": "绿东陵", "element": "木", "secondary_elements": ["土"], "color": "#6FA56B",
        "effects": ["成长", "稳定", "舒心"],
    },
    "malachite": {
        "name": "孔雀石", "element": "木", "secondary_elements": ["土"], "color": "#1F7B4A",
        "effects": ["安定", "放松", "边界"],
    },
    "red_phantom": {
        "name": "红幽灵", "element": "火", "secondary_elements": ["土"], "color": "#A74C3E",
        "effects": ["行动", "稳定", "落地"],
    },
    "colorful_phantom": {
        "name": "彩幽灵", "element": "木", "secondary_elements": ["水", "火"], "color": "#7D8B6F",
        "effects": ["灵感", "流动", "成长"],
    },
    "blue_lace_agate": {
        "name": "蓝纹玛瑙", "element": "水", "secondary_elements": ["金"], "color": "#9EC7D8",
        "effects": ["沟通", "舒缓", "表达"],
    },
    "lapis_lazuli": {
        "name": "青金石", "element": "水", "secondary_elements": ["金"], "color": "#244A8F",
        "effects": ["洞察", "表达", "边界"],
    },
    "amazonite": {
        "name": "天河石", "element": "水", "secondary_elements": ["木"], "color": "#63B7AD",
        "effects": ["沟通", "松弛", "接纳"],
    },
    "apatite": {
        "name": "蓝磷灰石", "element": "水", "secondary_elements": ["木"], "color": "#2F91BF",
        "effects": ["表达", "灵感", "行动"],
    },
    "blue_fluorite": {
        "name": "蓝萤石", "element": "水", "secondary_elements": ["金"], "color": "#6A9BC5",
        "effects": ["专注", "洞察", "安静"],
    },
    "amethyst": {
        "name": "紫水晶", "element": "水", "secondary_elements": ["火"], "color": "#7C63A7",
        "effects": ["灵感", "安静", "清爽"],
    },
    "moonstone": {
        "name": "月光石", "element": "水", "secondary_elements": ["金"], "color": "#E5E5D9",
        "effects": ["放松", "柔软", "安静"],
    },
    "labradorite": {
        "name": "拉长石", "element": "水", "secondary_elements": ["金"], "color": "#596B74",
        "effects": ["直觉", "安定", "洞察"],
    },
    "lepidolite": {
        "name": "锂云母", "element": "水", "secondary_elements": ["金"], "color": "#B99AC7",
        "effects": ["安静", "放松", "松弛"],
    },
}

SUPPORTING_BY_ELEMENT = {
    element: [
        code
        for code, crystal in CRYSTAL_CATALOG.items()
        if crystal["element"] == element or element in crystal.get("secondary_elements", [])
    ]
    for element in ELEMENTS
}

PRIMARY_POOLS = {
    "招财进宝/事业腾飞": ["titanium_quartz", "citrine", "gold_rutilated_quartz"],
    "正缘桃花/人际和合": ["rhodochrosite", "strawberry_quartz", "rose_quartz"],
    "辟邪防小人/消除焦虑": ["blue_rutilated_quartz", "obsidian", "black_rutilated_quartz"],
    "健康护身/保持专注": ["green_phantom", "clear_quartz"],
}

CORE_WISH_TAGS = {
    "招财进宝/事业腾飞": {"wealth", "career"},
    "正缘桃花/人际和合": {"love", "relationship"},
    "辟邪防小人/消除焦虑": {"protection", "calm"},
    "健康护身/保持专注": {"health", "focus"},
}

ELEMENT_LANGUAGE = {
    "金": "建立边界与清晰决断",
    "木": "唤醒生长感与持续行动",
    "水": "安定情绪并恢复内在流动",
    "火": "点亮表达、热情与吸引力",
    "土": "增强稳定、承接与落地能力",
}


class RecommendationEngine:
    ROLE_KEY = {
        "primary": "primary",
        "support": "support",
        "accent": "accent",
    }

    @staticmethod
    def catalog() -> dict:
        return build_recommendation_catalog(CRYSTAL_CATALOG)

    @staticmethod
    def primary_pools(catalog: dict | None = None) -> dict[str, list[str]]:
        catalog = catalog or RecommendationEngine.catalog()
        pools = build_primary_pools(PRIMARY_POOLS, catalog)
        for wish, wish_tags in CORE_WISH_TAGS.items():
            pool = pools.setdefault(wish, [])
            for code, crystal in catalog.items():
                if set(unique_list(crystal.get("wish_pools"))) & wish_tags and code not in pool:
                    pool.append(code)
        return pools

    def recommend(self, request: AssessmentRequest, energy: dict) -> dict:
        final = energy["final"]
        primary_wish = request.primary_core_wish
        context = self.recommendation_context(request, energy)
        useful_elements = [element for element in energy.get("useful_elements", []) if element in ELEMENTS]
        catalog = self.catalog()
        primary_pools = self.primary_pools(catalog)
        available_codes = self.available_catalog_codes(catalog, request.bead_size_mm)
        primary_code = self.select_primary(request, energy, context, catalog, primary_pools, available_codes)
        primary_data = catalog[primary_code]
        excluded = {primary_data["element"], *primary_data["secondary_elements"]}
        support_element = self.select_support_element(final, excluded, useful_elements)
        support_codes = self.select_supporting(
            support_element,
            excluded,
            primary_code,
            request,
            energy,
            context,
            catalog,
            primary_pools,
            available_codes,
        )
        bead_count = self.estimate_stringed_bead_count(request.wrist_size_cm, request.bead_size_mm)
        primary_quantity = 1
        accent_quantity = 2
        support_quantity = bead_count - primary_quantity - accent_quantity

        primary = self.build_item(
            primary_code,
            role="主石",
            quantity=primary_quantity,
            bead_size_mm=request.bead_size_mm,
            reason=f"你的首要佩戴目标是“{safe_wish_label(primary_wish)}”，主石优先承接这份当下诉求。",
            catalog=catalog,
        )
        supporting = [
            self.build_item(
                support_codes[0],
                role="调和配珠",
                quantity=support_quantity,
                bead_size_mm=request.bead_size_mm,
                reason=f"结合元素参考与当前状态，本次配珠优先照看{support_element}，用于{ELEMENT_LANGUAGE[support_element]}。",
                catalog=catalog,
            ),
            self.build_item(
                support_codes[1],
                role="点睛配珠",
                quantity=accent_quantity,
                bead_size_mm=request.bead_size_mm,
                reason="作为两侧点睛珠，帮助主石与调和配珠之间形成更柔和的视觉过渡。",
                catalog=catalog,
            ),
        ]
        layout = self.build_layout(bead_count, primary, supporting)
        validation = self.validate_bracelet_plan(request, bead_count, layout, [primary, *supporting])
        if not validation["is_valid"]:
            failed_labels = "、".join(
                check["label"] for check in validation["checks"] if not check["passed"]
            )
            raise ValueError(f"暂无满足{failed_labels or '当前条件'}的推荐方案，请调整珠径后重试")
        return {
            "primary": primary,
            "supporting": supporting,
            "bracelet_plan": {
                "wrist_size_cm": request.wrist_size_cm,
                "bead_size_mm": request.bead_size_mm,
                "estimated_bead_count": bead_count,
                "pattern": "中心主石 + 对称点睛 + 调和配珠",
                "items": [primary, *supporting],
                "layout": layout,
                "estimated_stringed_length_cm": validation["estimated_stringed_length_cm"],
                "target_stringed_length_cm": validation["target_stringed_length_cm"],
                "validation": validation,
            },
            "copy": self.build_copy(request, energy, primary, supporting[0], support_element),
        }

    @staticmethod
    def estimate_stringed_bead_count(wrist_size_cm: float, bead_size_mm: int) -> int:
        bead_size = max(float(bead_size_mm or 8), 1)
        target_mm = max(float(wrist_size_cm or 0) * 10 + STRINGED_COMFORT_ALLOWANCE_MM, 0)
        candidates = [
            (
                count,
                RecommendationEngine.estimate_stringed_length_mm([bead_size] * count),
            )
            for count in range(MIN_RECOMMENDED_BEAD_COUNT, MAX_RECOMMENDED_BEAD_COUNT + 1)
        ]
        return min(
            candidates,
            key=lambda item: (
                abs(item[1] - target_mm),
                item[1] < target_mm,
                item[0],
            ),
        )[0]

    @staticmethod
    def estimate_stringed_length_mm(bead_sizes_mm: list[float]) -> float:
        """Approximate the wearable inner circumference of a closed round-bead loop."""
        sizes: list[float] = []
        for raw_size in bead_sizes_mm:
            try:
                size = float(raw_size)
            except (TypeError, ValueError):
                continue
            if math.isfinite(size) and size > 0:
                sizes.append(size)
        if len(sizes) < 3:
            return 0.0

        radii = [size / 2 for size in sizes]
        contacts = [
            radii[index] + radii[(index + 1) % len(radii)]
            for index in range(len(radii))
        ]

        def central_angles(center_radius: float) -> list[float]:
            return [
                2 * math.asin(min(1.0, contact / (2 * center_radius)))
                for contact in contacts
            ]

        lower = max(max(radii), max(contacts) / 2) * (1 + 1e-9)
        lower_angle = sum(central_angles(lower))
        if lower_angle < 2 * math.pi:
            return 0.0

        upper = max(lower * 2, sum(contacts))
        while sum(central_angles(upper)) > 2 * math.pi:
            upper *= 2

        for _ in range(72):
            midpoint = (lower + upper) / 2
            if sum(central_angles(midpoint)) > 2 * math.pi:
                lower = midpoint
            else:
                upper = midpoint

        center_radius = (lower + upper) / 2
        angles = central_angles(center_radius)
        inner_circumference = 0.0
        for index, radius in enumerate(radii):
            bead_angle = (angles[index - 1] + angles[index]) / 2
            inner_circumference += max(0.0, center_radius - radius) * bead_angle
        return inner_circumference

    @staticmethod
    def material_is_sellable(material: dict | None) -> bool:
        if not material:
            return False
        if material.get("enabled") is False:
            return False
        stock_status = str(
            material.get("stock_status")
            or (material.get("sku") or {}).get("stock_status")
            or (material.get("ops") or {}).get("stock_status")
            or ""
        ).strip().lower()
        if stock_status == "out":
            return False
        price = material.get("price")
        if price in (None, ""):
            price = (material.get("sku") or {}).get("price_per_bead")
        try:
            return math.isfinite(float(price)) and float(price) >= 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def validate_bracelet_plan(
        request: AssessmentRequest,
        bead_count: int,
        layout: list[dict],
        items: list[dict],
    ) -> dict:
        sizes = [
            float(
                item.get("string_axis_width_mm")
                or item.get("actual_material_size_mm")
                or item.get("bead_size_mm")
                or request.bead_size_mm
            )
            for item in layout
        ]
        effective_length_mm = RecommendationEngine.estimate_stringed_length_mm(sizes)
        estimated_length_cm = round(effective_length_mm / 10, 1)
        target_length_cm = round(float(request.wrist_size_cm) + STRINGED_COMFORT_ALLOWANCE_MM / 10, 1)
        count_valid = (
            MIN_RECOMMENDED_BEAD_COUNT <= bead_count <= MAX_RECOMMENDED_BEAD_COUNT
            and len(layout) == bead_count
        )
        length_valid = abs(estimated_length_cm - target_length_cm) <= STRINGED_LENGTH_TOLERANCE_CM
        sellable_valid = all(item.get("material_id") and item.get("available") for item in items)
        price_valid = all(
            isinstance(item.get("unit_price"), (int, float))
            and math.isfinite(float(item["unit_price"]))
            and float(item["unit_price"]) >= 0
            for item in items
        )
        checks = [
            {"key": "bead_count", "label": "颗数上限", "passed": count_valid},
            {"key": "string_length", "label": "腕围适配", "passed": length_valid},
            {"key": "sellable", "label": "库存可售", "passed": sellable_valid},
            {"key": "price", "label": "价格可计算", "passed": price_valid},
        ]
        return {
            "is_valid": all(check["passed"] for check in checks),
            "checks": checks,
            "estimated_stringed_length_cm": estimated_length_cm,
            "target_stringed_length_cm": target_length_cm,
            "length_tolerance_cm": STRINGED_LENGTH_TOLERANCE_CM,
            "max_bead_count": MAX_RECOMMENDED_BEAD_COUNT,
        }

    @staticmethod
    def recommendation_context(request: AssessmentRequest, energy: dict) -> dict:
        chakra = energy.get("chakra_analysis") or {}
        mood = energy.get("mood_analysis") or {}
        mbti = energy.get("mbti_analysis") or {}
        wish_tags = set(request.core_wishes)
        for wish in request.core_wishes:
            wish_tags.update(CORE_WISH_TAGS.get(wish, set()))
        return {
            "useful_elements": set(energy.get("useful_elements") or []),
            "wish_elements": set(WISH_MAPPING[request.primary_core_wish]),
            "mbti_elements": set(mbti.get("top_elements") or []) if mbti.get("selected") else set(),
            "wish_tags": wish_tags,
            "chakras": set(chakra.get("chakras") or []),
            "color_families": set(chakra.get("color_families") or []) | set(mood.get("color_families") or []),
            "mood_tags": set(chakra.get("mood_tags") or []) | set(mood.get("mood_tags") or []),
            "visual_tags": set(chakra.get("visual_tags") or []) | set(mood.get("visual_tags") or []),
        }

    @staticmethod
    def select_primary(
        request: AssessmentRequest,
        energy: dict,
        context: dict,
        catalog: dict,
        primary_pools: dict[str, list[str]],
        available_codes: set[str] | None = None,
    ) -> str:
        pool = set(primary_pools[request.primary_core_wish])
        candidates = [code for code in catalog if not available_codes or code in available_codes]
        if not candidates:
            candidates = list(catalog)
        return max(
            candidates,
            key=lambda code: (
                RecommendationEngine.score_crystal(
                    code, request, energy, context, role="primary", catalog=catalog, primary_pools=primary_pools
                ),
                10 if code in pool else 0,
                -list(catalog).index(code),
            ),
        )

    @staticmethod
    def select_support_element(final: dict[str, float], excluded: set[str], useful_elements: list[str]) -> str:
        for element in useful_elements:
            if element not in excluded:
                return element
        candidate_elements = [element for element in ELEMENTS if element not in excluded]
        return min(candidate_elements, key=lambda element: final[element])

    @staticmethod
    def select_supporting(
        target_element: str,
        excluded: set[str],
        primary_code: str,
        request: AssessmentRequest,
        energy: dict,
        context: dict,
        catalog: dict,
        primary_pools: dict[str, list[str]],
        available_codes: set[str] | None = None,
    ) -> list[str]:
        role_candidates = [
            code
            for code, crystal in catalog.items()
            if code != primary_code
            and RecommendationEngine.role_allowed(crystal, "support")
            and not RecommendationEngine.conflicts_with(code, crystal, {primary_code}, catalog)
        ]
        strict_candidates = [
            code
            for code in role_candidates
            if not (crystal_elements(code, catalog[code]) & excluded)
            and "avoid_dense" not in RecommendationEngine.rule_list(catalog[code], "match_rules")
        ]
        support_candidates = strict_candidates
        if available_codes:
            available_strict = [code for code in strict_candidates if code in available_codes]
            available_relaxed = [
                code
                for code in role_candidates
                if code in available_codes
                and element_label(catalog[code].get("element")) not in excluded
                and "avoid_dense" not in RecommendationEngine.rule_list(catalog[code], "match_rules")
            ]
            available_role_candidates = [code for code in role_candidates if code in available_codes]
            available_fallback = [
                code
                for code, crystal in catalog.items()
                if code != primary_code
                and code in available_codes
                and not RecommendationEngine.conflicts_with(code, crystal, {primary_code}, catalog)
            ]
            support_candidates = (
                available_strict or available_relaxed or available_role_candidates or available_fallback
            )
        if not support_candidates:
            support_candidates = role_candidates or [code for code in catalog if code != primary_code]
        first = max(
            support_candidates,
            key=lambda code: RecommendationEngine.score_crystal(
                code,
                request,
                energy,
                context,
                role="support",
                target_element=target_element,
                catalog=catalog,
                primary_pools=primary_pools,
            ),
        )
        accent_candidates = [
            code
            for code, crystal in catalog.items()
            if code not in {primary_code, first}
            and RecommendationEngine.role_allowed(crystal, "accent")
            and not RecommendationEngine.conflicts_with(code, crystal, {primary_code, first}, catalog)
        ]
        if available_codes:
            available_accent_candidates = [code for code in accent_candidates if code in available_codes]
            available_relaxed_accents = [
                code
                for code, crystal in catalog.items()
                if code not in {primary_code, first}
                and code in available_codes
                and not RecommendationEngine.conflicts_with(code, crystal, {primary_code, first}, catalog)
            ]
            accent_candidates = available_accent_candidates or available_relaxed_accents
        if not accent_candidates:
            accent_candidates = [first] if available_codes else [
                code for code in catalog if code not in {primary_code, first}
            ]
        accent = max(
            accent_candidates,
            key=lambda code: RecommendationEngine.score_crystal(
                code, request, energy, context, role="accent", catalog=catalog, primary_pools=primary_pools
            ),
            default=first,
        )
        return [first, accent]

    @staticmethod
    def score_crystal(
        code: str,
        request: AssessmentRequest,
        energy: dict,
        context: dict,
        role: str,
        target_element: str | None = None,
        catalog: dict | None = None,
        primary_pools: dict[str, list[str]] | None = None,
    ) -> float:
        catalog = catalog or RecommendationEngine.catalog()
        primary_pools = primary_pools or RecommendationEngine.primary_pools(catalog)
        crystal = catalog[code]
        if not RecommendationEngine.role_allowed(crystal, role):
            return -10000
        taxonomy = merge_taxonomy(code, crystal)
        elements = crystal_elements(code, crystal)
        score = 0.0
        score += 18 * len(elements & context["useful_elements"])
        score += 12 * len(elements & context["wish_elements"])
        score += 4 * len(elements & context.get("mbti_elements", set()))
        score += 18 if target_element and target_element in elements else 0
        score += 18 if set(taxonomy.get("wish_tags", [])) & context["wish_tags"] else 0
        score += 8 * len(set(taxonomy.get("chakras", [])) & context["chakras"])
        score += 3 * len(set(taxonomy.get("color_families", [])) & context["color_families"])
        score += 3 * len(set(taxonomy.get("mood_tags", [])) & context["mood_tags"])
        score += 2 * len(set(taxonomy.get("visual_tags", [])) & context["visual_tags"])
        if role == "primary" and code in primary_pools[request.primary_core_wish]:
            score += 16
        if role == "accent":
            score += 2 * len(set(taxonomy.get("color_families", [])) & context["color_families"])
            score += 2 * len(set(taxonomy.get("visual_tags", [])) & context["visual_tags"])
        score += RecommendationEngine.rule_score(crystal, role)
        score += float((energy.get("final") or {}).get(element_label(crystal["element"]), 0)) / 20
        return score

    @staticmethod
    def rule_list(crystal: dict, key: str) -> set[str]:
        return set(unique_list(crystal.get(key)))

    @staticmethod
    def role_allowed(crystal: dict, role: str) -> bool:
        role_key = RecommendationEngine.ROLE_KEY.get(role, role)
        allowed_roles = RecommendationEngine.rule_list(crystal, "allowed_roles")
        if allowed_roles and role_key not in allowed_roles:
            return False
        rules = RecommendationEngine.rule_list(crystal, "match_rules")
        if role_key == "primary" and {"accent_only", "spacer_only"} & rules:
            return False
        if role_key == "support" and {"accent_only", "spacer_only"} & rules:
            return False
        if role_key == "accent" and "best_as_primary" in rules and "accent" not in allowed_roles:
            return False
        return True

    @staticmethod
    def rule_score(crystal: dict, role: str) -> float:
        rules = RecommendationEngine.rule_list(crystal, "match_rules")
        role_key = RecommendationEngine.ROLE_KEY.get(role, role)
        score = 0.0
        if role_key == "primary":
            if "best_as_primary" in rules:
                score += 18
            if "best_as_support" in rules:
                score -= 12
            if "avoid_dense" in rules:
                score -= 6
        elif role_key == "support":
            if "best_as_support" in rules:
                score += 16
            if "best_as_primary" in rules:
                score -= 10
            if "avoid_dense" in rules:
                score -= 24
        elif role_key == "accent":
            if "accent_only" in rules or "spacer_only" in rules:
                score += 18
            if "pair_symmetry" in rules:
                score += 8
            if "needs_color_balance" in rules:
                score += 4
        return score

    @staticmethod
    def conflicts_with(code: str, crystal: dict, selected_codes: set[str], catalog: dict) -> bool:
        conflicts = RecommendationEngine.rule_list(crystal, "conflict_codes")
        if conflicts & selected_codes:
            return True
        for selected in selected_codes:
            selected_crystal = catalog.get(selected) or {}
            if code in RecommendationEngine.rule_list(selected_crystal, "conflict_codes"):
                return True
        return False

    @staticmethod
    def build_item(
        code: str,
        role: str,
        quantity: int,
        bead_size_mm: int,
        reason: str,
        catalog: dict | None = None,
    ) -> dict:
        catalog = catalog or RecommendationEngine.catalog()
        crystal = catalog[code]
        taxonomy = merge_taxonomy(code, crystal)
        material = RecommendationEngine.resolve_material_for_code(code, bead_size_mm, crystal.get("name") or "")
        material_image_url = material.get("image_url") or material.get("thumbnail_url") or ""
        material_size = RecommendationEngine.material_size_mm(material)
        material_params = {
            **(crystal.get("material_params") or {}),
            **(material.get("material_params") or {}),
        }
        string_axis_width_mm = material_params.get("string_axis_width_mm") or material_size or bead_size_mm
        material_id = str(material.get("id") or "")
        unit_price = material.get("price")
        if unit_price in (None, ""):
            unit_price = (material.get("sku") or {}).get("price_per_bead")
        try:
            unit_price = float(unit_price)
        except (TypeError, ValueError):
            unit_price = None
        return {
            "code": code,
            "name": crystal["name"],
            "role": role,
            "element": crystal["element"],
            "secondary_elements": unique_list(crystal.get("secondary_elements")),
            "chakras": taxonomy.get("chakras", []),
            "color_families": taxonomy.get("color_families", []),
            "mood_tags": taxonomy.get("mood_tags", [])[:5],
            "color": crystal["color"],
            "effects": [safe_display_text(effect) for effect in unique_list(crystal.get("effects"))],
            "reason": safe_display_text(reason),
            "quantity": quantity,
            "bead_size_mm": bead_size_mm,
            "preferred_bead_size_mm": bead_size_mm,
            "material_id": material_id,
            "source_material_id": material_id,
            "sku_id": material.get("skuId") or material.get("sku_id") or "",
            "material_code": material.get("material_code") or code,
            "actual_material_size_mm": material_size or bead_size_mm,
            "string_axis_width_mm": string_axis_width_mm,
            "unit_price": unit_price,
            "stock": material.get("stock"),
            "available": RecommendationEngine.material_is_sellable(material),
            "image_url": material_image_url or (crystal.get("asset") or {}).get("thumbnail_url", ""),
            "rules": {
                "allowed_roles": unique_list(crystal.get("allowed_roles")),
                "conflict_codes": unique_list(crystal.get("conflict_codes")),
                "match_rules": unique_list(crystal.get("match_rules")),
                "care_tags": unique_list(crystal.get("care_tags")),
            },
            "material_params": material_params,
        }

    @staticmethod
    def material_size_mm(material: dict | None) -> float:
        if not material:
            return 0
        size = material.get("size") or material.get("size_mm")
        if size in (None, ""):
            sku = material.get("sku") or {}
            size = sku.get("size_mm")
        try:
            return float(size or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def material_sort_order(material: dict | None) -> int:
        if not material:
            return 0
        sort_order = material.get("sort_order") or material.get("sortOrder")
        if sort_order in (None, ""):
            sku = material.get("sku") or {}
            sort_order = sku.get("sort_order")
        try:
            return int(float(sort_order or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def material_matches_code(material: dict, code: str) -> bool:
        target = material_code_token(code)
        tokens = {
            material_code_token(material.get("id")),
            material_code_token(material.get("skuId")),
            material_code_token(material.get("sku_id")),
            material_code_token(material.get("material_code")),
            material_code_token(material_code_from_payload(material)),
        }
        return target in tokens

    @staticmethod
    def material_matches_name(material: dict, name: str) -> bool:
        target = str(name or "").strip()
        if not target:
            return False
        text = " ".join(
            str(material.get(key) or "")
            for key in ("name", "category", "series", "skuId", "sku_id", "material_code", "effect")
        )
        return target in text

    @staticmethod
    def material_matches_size(material: dict, bead_size_mm: int) -> bool:
        target_size = float(bead_size_mm or 0)
        size = RecommendationEngine.material_size_mm(material)
        return bool(target_size and size and abs(size - target_size) <= 0.25)

    @staticmethod
    def load_bead_inventory() -> tuple[list[dict], bool]:
        from .materials import MATERIAL_CATALOG, list_db_materials

        db_materials = list_db_materials(top="bead", enrich=False)
        if db_materials is not None:
            return db_materials, True
        return MATERIAL_CATALOG, False

    @staticmethod
    def material_matches_catalog_entry(material: dict, code: str, crystal: dict) -> bool:
        return RecommendationEngine.material_matches_code(material, code) or RecommendationEngine.material_matches_name(
            material,
            crystal.get("name") or "",
        )

    @staticmethod
    def available_catalog_codes(catalog: dict[str, dict], bead_size_mm: int) -> set[str]:
        try:
            materials, _ = RecommendationEngine.load_bead_inventory()
        except Exception:
            return set()
        available: set[str] = set()
        exact_materials = [
            item
            for item in materials
            if RecommendationEngine.material_matches_size(item, bead_size_mm)
            and RecommendationEngine.material_is_sellable(item)
        ]
        for code, crystal in catalog.items():
            if any(RecommendationEngine.material_matches_catalog_entry(item, code, crystal) for item in exact_materials):
                available.add(code)
        return available

    @staticmethod
    def choose_closest_material(candidates: list[dict], bead_size_mm: int) -> dict:
        if not candidates:
            return {}
        exact_candidates = [
            item for item in candidates
            if RecommendationEngine.material_matches_size(item, bead_size_mm)
        ]
        if exact_candidates:
            candidates = exact_candidates
        target_size = float(bead_size_mm or 8)
        return min(
            candidates,
            key=lambda item: (
                abs((RecommendationEngine.material_size_mm(item) or target_size) - target_size),
                RecommendationEngine.material_sort_order(item),
                str(item.get("id") or ""),
            ),
        )

    @staticmethod
    def resolve_material_for_code(code: str, bead_size_mm: int, crystal_name: str = "") -> dict:
        try:
            materials, _ = RecommendationEngine.load_bead_inventory()
            candidates = [
                item for item in materials
                if RecommendationEngine.material_matches_code(item, code)
                and RecommendationEngine.material_is_sellable(item)
            ]
            if not candidates and crystal_name:
                candidates = [
                    item for item in materials
                    if RecommendationEngine.material_matches_name(item, crystal_name)
                    and RecommendationEngine.material_is_sellable(item)
                ]
            return RecommendationEngine.choose_closest_material(candidates, bead_size_mm)
        except Exception:
            return {}

    @staticmethod
    def build_layout(bead_count: int, primary: dict, supporting: list[dict]) -> list[dict]:
        layout = []
        accent_positions = {1, bead_count - 1}
        for index in range(bead_count):
            item = primary if index == 0 else supporting[1] if index in accent_positions else supporting[0]
            layout.append(
                {
                    "position": index + 1,
                    "crystal_code": item["code"],
                    "crystal_name": item["name"],
                    "role": item["role"],
                    "color": item["color"],
                    "bead_size_mm": item.get("bead_size_mm"),
                    "actual_material_size_mm": item.get("actual_material_size_mm"),
                    "string_axis_width_mm": item.get("string_axis_width_mm"),
                    "preferred_bead_size_mm": item.get("preferred_bead_size_mm") or item.get("bead_size_mm"),
                    "material_id": item.get("material_id", ""),
                    "source_material_id": item.get("source_material_id", ""),
                    "sku_id": item.get("sku_id", ""),
                    "material_code": item.get("material_code", item["code"]),
                }
            )
        return layout

    @staticmethod
    def build_copy(
        request: AssessmentRequest,
        energy: dict,
        primary: dict,
        supporting: dict,
        support_element: str,
    ) -> str:
        strongest = energy["strongest"]
        strategy = safe_display_text(energy.get("recommendation_strategy") or "以元素比例为基础做温柔调和。")
        chakra = energy.get("chakra_analysis") or {}
        mood = energy.get("mood_analysis") or {}
        live_state = "".join(
            item
            for item in [
                chakra.get("summary", ""),
                mood.get("summary", ""),
            ]
            if item
        )
        return (
            f"{request.name}，你的五行画像中{strongest}元素倾向最为鲜明，{strategy}"
            f"以{primary['name']}作为手串主石，"
            f"承接“{'、'.join(safe_wish_label(wish) for wish in request.core_wishes)}”的佩戴目标；再用{supporting['name']}调和{support_element}元素，"
            f"让你原本的优势不被削弱，也为当下需要生长的部分留出空间。"
            f"{safe_display_text(live_state)}"
        )


def interpretation(final: dict[str, float], strongest: str, weakest: str) -> dict:
    average = sum(final.values()) / len(final)
    balance = round(max(0, 100 - (max(final.values()) - min(final.values())) * 3), 1)
    return {
        "headline": f"{strongest}元素倾向鲜明，{weakest}元素适合温柔调和",
        "strongest": f"{strongest}代表你当前较自然、较容易调用的风格力量。",
        "weakest": f"{weakest}并非缺点，而是适合通过配珠与日常习惯慢慢调和的方向。",
        "balance_index": balance,
        "average_score": round(average, 2),
    }
