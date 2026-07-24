from datetime import date, time
import math

import pytest

from app.energy import ELEMENTS, ENERGY_WEIGHTS, EnergyCalculator
from app.copy_safety import safe_display_text
from app.material_knowledge import crystal_elements
from app.recommendation import CORE_WISH_TAGS, RecommendationEngine
from app.schemas import AssessmentRequest


def make_request(**overrides) -> AssessmentRequest:
    payload = {
        "user_id": "wx-test-user",
        "name": "林安",
        "birthday": "1995-08-16",
        "birth_time": "09:30",
        "birth_place": "四川省成都市",
        "mbti": "infj",
        "core_wish": "健康护身/保持专注",
        "wrist_size_cm": 15.5,
        "bead_size_mm": 8,
    }
    payload.update(overrides)
    return AssessmentRequest(**payload)


def test_energy_profile_totals_exactly_100():
    result = EnergyCalculator().calculate(make_request())

    assert round(sum(result["final"].values()), 2) == 100
    assert round(sum(result["breakdown"]["bazi"].values()), 2) == ENERGY_WEIGHTS["bazi"]
    assert round(sum(result["breakdown"]["wish"].values()), 2) == ENERGY_WEIGHTS["wish"]
    assert round(sum(result["breakdown"]["name"].values()), 2) == ENERGY_WEIGHTS["name"]
    assert round(sum(result["breakdown"]["mbti"].values()), 2) == ENERGY_WEIGHTS["mbti"]
    assert round(sum(result["breakdown"]["chakra"].values()), 2) == ENERGY_WEIGHTS["chakra"]
    assert round(sum(result["breakdown"]["mood"].values()), 2) == ENERGY_WEIGHTS["mood"]
    assert result["mbti_analysis"]["selected"] is True
    assert result["mbti_analysis"]["type"] == "INFJ"
    assert result["mbti_analysis"]["weight"] == ENERGY_WEIGHTS["mbti"]
    assert result["mbti_analysis"]["top_elements"] == ["水", "木"]
    assert result["mbti_analysis"]["keywords"] == ["安静聚焦", "灵感探索", "柔和共情", "计划有序"]


def test_optional_mbti_uses_neutral_profile():
    result = EnergyCalculator().calculate(make_request(mbti=None))

    assert result["breakdown"]["mbti"] == {"金": 1.6, "木": 1.6, "水": 1.6, "火": 1.6, "土": 1.6}
    assert result["mbti_analysis"]["selected"] is False
    assert result["mbti_analysis"]["top_elements"] == []
    assert round(sum(result["final"].values()), 2) == 100


def test_mbti_adds_a_small_explicit_material_preference_score():
    request = make_request(mbti="INTJ")
    energy = EnergyCalculator().calculate(request)
    context = {
        "useful_elements": set(),
        "wish_elements": set(),
        "mbti_elements": {"水"},
        "wish_tags": set(),
        "chakras": set(),
        "color_families": set(),
        "mood_tags": set(),
        "visual_tags": set(),
    }
    catalog = {
        "water_stone": {"name": "水系材质", "element": "水", "secondary_elements": [], "color": "#fff", "effects": []},
        "wood_stone": {"name": "木系材质", "element": "木", "secondary_elements": [], "color": "#fff", "effects": []},
    }
    pools = {request.primary_core_wish: []}

    water_score = RecommendationEngine.score_crystal(
        "water_stone", request, {**energy, "final": {}}, context, "support", catalog=catalog, primary_pools=pools
    )
    wood_score = RecommendationEngine.score_crystal(
        "wood_stone", request, {**energy, "final": {}}, context, "support", catalog=catalog, primary_pools=pools
    )

    assert water_score - wood_score == 4


