from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.admin_service import AdminService
from app.main import app
from app.migrations.runner import downgrade, upgrade
from app.observability import JsonLogFormatter, bind_request_id, metrics, reset_request_id
from app.order_service import Kuaidi100Config, OrderService
from app.repository import AssessmentRepository
from app.runtime_health import readiness
from app.runtime_tasks import LogisticsTaskRunner


client = TestClient(app, raise_server_exceptions=False)


def runtime_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "p1c-runtime.db"
    AdminService(db_path)
    OrderService(db_path)
    AssessmentRepository(db_path)
    upgrade("sqlite", db_path)
    return db_path


def test_web_process_does_not_start_logistics_thread():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert "threading.Thread" not in source
    assert "logistics_sync_loop" not in source
    assert "start_logistics_sync_worker" not in source


def test_two_workers_share_database_lease_and_execute_once(tmp_path, monkeypatch):
    db_path = runtime_db(tmp_path)
    monkeypatch.setenv("LOGISTICS_SYNC_ENABLED", "true")
    calls = 0
    lock = threading.Lock()

    class FakeOrders:
        def refresh_active_shipments(self, limit=50):
            nonlocal calls
            with lock:
                calls += 1
            time.sleep(0.05)
            return {"checked": 1, "failed_order_ids": []}

    def run(owner):
        return LogisticsTaskRunner(
            db_path,
            order_service=FakeOrders(),
            sleep_fn=lambda _seconds: None,
            owner_id=owner,
        ).run_once()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, ("worker-a", "worker-b")))
    assert calls == 1
    assert sum(result["executed"] for result in results) == 1
    assert {result["status"] for result in results} == {"completed", "skipped_locked"}


def test_logistics_retries_only_failed_orders_with_bounded_attempts(tmp_path, monkeypatch):
    db_path = runtime_db(tmp_path)
    monkeypatch.setenv("LOGISTICS_SYNC_ENABLED", "true")
    monkeypatch.setenv("LOGISTICS_SYNC_MAX_ATTEMPTS", "3")

    class FakeOrders:
        retries = 0

        def refresh_active_shipments(self, limit=50):
            return {"checked": 2, "failed_order_ids": ["order-bad"]}

        def refresh_order_logistics(self, order_id, force=False):
            assert order_id == "order-bad"
            self.retries += 1
            return {"order_id": order_id, "logistics": {"sync_error": self.retries < 2}}

    orders = FakeOrders()
    result = LogisticsTaskRunner(
        db_path,
        order_service=orders,
        sleep_fn=lambda _seconds: None,
        owner_id="retry-worker",
    ).run_once()
    assert result == {
        "status": "completed",
        "executed": True,
        "run_id": result["run_id"],
        "checked": 2,
        "failed": 0,
        "attempts": 3,
    }
    assert orders.retries == 2
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT status, attempt_count, checked_count, failed_count FROM runtime_task_runs"
        ).fetchone()
    assert row == ("completed", 3, 2, 0)


def test_logistics_retries_transient_batch_failure_without_infinite_loop(tmp_path, monkeypatch):
    db_path = runtime_db(tmp_path)
    monkeypatch.setenv("LOGISTICS_SYNC_ENABLED", "true")
    monkeypatch.setenv("LOGISTICS_SYNC_MAX_ATTEMPTS", "3")

    class FlakyOrders:
        calls = 0

        def refresh_active_shipments(self, limit=50):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("transient")
            return {"checked": 1, "failed_order_ids": []}

    orders = FlakyOrders()
    result = LogisticsTaskRunner(
        db_path,
        order_service=orders,
        sleep_fn=lambda _seconds: None,
        owner_id="flaky-worker",
    ).run_once()
    assert result["status"] == "completed"
    assert result["attempts"] == 2
    assert orders.calls == 2


def test_disabled_logistics_worker_does_not_construct_runner(monkeypatch):
    from app import logistics_worker

    monkeypatch.setenv("LOGISTICS_SYNC_ENABLED", "false")
    monkeypatch.setattr(
        logistics_worker,
        "LogisticsTaskRunner",
        lambda: (_ for _ in ()).throw(AssertionError("disabled worker must not touch the database")),
    )
    assert logistics_worker.run(once=True) == 0


def test_request_id_is_generated_propagated_and_repeatable():
    generated = client.get("/health/live")
    request_id = generated.headers["X-Request-ID"]
    assert request_id.startswith("req_") and len(request_id) >= 20

    custom = "trace-client-1234"
    first = client.get("/health/live", headers={"X-Request-ID": custom})
    second = client.get("/health/live", headers={"X-Request-ID": custom})
    assert first.headers["X-Request-ID"] == second.headers["X-Request-ID"] == custom

    invalid = client.get("/health/live", headers={"X-Request-ID": "bad id"})
    assert invalid.headers["X-Request-ID"].startswith("req_")


def test_validation_and_http_errors_include_request_id_without_echoing_input(monkeypatch):
    request_id = "trace-error-1234"
    invalid = client.post(
        "/api/v1/auth/wechat-login",
        headers={"X-Request-ID": request_id},
        json={"code": "x", "nickname": "13800138000 Secret Address" * 10},
    )
    body = invalid.json()
    serialized = json.dumps(body, ensure_ascii=False)
    assert invalid.status_code == 422
    assert body["request_id"] == request_id
    assert "13800138000" not in serialized
    assert "Secret Address" not in serialized

    monkeypatch.setenv("COMMERCE_CHECKOUT_ENABLED", "false")
    unauthorized_feature = client.post(
        "/api/v1/orders",
        headers={"X-Request-ID": request_id},
        json={},
    )
    assert unauthorized_feature.status_code in {401, 422}
    assert unauthorized_feature.json()["request_id"] == request_id


