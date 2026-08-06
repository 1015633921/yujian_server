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
    database = tmp_path / "custom-design-admin-detail.db"
    AssessmentRepository(database)
    AdminService(database)
    OrderService(database)
    upgrade("sqlite", database)
    service = CustomDesignService(database)
    timestamp = "2026-08-06T09:00:00Z"
    report_output = {
        "report_projection": {
            "core_conclusion": {"title": "平衡设计方向", "description": "清透、稳定"},
            "elements": [{"element": "水", "score": 72}],
            "keywords": ["清透", "稳定"],
        },
        "report_context": {"core_wishes": ["日常舒缓"]},
    }
    with service.connect() as connection:
        connection.execute(
            """
            INSERT INTO report_snapshots
            (report_id, assessment_id, user_id, report_version, source_input_hash,
             algorithm_version, schema_version, calibration_version,
             calibration_status, calibration_source, calibration_reason_code,
             input_snapshot_json, output_snapshot_json, created_at, report_code)
            VALUES ('report-001', 'assessment-001', 'user-1', 1, 'hash', 'algorithm', 1,
                    'calibration', 'ready', 'test', '', '{}', ?, ?, 'RPT-20260806-0001')
            """,
            (json.dumps(report_output, ensure_ascii=False), timestamp),
        )
        request = {
            "assessment_id": "assessment-001",
            "wrist_size_cm": 16,
            "bead_size_mm": 8,
            "budget": "300–500 元",
            "style_preference": "清透自然",
            "color_preference": "蓝白",
            "accessory_preference": "少量银饰",
            "wear_scene": "日常佩戴",
            "unexpected_private_field": "must-not-leak",
        }
        connection.execute(
            """
            INSERT INTO custom_design_requests
            (request_id, user_id, report_id, report_version, request_json, status,
             first_draft_due_at, created_at, updated_at)
            VALUES ('CD-001', 'user-1', 'report-001', 1, ?, 'designing',
                    '2026-08-07T09:00:00Z', ?, ?)
            """,
            (json.dumps(request, ensure_ascii=False), timestamp, timestamp),
        )
        connection.execute(
            """
            INSERT INTO custom_design_deposits
            (deposit_id, request_id, user_id, out_trade_no, amount_fee, currency, status,
             payment_json, refund_json, created_at, updated_at)
            VALUES ('DEP-001', 'CD-001', 'user-1', 'trade-001', 990, 'CNY', 'paid',
                    '{}', '{}', ?, ?)
            """,
            (timestamp, timestamp),
        )
        connection.execute(
            """
            INSERT INTO custom_design_proposals
            (proposal_id, request_id, proposal_version, title, description, image_urls_json,
             workbench_json, order_id, confirmed_at, status, created_by, created_at)
            VALUES ('proposal-001', 'CD-001', 1, '清透专属款', '方案完整说明',
                    '["https://cdn.example.com/design.webp"]', ?, '', NULL, 'active',
                    'designer-1', ?)
            """,
            (json.dumps({"wrist_size_cm": 16, "bead_size_mm": 8, "layout": [{"material_id": "bead-1"}] * 30}), timestamp),
        )
        connection.execute(
            """
            INSERT INTO custom_design_drafts
            (draft_id, request_id, draft_version, workbench_json, created_by, created_at, updated_at)
            VALUES ('draft-001', 'CD-001', 2, ?, 'designer-1', ?, ?)
            """,
            (json.dumps({"layout": ["large-draft"] * 100}), timestamp, timestamp),
        )
        connection.execute(
            """
            INSERT INTO custom_design_events
            (event_id, request_id, event_type, from_status, to_status, actor_type,
             actor_id, note, created_at)
            VALUES ('event-001', 'CD-001', 'draft_saved', 'submitted', 'designing',
                    'admin', 'designer-1', '已保存草稿', ?)
            """,
            (timestamp,),
        )
    return service


def test_admin_detail_overview_is_small_and_regions_are_loaded_on_demand(tmp_path):
    service = _service(tmp_path)
    queries: list[str] = []
    original_connect = service.connect

    def traced_connect():
        connection = original_connect()
        connection.set_trace_callback(queries.append)
        return connection

    service.connect = traced_connect
    overview = service.get_admin_overview("CD-001")

    assert overview["report_code"] == "RPT-20260806-0001"
    assert overview["design_brief"]
    assert overview["latest_proposal"]["title"] == "清透专属款"
    assert overview["draft"] == {
        "draft_id": "draft-001",
        "draft_version": 2,
        "created_by": "designer-1",
        "created_at": "2026-08-06T09:00:00Z",
        "updated_at": "2026-08-06T09:00:00Z",
    }
    assert "report_summary" not in overview
    assert "proposals" not in overview
    assert "events" not in overview
    assert "workbench" not in overview
    assert "assessment_id" not in overview["request"]
    assert "unexpected_private_field" not in overview["request"]
    overview_queries = "\n".join(queries).lower()
    assert "workbench_json" not in overview_queries
    assert "custom_design_events" not in overview_queries

    evidence = service.get_admin_assessment_evidence("CD-001")
    assert evidence["report_summary"]["keywords"] == ["清透", "稳定"]
    proposals = service.list_admin_proposals("CD-001")
    assert proposals[0]["image_urls"] == ["https://cdn.example.com/design.webp"]
    assert "workbench" not in proposals[0]
    composition = service.get_admin_proposal_composition("CD-001", "proposal-001")
    assert len(composition["layout"]) == 30
    assert service.list_admin_events("CD-001")[0]["note"] == "已保存草稿"


