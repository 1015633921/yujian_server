from __future__ import annotations

from .energy import ELEMENTS, WISH_MAPPING
from .material_knowledge import (
    build_primary_pools,
    build_recommendation_catalog,
    crystal_elements,
    merge_taxonomy,
    unique_list,
)
from .schemas import AssessmentRequest

CRYSTAL_CATALOG = {
    "titanium_quartz": {
        "name": "钛晶", "element": "金", "secondary_elements": ["土"], "color": "#C99A2E",
        "effects": ["聚财", "行动力", "事业突破"],
    },
    "citrine": {
        "name": "黄水晶", "element": "土", "secondary_elements": ["金"], "color": "#E4B83F",
        "effects": ["财富流动", "自信", "目标感"],
    },
    "gold_rutilated_quartz": {
        "name": "金发晶", "element": "金", "secondary_elements": ["火"], "color": "#D4A62A",
        "effects": ["决断", "贵人运", "事业能量"],
    },
    "rhodochrosite": {
        "name": "红纹石", "element": "火", "secondary_elements": ["木"], "color": "#D85A72",
        "effects": ["正缘", "自我接纳", "情感流动"],
    },
    "strawberry_quartz": {
        "name": "草莓晶", "element": "火", "secondary_elements": ["木"], "color": "#E77C8E",
        "effects": ["人缘", "魅力", "温柔表达"],
    },
    "rose_quartz": {
        "name": "粉晶", "element": "木", "secondary_elements": ["火"], "color": "#ECA8B7",
        "effects": ["桃花", "关系修复", "柔和"],
    },
    "blue_rutilated_quartz": {
        "name": "蓝发晶", "element": "水", "secondary_elements": ["金"], "color": "#4F789B",
        "effects": ["冷静", "洞察", "边界感"],
    },
    "obsidian": {
        "name": "黑曜石", "element": "水", "secondary_elements": ["金"], "color": "#23252A",
        "effects": ["辟邪", "防护", "稳定"],
    },
    "black_rutilated_quartz": {
        "name": "黑发晶", "element": "金", "secondary_elements": ["水"], "color": "#34343A",
        "effects": ["防小人", "清理杂念", "坚定"],
    },
    "green_phantom": {
        "name": "绿幽灵", "element": "木", "secondary_elements": ["土"], "color": "#4A825F",
        "effects": ["健康", "生长", "专注"],
    },
    "clear_quartz": {
        "name": "白水晶", "element": "金", "secondary_elements": ["土"], "color": "#E8EDF0",
        "effects": ["净化", "专注", "能量放大"],
    },
    "aquamarine": {
        "name": "海蓝宝", "element": "水", "secondary_elements": [], "color": "#75B8D1",
        "effects": ["平静", "表达", "舒缓焦虑"],
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
        "effects": ["决断", "稳定", "事业守护"],
    },
    "rhodonite": {
        "name": "蔷薇辉石", "element": "火", "secondary_elements": ["木", "土"], "color": "#C86A78",
        "effects": ["关系修复", "边界", "温柔坚定"],
    },
    "prehnite": {
        "name": "葡萄石", "element": "木", "secondary_elements": ["水"], "color": "#B6D89B",
        "effects": ["疗愈", "松弛", "心轮滋养"],
    },
    "green_aventurine": {
        "name": "绿东陵", "element": "木", "secondary_elements": ["土"], "color": "#6FA56B",
        "effects": ["成长", "稳定", "舒心"],
    },
    "malachite": {
        "name": "孔雀石", "element": "木", "secondary_elements": ["土"], "color": "#1F7B4A",
        "effects": ["保护", "修复", "边界"],
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
        "effects": ["灵感", "安静", "净化"],
    },
    "moonstone": {
        "name": "月光石", "element": "水", "secondary_elements": ["金"], "color": "#E5E5D9",
        "effects": ["修复", "柔软", "安静"],
    },
    "labradorite": {
        "name": "拉长石", "element": "水", "secondary_elements": ["金"], "color": "#596B74",
        "effects": ["直觉", "保护", "洞察"],
    },
    "lepidolite": {
        "name": "锂云母", "element": "水", "secondary_elements": ["金"], "color": "#B99AC7",
        "effects": ["安静", "修复", "松弛"],
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
        return build_primary_pools(PRIMARY_POOLS, catalog or RecommendationEngine.catalog())

    def recommend(self, request: AssessmentRequest, energy: dict) -> dict:
        final = energy["final"]
        primary_wish = request.primary_core_wish
        context = self.recommendation_context(request, energy)
        useful_elements = [element for element in energy.get("useful_elements", []) if element in ELEMENTS]
        catalog = self.catalog()
        primary_pools = self.primary_pools(catalog)
        primary_code = self.select_primary(request, energy, context, catalog, primary_pools)
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
        )
        bead_count = max(12, min(28, round(request.wrist_size_cm * 10 / request.bead_size_mm)))
        primary_quantity = 1
        accent_quantity = 2
        support_quantity = bead_count - primary_quantity - accent_quantity

        primary = self.build_item(
            primary_code,
            role="主石",
            quantity=primary_quantity,
            bead_size_mm=request.bead_size_mm + 2,
            reason=f"你的首要愿望是“{primary_wish}”，主石优先承接这份当下诉求。",
            catalog=catalog,
        )
        supporting = [
            self.build_item(
                support_codes[0],
                role="调和配珠",
                quantity=support_quantity,
                bead_size_mm=request.bead_size_mm,
                reason=f"结合日主喜用与当前状态，本次配珠优先照看{support_element}，用于{ELEMENT_LANGUAGE[support_element]}。",
                catalog=catalog,
            ),
            self.build_item(
                support_codes[1],
                role="点睛配珠",
                quantity=accent_quantity,
                bead_size_mm=max(4, request.bead_size_mm - 2),
                reason="作为两侧点睛珠，帮助主石与调和配珠之间形成更柔和的能量过渡。",
                catalog=catalog,
            ),
        ]
        layout = self.build_layout(bead_count, primary, supporting)
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
            },
            "copy": self.build_copy(request, energy, primary, supporting[0], support_element),
        }

    @staticmethod
    def recommendation_context(request: AssessmentRequest, energy: dict) -> dict:
        chakra = energy.get("chakra_analysis") or {}
        mood = energy.get("mood_analysis") or {}
        return {
            "useful_elements": set(energy.get("useful_elements") or []),
            "wish_elements": set(WISH_MAPPING[request.primary_core_wish]),
            "wish_tags": {request.primary_core_wish, *request.core_wishes},
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
    ) -> str:
        pool = set(primary_pools[request.primary_core_wish])
        return max(
            catalog,
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
    ) -> list[str]:
        support_candidates = [
            code
            for code, crystal in catalog.items()
            if code != primary_code
            and not (crystal_elements(code, crystal) & excluded)
            and RecommendationEngine.role_allowed(crystal, "support")
            and "avoid_dense" not in RecommendationEngine.rule_list(crystal, "match_rules")
            and not RecommendationEngine.conflicts_with(code, crystal, {primary_code}, catalog)
        ]
        if not support_candidates:
            support_candidates = [
                code
                for code, crystal in catalog.items()
                if code != primary_code
                and RecommendationEngine.role_allowed(crystal, "support")
                and not RecommendationEngine.conflicts_with(code, crystal, {primary_code}, catalog)
            ]
        if not support_candidates:
            support_candidates = [code for code in catalog if code != primary_code]
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
        if not accent_candidates:
            accent_candidates = [
                code
                for code, crystal in catalog.items()
                if code not in {primary_code, first}
                and not RecommendationEngine.conflicts_with(code, crystal, {primary_code, first}, catalog)
            ]
        if not accent_candidates:
            accent_candidates = [code for code in catalog if code not in {primary_code, first}]
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
        score += 18 if target_element and target_element in elements else 0
        score += 18 if request.primary_core_wish in taxonomy.get("wish_tags", []) else 0
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
        score += float((energy.get("final") or {}).get(crystal["element"], 0)) / 20
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
            "effects": unique_list(crystal.get("effects")),
            "reason": reason,
            "quantity": quantity,
            "bead_size_mm": bead_size_mm,
            "image_url": (crystal.get("asset") or {}).get("thumbnail_url", ""),
            "rules": {
                "allowed_roles": unique_list(crystal.get("allowed_roles")),
                "conflict_codes": unique_list(crystal.get("conflict_codes")),
                "match_rules": unique_list(crystal.get("match_rules")),
                "care_tags": unique_list(crystal.get("care_tags")),
            },
            "material_params": crystal.get("material_params") or {},
        }

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
        strategy = energy.get("recommendation_strategy") or "以五行平衡为基础做温柔调和。"
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
            f"{request.name}，你的五行画像中{strongest}能量最为鲜明，{strategy}"
            f"以{primary['name']}作为手串主石，"
            f"承接“{'、'.join(request.core_wishes)}”的核心愿望；再用{supporting['name']}调和{support_element}能量，"
            f"让你原本的优势不被削弱，也为当下需要生长的部分留出空间。"
            f"{live_state}"
        )


def interpretation(final: dict[str, float], strongest: str, weakest: str) -> dict:
    average = sum(final.values()) / len(final)
    balance = round(max(0, 100 - (max(final.values()) - min(final.values())) * 3), 1)
    return {
        "headline": f"{strongest}能量主导，{weakest}能量需要温柔补足",
        "strongest": f"{strongest}代表你当前最自然、最容易调用的力量。",
        "weakest": f"{weakest}并非缺点，而是适合通过配珠与日常习惯慢慢调和的方向。",
        "balance_index": balance,
        "average_score": round(average, 2),
    }