def test_three_wishes_share_the_same_20_point_weight():
    result = EnergyCalculator().calculate(
        make_request(
            core_wish=None,
            core_wishes=[
                "招财进宝/事业腾飞",
                "正缘桃花/人际和合",
                "辟邪防小人/消除焦虑",
            ],
        )
    )

    assert round(sum(result["breakdown"]["wish"].values()), 2) == ENERGY_WEIGHTS["wish"]


def test_lunar_python_bazi_basis_is_returned():
    result = EnergyCalculator().calculate(make_request())

    assert result["bazi_basis"]["pillars"]["year"]
    assert result["bazi_basis"]["day_master"]
    assert result["bazi_basis"]["day_master_strength"] in {"身强", "身弱", "中和"}
    assert result["useful_elements"]


def test_chakra_and_mood_inputs_affect_dynamic_breakdown():
    result = EnergyCalculator().calculate(
        make_request(
            chakra_answers=["state_expression", "need_clarity"],
            mood_palette_id="sea_salt_blue",
        )
    )

    assert result["chakra_analysis"]["primary_chakra"] == "throat"
    assert result["mood_analysis"]["palette_id"] == "sea_salt_blue"
    assert result["breakdown"]["chakra"]["水"] > result["breakdown"]["chakra"]["火"]
    assert "blue" in result["chakra_analysis"]["color_families"]
    assert "通透" in result["mood_analysis"]["visual_tags"]


def test_true_solar_time_uses_chengdu_longitude():
    result = EnergyCalculator().calculate(make_request())

    assert result["solar_time"]["longitude"] == 104.0665
    assert result["solar_time"]["location_source"] == "built_in_place_lookup"
    assert result["solar_time"]["total_correction_minutes"] < 0


def test_true_solar_time_uses_lanzhou_longitude():
    result = EnergyCalculator().calculate(make_request(birth_place="兰州"))

    assert result["solar_time"]["longitude"] == 103.8343
    assert result["solar_time"]["location_source"] == "built_in_place_lookup"


def test_recommendation_primary_follows_wish_and_support_avoids_primary_elements():
    request = make_request(core_wish="招财进宝/事业腾飞")
    energy = EnergyCalculator().calculate(request)
    recommendation = RecommendationEngine().recommend(request, energy)
    primary = recommendation["primary"]

    catalog = RecommendationEngine.catalog()
    primary_tags = set(catalog[primary["code"]].get("wish_pools") or [])
    assert primary["code"] in RecommendationEngine.primary_pools(catalog)[request.primary_core_wish]
    assert primary_tags & CORE_WISH_TAGS[request.primary_core_wish]
    assert primary["element"] in ELEMENTS
    excluded = {primary["element"], *primary["secondary_elements"]}
    assert recommendation["supporting"][0]["element"] not in excluded
    assert len(recommendation["bracelet_plan"]["layout"]) == recommendation["bracelet_plan"]["estimated_bead_count"]


def test_material_knowledge_keys_are_normalized_before_recommendation_scoring():
    request = make_request(core_wish="招财进宝/事业腾飞")
    energy = EnergyCalculator().calculate(request)
    context = RecommendationEngine.recommendation_context(request, energy)
    catalog = {
        "citrine": {
            "name": "黄水晶",
            "element": "earth",
            "secondary_elements": ["metal", "fire"],
            "color": "#E4B83F",
            "effects": ["财富与行动"],
            "wish_pools": ["wealth", "career"],
        },
        "green_phantom": {
            "name": "绿幽灵",
            "element": "wood",
            "secondary_elements": ["earth"],
            "color": "#4A825F",
            "effects": ["生长与专注"],
            "wish_pools": ["career", "wealth", "focus"],
            "match_rules": ["best_as_primary"],
        },
    }
    pools = RecommendationEngine.primary_pools(catalog)

    citrine_score = RecommendationEngine.score_crystal(
        "citrine", request, energy, context, "primary", catalog=catalog, primary_pools=pools
    )
    green_score = RecommendationEngine.score_crystal(
        "green_phantom", request, energy, context, "primary", catalog=catalog, primary_pools=pools
    )

    assert {"金", "土", "火"}.issuperset(crystal_elements("citrine", catalog["citrine"]))
    assert {"wealth", "career"}.issubset(context["wish_tags"])
    assert citrine_score > green_score


