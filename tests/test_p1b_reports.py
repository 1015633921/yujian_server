from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.reporting import (
    ELEMENT_ORDER,
    balance_level,
    build_report_projection,
    display_percentages,
    stable_element_ranking,
)
from app.schemas import AssessmentRequest
from app.service import AssessmentService
from app.user_sessions import session_service


client = TestClient(app)


def headers(user_id: str) -> dict[str, str]:
    session = session_service.create(user_id)
    return {"Authorization": f"Bearer {session['access_token']}"}


def payload(user_id: str, **updates) -> dict:
    value = {
        "user_id": user_id,
        "name": "版本测试",
        "birthday": "1995-08-16",
        "birth_time": "09:30",
        "birth_time_unknown": False,
        "birth_place": "成都市",
        "mbti": "INFJ",
        "core_wishes": ["健康护身/保持专注"],
        "chakra_answers": ["need_grounding"],
        "mood_palette_id": "moon_violet",
        "wrist_size_cm": 16,
        "bead_size_mm": 8,
        "force_recalculate": True,
    }
    value.update(updates)
    return value


def generate(user_id: str, key: str, **updates) -> tuple[dict, dict[str, str]]:
    auth_headers = headers(user_id)
    response = client.post(
        "/api/v1/assessment/energy",
        headers={**auth_headers, "Idempotency-Key": key},
        json=payload(user_id, **updates),
    )
    assert response.status_code == 200, response.text
    return response.json()["data"], auth_headers


def test_report_generation_idempotency_versions_and_client_cannot_forge_version(monkeypatch):
    monkeypatch.setenv("REPORT_VERSIONING_V2_ENABLED", "true")
    user_id = f"p1b-{uuid4().hex}"
    auth_headers = headers(user_id)
    key = f"report-key-{uuid4().hex}"
    first_response = client.post(
        "/api/v1/assessment/energy",
        headers={**auth_headers, "Idempotency-Key": key},
        json=payload(user_id),
    )
    replay_response = client.post(
        "/api/v1/assessment/energy",
        headers={**auth_headers, "Idempotency-Key": key},
        json=payload(user_id),
    )
    first = first_response.json()["data"]
    replay = replay_response.json()["data"]
    assert first["report_id"] == replay["report_id"]
    assert first["assessment_id"] == replay["assessment_id"]
    assert first["report_version"] == replay["report_version"] == 1
    assert replay["idempotent_replay"] is True

    conflict = client.post(
        "/api/v1/assessment/energy",
        headers={**auth_headers, "Idempotency-Key": key},
        json=payload(user_id, mbti="INTP"),
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "report_idempotency_conflict"

    second = client.post(
        "/api/v1/assessment/energy",
        headers={**auth_headers, "Idempotency-Key": f"report-key-{uuid4().hex}"},
        json=payload(user_id, mbti="INTP"),
    ).json()["data"]
    assert second["report_id"] != first["report_id"]
    assert second["report_version"] == 2

    forged = client.post(
        "/api/v1/assessment/energy",
        headers={**auth_headers, "Idempotency-Key": f"report-key-{uuid4().hex}"},
        json={**payload(user_id), "report_version": 99},
    )
    assert forged.status_code == 422


def test_report_v2_flag_defaults_closed_and_requires_idempotency_key(monkeypatch):
    monkeypatch.delenv("REPORT_VERSIONING_V2_ENABLED", raising=False)
    user_id = f"p1b-flag-{uuid4().hex}"
    auth_headers = headers(user_id)
    legacy = client.post("/api/v1/assessment/energy", headers=auth_headers, json=payload(user_id))
    assert legacy.status_code == 200
    assert "report_id" not in legacy.json()["data"]
    disabled = client.get("/api/v1/reports/rpt_missing?report_version=1", headers=auth_headers)
    assert disabled.status_code == 503

    monkeypatch.setenv("REPORT_VERSIONING_V2_ENABLED", "true")
    missing_key = client.post("/api/v1/assessment/energy", headers=auth_headers, json=payload(user_id))
    assert missing_key.status_code == 400


def test_idempotent_replay_returns_snapshot_without_recalculating(monkeypatch):
    monkeypatch.setenv("REPORT_VERSIONING_V2_ENABLED", "true")
    user_id = f"p1b-replay-{uuid4().hex}"
    key = f"replay-{uuid4().hex}"
    first, auth_headers = generate(user_id, key)
    from app import api as api_module

    monkeypatch.setattr(
        api_module.service,
        "_build_energy_result",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("replay recalculated report")),
    )
    replay = client.post(
        "/api/v1/assessment/energy",
        headers={**auth_headers, "Idempotency-Key": key},
        json=payload(user_id),
    )
    assert replay.status_code == 200
    assert replay.json()["data"]["report_id"] == first["report_id"]
    assert replay.json()["data"]["idempotent_replay"] is True


