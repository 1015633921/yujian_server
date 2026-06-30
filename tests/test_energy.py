from datetime import date, time

from app.energy import ELEMENTS, ENERGY_WEIGHTS, EnergyCalculator
from app.recommendation import RecommendationEngine
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


def test_optional_mbti_uses_neutral_profile():
    result = EnergyCalculator().calculate(make_request(mbti=None))

    assert result["breakdown"]["mbti"] == {"金": 1.6, "木": 1.6, "水": 1.6, "火": 1.6, "土": 1.6}
    assert round(sum(result["final"].values()), 2) == 100


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

    assert primary["name"] in {"钛晶", "黄水晶", "金发晶", "太阳石"}
    excluded = {primary["element"], *primary["secondary_elements"]}
    assert recommendation["supporting"][0]["element"] not in excluded
    assert len(recommendation["bracelet_plan"]["layout"]) == recommendation["bracelet_plan"]["estimated_bead_count"]


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


def test_every_element_is_present():
    result = EnergyCalculator().calculate(make_request())
    assert tuple(result["final"].keys()) == ELEMENTS