def test_recommendation_uses_preferred_bead_size_in_items_and_layout():
    request = make_request(bead_size_mm=10)
    energy = EnergyCalculator().calculate(request)
    recommendation = RecommendationEngine().recommend(request, energy)

    plan = recommendation["bracelet_plan"]

    assert plan["bead_size_mm"] == 10
    assert recommendation["primary"]["bead_size_mm"] == 10
    assert all(item["bead_size_mm"] == 10 for item in recommendation["supporting"])
    assert {item["bead_size_mm"] for item in plan["items"]} == {10}
    assert {item["bead_size_mm"] for item in plan["layout"]} == {10}
    assert {
        item["actual_material_size_mm"]
        for item in plan["items"]
        if item.get("top") == "bead"
    } == {10}
    assert all(
        float(item["string_axis_width_mm"]) > 0
        for item in plan["items"]
        if item.get("top") == "accessory"
    )
    assert all(item["material_id"] for item in plan["items"])


def test_stringed_bead_count_accounts_for_closed_bracelet_loss():
    assert RecommendationEngine.estimate_stringed_bead_count(15.5, 8) == 23
    assert RecommendationEngine.estimate_stringed_bead_count(16, 10) == 20


def test_round_bead_inner_circumference_uses_closed_ring_geometry():
    twenty_beads = RecommendationEngine.estimate_stringed_length_mm([8] * 20)
    twenty_two_beads = RecommendationEngine.estimate_stringed_length_mm([8] * 22)
    analytical = math.pi * 8 * (1 / math.sin(math.pi / 22) - 1)

    assert twenty_beads == pytest.approx(135.53, abs=0.01)
    assert twenty_two_beads == pytest.approx(151.47, abs=0.01)
    assert twenty_two_beads == pytest.approx(analytical, abs=1e-8)


def test_mixed_bead_inner_circumference_is_rotation_invariant():
    sizes = [8, 8, 10, 8, 12, 8, 10, 8, 8, 8, 10, 8]

    assert RecommendationEngine.estimate_stringed_length_mm(sizes) == pytest.approx(
        RecommendationEngine.estimate_stringed_length_mm(sizes[4:] + sizes[:4]),
        abs=1e-8,
    )


def test_recommendation_plan_passes_all_hard_constraints_for_16cm_8mm():
    request = make_request(wrist_size_cm=16, bead_size_mm=8)
    energy = EnergyCalculator().calculate(request)
    plan = RecommendationEngine().recommend(request, energy)["bracelet_plan"]

    assert 12 <= plan["estimated_bead_count"] <= 40
    assert plan["target_stringed_length_cm"] == 16.8
    assert abs(plan["estimated_stringed_length_cm"] - 16.8) <= 0.5
    assert plan["validation"]["is_valid"] is True
    assert all(check["passed"] for check in plan["validation"]["checks"])
    assert all(item["available"] for item in plan["items"])
    assert all(item["unit_price"] is not None for item in plan["items"])


def test_recommendation_plan_fits_14_5cm_wrist_instead_of_under_sizing():
    request = make_request(wrist_size_cm=14.5, bead_size_mm=8)
    energy = EnergyCalculator().calculate(request)
    plan = RecommendationEngine().recommend(request, energy)["bracelet_plan"]

    assert plan["target_stringed_length_cm"] == 15.3
    assert plan["estimated_stringed_length_cm"] >= 14.8
    assert plan["validation"]["is_valid"] is True


