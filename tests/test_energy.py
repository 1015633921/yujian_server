from datetime import date, time

from app.energy import ELEMENTS, EnergyCalculator
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
    assert round(sum(result["breakdown"]["bazi"].values()), 2) == 55
    assert round(sum(result["breakdown"]["mbti"].values()), 2) == 15
    assert round(sum(result["breakdown"]["name"].values()), 2) == 10
    assert round(sum(result["breakdown"]["wish"].values()), 2) == 20


def test_optional_mbti_uses_neutral_15_point_profile():
    result = EnergyCalculator().calculate(make_request(mbti=None))

    assert result["breakdown"]["mbti"] == {"金": 3.0, "木": 3.0, "水": 3.0, "火": 3.0, "土": 3.0}
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

    assert round(sum(result["breakdown"]["wish"].values()), 2) == 20


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

    assert primary["name"] in {"钛晶", "黄水晶", "金发晶"}
    excluded = {primary["element"], *primary["secondary_elements"]}
    assert recommendation["supporting"][0]["element"] not in excluded
    assert len(recommendation["bracelet_plan"]["layout"]) == recommendation["bracelet_plan"]["estimated_bead_count"]


def test_every_element_is_present():
    result = EnergyCalculator().calculate(make_request())
    assert tuple(result["final"].keys()) == ELEMENTS
