from __future__ import annotations

from .energy import ELEMENTS, WISH_MAPPING
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
}

PRIMARY_POOLS = {
    "招财进宝/事业腾飞": ["titanium_quartz", "citrine", "gold_rutilated_quartz"],
    "正缘桃花/人际和合": ["rhodochrosite", "strawberry_quartz", "rose_quartz"],
    "辟邪防小人/消除焦虑": ["blue_rutilated_quartz", "obsidian", "black_rutilated_quartz"],
    "健康护身/保持专注": ["green_phantom", "clear_quartz"],
}

SUPPORTING_BY_ELEMENT = {
    "金": ["hematite", "clear_quartz"],
    "木": ["turquoise", "green_phantom"],
    "水": ["aquamarine", "blue_rutilated_quartz"],
    "火": ["garnet", "strawberry_quartz"],
    "土": ["smoky_quartz", "citrine"],
}

ELEMENT_LANGUAGE = {
    "金": "建立边界与清晰决断",
    "木": "唤醒生长感与持续行动",
    "水": "安定情绪并恢复内在流动",
    "火": "点亮表达、热情与吸引力",
    "土": "增强稳定、承接与落地能力",
}


class RecommendationEngine:
    def recommend(self, request: AssessmentRequest, energy: dict) -> dict:
        final = energy["final"]
        primary_wish = request.primary_core_wish
        primary_code = self.select_primary(primary_wish, final)
        primary_data = CRYSTAL_CATALOG[primary_code]
        excluded = {primary_data["element"], *primary_data["secondary_elements"]}
        candidate_elements = [element for element in ELEMENTS if element not in excluded]
        weakest_available = min(candidate_elements, key=lambda element: final[element])
        support_codes = self.select_supporting(weakest_available, excluded, primary_code)
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
        )
        supporting = [
            self.build_item(
                support_codes[0],
                role="调和配珠",
                quantity=support_quantity,
                bead_size_mm=request.bead_size_mm,
                reason=f"排除主石五行后，你最需要补足的是{weakest_available}，用于{ELEMENT_LANGUAGE[weakest_available]}。",
            ),
            self.build_item(
                support_codes[1],
                role="点睛配珠",
                quantity=accent_quantity,
                bead_size_mm=max(4, request.bead_size_mm - 2),
                reason="作为两侧点睛珠，帮助主石与调和配珠之间形成更柔和的能量过渡。",
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
            "copy": self.build_copy(request, energy, primary, supporting[0], weakest_available),
        }

    @staticmethod
    def select_primary(core_wish: str, final: dict[str, float]) -> str:
        pool = PRIMARY_POOLS[core_wish]
        wish_elements = WISH_MAPPING[core_wish]
        return max(
            pool,
            key=lambda code: (
                final[CRYSTAL_CATALOG[code]["element"]] if CRYSTAL_CATALOG[code]["element"] in wish_elements else 0,
                -pool.index(code),
            ),
        )

    @staticmethod
    def select_supporting(weakest: str, excluded: set[str], primary_code: str) -> list[str]:
        first = next(code for code in SUPPORTING_BY_ELEMENT[weakest] if code != primary_code)
        accent_candidates = [
            code
            for element in ELEMENTS
            for code in SUPPORTING_BY_ELEMENT[element]
            if code not in {first, primary_code} and CRYSTAL_CATALOG[code]["element"] not in excluded
        ]
        return [first, accent_candidates[0] if accent_candidates else first]

    @staticmethod
    def build_item(code: str, role: str, quantity: int, bead_size_mm: int, reason: str) -> dict:
        crystal = CRYSTAL_CATALOG[code]
        return {
            "code": code,
            "name": crystal["name"],
            "role": role,
            "element": crystal["element"],
            "secondary_elements": crystal["secondary_elements"],
            "color": crystal["color"],
            "effects": crystal["effects"],
            "reason": reason,
            "quantity": quantity,
            "bead_size_mm": bead_size_mm,
            "image_url": "",
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
        weakest_available: str,
    ) -> str:
        strongest = energy["strongest"]
        return (
            f"{request.name}，你的五行画像中{strongest}能量最为鲜明，而在避开主石属性后，"
            f"{weakest_available}是此刻最值得温柔补足的一环。以{primary['name']}作为手串主石，"
            f"承接“{'、'.join(request.core_wishes)}”的核心愿望；再用{supporting['name']}调和{weakest_available}能量，"
            f"让你原本的优势不被削弱，也为当下需要生长的部分留出空间。"
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
