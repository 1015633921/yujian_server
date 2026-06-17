from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app

client = TestClient(app)

PAYLOAD = {
    "user_id": "api-test-user",
    "name": "林安",
    "birthday": "1995-08-16",
    "birth_time": "09:30",
    "birth_place": "四川省成都市",
    "mbti": "INFJ",
    "core_wish": "健康护身/保持专注",
    "wrist_size_cm": 15.5,
    "bead_size_mm": 8,
}


def test_options_support_form_rendering():
    response = client.get("/api/v1/assessment/options")
    assert response.status_code == 200
    assert len(response.json()["data"]["mbti_options"]) == 16


def test_wechat_login_profile_and_phone_flow_without_secret():
    login = client.post("/api/v1/auth/wechat-login", json={"code": f"unit-test-login-code-{uuid4()}"})
    user = login.json()["data"]

    assert login.status_code == 200
    assert user["user_id"].startswith("dev_")
    assert user["has_profile"] is False

    profile = client.post(
        "/api/v1/auth/profile",
        json={
            "user_id": user["user_id"],
            "nickname": "Test User",
            "avatar_url": "https://example.com/avatar.png",
            "gender": "1",
        },
    )
    updated = profile.json()["data"]

    assert profile.status_code == 200
    assert updated["nickname"] == "Test User"
    assert updated["has_profile"] is True

    phone = client.post(
        "/api/v1/auth/phone",
        json={"user_id": user["user_id"], "phone_number": "13800000000"},
    )

    assert phone.status_code == 200
    assert phone.json()["data"]["has_phone"] is True


def test_calculate_returns_ui_ready_result():
    response = client.post("/api/v1/assessment/calculate", json={**PAYLOAD, "force_recalculate": True})
    data = response.json()["data"]

    assert response.status_code == 200
    assert data["chart"]["type"] == "radar"
    assert data["primary_crystal"]["role"] == "主石"
    assert data["bracelet_plan"]["layout"]


def test_two_step_energy_to_diy_workbench_flow():
    energy_response = client.post(
        "/api/v1/assessment/energy",
        json={**PAYLOAD, "force_recalculate": True},
    )
    energy_data = energy_response.json()["data"]

    assert energy_response.status_code == 200
    assert energy_data["status"] == "energy_ready"
    assert energy_data["next_step"]["action"] == "open_wrist_size_form"
    assert "bracelet_plan" not in energy_data

    recommendation_response = client.post(
        f"/api/v1/assessment/{energy_data['assessment_id']}/diy-recommendation",
        json={"wrist_size_cm": 16.5, "bead_size_mm": 8},
    )
    recommendation_data = recommendation_response.json()["data"]

    assert recommendation_response.status_code == 200
    assert recommendation_data["status"] == "diy_ready"
    assert recommendation_data["next_step"]["action"] == "navigate_to_diy_workbench"
    assert recommendation_data["workbench_payload"]["wrist_size_cm"] == 16.5
    assert recommendation_data["workbench_payload"]["bracelet_plan"]["layout"]


def test_invalid_mbti_is_rejected():
    response = client.post("/api/v1/assessment/calculate", json={**PAYLOAD, "mbti": "NOPE"})
    assert response.status_code == 422
    assert response.json()["code"] == 422


def test_optional_mbti_and_three_core_wishes_are_accepted():
    response = client.post(
        "/api/v1/assessment/energy",
        json={
            **PAYLOAD,
            "mbti": None,
            "core_wish": None,
            "core_wishes": [
                "招财进宝/事业腾飞",
                "正缘桃花/人际和合",
                "健康护身/保持专注",
            ],
            "force_recalculate": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["input_summary"]["mbti"] is None
    assert len(response.json()["data"]["input_summary"]["core_wishes"]) == 3


def test_more_than_three_core_wishes_are_rejected():
    response = client.post(
        "/api/v1/assessment/energy",
        json={
            **PAYLOAD,
            "core_wish": None,
            "core_wishes": [
                "招财进宝/事业腾飞",
                "正缘桃花/人际和合",
                "辟邪防小人/消除焦虑",
                "健康护身/保持专注",
            ],
        },
    )

    assert response.status_code == 422


def test_first_time_user_gets_starter_daily_energy_and_same_day_is_cached():
    user_id = "daily-starter-user"
    first = client.get(f"/api/v1/daily-energy/today?user_id={user_id}&force_recalculate=true")
    second = client.get(f"/api/v1/daily-energy/today?user_id={user_id}")

    assert first.status_code == 200
    assert first.json()["data"]["mode"] == "starter"
    assert first.json()["data"]["personalized"] is False
    assert first.json()["data"]["guide"]["route"] == "/pages/assessment/assessment"
    assert second.json()["data"]["cache_hit"] is True
    assert second.json()["data"]["score"] == first.json()["data"]["score"]


def test_assessed_user_gets_personalized_daily_energy():
    user_id = "daily-personalized-user"
    client.post(
        "/api/v1/assessment/energy",
        json={**PAYLOAD, "user_id": user_id, "force_recalculate": True},
    )
    response = client.get(f"/api/v1/daily-energy/today?user_id={user_id}&force_recalculate=true")
    data = response.json()["data"]

    assert response.status_code == 200
    assert data["mode"] == "personalized"
    assert data["personalized"] is True
    assert data["assessment_id"]
    assert data["guide"] is None


def test_daily_checkin_is_saved_and_used_on_recalculation():
    user_id = "daily-checkin-user"
    checkin = client.post(
        "/api/v1/daily-energy/check-in?checkin_date=2026-06-04",
        json={"user_id": user_id, "mood": 5, "sleep": 5, "stress": 1},
    )
    response = client.get(
        f"/api/v1/daily-energy/2026-06-04?user_id={user_id}&force_recalculate=true"
    )

    assert checkin.status_code == 200
    assert response.status_code == 200
    assert response.json()["data"]["state_context"]["source"] == "recent_checkins"
    assert response.json()["data"]["state_context"]["adjustment"] > 0
