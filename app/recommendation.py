from __future__ import annotations

import hashlib
import math
import os

from .bracelet_sizing import (
    BRACELET_FIT_MODEL_VERSION,
    calculate_bracelet_fit,
    estimate_inner_circumference_mm,
    recommend_bead_count,
)
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
BRACELET_COMPOSER_VERSION = "2026-07-27-v3"

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

    def recommend(self, request: AssessmentRequest, energy: dict, refinement: dict | None = None) -> dict:
        refinement = refinement or {}
        final = energy["final"]
        primary_wish = request.primary_core_wish
        context = self.recommendation_context(request, energy)
        useful_elements = [element for element in energy.get("useful_elements", []) if element in ELEMENTS]
        catalog = self.catalog()
        primary_pools = self.primary_pools(catalog)
        available_codes = self.available_catalog_codes(catalog, request.bead_size_mm)
        primary_codes = self.select_primary_candidates(
            request, energy, context, catalog, primary_pools, available_codes
        )
        primary_code = primary_codes[0]
        primary_data = catalog[primary_code]
        excluded = {primary_data["element"], *primary_data["secondary_elements"]}
        support_element = self.select_support_element(final, excluded, useful_elements)
        accessory_preference = refinement.get("accessory_preference") or "balanced"
        accessory_limit = 1 if accessory_preference == "less" else 2
        palette_variants = []
        for variant_index in range(3):
            variant_primary_code = primary_codes[min(variant_index, len(primary_codes) - 1)]
            variant_primary_data = catalog[variant_primary_code]
            variant_excluded = {
                variant_primary_data["element"],
                *variant_primary_data["secondary_elements"],
            }
            variant_support_element = self.select_support_element(final, variant_excluded, useful_elements)
            variant_support_codes = self.select_supporting(
                variant_support_element,
                variant_excluded,
                variant_primary_code,
                request,
                energy,
                context,
                catalog,
                primary_pools,
                available_codes,
                variant_index=variant_index,
            )
            variant_primary = self.build_item(
                variant_primary_code,
                role="主石",
                quantity=1,
                bead_size_mm=request.bead_size_mm,
                reason=f"你的首要佩戴目标是“{safe_wish_label(primary_wish)}”，主石优先承接这份当下诉求。",
                catalog=catalog,
            )
            variant_support = self.build_item(
                variant_support_codes[0],
                role="调和配珠",
                quantity=1,
                bead_size_mm=request.bead_size_mm,
                reason=f"结合元素参考与当前状态，本次配珠优先照看{variant_support_element}，用于{ELEMENT_LANGUAGE[variant_support_element]}。",
                catalog=catalog,
            )
            variant_accent = self.build_item(
                variant_support_codes[1],
                role="点睛配珠",
                quantity=2,
                bead_size_mm=request.bead_size_mm,
                reason="作为两侧点睛珠，帮助主石与调和配珠之间形成更自然的色彩与质感过渡。",
                catalog=catalog,
            )
            additional_code = self.select_additional_support(
                selected_codes={variant_primary_code, *variant_support_codes},
                request=request,
                energy=energy,
                context=context,
                catalog=catalog,
                primary_pools=primary_pools,
                available_codes=available_codes,
                variant_index=variant_index,
            )
            variant_transition = (
                self.build_item(
                    additional_code,
                    role="过渡配珠",
                    quantity=1,
                    bead_size_mm=request.bead_size_mm,
                    reason="作为过渡材质加入少量层次，让颜色和质感变化更自然。",
                    catalog=catalog,
                )
                if additional_code
                else variant_support
            )
            variant_accessories = self.select_accessory_items(
                request=request,
                context=context,
                bead_items=[variant_primary, variant_support, variant_accent, variant_transition],
                limit=accessory_limit,
            )
            palette_variants.append(
                {
                    "primary": variant_primary,
                    "support": variant_support,
                    "accent": variant_accent,
                    "transition": variant_transition,
                    "accessories": variant_accessories,
                }
            )
        primary = palette_variants[0]["primary"]
        supporting = [palette_variants[0]["support"], palette_variants[0]["accent"]]
        additional = palette_variants[0]["transition"]
        accessories = palette_variants[0]["accessories"]
        locked_ids = set(refinement.get("locked_material_ids") or [])
        available_items = [
            item
            for palette in palette_variants
            for item in (
                palette["primary"],
                palette["support"],
                palette["accent"],
                palette["transition"],
                *palette["accessories"],
            )
        ]
        locked_items = [
            {**item, "locked": True}
            for item in available_items
            if self.item_identity(item) in locked_ids
        ]
        if locked_ids and len({self.item_identity(item) for item in locked_items}) != len(locked_ids):
            raise ValueError("部分保留材料已不可用，请重新选择")
        locked_accessories = [item for item in locked_items if item.get("top") == "accessory"]
        if locked_accessories:
            locked_identity = self.item_identity(locked_accessories[0])
            for palette in palette_variants:
                palette["accessories"] = [
                    locked_accessories[0],
                    *[
                        item
                        for item in palette["accessories"]
                        if self.item_identity(item) != locked_identity
                    ],
                ][:accessory_limit]
            accessories = palette_variants[0]["accessories"]
        bracelet_plans = self.compose_bracelet_plans(
            request=request,
            primary=primary,
            support=supporting[0],
            accent=supporting[1],
            transition=additional,
            accessories=accessories,
            palette_variants=palette_variants,
            locked_items=locked_items,
            style_preference=refinement.get("style_preference"),
            accessory_preference=accessory_preference,
            rejected_plan_id=refinement.get("rejected_plan_id"),
        )
        if not bracelet_plans:
            raise ValueError("暂无满足腕围、库存与材料规则的推荐方案，请调整珠径后重试")
        preferred_style = {
            "minimal": "daily_minimal",
            "layered": "signature_accent",
        }.get(refinement.get("style_preference"), "balanced_layers")
        recommended_index = next(
            (
                index
                for index, plan in enumerate(bracelet_plans)
                if plan.get("style") == preferred_style
                and (accessory_preference != "more" or plan.get("has_accessories"))
            ),
            next(
                (
                    index
                    for index, plan in enumerate(bracelet_plans)
                    if plan.get("style") == preferred_style
                ),
                0,
            ),
        )
        for index, plan in enumerate(bracelet_plans):
            plan["is_recommended"] = index == recommended_index
        selected_plan = bracelet_plans[recommended_index]
        return {
            "primary": primary,
            "supporting": supporting,
            "bracelet_plan": selected_plan,
            "bracelet_plans": bracelet_plans,
            "copy": self.build_copy(request, energy, primary, supporting[0], support_element),
        }

    @staticmethod
    def estimate_stringed_bead_count(wrist_size_cm: float, bead_size_mm: int) -> int:
        bead_size = max(float(bead_size_mm or 8), 1)
        return recommend_bead_count(
            [bead_size],
            wrist_size_cm,
            allowance_mm=STRINGED_COMFORT_ALLOWANCE_MM,
            min_count=MIN_RECOMMENDED_BEAD_COUNT,
            max_count=MAX_RECOMMENDED_BEAD_COUNT,
        )

    @staticmethod
    def estimate_stringed_length_mm(bead_sizes_mm: list[float]) -> float:
        """Approximate the wearable inner circumference of a closed round-bead loop."""
        return estimate_inner_circumference_mm(bead_sizes_mm)

    @staticmethod
    def material_is_sellable(material: dict | None) -> bool:
        if not material:
            return False
        enabled = material.get("enabled", True)
        if enabled in {False, 0, "0", "false", "False"}:
            return False
        stock_status = str(
            material.get("stock_status")
            or (material.get("sku") or {}).get("stock_status")
            or (material.get("ops") or {}).get("stock_status")
            or ""
        ).strip().lower()
        if stock_status == "out":
            return False
        stock = material.get("stock")
        if stock not in (None, ""):
            try:
                if int(float(stock)) <= 0:
                    return False
            except (TypeError, ValueError):
                return False
        price = material.get("price")
        if price in (None, ""):
            price = (material.get("sku") or {}).get("price_per_bead")
        try:
            return math.isfinite(float(price)) and float(price) > 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def validate_bracelet_plan(
        request: AssessmentRequest,
        bead_count: int,
        layout: list[dict],
        items: list[dict],
    ) -> dict:
        sizing_items = [
            {
                **item,
                "string_axis_width_mm": (
                    item.get("string_axis_width_mm")
                    or item.get("actual_material_size_mm")
                    or item.get("bead_size_mm")
                    or request.bead_size_mm
                ),
            }
            for item in layout
        ]
        fit = calculate_bracelet_fit(
            sizing_items,
            request.wrist_size_cm,
            allowance_mm=STRINGED_COMFORT_ALLOWANCE_MM,
            tolerance_mm=STRINGED_LENGTH_TOLERANCE_CM * 10,
            min_count=MIN_RECOMMENDED_BEAD_COUNT,
            max_count=MAX_RECOMMENDED_BEAD_COUNT,
        )
        estimated_length_cm = round(fit["actual_inner_mm"] / 10, 1)
        target_length_cm = round(fit["target_inner_mm"] / 10, 1)
        count_valid = (
            MIN_RECOMMENDED_BEAD_COUNT <= bead_count <= MAX_RECOMMENDED_BEAD_COUNT
            and len(layout) == bead_count
        )
        length_valid = fit["status"] == "fit"
        sellable_valid = all(item.get("material_id") and item.get("available") for item in items)
        price_valid = all(
            isinstance(item.get("unit_price"), (int, float))
            and math.isfinite(float(item["unit_price"]))
            and float(item["unit_price"]) >= 0
            for item in items
        )
        quantity_valid = sum(int(item.get("quantity") or 0) for item in items) == bead_count
        stock_valid = True
        role_valid = True
        symmetry_valid = True
        usage_valid = True
        identities = set()
        for item in items:
            identity = RecommendationEngine.item_identity(item)
            if identity:
                identities.add(identity)
            stock = item.get("stock")
            if stock not in (None, ""):
                try:
                    stock_valid = stock_valid and int(float(stock)) >= int(item.get("quantity") or 0)
                except (TypeError, ValueError):
                    stock_valid = False
            role_key = str(item.get("role_key") or "")
            allowed_roles = set(RecommendationEngine.material_rule_values(item, "allowed_roles"))
            if allowed_roles and role_key and role_key not in allowed_roles:
                role_valid = False
            rules = set(RecommendationEngine.material_rule_values(item, "match_rules"))
            if "pair_symmetry" in rules and role_key in {"accent", "spacer"}:
                symmetry_valid = symmetry_valid and int(item.get("quantity") or 0) % 2 == 0
            usage = item.get("recommended_usage") or {}
            if item.get("top") == "accessory" and usage:
                try:
                    count_min = int(usage.get("count_min") or 1)
                    count_max = int(usage.get("count_max") or MAX_RECOMMENDED_BEAD_COUNT)
                    quantity = int(item.get("quantity") or 0)
                    usage_valid = usage_valid and count_min <= quantity <= count_max
                except (TypeError, ValueError):
                    usage_valid = False
        variety_valid = len(identities) >= 2
        checks = [
            {"key": "bead_count", "label": "颗数上限", "passed": count_valid},
            {"key": "string_length", "label": "腕围适配", "passed": length_valid},
            {"key": "sellable", "label": "库存可售", "passed": sellable_valid},
            {"key": "stock_quantity", "label": "库存数量", "passed": stock_valid},
            {"key": "price", "label": "价格可计算", "passed": price_valid},
            {"key": "quantity", "label": "材料数量", "passed": quantity_valid},
            {"key": "role", "label": "材料角色", "passed": role_valid},
            {"key": "symmetry", "label": "对称规则", "passed": symmetry_valid},
            {"key": "usage", "label": "配饰用量", "passed": usage_valid},
            {"key": "variety", "label": "材料层次", "passed": variety_valid},
        ]
        return {
            "is_valid": all(check["passed"] for check in checks),
            "checks": checks,
            "estimated_stringed_length_cm": estimated_length_cm,
            "target_stringed_length_cm": target_length_cm,
            "length_tolerance_cm": STRINGED_LENGTH_TOLERANCE_CM,
            "max_bead_count": MAX_RECOMMENDED_BEAD_COUNT,
            "sizing_model_version": BRACELET_FIT_MODEL_VERSION,
            "fit_status": fit["status"],
            "fit_error_mm": round(float(fit["error_mm"]), 3),
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
        return RecommendationEngine.select_primary_candidates(
            request, energy, context, catalog, primary_pools, available_codes
        )[0]

    @staticmethod
    def select_primary_candidates(
        request: AssessmentRequest,
        energy: dict,
        context: dict,
        catalog: dict,
        primary_pools: dict[str, list[str]],
        available_codes: set[str] | None = None,
        limit: int = 3,
    ) -> list[str]:
        pool = set(primary_pools[request.primary_core_wish])
        candidates = [
            code
            for code in catalog
            if available_codes is None or code in available_codes
        ]
        if not candidates:
            if available_codes is not None:
                raise ValueError("暂无匹配当前珠径的可售材料，请调整珠径后重试")
            candidates = list(catalog)
        ranked = RecommendationEngine.rank_aesthetic_candidates(
            candidates,
            request=request,
            energy=energy,
            context=context,
            role="primary",
            catalog=catalog,
            primary_pools=primary_pools,
            preferred_codes=pool,
        )
        return ranked[:max(1, limit)]

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
        variant_index: int = 0,
    ) -> list[str]:
        role_candidates = [
            code
            for code, crystal in catalog.items()
            if code != primary_code
            and RecommendationEngine.role_allowed(crystal, "support")
        ]
        strict_candidates = [
            code
            for code in role_candidates
            if not (crystal_elements(code, catalog[code]) & excluded)
            and "avoid_dense" not in RecommendationEngine.rule_list(catalog[code], "match_rules")
        ]
        support_candidates = strict_candidates
        if available_codes is not None:
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
            ]
            support_candidates = (
                available_strict or available_relaxed or available_role_candidates or available_fallback
            )
        if not support_candidates and available_codes is not None:
            raise ValueError("暂无可售的调和配珠，请调整珠径后重试")
        if not support_candidates:
            support_candidates = role_candidates or [code for code in catalog if code != primary_code]
        ranked_support = RecommendationEngine.rank_aesthetic_candidates(
            support_candidates,
            request=request,
            energy=energy,
            context=context,
            role="support",
            target_element=target_element,
            catalog=catalog,
            primary_pools=primary_pools,
        )
        first = ranked_support[min(variant_index, len(ranked_support) - 1)]
        accent_candidates = [
            code
            for code, crystal in catalog.items()
            if code not in {primary_code, first}
            and RecommendationEngine.role_allowed(crystal, "accent")
        ]
        if available_codes is not None:
            available_accent_candidates = [code for code in accent_candidates if code in available_codes]
            available_relaxed_accents = [
                code
                for code, crystal in catalog.items()
                if code not in {primary_code, first}
                and code in available_codes
            ]
            accent_candidates = available_accent_candidates or available_relaxed_accents
        if not accent_candidates:
            accent_candidates = [first] if available_codes is not None else [
                code for code in catalog if code not in {primary_code, first}
            ]
        ranked_accents = RecommendationEngine.rank_aesthetic_candidates(
            accent_candidates,
            request=request,
            energy=energy,
            context=context,
            role="accent",
            catalog=catalog,
            primary_pools=primary_pools,
        )
        accent = ranked_accents[min(variant_index, len(ranked_accents) - 1)] if ranked_accents else first
        return [first, accent]

    @staticmethod
    def select_additional_support(
        *,
        selected_codes: set[str],
        request: AssessmentRequest,
        energy: dict,
        context: dict,
        catalog: dict,
        primary_pools: dict[str, list[str]],
        available_codes: set[str] | None = None,
        variant_index: int = 0,
    ) -> str:
        candidates = [
            code
            for code, crystal in catalog.items()
            if code not in selected_codes
            and (available_codes is None or code in available_codes)
            and RecommendationEngine.role_allowed(crystal, "support")
            and "avoid_dense" not in RecommendationEngine.rule_list(crystal, "match_rules")
        ]
        ranked = RecommendationEngine.rank_aesthetic_candidates(
            candidates,
            request=request,
            energy=energy,
            context=context,
            role="support",
            catalog=catalog,
            primary_pools=primary_pools,
        )
        return ranked[min(variant_index, len(ranked) - 1)] if ranked else ""

    @staticmethod
    def personal_resonance_score(code: str, request: AssessmentRequest) -> float:
        """Stable light-weight tiebreaker so similar profiles are not all identical."""
        identity = "|".join(
            [
                str(request.birthday),
                str(request.birth_time),
                str(request.mbti or ""),
                str(request.primary_core_wish),
                code,
            ]
        )
        return int(hashlib.sha1(identity.encode("utf-8")).hexdigest()[:6], 16) / 0xFFFFFF * 3

    @staticmethod
    def rank_aesthetic_candidates(
        candidates: list[str],
        *,
        request: AssessmentRequest,
        energy: dict,
        context: dict,
        role: str,
        catalog: dict,
        primary_pools: dict[str, list[str]],
        target_element: str | None = None,
        preferred_codes: set[str] | None = None,
    ) -> list[str]:
        preferred_codes = preferred_codes or set()
        scored = sorted(
            dict.fromkeys(candidates),
            key=lambda code: (
                -(
                    RecommendationEngine.score_crystal(
                        code,
                        request,
                        energy,
                        context,
                        role=role,
                        target_element=target_element,
                        catalog=catalog,
                        primary_pools=primary_pools,
                    )
                    + (8 if code in preferred_codes else 0)
                    + RecommendationEngine.personal_resonance_score(code, request)
                ),
                str(code),
            ),
        )
        # First expose different colour/element stories, then keep score order
        # for the remaining candidates. This avoids three near-identical plans.
        result: list[str] = []
        seen_stories: set[tuple[str, str]] = set()
        for code in scored:
            crystal = catalog.get(code) or {}
            taxonomy = merge_taxonomy(code, crystal)
            story = (
                str(crystal.get("element") or ""),
                str((taxonomy.get("color_families") or [""])[0] or ""),
            )
            if story in seen_stories:
                continue
            result.append(code)
            seen_stories.add(story)
        result.extend(code for code in scored if code not in result)
        return result

    @staticmethod
    def load_accessory_inventory() -> tuple[list[dict], bool]:
        from .materials import MATERIAL_CATALOG, list_db_materials

        db_materials = list_db_materials(top="accessory", enrich=True)
        if db_materials:
            return db_materials, True
        if os.getenv("APP_ENV", "").strip().lower() in {"production", "prod"}:
            return [], db_materials is not None
        return [
            item
            for item in MATERIAL_CATALOG
            if str(item.get("top") or "").strip().lower() == "accessory"
        ], False

    @staticmethod
    def material_rule_values(material: dict, key: str) -> list[str]:
        return unique_list(
            material.get(key)
            or (material.get("rules") or {}).get(key)
            or (material.get("knowledge") or {}).get(key)
        )

    @staticmethod
    def accessory_score(material: dict, context: dict) -> float:
        color_family = str(
            material.get("color_family")
            or (material.get("energy") or {}).get("color_family")
            or ""
        ).strip()
        mood_tags = set(
            unique_list(
                material.get("mood_tags")
                or (material.get("energy") or {}).get("mood_tags")
            )
        )
        visual_tags = set(
            unique_list(
                material.get("visual_tags")
                or (material.get("energy") or {}).get("visual_tags")
            )
        )
        allowed_roles = set(RecommendationEngine.material_rule_values(material, "allowed_roles"))
        rules = set(RecommendationEngine.material_rule_values(material, "match_rules"))
        score = 0.0
        if "spacer" in allowed_roles:
            score += 8
        if "accent" in allowed_roles:
            score += 4
        if "pair_symmetry" in rules:
            score += 6
        if color_family and color_family in context.get("color_families", set()):
            score += 10
        score += 3 * len(mood_tags & context.get("mood_tags", set()))
        score += 2 * len(visual_tags & context.get("visual_tags", set()))
        if "avoid_dense" in rules:
            score += 2
        score += RecommendationEngine.metal_palette_score(material, context)
        score -= max(0, RecommendationEngine.material_sort_order(material)) / 100000
        return score

    @staticmethod
    def accessory_is_metal(material: dict) -> bool:
        material_params = {
            **(((material.get("visual") or {}).get("material_params")) or {}),
            **(material.get("material_params") or {}),
        }
        material_text = " ".join(
            str(value or "").strip().lower()
            for value in (
                material.get("category"),
                material.get("series"),
                material_params.get("material_type"),
                material_params.get("material"),
                material_params.get("finish"),
            )
        )
        if any(
            keyword in material_text
            for keyword in (
                "隔珠",
                "隔片",
                "花托",
                "金属",
                "合金",
                "银",
                "铜",
                "不锈钢",
                "metal",
                "alloy",
                "silver",
                "gold",
                "copper",
                "brass",
                "steel",
            )
        ):
            return True
        name = str(material.get("name") or material.get("series") or "").strip().lower()
        return any(
            keyword in name
            for keyword in (
                "银色",
                "亮银",
                "高光银",
                "古金",
                "亮金",
                "镀金",
                "镀银",
                "锆石排镶",
            )
        )

    @staticmethod
    def metal_palette_score(material: dict, context: dict) -> float:
        if not RecommendationEngine.accessory_is_metal(material):
            return 0.0
        material_params = {
            **(((material.get("visual") or {}).get("material_params")) or {}),
            **(material.get("material_params") or {}),
        }
        descriptor = " ".join(
            str(value or "").strip().lower()
            for value in (
                material.get("name"),
                material.get("series"),
                material.get("category"),
                material_params.get("material_type"),
                material_params.get("material"),
                material_params.get("finish"),
                material_params.get("metal_tone"),
            )
        )
        warm_keywords = ("金色", "亮金", "古金", "玫瑰金", "镀金", "黄金", "铜", "gold", "copper", "brass")
        cool_keywords = ("银色", "亮银", "高光银", "镀银", "白金", "钢", "silver", "steel")
        tone = (
            "warm"
            if any(keyword in descriptor for keyword in warm_keywords)
            else "cool"
            if any(keyword in descriptor for keyword in cool_keywords)
            else "neutral"
        )
        palette = {
            str(value or "").strip().lower()
            for value in context.get("bracelet_color_families", set())
            if str(value or "").strip()
        }
        warm_palette = {"gold", "yellow", "orange", "red", "pink", "brown", "earth"}
        cool_palette = {"blue", "purple", "indigo", "white", "clear", "gray", "black"}
        warm_weight = len(palette & warm_palette)
        cool_weight = len(palette & cool_palette)
        if tone == "warm":
            return 8.0 if warm_weight > cool_weight else -5.0 if cool_weight > warm_weight else 2.0
        if tone == "cool":
            return 8.0 if cool_weight > warm_weight else -5.0 if warm_weight > cool_weight else 2.0
        return 3.0 if palette & {"white", "clear", "gray", "black", "gold"} else 1.0

    @staticmethod
    def build_accessory_item(material: dict, request: AssessmentRequest) -> dict:
        sku = material.get("sku") or {}
        energy = material.get("energy") or {}
        visual = material.get("visual") or {}
        material_params = {
            **(visual.get("material_params") or {}),
            **(material.get("material_params") or {}),
        }
        size_mm = RecommendationEngine.material_size_mm(material)
        string_axis_width_mm = (
            material_params.get("string_axis_width_mm")
            or size_mm
            or max(1.0, float(request.bead_size_mm) / 3)
        )
        unit_price = material.get("price")
        if unit_price in (None, ""):
            unit_price = sku.get("price_per_bead")
        try:
            unit_price = float(unit_price)
        except (TypeError, ValueError):
            unit_price = None
        material_id = str(sku.get("id") or material.get("id") or "")
        material_code = str(
            sku.get("material_code")
            or material.get("material_code")
            or material_id
        )
        name = str(sku.get("name") or material.get("name") or material.get("series") or "配饰")
        allowed_roles = RecommendationEngine.material_rule_values(material, "allowed_roles")
        match_rules = RecommendationEngine.material_rule_values(material, "match_rules")
        ai_profile = (
            (material.get("asset") or {}).get("ai_visual_profile")
            or ((visual.get("asset") or {}).get("ai_visual_profile"))
            or {}
        )
        recommended_usage = ai_profile.get("recommended_usage") or {}
        image_url = (
            visual.get("thumbnail_url")
            or visual.get("image_url")
            or material.get("thumbnail_url")
            or material.get("image_url")
            or ""
        )
        inferred_spacer = "spacer" in allowed_roles or RecommendationEngine.accessory_is_metal(material)
        return {
            "code": material_code,
            "name": name,
            "top": "accessory",
            "kind": "accessory",
            "role": "隔片配饰" if inferred_spacer else "点睛配饰",
            "role_key": "spacer" if inferred_spacer else "accent",
            "element": element_label(
                energy.get("primary_element")
                or material.get("primary_element")
                or material.get("element")
            ),
            "secondary_elements": unique_list(
                energy.get("secondary_elements") or material.get("secondary_elements")
            ),
            "color": visual.get("color_hex") or material.get("color") or "#B8B8B5",
            "color_families": unique_list(
                [
                    energy.get("color_family")
                    or material.get("color_family")
                    or ""
                ]
            ),
            "effects": [
                safe_display_text(value)
                for value in unique_list(energy.get("effects") or material.get("effects"))
            ],
            "reason": "用于建立节奏和视觉停顿，让珠材层次更清楚。",
            "quantity": 1,
            "bead_size_mm": request.bead_size_mm,
            "preferred_bead_size_mm": request.bead_size_mm,
            "actual_material_size_mm": size_mm or float(string_axis_width_mm),
            "string_axis_width_mm": float(string_axis_width_mm),
            "material_id": material_id,
            "source_material_id": material_id,
            "sku_id": sku.get("sku_id") or material.get("skuId") or material.get("sku_id") or "",
            "material_code": material_code,
            "unit_price": unit_price,
            "stock": material.get("stock") if material.get("stock") not in (None, "") else sku.get("stock"),
            "available": RecommendationEngine.material_is_sellable(material),
            "image_url": image_url,
            "rules": {
                "allowed_roles": allowed_roles,
                "match_rules": match_rules,
                "care_tags": RecommendationEngine.material_rule_values(material, "care_tags"),
            },
            "recommended_usage": recommended_usage,
            "material_params": material_params,
        }

    @staticmethod
    def select_accessory_items(
        *,
        request: AssessmentRequest,
        context: dict,
        bead_items: list[dict],
        limit: int = 2,
    ) -> list[dict]:
        try:
            materials, _ = RecommendationEngine.load_accessory_inventory()
        except Exception:
            return []
        selection_context = {
            **context,
            "bracelet_color_families": {
                str(color or "").strip().lower()
                for item in bead_items
                for color in unique_list(item.get("color_families"))
                if str(color or "").strip()
            },
        }
        selected_codes = {
            str(item.get("material_code") or item.get("code") or "")
            for item in bead_items
        }
        candidates = []
        for material in materials:
            code = str(material.get("material_code") or material.get("id") or "")
            allowed_roles = set(RecommendationEngine.material_rule_values(material, "allowed_roles"))
            match_rules = set(RecommendationEngine.material_rule_values(material, "match_rules"))
            is_metal = RecommendationEngine.accessory_is_metal(material)
            if code in selected_codes or (
                not (allowed_roles & {"spacer", "accent"}) and not is_metal
            ):
                continue
            if not RecommendationEngine.material_is_sellable(material):
                continue
            if not (
                material.get("image_url")
                or material.get("thumbnail_url")
                or (material.get("visual") or {}).get("thumbnail_url")
            ):
                continue
            width = (
                (material.get("material_params") or {}).get("string_axis_width_mm")
                or ((material.get("visual") or {}).get("material_params") or {}).get("string_axis_width_mm")
                or RecommendationEngine.material_size_mm(material)
            )
            try:
                width = float(width)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(width) or width <= 0 or width > max(24, request.bead_size_mm * 2.5):
                continue
            visual = material.get("visual") or {}
            ai_profile = (
                (material.get("asset") or {}).get("ai_visual_profile")
                or (visual.get("asset") or {}).get("ai_visual_profile")
                or {}
            )
            usage = ai_profile.get("recommended_usage") or {}
            try:
                count_min = int(usage.get("count_min") or 1)
                count_max = int(usage.get("count_max") or 2)
            except (TypeError, ValueError):
                count_min, count_max = 1, 2
            if count_min > 2 or count_max < 1:
                continue
            if "pair_symmetry" in match_rules and count_max < 2:
                continue
            candidates.append(material)
        ranked = sorted(
            candidates,
            key=lambda item: (
                -RecommendationEngine.accessory_score(item, selection_context),
                RecommendationEngine.material_sort_order(item),
                str(item.get("id") or ""),
            ),
        )
        result = []
        seen_codes: set[str] = set()
        for material in ranked:
            item = RecommendationEngine.build_accessory_item(material, request)
            code = item["material_code"]
            if not item["material_id"] or code in seen_codes:
                continue
            seen_codes.add(code)
            result.append(item)
            if len(result) >= limit:
                break
        return result

    @staticmethod
    def item_identity(item: dict) -> str:
        return str(
            item.get("material_id")
            or item.get("source_material_id")
            or item.get("material_code")
            or item.get("code")
            or ""
        )

    @staticmethod
    def item_layout_entry(item: dict, position: int) -> dict:
        return {
            "position": position,
            "crystal_code": item.get("code") or item.get("material_code") or "",
            "crystal_name": item.get("name") or "",
            "role": item.get("role") or "",
            "role_key": item.get("role_key") or "",
            "top": item.get("top") or "bead",
            "kind": item.get("kind") or item.get("top") or "bead",
            "color": item.get("color") or "",
            "bead_size_mm": item.get("bead_size_mm"),
            "actual_material_size_mm": item.get("actual_material_size_mm"),
            "string_axis_width_mm": item.get("string_axis_width_mm"),
            "material_params": item.get("material_params") or {},
            "physical_specs": item.get("physical_specs") or {},
            "placement_mode": item.get("placement_mode") or "",
            "preferred_bead_size_mm": item.get("preferred_bead_size_mm") or item.get("bead_size_mm"),
            "material_id": item.get("material_id", ""),
            "source_material_id": item.get("source_material_id", ""),
            "sku_id": item.get("sku_id", ""),
            "material_code": item.get("material_code") or item.get("code") or "",
        }

    @staticmethod
    def summarized_items(sequence: list[dict]) -> list[dict]:
        counts: dict[str, int] = {}
        order: list[str] = []
        samples: dict[str, dict] = {}
        for item in sequence:
            identity = RecommendationEngine.item_identity(item)
            if not identity:
                continue
            if identity not in counts:
                order.append(identity)
                samples[identity] = item
                counts[identity] = 0
            counts[identity] += 1
        return [
            {**samples[identity], "quantity": counts[identity]}
            for identity in order
        ]

    @staticmethod
    def accessory_positions(item: dict, count: int, near_primary: bool) -> list[int]:
        usage = item.get("recommended_usage") or {}
        try:
            count_max = int(usage.get("count_max") or 2)
        except (TypeError, ValueError):
            count_max = 2
        pair_required = "pair_symmetry" in set(
            RecommendationEngine.material_rule_values(item, "match_rules")
        )
        if count_max >= 2 or pair_required:
            if near_primary:
                return [1, count - 1]
            offset = max(3, count // 3)
            return [offset, count - offset]
        return [count // 2]

    @staticmethod
    def build_template_sequence(
        style: str,
        count: int,
        primary: dict,
        support: dict,
        accent: dict,
        transition: dict,
        accessories: list[dict],
    ) -> list[dict]:
        if style == "daily_minimal":
            sequence = [support for _ in range(count)]
            sequence[0] = primary
            sequence[1] = accent
            sequence[-1] = accent
            return sequence

        if style == "balanced_layers":
            sequence = [
                transition if index % 4 == 2 else support
                for index in range(count)
            ]
            sequence[0] = primary
            sequence[2] = accent
            sequence[-2] = accent
            if accessories:
                for position in RecommendationEngine.accessory_positions(
                    accessories[0],
                    count,
                    near_primary=True,
                ):
                    sequence[position] = accessories[0]
            return sequence

        if style == "signature_accent":
            sequence = [
                transition if index % 2 else support
                for index in range(count)
            ]
            sequence[0] = primary
            sequence[1] = accent
            sequence[-1] = accent
            accessory = accessories[1] if len(accessories) > 1 else (accessories[0] if accessories else None)
            if accessory:
                for position in RecommendationEngine.accessory_positions(
                    accessory,
                    count,
                    near_primary=False,
                ):
                    sequence[position] = accessory
            else:
                sequence[3] = accent
                sequence[-3] = accent
            return sequence

        midpoint = count // 2
        sequence = [
            support if index <= midpoint else transition
            for index in range(count)
        ]
        sequence[0] = primary
        quarter = max(2, count // 4)
        sequence[quarter] = accent
        sequence[count - quarter] = accent
        return sequence

    @staticmethod
    def ensure_locked_items(sequence: list[dict], locked_items: list[dict]) -> list[dict]:
        if not locked_items:
            return sequence
        result = list(sequence)
        present = {RecommendationEngine.item_identity(item) for item in result}
        used_positions: set[int] = set()
        count = len(result)
        bead_positions = [
            max(2, count // 4),
            count // 2,
            min(count - 2, count - count // 4),
        ]
        for item in locked_items:
            identity = RecommendationEngine.item_identity(item)
            if not identity or identity in present:
                continue
            positions = bead_positions
            if item.get("top") == "accessory":
                positions = RecommendationEngine.accessory_positions(item, count, near_primary=False)
            placed = False
            for position in positions:
                normalized_position = max(1, min(count - 1, int(position)))
                if normalized_position in used_positions:
                    continue
                result[normalized_position] = item
                used_positions.add(normalized_position)
                placed = True
                if item.get("top") != "accessory":
                    break
            if placed:
                present.add(identity)
        return result

    @staticmethod
    def fit_template_plan(
        *,
        style: str,
        title: str,
        subtitle: str,
        pattern: str,
        request: AssessmentRequest,
        primary: dict,
        support: dict,
        accent: dict,
        transition: dict,
        accessories: list[dict],
        locked_items: list[dict] | None = None,
    ) -> dict | None:
        best: tuple[float, int, list[dict], list[dict], list[dict], dict] | None = None
        target_cm = float(request.wrist_size_cm) + STRINGED_COMFORT_ALLOWANCE_MM / 10
        for count in range(MIN_RECOMMENDED_BEAD_COUNT, MAX_RECOMMENDED_BEAD_COUNT + 1):
            sequence = RecommendationEngine.build_template_sequence(
                style,
                count,
                primary,
                support,
                accent,
                transition,
                accessories,
            )
            sequence = RecommendationEngine.ensure_locked_items(sequence, locked_items or [])
            items = RecommendationEngine.summarized_items(sequence)
            layout = [
                RecommendationEngine.item_layout_entry(item, index + 1)
                for index, item in enumerate(sequence)
            ]
            validation = RecommendationEngine.validate_bracelet_plan(
                request,
                count,
                layout,
                items,
            )
            error = validation["estimated_stringed_length_cm"] - target_cm
            rank = (abs(error), error < 0, count, sequence, items, layout, validation)
            if best is None or rank[:3] < best[:3]:
                best = rank
        if not best:
            return None
        _, _, count, sequence, items, layout, validation = best
        if not validation["is_valid"]:
            return None
        estimated_price = round(
            sum(float(item.get("unit_price") or 0) * int(item.get("quantity") or 0) for item in items),
            2,
        )
        accessory_names = [
            item["name"]
            for item in items
            if item.get("top") == "accessory"
        ]
        material_names = [item["name"] for item in items]
        reasons = [
            f"使用{len(material_names)}种材料形成主次层次",
            f"按{request.wrist_size_cm:.1f}cm手围校准至约{validation['estimated_stringed_length_cm']:.1f}cm串长",
        ]
        if accessory_names:
            reasons.append(f"加入{'、'.join(accessory_names)}建立节奏")
        layout_signature = "|".join(
            str(item.get("material_id") or item.get("material_code") or "")
            for item in layout
        )
        layout_hash = hashlib.sha1(layout_signature.encode("utf-8")).hexdigest()[:8]
        return {
            "plan_id": f"{style}-{request.bead_size_mm}mm-{count}-{layout_hash}",
            "style": style,
            "title": title,
            "subtitle": subtitle,
            "wrist_size_cm": request.wrist_size_cm,
            "bead_size_mm": request.bead_size_mm,
            "estimated_bead_count": count,
            "pattern": pattern,
            "items": items,
            "layout": layout,
            "estimated_price": estimated_price,
            "material_variety": len(items),
            "has_accessories": bool(accessory_names),
            "accessory_names": accessory_names,
            "match_reasons": reasons,
            "estimated_stringed_length_cm": validation["estimated_stringed_length_cm"],
            "target_stringed_length_cm": validation["target_stringed_length_cm"],
            "validation": validation,
            "composer_version": BRACELET_COMPOSER_VERSION,
        }

    @staticmethod
    def compose_bracelet_plans(
        *,
        request: AssessmentRequest,
        primary: dict,
        support: dict,
        accent: dict,
        transition: dict,
        accessories: list[dict],
        palette_variants: list[dict] | None = None,
        locked_items: list[dict] | None = None,
        style_preference: str | None = None,
        accessory_preference: str = "balanced",
        rejected_plan_id: str | None = None,
    ) -> list[dict]:
        specs = [
            (
                "daily_minimal",
                "日常克制",
                "颜色集中、配饰更少，适合通勤和长期佩戴",
                "中心主石 + 对称点睛 + 同色调和",
            ),
            (
                "balanced_layers",
                "层次平衡",
                "珠材与配饰共同建立清楚的主次关系",
                "中心主石 + 对称配饰 + 双材质过渡",
            ),
            (
                "signature_accent",
                "个性点睛",
                "增加质感反差和节奏变化，视觉更有记忆点",
                "中心主石 + 节奏点睛 + 交替过渡",
            ),
            (
                "gradient_transition",
                "柔和渐变",
                "按颜色和质感分段过渡，整体变化更柔和",
                "中心主石 + 双侧点睛 + 分段渐变",
            ),
        ]
        candidates = []
        seen_layouts: set[tuple[str, ...]] = set()
        default_palette = {
            "primary": primary,
            "support": support,
            "accent": accent,
            "transition": transition,
            "accessories": accessories,
        }
        palettes = palette_variants or [default_palette]
        for variant_index, (style, title, subtitle, pattern) in enumerate(specs):
            palette = palettes[min(variant_index, len(palettes) - 1)]
            plan = RecommendationEngine.fit_template_plan(
                style=style,
                title=title,
                subtitle=subtitle,
                pattern=pattern,
                request=request,
                primary=palette["primary"],
                support=palette["support"],
                accent=palette["accent"],
                transition=palette["transition"],
                accessories=palette["accessories"],
                locked_items=locked_items,
            )
            if not plan:
                continue
            if rejected_plan_id and plan.get("plan_id") == rejected_plan_id:
                continue
            signature = tuple(
                str(item.get("material_id") or item.get("material_code") or "")
                for item in plan["layout"]
            )
            if signature in seen_layouts:
                continue
            seen_layouts.add(signature)
            candidates.append(plan)
        if style_preference == "minimal" or accessory_preference == "less":
            preferred_styles = ["daily_minimal", "gradient_transition", "balanced_layers"]
        elif style_preference == "layered" or accessory_preference == "more":
            preferred_styles = ["signature_accent", "balanced_layers", "gradient_transition"]
        else:
            preferred_styles = (
                ["daily_minimal", "balanced_layers", "signature_accent"]
                if accessories
                else ["daily_minimal", "balanced_layers", "gradient_transition"]
            )
        by_style = {plan["style"]: plan for plan in candidates}
        selected = [by_style[style] for style in preferred_styles if style in by_style]
        if len(selected) < 3:
            selected.extend(
                plan
                for plan in candidates
                if plan not in selected
            )
        return selected[:3]

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
        role_key = {
            "主石": "primary",
            "调和配珠": "support",
            "过渡配珠": "support",
            "点睛配珠": "accent",
        }.get(role, "support")
        return {
            "code": code,
            "name": crystal["name"],
            "top": "bead",
            "kind": "bead",
            "role": role,
            "role_key": role_key,
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
    def recommendation_size_tolerance_mm(bead_size_mm: int) -> float:
        """Permit adjacent commercial sizes without making a mixed-size bracelet."""
        target = float(bead_size_mm or 0)
        if target <= 10:
            return 1.0
        if target <= 14:
            return 1.5
        return 2.0

    @staticmethod
    def material_matches_recommendation_size(material: dict, bead_size_mm: int) -> bool:
        target_size = float(bead_size_mm or 0)
        size = RecommendationEngine.material_size_mm(material)
        return bool(
            target_size
            and size
            and abs(size - target_size)
            <= RecommendationEngine.recommendation_size_tolerance_mm(bead_size_mm)
        )

    @staticmethod
    def load_bead_inventory() -> tuple[list[dict], bool]:
        from .materials import MATERIAL_CATALOG, list_db_materials

        db_materials = list_db_materials(top="bead", enrich=False)
        if db_materials:
            return db_materials, True
        if os.getenv("APP_ENV", "").strip().lower() in {"production", "prod"}:
            return [], db_materials is not None
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
        suitable_materials = [
            item
            for item in materials
            if RecommendationEngine.material_matches_recommendation_size(item, bead_size_mm)
            and RecommendationEngine.material_is_sellable(item)
        ]
        for code, crystal in catalog.items():
            if any(RecommendationEngine.material_matches_catalog_entry(item, code, crystal) for item in suitable_materials):
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
            candidates = [
                item
                for item in candidates
                if RecommendationEngine.material_matches_recommendation_size(item, bead_size_mm)
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