def test_report_detail_basis_poster_and_recommendation_share_one_version(monkeypatch):
    monkeypatch.setenv("REPORT_VERSIONING_V2_ENABLED", "true")
    user_id = f"p1b-chain-{uuid4().hex}"
    report, auth_headers = generate(user_id, f"chain-{uuid4().hex}")
    query = f"report_version={report['report_version']}"
    detail = client.get(f"/api/v1/reports/{report['report_id']}?{query}", headers=auth_headers).json()["data"]
    basis = client.get(f"/api/v1/reports/{report['report_id']}/basis?{query}", headers=auth_headers).json()["data"]
    poster = client.get(f"/api/v1/reports/{report['report_id']}/poster?{query}", headers=auth_headers).json()["data"]
    recommendation = client.post(
        f"/api/v1/reports/{report['report_id']}/diy-recommendation",
        headers=auth_headers,
        json={
            "report_id": report["report_id"],
            "expected_report_version": report["report_version"],
            "wrist_size_cm": 16,
            "bead_size_mm": 8,
        },
    ).json()["data"]
    identities = {
        (item["report_id"], int(item["report_version"]))
        for item in (detail, basis, poster, recommendation)
    }
    assert identities == {(report["report_id"], int(report["report_version"]))}
    assert recommendation["workbench_payload"]["report_id"] == report["report_id"]
    assert recommendation["workbench_payload"]["report_version"] == report["report_version"]
    assert sum(item["percent"] for item in detail["report_projection"]["elements"]) == 100
    assert poster["elements"] == detail["report_projection"]["elements"]
    assert poster["balance"] == detail["report_projection"]["balance"]


def test_report_plan_refinement_does_not_overwrite_the_base_recommendation_cache(monkeypatch):
    monkeypatch.setenv("REPORT_VERSIONING_V2_ENABLED", "true")
    user_id = f"p1b-refine-{uuid4().hex}"
    report, auth_headers = generate(user_id, f"refine-{uuid4().hex}")
    endpoint = f"/api/v1/reports/{report['report_id']}/diy-recommendation"
    base_payload = {
        "report_id": report["report_id"],
        "expected_report_version": report["report_version"],
        "wrist_size_cm": 16,
        "bead_size_mm": 8,
    }
    original = client.post(endpoint, headers=auth_headers, json=base_payload).json()["data"]
    rejected = original["bracelet_plans"][1]
    locked = next(item for item in rejected["items"] if item.get("top") == "accessory")

    refined_response = client.post(
        endpoint,
        headers=auth_headers,
        json={
            **base_payload,
            "style_preference": "layered",
            "accessory_preference": "more",
            "locked_material_ids": [locked["material_id"]],
            "rejected_plan_id": rejected["plan_id"],
        },
    )
    refined = refined_response.json()["data"]
    replay = client.post(endpoint, headers=auth_headers, json=base_payload).json()["data"]

    assert refined_response.status_code == 200
    assert refined["recommendation_cache_hit"] is False
    assert rejected["plan_id"] not in {item["plan_id"] for item in refined["bracelet_plans"]}
    assert replay["recommendation_cache_hit"] is True
    assert replay["bracelet_plan"]["plan_id"] == original["bracelet_plan"]["plan_id"]


