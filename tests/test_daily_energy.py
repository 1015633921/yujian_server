from datetime import date

from app.daily_energy import DailyEnergyCalculator


def test_daily_date_profile_totals_100_and_is_stable():
    calculator = DailyEnergyCalculator()
    target_date = date(2026, 6, 4)

    first = calculator.date_profile(target_date)
    second = calculator.date_profile(target_date)

    assert first == second
    assert round(sum(first.values()), 2) == 100


def test_starter_result_is_deterministic_for_same_user_and_day():
    calculator = DailyEnergyCalculator()
    target_date = date(2026, 6, 4)
    date_profile = calculator.date_profile(target_date)
    state = calculator.state_score([])

    first = calculator.starter("new-user", target_date, date_profile, state, None)
    second = calculator.starter("new-user", target_date, date_profile, state, None)

    assert first == second
    assert first["mode"] == "starter"
    assert first["guide"]["button_text"] == "开始专属测算"
