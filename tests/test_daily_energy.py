from datetime import date

from app.daily_energy import DailyEnergyCalculator


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
    assert first["guide"]["button_text"] == "开始专属测算"
    assert first["state_context"]["source"] == "live_selection"


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