def test_report_snapshot_is_immutable_and_get_does_not_recalculate(monkeypatch):
    monkeypatch.setenv("REPORT_VERSIONING_V2_ENABLED", "true")
    user_id = f"p1b-immutable-{uuid4().hex}"
    report, auth_headers = generate(user_id, f"immutable-{uuid4().hex}")
    before = client.get(
        f"/api/v1/reports/{report['report_id']}/basis?report_version={report['report_version']}",
        headers=auth_headers,
    ).json()["data"]
    from app import api as api_module

    monkeypatch.setattr(
        api_module.service.energy_calculator,
        "calculate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("GET recalculated report")),
    )
    detail = client.get(
        f"/api/v1/reports/{report['report_id']}?report_version={report['report_version']}",
        headers=auth_headers,
    )
    after = client.get(
        f"/api/v1/reports/{report['report_id']}/basis?report_version={report['report_version']}",
        headers=auth_headers,
    ).json()["data"]
    assert detail.status_code == 200
    assert before == after
    assert after["input_snapshot"]["mbti"] == "INFJ"


def test_report_ownership_version_conflict_and_poster_privacy(monkeypatch):
    monkeypatch.setenv("REPORT_VERSIONING_V2_ENABLED", "true")
    owner = f"p1b-owner-{uuid4().hex}"
    report, owner_headers = generate(owner, f"owner-{uuid4().hex}")
    other_headers = headers(f"p1b-other-{uuid4().hex}")
    paths = (
        f"/api/v1/reports/{report['report_id']}?report_version={report['report_version']}",
        f"/api/v1/reports/{report['report_id']}/basis?report_version={report['report_version']}",
        f"/api/v1/reports/{report['report_id']}/poster?report_version={report['report_version']}",
    )
    assert all(client.get(path, headers=other_headers).status_code == 404 for path in paths)
    forbidden_recommendation = client.post(
        f"/api/v1/reports/{report['report_id']}/diy-recommendation",
        headers=other_headers,
        json={
            "report_id": report["report_id"],
            "expected_report_version": report["report_version"],
            "wrist_size_cm": 16,
            "bead_size_mm": 8,
        },
    )
    assert forbidden_recommendation.status_code == 404
    mismatch = client.get(
        f"/api/v1/reports/{report['report_id']}?report_version={report['report_version'] + 1}",
        headers=owner_headers,
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["detail"]["code"] == "report_version_conflict"

    poster = client.get(paths[2], headers=owner_headers).json()["data"]
    serialized = json.dumps(poster, ensure_ascii=False).lower()
    for forbidden in (
        "1995-08-16", "09:30", "成都市", "infj", "need_grounding",
        "moon_violet", owner.lower(), "openid", "phone",
    ):
        assert forbidden not in serialized


def test_unknown_location_never_uses_default_120_and_known_location_is_applied(monkeypatch):
    monkeypatch.setenv("REPORT_VERSIONING_V2_ENABLED", "true")
    unknown_user = f"p1b-location-{uuid4().hex}"
    unknown, unknown_headers = generate(
        unknown_user,
        f"unknown-{uuid4().hex}",
        birth_place="石家庄市",
    )
    basis = client.get(
        f"/api/v1/reports/{unknown['report_id']}/basis?report_version={unknown['report_version']}",
        headers=unknown_headers,
    ).json()["data"]
    assert unknown["calibration_status"] == "unsupported"
    assert basis["calibration"]["status"] == "unsupported"
    assert basis["calibration"]["details"]["longitude"] is None
    assert basis["calibration"]["details"]["calibrated_time"] is None

    known_user = f"p1b-known-{uuid4().hex}"
    known, known_headers = generate(known_user, f"known-{uuid4().hex}")
    known_basis = client.get(
        f"/api/v1/reports/{known['report_id']}/basis?report_version={known['report_version']}",
        headers=known_headers,
    ).json()["data"]
    assert known["calibration_status"] == "applied"
    assert known_basis["calibration"]["details"]["longitude"] == 104.0665
    assert known_basis["calibration"]["details"]["calibrated_time"]


def test_unknown_birth_time_and_mismatched_coordinates_never_claim_calibration(monkeypatch):
    monkeypatch.setenv("REPORT_VERSIONING_V2_ENABLED", "true")
    unknown_time_user = f"p1b-time-{uuid4().hex}"
    unknown_time, unknown_headers = generate(
        unknown_time_user,
        f"time-{uuid4().hex}",
        birth_time_unknown=True,
    )
    basis = client.get(
        f"/api/v1/reports/{unknown_time['report_id']}/basis?report_version={unknown_time['report_version']}",
        headers=unknown_headers,
    ).json()["data"]
    assert basis["calibration"]["status"] == "not_required"
    assert basis["calibration"]["details"]["calibrated_time"] is None

    invalid_user = f"p1b-coordinate-{uuid4().hex}"
    invalid, invalid_headers = generate(
        invalid_user,
        f"coordinate-{uuid4().hex}",
        lng=120,
        lat=30,
    )
    invalid_basis = client.get(
        f"/api/v1/reports/{invalid['report_id']}/basis?report_version={invalid['report_version']}",
        headers=invalid_headers,
    ).json()["data"]
    assert invalid_basis["calibration"]["status"] == "invalid_location"
    assert invalid_basis["calibration"]["details"]["longitude"] is None
    assert invalid_basis["calibration"]["details"]["calibrated_time"] is None

    invalid_code_user = f"p1b-location-code-{uuid4().hex}"
    invalid_code, invalid_code_headers = generate(
        invalid_code_user,
        f"location-code-{uuid4().hex}",
        location_code="cn:not-a-real-code",
    )
    invalid_code_basis = client.get(
        f"/api/v1/reports/{invalid_code['report_id']}/basis?report_version={invalid_code['report_version']}",
        headers=invalid_code_headers,
    ).json()["data"]
    assert invalid_code_basis["calibration"]["status"] == "unsupported"
    assert invalid_code_basis["calibration"]["details"]["calibrated_time"] is None


def test_location_input_validation_and_leap_day_boundary(monkeypatch):
    monkeypatch.setenv("REPORT_VERSIONING_V2_ENABLED", "true")
    user_id = f"p1b-location-validation-{uuid4().hex}"
    auth_headers = headers(user_id)
    empty_location = client.post(
        "/api/v1/assessment/energy",
        headers={**auth_headers, "Idempotency-Key": f"empty-{uuid4().hex}"},
        json=payload(user_id, birth_place=""),
    )
    invalid_range = client.post(
        "/api/v1/assessment/energy",
        headers={**auth_headers, "Idempotency-Key": f"range-{uuid4().hex}"},
        json=payload(user_id, lng=181, lat=30),
    )
    assert empty_location.status_code == 422
    assert invalid_range.status_code == 422

    leap, leap_headers = generate(
        user_id,
        f"leap-{uuid4().hex}",
        birthday="2024-02-29",
        birth_time="00:05",
    )
    leap_basis = client.get(
        f"/api/v1/reports/{leap['report_id']}/basis?report_version={leap['report_version']}",
        headers=leap_headers,
    ).json()["data"]
    assert leap_basis["calibration"]["status"] == "applied"
    assert leap_basis["calibration"]["details"]["calibrated_time"].startswith("2024-02-28")


def test_same_idempotency_key_is_safe_across_two_workers(tmp_path):
    from app.admin_service import AdminService
    from app.migrations.runner import upgrade
    from app.order_service import OrderService
    from app.repository import AssessmentRepository

    db_path = tmp_path / "p1b-concurrent.db"
    AdminService(db_path)
    OrderService(db_path)
    AssessmentRepository(db_path)
    upgrade("sqlite", db_path)
    request = AssessmentRequest(
        user_id="p1b-concurrent-user",
        name="并发测试",
        birthday=date(1995, 8, 16),
        birth_time=time(9, 30),
        birth_place="成都市",
        core_wishes=["健康护身/保持专注"],
    )

    def attempt(_index: int):
        return AssessmentService(db_path).calculate_energy_v2(request, "same-worker-key")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))
    report_ids = {item[0]["report_id"] for item in results}
    assert len(report_ids) == 1
    assert sorted(item[1] for item in results) == [False, True]