def test_recommendation_returns_three_distinct_editable_design_directions():
    request = make_request(wrist_size_cm=16, bead_size_mm=8)
    energy = EnergyCalculator().calculate(request)
    recommendation = RecommendationEngine().recommend(request, energy)
    plans = recommendation["bracelet_plans"]

    assert len(plans) == 3
    assert {plan["style"] for plan in plans} == {
        "daily_minimal",
        "balanced_layers",
        "signature_accent",
    }
    assert len(
        {
            tuple(item["material_id"] for item in plan["layout"])
            for plan in plans
        }
    ) == 3
    assert all(plan["validation"]["is_valid"] for plan in plans)
    assert all(plan["material_variety"] >= 3 for plan in plans)
    assert sum(bool(plan["is_recommended"]) for plan in plans) == 1
    assert recommendation["bracelet_plan"]["plan_id"] == next(
        plan["plan_id"] for plan in plans if plan["is_recommended"]
    )


def test_at_least_one_recommendation_uses_sellable_symmetric_accessories():
    request = make_request(wrist_size_cm=16, bead_size_mm=8)
    energy = EnergyCalculator().calculate(request)
    plans = RecommendationEngine().recommend(request, energy)["bracelet_plans"]
    accessory_plans = [plan for plan in plans if plan["has_accessories"]]

    assert accessory_plans
    for plan in accessory_plans:
        accessories = [item for item in plan["items"] if item.get("top") == "accessory"]
        assert accessories
        assert all(item["available"] for item in accessories)
        assert all(int(item["stock"]) >= int(item["quantity"]) for item in accessories)
        assert all(
            int(item["quantity"]) % 2 == 0
            for item in accessories
            if "pair_symmetry" in set((item.get("rules") or {}).get("match_rules") or [])
        )


def test_accessory_selection_prefers_metal_tone_that_matches_bead_palette(monkeypatch):
    materials = [
        {
            "id": "crystal-shape",
            "material_code": "crystal-shape",
            "name": "幽灵三角牌",
            "category": "异形件",
            "top": "accessory",
            "allowed_roles": ["spacer", "accent"],
            "match_rules": ["spacer_only"],
            "enabled": True,
            "stock": 20,
            "price": 12,
            "image_url": "https://example.com/crystal.webp",
            "size": 16,
            "sort_order": 1,
        },
        {
            "id": "silver-spacer",
            "material_code": "silver-spacer",
            "name": "亮银圆珠隔珠",
            "category": "隔珠",
            "top": "accessory",
            "allowed_roles": ["spacer", "accent"],
            "match_rules": ["spacer_only"],
            "enabled": True,
            "stock": 20,
            "price": 6,
            "image_url": "https://example.com/metal.webp",
            "size": 8,
            "sort_order": 2,
        },
        {
            "id": "gold-spacer",
            "material_code": "gold-spacer",
            "name": "亮金圆珠隔珠",
            "category": "隔珠",
            "top": "accessory",
            "allowed_roles": ["spacer", "accent"],
            "match_rules": ["spacer_only"],
            "enabled": True,
            "stock": 20,
            "price": 6,
            "image_url": "https://example.com/gold.webp",
            "size": 8,
            "sort_order": 99,
        },
    ]
    monkeypatch.setattr(
        RecommendationEngine,
        "load_accessory_inventory",
        staticmethod(lambda: (materials, True)),
    )

    selected = RecommendationEngine.select_accessory_items(
        request=make_request(wrist_size_cm=16, bead_size_mm=8),
        context={"color_families": set(), "mood_tags": set(), "visual_tags": set()},
        bead_items=[{"material_code": "citrine", "color_families": ["gold", "yellow", "clear"]}],
    )

    assert selected[0]["material_id"] == "gold-spacer"
    assert any(item["material_id"] == "crystal-shape" for item in selected)