def test_unhandled_exception_returns_safe_error_with_request_id(monkeypatch):
    from app import main as main_module

    monkeypatch.setattr(
        main_module,
        "readiness",
        lambda: (_ for _ in ()).throw(RuntimeError("SQL secret /private/server/path 13800138000")),
    )
    response = client.get("/health/ready", headers={"X-Request-ID": "trace-crash-1234"})
    serialized = json.dumps(response.json(), ensure_ascii=False)
    assert response.status_code == 500
    assert response.json()["request_id"] == "trace-crash-1234"
    assert "SQL secret" not in serialized
    assert "/private/server/path" not in serialized
    assert "13800138000" not in serialized


def test_structured_log_formatter_redacts_sensitive_values():
    record = logging.LogRecord(
        name="yujian.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Bearer abcdefghijklmnopqrstuvwxyz 13800138000",
        args=(),
        exc_info=None,
    )
    record.event = "security.test"
    record.structured_fields = {
        "token": "top-secret-token",
        "openid": "oSensitiveOpenidValue123456789",
        "phone": "13800138000",
        "address": "某省某市详细地址",
        "user_id": "private-user-id",
    }
    output = JsonLogFormatter().format(record)
    for forbidden in (
        "top-secret-token", "oSensitiveOpenidValue123456789", "13800138000",
        "某省某市详细地址", "private-user-id",
    ):
        assert forbidden not in output
    assert "user_id_hash" in output


def test_readiness_checks_database_and_required_configuration(tmp_path, monkeypatch):
    db_path = runtime_db(tmp_path)
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    assert readiness(db_path)["ready"] is True
    assert readiness(tmp_path / "missing.db")["ready"] is False

    monkeypatch.setenv("DATABASE_BACKEND", "invalid")
    result = readiness(db_path)
    assert result["ready"] is False
    assert "DATABASE_BACKEND_INVALID" in result["missing_config"]

    from app import main as main_module
    monkeypatch.setattr(main_module, "readiness", lambda: {"ready": False, "checks": {}, "missing_config": [], "missing_tables": []})
    assert client.get("/health/ready").status_code == 503
    assert client.get("/health/live").status_code == 200


def test_metrics_endpoint_is_closed_by_default_and_requires_token(monkeypatch):
    monkeypatch.delenv("METRICS_ENDPOINT_ENABLED", raising=False)
    assert client.get("/internal/metrics").status_code == 404

    monkeypatch.setenv("METRICS_ENDPOINT_ENABLED", "true")
    monkeypatch.setenv("METRICS_ACCESS_TOKEN", "metrics-test-secret")
    assert client.get("/internal/metrics").status_code == 401
    response = client.get(
        "/internal/metrics",
        headers={"Authorization": "Bearer metrics-test-secret"},
    )
    assert response.status_code == 200
    names = {item["name"] for item in response.json()["data"]["counters"]}
    assert {
        "login_success_total", "report_generate_total", "order_create_total",
        "payment_callback_total", "logistics_sync_total", "api_request_total",
    }.issubset(names)


def test_login_business_metrics_increment_for_success_and_failure(monkeypatch):
    from app import api as api_module

    def total(name):
        return sum(item["value"] for item in metrics.snapshot()["counters"] if item["name"] == name)

    success_before = total("login_success_total")
    failed_before = total("login_failed_total")
    monkeypatch.setattr(
        api_module.auth_service,
        "login",
        lambda *_args, **_kwargs: {
            "user_id": "p1c-metric-user",
            "nickname": "",
            "avatar_url": "",
            "gender": "",
            "has_profile": False,
            "has_phone": False,
        },
    )
    assert client.post("/api/v1/auth/wechat-login", json={"code": "metric-success"}).status_code == 200
    assert total("login_success_total") == success_before + 1

    monkeypatch.setattr(
        api_module.auth_service,
        "login",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("safe login failure")),
    )
    assert client.post("/api/v1/auth/wechat-login", json={"code": "metric-failure"}).status_code == 400
    assert total("login_failed_total") == failed_before + 1


def test_kuaidi100_timeout_is_bounded_and_request_id_is_propagated(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "external.db")
    config = Kuaidi100Config()
    config.customer = "customer"
    config.key = "key"
    config.query_url = "https://example.invalid/query"
    captured = {}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, _url, **kwargs):
            captured["headers"] = kwargs["headers"]
            raise httpx.ReadTimeout("timeout", request=httpx.Request("POST", "https://example.invalid"))

    monkeypatch.setattr("app.order_service.httpx.Client", FakeClient)
    token = bind_request_id("trace-external-1234")
    try:
        try:
            service.query_kuaidi100(
                {"carrier_code": "zhongtong", "tracking_no": "TEST"},
                config,
            )
            raise AssertionError("timeout should fail")
        except ValueError as exc:
            assert "超时" in str(exc)
    finally:
        reset_request_id(token)
    assert captured["timeout"] == 10
    assert captured["headers"]["X-Request-ID"] == "trace-external-1234"


def test_p1c_runtime_migration_round_trip(tmp_path):
    db_path = runtime_db(tmp_path)
    with sqlite3.connect(db_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"runtime_task_leases", "runtime_task_runs"}.issubset(tables)
    assert downgrade("sqlite", db_path, steps=3) == [
        "20260713_07_order_receipt_completion",
        "20260712_06_p1_material_price_cents",
        "20260712_05_p1c_runtime_tasks",
    ]
    assert upgrade("sqlite", db_path) == [
        "20260712_05_p1c_runtime_tasks",
        "20260712_06_p1_material_price_cents",
        "20260713_07_order_receipt_completion",
    ]
