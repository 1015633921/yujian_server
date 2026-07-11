from datetime import date

from app.daily_energy import DailyEnergyCalculator
from app.daily_service import DailyEnergyService
from app.energy import ELEMENTS
from app.recommendation import RecommendationEngine


def test_daily_date_profile_totals_100_and_is_stable():
    calculator = DailyEnergyCalculator()
    target_date = date(2026, 6, 4)

    first = calculator.date_profile(target_date)
    second = calculator.date_profile(target_date)

    assert first == second
    assert round(sum(first.values()), 2) == 100
    assert calculator.date_basis(target_date)["day_ganzhi"]


def test_starter_result_is_deterministic_for_same_user_and_day():
    calculator = DailyEnergyCalculator()
    target_date = date(2026, 6, 4)

    first = calculator.calculate("new-user", target_date, None, {})
    second = calculator.calculate("new-user", target_date, None, {})

    assert first == second
    assert first["mode"] == "starter"
    assert first["guide"]["button_text"] == "开始专属分析"
    assert first["state_context"]["source"] == "live_selection"
    assert first["recommended_crystals"][0]["material_id"]
    assert first["recommended_crystals"][0]["image_url"]
    assert first["workbench_payload"]["bracelet_plan"]["items"][0]["image_url"]
    assert first["workbench_payload"]["bracelet_plan"]["layout"][0]["material_id"]


def test_interaction_tags_change_daily_recommendation():
    calculator = DailyEnergyCalculator()
    target_date = date(2026, 6, 4)

    calm = calculator.calculate(
        "new-user",
        target_date,
        None,
        {"status_tags": ["calm"], "scene_key": "work_comm", "goal_keys": ["stable_expression"]},
    )
    money = calculator.calculate(
        "new-user",
        target_date,
        None,
        {"status_tags": ["money"], "scene_key": "deadline", "goal_keys": ["wealth"]},
    )

    assert calm["state_context"]["selected_status_tags"][0]["key"] == "calm"
    assert money["state_context"]["selected_status_tags"][0]["key"] == "money"
    assert calm["energy_profile"] != money["energy_profile"]


def test_daily_workbench_payload_respects_latest_assessment_wrist_size():
    calculator = DailyEnergyCalculator()
    target_date = date(2026, 6, 4)
    assessment = {
        "assessment_id": "assessment-wrist-145",
        "final_energy_profile": {element: 20 for element in ELEMENTS},
        "input_summary": {"wrist_size_cm": 14.5},
    }

    result = calculator.calculate("wrist-user", target_date, assessment, {})
    payload = result["workbench_payload"]
    plan = payload["bracelet_plan"]
    layout = plan["layout"]
    sizes = [float(item.get("size") or item.get("bead_size_mm") or 8) for item in layout]
    effective_length_cm = RecommendationEngine.estimate_stringed_length_mm(sizes) / 10

    assert payload["wrist_size_cm"] == 14.5
    assert plan["wrist_size_cm"] == 14.5
    assert len(layout) == plan["estimated_bead_count"]
    assert effective_length_cm >= 15.0


def test_daily_score_labels_are_descriptive_not_health_claims():
    assert DailyEnergyCalculator.score_level(90) == "活力充足"
    assert DailyEnergyCalculator.score_level(80) == "状态稳定"
    assert DailyEnergyCalculator.score_level(65) == "温柔蓄能"
    assert DailyEnergyCalculator.score_level(50) == "慢节奏"


def test_daily_service_recalculates_when_latest_assessment_changes():
    class FakeRepository:
        def __init__(self):
            self.assessment = None
            self.daily = None

        def get_setting(self, _key):
            return None

        def latest_for_user(self, _user_id):
            return self.assessment

        def get_daily_energy(self, _user_id, _energy_date):
            return self.daily

        def save_daily_energy(self, result):
            self.daily = result

    repository = FakeRepository()
    service = DailyEnergyService()
    service.repository = repository
    target_date = date(2026, 6, 4)

    repository.assessment = {
        "assessment_id": "assessment-wrist-145",
        "final_energy_profile": {element: 20 for element in ELEMENTS},
        "input_summary": {"wrist_size_cm": 14.5},
    }
    first, first_cached = service.get_or_calculate("wrist-user", target_date, force_recalculate=True)

    repository.assessment = {
        "assessment_id": "assessment-wrist-170",
        "final_energy_profile": {element: 20 for element in ELEMENTS},
        "input_summary": {"wrist_size_cm": 17},
    }
    second, second_cached = service.get_or_calculate("wrist-user", target_date)

    assert first_cached is False
    assert second_cached is False
    assert first["assessment_id"] == "assessment-wrist-145"
    assert second["assessment_id"] == "assessment-wrist-170"
    assert second["workbench_payload"]["wrist_size_cm"] == 17