def test_admin_workbench_restores_only_current_draft_or_latest_proposal(tmp_path):
    service = _service(tmp_path)
    source = service.get_admin_workbench("CD-001")

    assert source["source_kind"] == "draft"
    assert source["overview"]["request_id"] == "CD-001"
    assert source["workbench"]["layout"] == ["large-draft"] * 100
    assert source["proposal"] is None

    with service.connect() as connection:
        connection.execute("DELETE FROM custom_design_drafts WHERE request_id = 'CD-001'")
    from_proposal = service.get_admin_workbench("CD-001")
    assert from_proposal["source_kind"] == "proposal"
    assert from_proposal["proposal"] == {
        "proposal_id": "proposal-001",
        "proposal_version": 1,
        "title": "清透专属款",
        "description": "方案完整说明",
        "image_urls": ["https://cdn.example.com/design.webp"],
        "status": "active",
        "created_at": "2026-08-06T09:00:00Z",
    }
    assert len(from_proposal["workbench"]["layout"]) == 30


def test_admin_detail_v2_endpoints_require_admin_and_keep_legacy_detail(monkeypatch):
    calls: list[tuple[str, str]] = []

    class FakeAdminService:
        @staticmethod
        def require_admin(token):
            assert token == "detail-token"
            return {"admin_id": "admin-1"}

    class FakeCustomDesignService:
        @staticmethod
        def get_for_admin(request_id):
            calls.append(("legacy", request_id))
            return {"request_id": request_id, "workbench": "legacy-full"}

        @staticmethod
        def get_admin_overview(request_id):
            calls.append(("overview", request_id))
            return {"request_id": request_id}

        @staticmethod
        def get_admin_workbench(request_id):
            calls.append(("workbench", request_id))
            return {"overview": {"request_id": request_id}, "source_kind": "empty", "workbench": {}}

        @staticmethod
        def get_admin_assessment_evidence(request_id):
            calls.append(("evidence", request_id))
            return {"request_id": request_id}

        @staticmethod
        def list_admin_proposals(request_id):
            calls.append(("proposals", request_id))
            return []

        @staticmethod
        def get_admin_proposal_composition(request_id, proposal_id):
            calls.append(("composition", f"{request_id}:{proposal_id}"))
            return {"proposal_id": proposal_id, "layout": []}

        @staticmethod
        def list_admin_events(request_id):
            calls.append(("events", request_id))
            return []

    monkeypatch.setattr(admin_api, "admin_service", FakeAdminService())
    monkeypatch.setattr(admin_api, "custom_design_service", FakeCustomDesignService())
    headers = {"Authorization": "Bearer detail-token"}

    assert client.get("/api/v1/admin/custom-design-requests/CD-1", headers=headers).json()["data"]["workbench"] == "legacy-full"
    assert client.get("/api/v1/admin/custom-design-requests/CD-1/overview", headers=headers).json()["data"] == {"request_id": "CD-1"}
    assert client.get("/api/v1/admin/custom-design-requests/CD-1/workbench", headers=headers).json()["data"]["source_kind"] == "empty"
    assert client.get("/api/v1/admin/custom-design-requests/CD-1/assessment-evidence", headers=headers).status_code == 200
    assert client.get("/api/v1/admin/custom-design-requests/CD-1/proposals", headers=headers).status_code == 200
    assert client.get("/api/v1/admin/custom-design-requests/CD-1/proposals/P-1/composition", headers=headers).json()["data"]["proposal_id"] == "P-1"
    assert client.get("/api/v1/admin/custom-design-requests/CD-1/events", headers=headers).status_code == 200
    assert calls == [
        ("legacy", "CD-1"),
        ("overview", "CD-1"),
        ("workbench", "CD-1"),
        ("evidence", "CD-1"),
        ("proposals", "CD-1"),
        ("composition", "CD-1:P-1"),
        ("events", "CD-1"),
    ]
