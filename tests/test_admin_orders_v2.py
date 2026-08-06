from __future__ import annotations

from fastapi.testclient import TestClient

from app import admin_api
from app.main import app


client = TestClient(app)


def test_order_list_meta_is_opt_in_and_keeps_legacy_array_contract(monkeypatch):
    calls: list[dict[str, object]] = []

    class FakeAdminService:
        @staticmethod
        def require_admin(token):
            assert token == "orders-token"
            return {"admin_id": "admin-1"}

        @staticmethod
        def list_orders(**kwargs):
            calls.append(kwargs)
            if kwargs["include_meta"]:
                return {"items": [{"order_id": "ORDER-002"}], "total": 8, "limit": 2, "offset": 4, "has_more": True}
            return [{"order_id": "ORDER-001"}]

    monkeypatch.setattr(admin_api, "admin_service", FakeAdminService())
    headers = {"Authorization": "Bearer orders-token"}

    legacy = client.get("/api/v1/admin/orders?status=pending_ship", headers=headers)
    paged = client.get("/api/v1/admin/orders?status=pending_ship&limit=2&offset=4&include_meta=true", headers=headers)

    assert legacy.status_code == 200
    assert legacy.json()["data"] == [{"order_id": "ORDER-001"}]
    assert paged.status_code == 200
    assert paged.json()["data"]["items"] == [{"order_id": "ORDER-002"}]
    assert calls == [
        {"keyword": "", "status": "pending_ship", "limit": 100, "offset": 0, "include_meta": False},
        {"keyword": "", "status": "pending_ship", "limit": 2, "offset": 4, "include_meta": True},
    ]