def test_accessory_selection_does_not_force_mismatched_metal(monkeypatch):
    materials = [
        {
            "id": "blue-crystal-shape",
            "material_code": "blue-crystal-shape",
            "name": "海蓝宝随形横通",
            "category": "异形件",
            "top": "accessory",
            "allowed_roles": ["spacer", "accent"],
            "match_rules": ["pair_symmetry"],
            "color_family": "blue",
            "enabled": True,
            "stock": 20,
            "price": 12,
            "image_url": "https://example.com/crystal.webp",
            "size": 12,
            "sort_order": 1,
        },
        {
            "id": "gold-spacer",
            "material_code": "gold-spacer",
            "name": "亮金圆珠隔珠",
            "category": "隔珠",
            "top": "accessory",
            "allowed_roles": ["spacer"],
            "match_rules": ["spacer_only"],
            "enabled": True,
            "stock": 20,
            "price": 6,
            "image_url": "https://example.com/gold.webp",
            "size": 8,
            "sort_order": 2,
        },
    ]
    monkeypatch.setattr(
        RecommendationEngine,
        "load_accessory_inventory",
        staticmethod(lambda: (materials, True)),
    )

    selected = RecommendationEngine.select_accessory_items(
        request=make_request(wrist_size_cm=16, bead_size_mm=8),
        context={"color_families": {"blue"}, "mood_tags": set(), "visual_tags": set()},
        bead_items=[{"material_code": "aquamarine", "color_families": ["blue", "white", "clear"]}],
        limit=1,
    )

    assert selected[0]["material_id"] == "blue-crystal-shape"


def test_user_facing_copy_safety_removes_health_and_chakra_claim_terms():
    text = safe_display_text("海底轮助眠功效可改善睡眠并缓解焦虑")

    assert "海底轮" not in text
    assert "助眠" not in text
    assert "功效" not in text
    assert "改善睡眠" not in text
    assert "缓解焦虑" not in text


def test_explicit_out_of_stock_material_is_not_sellable():
    assert RecommendationEngine.material_is_sellable(
        {"id": "sold-out", "enabled": True, "stock": 99, "stock_status": "out", "price": 10}
    ) is False


@pytest.mark.parametrize(
    "material",
    [
        {"id": "disabled-int", "enabled": 0, "stock": 99, "price": 10},
        {"id": "zero-stock", "enabled": 1, "stock": 0, "price": 10},
        {"id": "zero-price", "enabled": 1, "stock": 99, "price": 0},
    ],
)
def test_disabled_or_unavailable_material_is_not_sellable(material):
    assert RecommendationEngine.material_is_sellable(material) is False


def test_recommendation_fails_closed_when_no_catalog_code_is_sellable():
    request = make_request()
    energy = EnergyCalculator().calculate(request)
    catalog = RecommendationEngine.catalog()

    with pytest.raises(ValueError, match="可售材料"):
        RecommendationEngine.select_primary(
            request,
            energy,
            RecommendationEngine.recommendation_context(request, energy),
            catalog,
            RecommendationEngine.primary_pools(catalog),
            available_codes=set(),
        )


def test_production_inventory_does_not_use_static_materials(monkeypatch):
    from app import materials as materials_module

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(materials_module, "list_db_materials", lambda **_kwargs: None)

    materials, from_database = RecommendationEngine.load_bead_inventory()

    assert materials == []
    assert from_database is False


def test_recommendation_respects_material_role_rules_for_primary():
    request = make_request(core_wish="招财进宝/事业腾飞")
    energy = EnergyCalculator().calculate(request)
    context = RecommendationEngine.recommendation_context(request, energy)
    catalog = {
        "accent_only_stone": {
            "name": "点缀石",
            "element": "金",
            "secondary_elements": [],
            "color": "#ffffff",
            "effects": ["招财"],
            "allowed_roles": ["accent"],
            "match_rules": ["accent_only"],
        },
        "valid_primary_stone": {
            "name": "主石",
            "element": "土",
            "secondary_elements": [],
            "color": "#f0e0c0",
            "effects": ["事业"],
            "allowed_roles": ["primary", "support"],
            "match_rules": ["best_as_primary"],
        },
    }
    primary_pools = {request.primary_core_wish: ["accent_only_stone", "valid_primary_stone"]}

    selected = RecommendationEngine.select_primary(request, energy, context, catalog, primary_pools)

    assert selected == "valid_primary_stone"