def test_personalization_deletion_removes_private_report_snapshots(tmp_path):
    from app.admin_service import AdminService
    from app.migrations.runner import upgrade
    from app.order_service import OrderService
    from app.repository import AssessmentRepository

    db_path = tmp_path / "p1b-privacy.db"
    AdminService(db_path)
    OrderService(db_path)
    AssessmentRepository(db_path)
    upgrade("sqlite", db_path)
    service = AssessmentService(db_path)
    request = AssessmentRequest(
        user_id="p1b-private-user",
        name="Private report",
        birthday=date(1995, 8, 16),
        birth_time=time(9, 30),
        birth_place="成都市",
        mbti="INFJ",
        core_wishes=["健康护身/保持专注"],
    )
    report, _ = service.calculate_energy_v2(request, "privacy-report-key")
    summary = service.privacy_data_summary(request.user_id)
    assert summary["counts"]["reports"] == 1
    result = service.delete_personalization_data(request.user_id)
    assert result["counts"]["reports"] == 1
    assert service.report_repository.get(report["report_id"]) is None
    assert service.report_repository.get_request(request.user_id, "privacy-report-key") is None


def test_report_transaction_failure_rolls_back_request_snapshot_and_assessment(tmp_path):
    import sqlite3

    from app.admin_service import AdminService
    from app.migrations.runner import upgrade
    from app.order_service import OrderService
    from app.repository import AssessmentRepository

    db_path = tmp_path / "p1b-rollback.db"
    AdminService(db_path)
    OrderService(db_path)
    AssessmentRepository(db_path)
    upgrade("sqlite", db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_p1b_snapshot BEFORE INSERT ON report_snapshots
            BEGIN SELECT RAISE(ABORT, 'forced snapshot failure'); END
            """
        )
    service = AssessmentService(db_path)
    request = AssessmentRequest(
        user_id="p1b-rollback-user",
        name="Rollback report",
        birthday=date(1995, 8, 16),
        birth_time=time(9, 30),
        birth_place="成都市",
        core_wishes=["健康护身/保持专注"],
    )
    with pytest.raises(ValueError, match="报告生成请求冲突"):
        service.calculate_energy_v2(request, "rollback-report-key")
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM report_generation_requests").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM report_snapshots").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM energy_assessments").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM report_version_counters").fetchone()[0] == 0


@pytest.mark.parametrize(
    "raw",
    [
        {"木": 20, "火": 20, "土": 20, "金": 20, "水": 19},
        {"木": 21, "火": 20, "土": 20, "金": 20, "水": 20},
        {"木": 1, "火": 1, "土": 1, "金": 1, "水": 2},
        {"木": 20.2, "火": 20.2, "土": 20.2, "金": 20.2, "水": 19.2},
        {"木": 0, "火": 0, "土": 0, "金": 0, "水": 100},
        {element: 1 for element in ELEMENT_ORDER},
    ],
)
def test_display_percentages_always_total_100_with_stable_ties(raw):
    result = display_percentages(raw)
    assert sum(result.values()) == 100
    assert list(result) == list(ELEMENT_ORDER)


def test_projection_balance_and_tie_order_are_single_source_of_truth():
    projection = build_report_projection(
        {
            "final_energy_profile": {"木": 20, "火": 20, "土": 20, "金": 20, "水": 20},
            "interpretation": {"balance_index": 85, "headline": "测试"},
            "useful_elements": ["金", "水", "木"],
        }
    )
    assert projection["ranking"]["dominant"] == "木"
    assert projection["ranking"]["secondary"] == "火"
    assert projection["ranking"]["lowest"] == "木"
    assert projection["balance"] == balance_level(85) == {"score": 85, "label": "分布接近"}


@pytest.mark.parametrize(
    ("percentages", "expected"),
    [
        ({"木": 30, "火": 30, "土": 20, "金": 10, "水": 10}, ["木", "火", "土", "金", "水"]),
        ({"木": 25, "火": 25, "土": 25, "金": 15, "水": 10}, ["木", "火", "土", "金", "水"]),
    ],
)
def test_two_and_three_way_ties_use_documented_element_order(percentages, expected):
    assert stable_element_ranking(percentages) == expected
