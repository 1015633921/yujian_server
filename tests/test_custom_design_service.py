from __future__ import annotations

import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app import api as api_module
from app.main import app
from app.user_sessions import session_service


client = TestClient(app)


def user_headers(user_id: str) -> dict[str, str]:
    session = session_service.create(user_id)
    return {"Authorization": f"Bearer {session['access_token']}"}


def report_payload(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "name": "人工搭配测试",
        "birthday": "1995-08-16",
        "birth_time": "09:30",
        "birth_place": "成都市",
        "mbti": "INFJ",
        "core_wishes": ["健康护身/保持专注"],
        "wrist_size_cm": 16,
        "bead_size_mm": 8,
        "force_recalculate": True,
    }


def test_custom_design_request_is_private_and_uses_independent_service_state(monkeypatch):
    monkeypatch.setenv("REPORT_VERSIONING_V2_ENABLED", "true")
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")
    user_id = f"custom-design-{uuid4().hex}"
    headers = user_headers(user_id)
    report_response = client.post(
        "/api/v1/assessment/energy",
        headers={**headers, "Idempotency-Key": f"custom-report-{uuid4().hex}"},
        json=report_payload(user_id),
    )
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()["data"]
    payload = {
        "user_id": user_id,
        "report_id": report["report_id"],
        "report_version": report["report_version"],
        "wrist_size_cm": 16,
        "bead_size_mm": 8,
        "budget": "300–500 元",
        "style_preference": "清透自然",
        "color_preference": "蓝白、低饱和",
        "accessory_preference": "少量银饰",
        "wear_scene": "日常佩戴",
        "preference_confirmed": True,
        "note": "希望整体轻盈",
    }
    invalid_size = client.post(
        "/api/v1/custom-design-requests",
        headers=headers,
        json={**payload, "bead_size_mm": 5},
    )
    assert invalid_size.status_code == 422
    created = client.post("/api/v1/custom-design-requests", headers=headers, json=payload)
    assert created.status_code == 200, created.text
    request = created.json()["data"]
    assert request["status"] == "deposit_pending"
    assert request["deposit"]["status"] == "unpaid"
    assert request["deposit"]["amount_fee"] == 990
    assert request["deposit"]["amount_text"] == "9.90"
    assert request["report_code"].startswith("RPT-")
    assert request["report_summary"]["core_conclusion"]
    assert request["design_brief"]["status"] == "ready"
    assert request["design_brief"]["lineage"]["report_code"] == request["report_code"]
    assert request["design_brief"]["hard_constraints"][0]["value"] == "16 cm"
    assert request["design_brief"]["hard_constraints"][1]["value"] == "8 mm"
    assert request["design_brief"]["preferences"]["accessory"] == "少量银饰"
    assert request["design_brief"]["preferences"]["wear_scene"] == "日常佩戴"
    assert request["design_brief"]["preferences"]["confirmed"] is True
    assert "birthday" not in str(request["report_summary"])
    assert "birthday" not in str(request["design_brief"])
    assert request["proposals"] == []
    assert "birthday" not in str(request)

    paid = api_module.custom_design_service.mark_deposit_paid_for_dev(request["request_id"], user_id)
    assert paid["status"] == "submitted"
    assert paid["deposit"]["status"] == "paid"

    with api_module.custom_design_service.connect() as connection:
        snapshot = connection.execute(
            "SELECT output_snapshot_json FROM report_snapshots WHERE report_id = ? AND report_version = ?",
            (report["report_id"], report["report_version"]),
        ).fetchone()
        legacy_output = json.loads(snapshot["output_snapshot_json"])
        legacy_output.pop("report_projection", None)
        legacy_output.pop("report_context", None)
        connection.execute(
            "UPDATE report_snapshots SET output_snapshot_json = ? WHERE report_id = ? AND report_version = ?",
            (json.dumps(legacy_output, ensure_ascii=False), report["report_id"], report["report_version"]),
        )
    legacy_admin_view = api_module.custom_design_service.get_for_admin(request["request_id"])
    assert legacy_admin_view["report_summary"]["core_conclusion"]
    assert legacy_admin_view["report_summary"]["mbti_analysis"]["type"] == "INFJ"
    assert legacy_admin_view["report_summary"]["core_wishes"] == ["健康护身/保持专注"]
    assert legacy_admin_view["design_brief"]["status"] == "ready"
    assert "birthday" not in str(legacy_admin_view["design_brief"])

    duplicate = client.post("/api/v1/custom-design-requests", headers=headers, json=payload)
    assert duplicate.status_code == 400
    assert "进行中的人工搭配申请" in duplicate.json()["detail"]

    other_headers = user_headers(f"other-{uuid4().hex}")
    assert client.get(f"/api/v1/custom-design-requests/{request['request_id']}", headers=other_headers).status_code == 404

    proposed = api_module.custom_design_service.publish_proposal(
        request["request_id"],
        "operator-1",
        {
            "title": "清透日常款",
            "description": "低饱和蓝白配色",
            "image_urls": ["https://example.com/design.jpg"],
            "workbench": {
                "schema_version": 1,
                "wrist_size_cm": 16,
                "bead_size_mm": 8,
                "layout": [{"id": "test-material", "image_url": "https://example.com/bead.jpg"}],
                "selected": ["test-material"],
                "summary": {"count": 1, "price": "10.00"},
            },
        },
    )
    assert proposed["status"] == "proposed"
    assert proposed["proposals"][0]["image_urls"] == ["https://example.com/design.jpg"]
    assert proposed["proposals"][0]["workbench"]["selected"] == ["test-material"]

    revised = client.post(
        f"/api/v1/custom-design-requests/{request['request_id']}/revision",
        headers=headers,
        json={"user_id": user_id, "note": "希望再减少一点配饰"},
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["data"]["status"] == "revision_requested"


def test_custom_design_request_accepts_a_legacy_assessment_source(monkeypatch):
    monkeypatch.delenv("REPORT_VERSIONING_V2_ENABLED", raising=False)
    user_id = f"custom-legacy-{uuid4().hex}"
    headers = user_headers(user_id)
    response = client.post("/api/v1/assessment/energy", headers=headers, json=report_payload(user_id))
    assert response.status_code == 200, response.text
    assessment = response.json()["data"]
    assert "report_id" not in assessment
    request = client.post(
        "/api/v1/custom-design-requests",
        headers=headers,
        json={
            "user_id": user_id,
            "report_id": f"assessment:{assessment['assessment_id']}",
            "report_version": 1,
            "assessment_id": assessment["assessment_id"],
            "wrist_size_cm": 16,
            "bead_size_mm": 8,
        },
    )
    assert request.status_code == 200, request.text
    assert request.json()["data"]["request"]["assessment_id"] == assessment["assessment_id"]
