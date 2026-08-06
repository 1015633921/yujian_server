from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app import admin_api
from app.admin_service import AdminService
from app.custom_design_service import CustomDesignService
from app.main import app
from app.migrations.runner import upgrade
from app.order_service import OrderService
from app.repository import AssessmentRepository


client = TestClient(app)


def _service(tmp_path) -> CustomDesignService:
    database = tmp_path / "custom-design-admin-list.db"
    AssessmentRepository(database)
    AdminService(database)
    OrderService(database)
    upgrade("sqlite", database)
    service = CustomDesignService(database)
    timestamp = "2026-08-06T09:00:00Z"
    requests = (
        ("CD-001", "report-001", 1, "submitted", "2026-08-06T09:00:01Z"),
        ("CD-002", "assessment%3Alegacy-002", 1, "designing", "2026-08-06T09:00:02Z"),
        ("CD-003", "report-003", 1, "proposed", "2026-08-06T09:00:03Z"),
    )
    with service.connect() as connection:
        for report_id, assessment_id, report_code in (
            ("report-001", "assessment-001", "RPT-20260806-0001"),
            ("report-003", "assessment-003", "RPT-20260806-0003"),
            ("report-legacy-002", "legacy-002", "RPT-20260806-0002"),
        ):
            connection.execute(
                """
                INSERT INTO report_snapshots
                (report_id, assessment_id, user_id, report_version, source_input_hash,
                 algorithm_version, schema_version, calibration_version,
                 calibration_status, calibration_source, calibration_reason_code,
                 input_snapshot_json, output_snapshot_json, created_at, report_code)
                VALUES (?, ?, ?, 1, 'hash', 'algorithm', 1, 'calibration',
                        'ready', 'test', '', '{}', '{}', ?, ?)
                """,
                (report_id, assessment_id, f"snapshot-{report_id}", timestamp, report_code),
            )
        for request_id, report_id, report_version, status, updated_at in requests:
            request = {
                "assessment_id": "legacy-002" if request_id == "CD-002" else "",
                "wrist_size_cm": 16,
                "bead_size_mm": 8,
                "budget": "300–500 元",
                "style_preference": "清透自然",
                "color_preference": "蓝白",
                "accessory_preference": "少量银饰",
                "wear_scene": "日常佩戴",
                "preference_confirmed": True,
                "note": "日常通勤",
                "unexpected_private_field": "must-not-leak",
            }
            connection.execute(
                """
                INSERT INTO custom_design_requests
                (request_id, user_id, report_id, report_version, request_json, status,
                 first_draft_due_at, created_at, updated_at)
                VALUES (?, 'admin-list-user', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    report_id,
                    report_version,
                    json.dumps(request, ensure_ascii=False),
                    status,
                    "2026-08-07T09:00:00Z",
                    timestamp,
                    updated_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO custom_design_deposits
                (deposit_id, request_id, user_id, out_trade_no, amount_fee, currency,
                 status, payment_json, refund_json, created_at, updated_at)
                VALUES (?, ?, 'admin-list-user', ?, 990, 'CNY', 'paid', '{}', '{}', ?, ?)
                """,
                (f"DEP-{request_id}", request_id, f"trade-{request_id}", timestamp, updated_at),
            )
        for version in (1, 2):
            connection.execute(
                """
                INSERT INTO custom_design_proposals
                (proposal_id, request_id, proposal_version, title, description,
                 image_urls_json, workbench_json, order_id, confirmed_at, status,
                 created_by, created_at)
                VALUES (?, 'CD-003', ?, ?, ?, '[]', ?, '', NULL, 'active', 'designer-1', ?)
                """,
                (
                    f"proposal-{version}",
                    version,
                    f"第 {version} 版方案",
                    "不应出现在列表 DTO 的长说明" * 30,
                    json.dumps({"layout": ["large-workbench-payload"] * 100}),
                    timestamp,
                ),
            )
        connection.execute(
            """
            INSERT INTO custom_design_drafts
            (draft_id, request_id, draft_version, workbench_json, created_by, created_at, updated_at)
            VALUES ('draft-CD-003', 'CD-003', 1, ?, 'designer-1', ?, ?)
            """,
            (json.dumps({"layout": ["large-draft-payload"] * 100}), timestamp, timestamp),
        )
        connection.execute(
            """
            INSERT INTO custom_design_events
            (event_id, request_id, event_type, from_status, to_status, actor_type,
             actor_id, note, created_at)
            VALUES ('event-CD-003', 'CD-003', 'proposal_published', 'designing', 'proposed',
                    'admin', 'designer-1', ?, ?)
            """,
            ("不应出现在列表 DTO 的事件记录" * 30, timestamp),
        )
    return service


