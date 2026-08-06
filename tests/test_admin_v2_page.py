from __future__ import annotations

from fastapi.testclient import TestClient

from app import admin_v2_page
from app.main import app


client = TestClient(app)


def test_admin_v2_deep_routes_inject_correct_asset_base_and_cache_headers(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text(
        "<!doctype html><html><head><script src=\"./assets/app.js\"></script></head><body></body></html>",
        encoding="utf-8",
    )
    monkeypatch.setattr(admin_v2_page, "ADMIN_V2_DIR", tmp_path)

    root = client.get("/admin-v2/design-requests/CD-001/workbench")
    test = client.get("/test-api/admin-v2/design-requests/CD-001/workbench")

    assert root.status_code == 200
    assert '<base href="/admin-v2/">' in root.text
    assert "no-store" in root.headers["cache-control"]
    assert test.status_code == 200
    assert '<base href="/test-api/admin-v2/">' in test.text

    dedicated_host = client.get(
        "/admin-v2/design-requests/CD-001/workbench",
        headers={"host": "operation-test.yustream.cn", "x-forwarded-host": "operation-test.yustream.cn"},
    )
    assert dedicated_host.status_code == 200
    assert '<base href="/">' in dedicated_host.text


def test_admin_v2_returns_service_unavailable_before_a_build_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(admin_v2_page, "ADMIN_V2_DIR", tmp_path)

    response = client.get("/admin-v2")

    assert response.status_code == 503
    assert response.json()["message"] == "服务暂时不可用"