def test_recommendation_filters_conflict_and_dense_support_rules():
    request = make_request(core_wish="招财进宝/事业腾飞")
    energy = EnergyCalculator().calculate(request)
    context = RecommendationEngine.recommendation_context(request, energy)
    catalog = {
        "primary_stone": {
            "name": "主石",
            "element": "金",
            "secondary_elements": [],
            "color": "#ffffff",
            "effects": ["事业"],
            "allowed_roles": ["primary"],
            "match_rules": ["best_as_primary"],
        },
        "conflict_support": {
            "name": "互斥辅石",
            "element": "水",
            "secondary_elements": [],
            "color": "#88bbff",
            "effects": ["沟通"],
            "allowed_roles": ["support"],
            "conflict_codes": ["primary_stone"],
        },
        "dense_support": {
            "name": "高密度辅石",
            "element": "水",
            "secondary_elements": [],
            "color": "#88bbff",
            "effects": ["沟通"],
            "allowed_roles": ["support"],
            "match_rules": ["avoid_dense"],
        },
        "valid_support": {
            "name": "普通辅石",
            "element": "水",
            "secondary_elements": [],
            "color": "#88bbff",
            "effects": ["沟通"],
            "allowed_roles": ["support"],
            "match_rules": ["best_as_support"],
        },
        "accent_stone": {
            "name": "点睛石",
            "element": "土",
            "secondary_elements": [],
            "color": "#dddddd",
            "effects": ["稳定"],
            "allowed_roles": ["accent"],
            "match_rules": ["accent_only", "pair_symmetry"],
        },
    }
    primary_pools = {request.primary_core_wish: ["primary_stone"]}

    support, accent = RecommendationEngine.select_supporting(
        "水",
        {"金"},
        "primary_stone",
        request,
        energy,
        context,
        catalog,
        primary_pools,
    )

    assert support == "valid_support"
    assert accent == "accent_stone"


def test_support_fallback_keeps_available_materials_when_secondary_elements_overlap():
    request = make_request(core_wish="招财进宝/事业腾飞")
    energy = EnergyCalculator().calculate(request)
    context = RecommendationEngine.recommendation_context(request, energy)
    catalog = {
        "primary_stone": {
            "name": "主石",
            "element": "土",
            "secondary_elements": ["金", "火"],
            "color": "#f0e0c0",
            "effects": ["事业"],
            "allowed_roles": ["primary"],
        },
        "available_water": {
            "name": "可售水系辅石",
            "element": "水",
            "secondary_elements": ["金"],
            "color": "#88bbff",
            "effects": ["沟通"],
            "allowed_roles": ["support", "accent"],
        },
        "unavailable_wood": {
            "name": "无库存木系辅石",
            "element": "木",
            "secondary_elements": [],
            "color": "#88aa88",
            "effects": ["生长"],
            "allowed_roles": ["support"],
        },
        "available_accent": {
            "name": "可售点睛石",
            "element": "水",
            "secondary_elements": [],
            "color": "#dddddd",
            "effects": ["过渡"],
            "allowed_roles": ["accent"],
        },
    }
    pools = {request.primary_core_wish: ["primary_stone"]}

    support, accent = RecommendationEngine.select_supporting(
        "水",
        {"土", "金", "火"},
        "primary_stone",
        request,
        energy,
        context,
        catalog,
        pools,
        {"primary_stone", "available_water", "available_accent"},
    )

    assert support == "available_water"
    assert accent == "available_accent"


def test_every_element_is_present():
    result = EnergyCalculator().calculate(make_request())
    assert tuple(result["final"].keys()) == ELEMENTS