def test_admin_queue_limits_before_hydration_and_returns_summary_dto(tmp_path):
    service = _service(tmp_path)
    queries: list[str] = []
    original_connect = service.connect

    def traced_connect():
        connection = original_connect()
        connection.set_trace_callback(queries.append)
        return connection

    service.connect = traced_connect
    page = service.list_for_admin(limit=2, offset=0, include_meta=True)

    assert page["total"] == 3
    assert page["limit"] == 2
    assert page["offset"] == 0
    assert [item["request_id"] for item in page["items"]] == ["CD-003", "CD-002"]

    latest = page["items"][0]
    assert latest["proposal_count"] == 2
    assert latest["latest_proposal"]["title"] == "第 2 版方案"
    assert len(latest["proposals"]) == 2  # Compatibility with the existing admin page.
    assert "workbench" not in latest["proposals"][0]
    assert "description" not in latest["proposals"][0]
    assert "report_summary" not in latest
    assert "design_brief" not in latest
    assert "events" not in latest
    assert "draft" not in latest
    assert latest["deposit"] == {
        "amount_fee": 990,
        "currency": "CNY",
        "status": "paid",
        "amount_text": "9.90",
    }
    assert latest["request"]["style_preference"] == "清透自然"
    assert "assessment_id" not in latest["request"]
    assert "unexpected_private_field" not in latest["request"]
    assert page["items"][1]["report_code"] == "RPT-20260806-0002"

    queue_queries = "\n".join(queries).lower()
    assert "from (select request_id" in queue_queries
    assert "limit 2 offset 0" in queue_queries
    assert "output_snapshot_json" not in queue_queries
    assert "input_snapshot_json" not in queue_queries
    assert "workbench_json" not in queue_queries
    assert "custom_design_events" not in queue_queries
    assert "custom_design_drafts" not in queue_queries
    assert "from custom_design_proposals" in queue_queries

    second_page = service.list_for_admin(status="submitted", limit=1, offset=0)
    assert isinstance(second_page, list)
    assert [item["request_id"] for item in second_page] == ["CD-001"]


def test_admin_queue_endpoint_keeps_default_array_and_opt_in_pagination(monkeypatch):
    calls: list[dict] = []

    class FakeAdminService:
        @staticmethod
        def require_admin(token):
            assert token == "queue-token"
            return {"admin_id": "admin-1", "role": "operator"}

    class FakeCustomDesignService:
        @staticmethod
        def list_for_admin(**kwargs):
            calls.append(kwargs)
            if kwargs["include_meta"]:
                return {"items": [{"request_id": "CD-1"}], "total": 1, "limit": 20, "offset": 40}
            return [{"request_id": "CD-1"}]

    monkeypatch.setattr(admin_api, "admin_service", FakeAdminService())
    monkeypatch.setattr(admin_api, "custom_design_service", FakeCustomDesignService())

    paged = client.get(
        "/api/v1/admin/custom-design-requests?status=designing&limit=20&offset=40&include_meta=true",
        headers={"Authorization": "Bearer queue-token"},
    )
    assert paged.status_code == 200
    assert paged.json()["data"] == {
        "items": [{"request_id": "CD-1"}],
        "total": 1,
        "limit": 20,
        "offset": 40,
    }
    assert calls[-1] == {
        "status": "designing",
        "limit": 20,
        "offset": 40,
        "include_meta": True,
    }

    legacy = client.get(
        "/api/v1/admin/custom-design-requests",
        headers={"Authorization": "Bearer queue-token"},
    )
    assert legacy.status_code == 200
    assert legacy.json()["data"] == [{"request_id": "CD-1"}]
    assert calls[-1] == {
        "status": "",
        "limit": 100,
        "offset": 0,
        "include_meta": False,
    }
