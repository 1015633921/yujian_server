from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import admin_api as admin_api_module
from app import api as api_module
from app.admin_service import AdminService
from app.main import app
from app.order_service import OrderService, now_iso


client = TestClient(app)


def seed_shipped_order(service: OrderService, order_id: str = "ORDER-KD100-1") -> dict:
    timestamp = now_iso()
    logistics = service.build_logistics(
        "顺丰速运",
        tracking_no="SF1234567890",
        carrier_code="shunfeng",
        phone_tail="5678",
    )
    with service.connect() as connection:
        connection.execute(
            """
            INSERT INTO orders
            (order_id, out_trade_no, user_id, status, payment_status, total_amount, total_fee,
             currency, receiver_json, design_json, sequence_json, bom_json, remark, payment_json,
             created_at, updated_at, paid_at, refund_json, logistics_json, status_history_json)
            VALUES (?, ?, 'user-kd100', 'shipped', 'paid', 1, 100, 'CNY', '{}', '{}', '[]',
                    '[]', '', '{}', ?, ?, ?, '{}', ?, ?)
            """,
            (
                order_id,
                f"OUT-{order_id}",
                timestamp,
                timestamp,
                timestamp,
                json.dumps(logistics, ensure_ascii=False),
                json.dumps([{"status": "shipped", "label": "后台已发货", "time": timestamp}], ensure_ascii=False),
            ),
        )
    return logistics


def configure_subscription(monkeypatch, salt: str = "subscription-test-salt-32-bytes") -> str:
    monkeypatch.setenv("KUAIDI100_SUBSCRIBE_ENABLED", "true")
    monkeypatch.setenv("KUAIDI100_CUSTOMER", "test-customer")
    monkeypatch.setenv("KUAIDI100_KEY", "test-key")
    monkeypatch.setenv(
        "KUAIDI100_CALLBACK_URL",
        "https://api.example.test/api/v1/logistics/kuaidi100/callback",
    )
    monkeypatch.setenv("KUAIDI100_CALLBACK_SALT", salt)
    return salt


def callback_param(
    *,
    monitor_status: str = "polling",
    state: str = "0",
    ischeck: str = "0",
    event_time: str = "2026-07-13 12:00:00",
    context: str = "快件已揽收",
) -> str:
    payload = {
        "status": monitor_status,
        "message": "ok",
        "lastResult": {
            "message": "ok",
            "state": state,
            "ischeck": ischeck,
            "com": "shunfeng",
            "nu": "SF1234567890",
            "data": [
                {
                    "ftime": event_time,
                    "areaName": "成都市",
                    "context": context,
                }
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def callback_sign(param_text: str, salt: str) -> str:
    return hashlib.md5(f"{param_text}{salt}".encode("utf-8")).hexdigest().upper()


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self.payload


class FakeClient:
    def __init__(self, response: FakeResponse, calls: list[dict]) -> None:
        self.response = response
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, url: str, data: dict, headers: dict):
        self.calls.append({"url": url, "data": data, "headers": headers})
        return self.response


def install_fake_http(monkeypatch, payload: dict) -> list[dict]:
    calls: list[dict] = []
    response = FakeResponse(payload)
    monkeypatch.setattr(
        "app.order_service.httpx.Client",
        lambda *args, **kwargs: FakeClient(response, calls),
    )
    return calls


def test_subscription_is_fail_closed_and_disabled_by_default(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    monkeypatch.delenv("KUAIDI100_SUBSCRIBE_ENABLED", raising=False)

    result = service.subscribe_order_logistics("ORDER-KD100-1")

    assert result == {"enabled": False, "status": "disabled", "replayed": False}
    assert "subscription_status" not in service.get_order("ORDER-KD100-1")["logistics"]


def test_subscription_uses_official_payload_and_is_idempotent(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    configure_subscription(monkeypatch)
    calls = install_fake_http(monkeypatch, {"result": True, "returnCode": "200", "message": "成功"})

    first = service.subscribe_order_logistics("ORDER-KD100-1")
    second = service.subscribe_order_logistics("ORDER-KD100-1")

    assert first["status"] == "active"
    assert second == {"enabled": True, "status": "active", "replayed": True}
    assert len(calls) == 1
    assert calls[0]["url"] == "https://poll.kuaidi100.com/poll"
    assert calls[0]["data"]["schema"] == "json"
    payload = json.loads(calls[0]["data"]["param"])
    assert payload["company"] == "shunfeng"
    assert payload["number"] == "SF1234567890"
    assert payload["key"] == "test-key"
    assert payload["parameters"]["phone"] == "5678"
    assert payload["parameters"]["resultv2"] == "1"
    callback_query = parse_qs(urlsplit(payload["parameters"]["callbackurl"]).query)
    assert callback_query == {"order_id": ["ORDER-KD100-1"]}
    stored = service.get_order("ORDER-KD100-1")["logistics"]
    assert stored["subscription_status"] == "active"
    assert "test-key" not in json.dumps(stored)
    assert "subscription-test-salt" not in json.dumps(stored)


def test_subscription_failure_does_not_rollback_shipping(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    configure_subscription(monkeypatch)
    install_fake_http(monkeypatch, {"result": False, "returnCode": "400", "message": "参数错误"})

    result = service.subscribe_order_logistics("ORDER-KD100-1")
    order = service.get_order("ORDER-KD100-1")

    assert result["status"] == "failed"
    assert order["status"] == "shipped"
    assert order["logistics"]["subscription_status"] == "failed"
    assert order["logistics"]["subscription_attempts"] == 1


def test_provider_duplicate_subscription_is_treated_as_active(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    configure_subscription(monkeypatch)
    calls = install_fake_http(monkeypatch, {"result": False, "returnCode": "501", "message": "重复订阅"})

    result = service.subscribe_order_logistics("ORDER-KD100-1")

    assert result == {"enabled": True, "status": "active", "replayed": True, "return_code": "501"}
    assert len(calls) == 1


def test_signed_callback_is_verified_deduplicated_and_keeps_order_waiting_for_receipt(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    salt = configure_subscription(monkeypatch)
    param_text = callback_param(
        monitor_status="shutdown",
        state="3",
        ischeck="1",
        event_time="2026-07-13 14:30:00",
        context="快件已签收",
    )
    sign = callback_sign(param_text, salt)

    first = service.handle_kuaidi100_callback("ORDER-KD100-1", param_text, sign)
    second = service.handle_kuaidi100_callback("ORDER-KD100-1", param_text, sign)
    order = service.get_order("ORDER-KD100-1")

    assert first == {"duplicate": False, "signed": True, "monitor_status": "shutdown"}
    assert second == {"duplicate": True, "signed": True, "monitor_status": "shutdown"}
    assert order["status"] == "shipped"
    assert order["logistics"]["status"] == "signed"
    assert order["logistics"]["sync_mode"] == "push"
    assert order["logistics"]["subscription_status"] == "completed"
    signed_at = service.parse_logistics_time(order["logistics"]["signed_at"])
    auto_complete_at = service.parse_logistics_time(order["logistics"]["auto_complete_at"])
    assert signed_at == datetime(2026, 7, 13, 6, 30, tzinfo=timezone.utc)
    assert auto_complete_at == signed_at + timedelta(days=7)
    assert order["logistics_signed_at"] == order["logistics"]["signed_at"]
    assert order["auto_complete_at"] == order["logistics"]["auto_complete_at"]
    assert any(trace["desc"] == "快件已签收" for trace in order["logistics"]["traces"])
    assert any("商家已打包" in trace["desc"] for trace in order["logistics"]["traces"])
    completion_events = [item for item in order["status_history"] if item["status"] == "completed"]
    assert completion_events == []


def test_signed_order_auto_completes_after_seven_days_and_is_idempotent(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    salt = configure_subscription(monkeypatch)
    param_text = callback_param(
        monitor_status="shutdown",
        state="3",
        ischeck="1",
        event_time="2026-07-13 14:30:00",
        context="快件已签收",
    )
    service.handle_kuaidi100_callback("ORDER-KD100-1", param_text, callback_sign(param_text, salt))
    signed_at = service.parse_logistics_time(
        service.get_order("ORDER-KD100-1")["logistics"]["signed_at"]
    )
    assert signed_at is not None

    early = service.complete_signed_orders_due(now=signed_at + timedelta(days=7, seconds=-1))
    assert early["completed"] == 0
    assert service.get_order("ORDER-KD100-1")["status"] == "shipped"

    due = service.complete_signed_orders_due(now=signed_at + timedelta(days=7))
    repeated = service.complete_signed_orders_due(now=signed_at + timedelta(days=8))
    order = service.get_order("ORDER-KD100-1")
    assert due["completed"] == 1
    assert repeated["completed"] == 0
    assert order["status"] == "completed"
    completion_events = [item for item in order["status_history"] if item["status"] == "completed"]
    assert [item["label"] for item in completion_events] == ["快递签收满7天，订单自动完成"]


def test_user_confirmation_completes_signed_order_before_deadline(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    salt = configure_subscription(monkeypatch)
    param_text = callback_param(
        monitor_status="shutdown",
        state="3",
        ischeck="1",
        event_time="2026-07-13 14:30:00",
        context="快件已签收",
    )
    service.handle_kuaidi100_callback("ORDER-KD100-1", param_text, callback_sign(param_text, salt))

    confirmed = service.confirm_receipt("ORDER-KD100-1", "user-kd100")
    repeated = service.confirm_receipt("ORDER-KD100-1", "user-kd100")

    assert confirmed["status"] == "completed"
    assert repeated["status"] == "completed"
    completion_events = [item for item in repeated["status_history"] if item["status"] == "completed"]
    assert [item["label"] for item in completion_events] == ["用户确认收货"]


def test_admin_generic_status_update_route_is_absent(tmp_path):
    database = tmp_path / "orders.db"
    service = OrderService(database)
    seed_shipped_order(service)
    admin = AdminService(database)

    assert not hasattr(admin, "update_order_status")
    assert "/api/v1/admin/orders/{order_id}/status" not in {
        route.path for route in app.routes if hasattr(route, "path")
    }
    assert service.get_order("ORDER-KD100-1")["status"] == "shipped"


def test_user_confirmation_and_auto_completion_race_creates_one_completion_event(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    salt = configure_subscription(monkeypatch)
    param_text = callback_param(
        monitor_status="shutdown",
        state="3",
        ischeck="1",
        event_time="2026-07-13 14:30:00",
        context="快件已签收",
    )
    service.handle_kuaidi100_callback("ORDER-KD100-1", param_text, callback_sign(param_text, salt))
    signed_at = service.parse_logistics_time(
        service.get_order("ORDER-KD100-1")["logistics"]["signed_at"]
    )
    assert signed_at is not None

    actions = [
        lambda: service.confirm_receipt("ORDER-KD100-1", "user-kd100"),
        lambda: service.complete_signed_order_if_due(
            "ORDER-KD100-1",
            signed_at + timedelta(days=7),
        ),
    ]
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda action: action(), actions))

    order = service.get_order("ORDER-KD100-1")
    completion_events = [item for item in order["status_history"] if item["status"] == "completed"]
    assert order["status"] == "completed"
    assert len(completion_events) == 1


def test_out_of_order_callback_and_polling_result_cannot_regress_signed_state(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    salt = configure_subscription(monkeypatch)
    signed_param = callback_param(
        monitor_status="shutdown",
        state="3",
        ischeck="1",
        event_time="2026-07-13 15:00:00",
        context="本人签收",
    )
    service.handle_kuaidi100_callback("ORDER-KD100-1", signed_param, callback_sign(signed_param, salt))
    signed_order = service.get_order("ORDER-KD100-1")
    signed_at = signed_order["logistics"]["signed_at"]
    auto_complete_at = signed_order["logistics"]["auto_complete_at"]
    old_param = callback_param(
        monitor_status="polling",
        state="1",
        event_time="2026-07-13 13:00:00",
        context="快件已揽收",
    )
    service.handle_kuaidi100_callback("ORDER-KD100-1", old_param, callback_sign(old_param, salt))
    old_abort = callback_param(
        monitor_status="abort",
        state="0",
        event_time="2026-07-13 12:30:00",
        context="历史订阅终止通知",
    )
    service.handle_kuaidi100_callback("ORDER-KD100-1", old_abort, callback_sign(old_abort, salt))
    merged = service.update_logistics(
        "ORDER-KD100-1",
        {
            "status": "in_transit",
            "status_text": "运输中",
            "source": "kuaidi100",
            "latest_event_time": "2026-07-13 12:00:00",
            "traces": [{"time": "2026-07-13 12:00:00", "location": "成都市", "desc": "运输中"}],
        },
    )

    assert merged["status"] == "signed"
    assert merged["subscription_status"] == "completed"
    assert merged["latest_event_time"] == "2026-07-13 15:00:00"
    assert merged["signed_at"] == signed_at
    assert merged["auto_complete_at"] == auto_complete_at
    assert {trace["desc"] for trace in merged["traces"]} >= {"本人签收", "快件已揽收", "运输中"}


def test_abort_callback_is_persisted_without_completing_order(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    salt = configure_subscription(monkeypatch)
    param_text = callback_param(monitor_status="abort", context="三天无轨迹")

    result = service.handle_kuaidi100_callback(
        "ORDER-KD100-1",
        param_text,
        callback_sign(param_text, salt),
    )
    order = service.get_order("ORDER-KD100-1")

    assert result["monitor_status"] == "abort"
    assert order["status"] == "shipped"
    assert order["logistics"]["subscription_status"] == "aborted"
    assert order["logistics"]["sync_error"] is True
    calls = install_fake_http(monkeypatch, {"result": True, "returnCode": "200", "message": "成功"})
    assert service.subscribe_order_logistics("ORDER-KD100-1") == {
        "enabled": True,
        "status": "cooldown",
        "replayed": True,
    }
    assert calls == []


def test_callback_rejects_invalid_signature_and_tracking_mismatch(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    salt = configure_subscription(monkeypatch)
    param_text = callback_param()
    with pytest.raises(ValueError, match="签名无效"):
        service.handle_kuaidi100_callback("ORDER-KD100-1", param_text, "BAD")

    payload = json.loads(param_text)
    payload["lastResult"]["nu"] = "SF-NOT-THIS-ORDER"
    wrong_tracking = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with pytest.raises(ValueError, match="单号与订单不一致"):
        service.handle_kuaidi100_callback(
            "ORDER-KD100-1",
            wrong_tracking,
            callback_sign(wrong_tracking, salt),
        )


def test_callback_accepts_provider_signed_company_correction(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    salt = configure_subscription(monkeypatch)
    payload = json.loads(callback_param())
    payload.update({"autoCheck": "1", "comOld": "shunfeng", "comNew": "ems"})
    payload["lastResult"]["com"] = "ems"
    param_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    service.handle_kuaidi100_callback(
        "ORDER-KD100-1",
        param_text,
        callback_sign(param_text, salt),
    )

    logistics = service.get_order("ORDER-KD100-1")["logistics"]
    assert logistics["carrier_code"] == "ems"
    assert logistics["carrier_code_corrected_from"] == "shunfeng"


def test_public_callback_endpoint_returns_provider_ack_without_user_auth(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "orders.db")
    seed_shipped_order(service)
    salt = configure_subscription(monkeypatch)
    monkeypatch.setattr(api_module, "order_service", service)
    param_text = callback_param()

    response = client.post(
        "/api/v1/logistics/kuaidi100/callback?order_id=ORDER-KD100-1",
        data={"param": param_text, "sign": callback_sign(param_text, salt)},
    )
    rejected = client.post(
        "/api/v1/logistics/kuaidi100/callback?order_id=ORDER-KD100-1",
        data={"param": param_text, "sign": "BAD"},
    )

    assert response.status_code == 200
    assert response.json() == {"result": True, "returnCode": "200", "message": "成功"}
    assert rejected.status_code == 401
    assert rejected.json()["result"] is False


def test_admin_shipping_submits_subscription_and_exposes_retry_state(tmp_path, monkeypatch):
    database = tmp_path / "orders.db"
    service = OrderService(database)
    seed_shipped_order(service)
    admin = AdminService(database)
    admin.register("shipping-admin", "Strong-Password-2026")
    token = admin.login("shipping-admin", "Strong-Password-2026")["token"]
    configure_subscription(monkeypatch)
    calls = install_fake_http(monkeypatch, {"result": True, "returnCode": "200", "message": "成功"})
    monkeypatch.setattr(admin_api_module, "admin_service", admin)
    monkeypatch.setattr(admin_api_module, "order_service", service)

    response = client.post(
        "/api/v1/admin/orders/ORDER-KD100-1/ship",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "carrier": "顺丰速运",
            "tracking_no": "SF1234567890",
            "carrier_code": "shunfeng",
            "phone_tail": "5678",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["logistics_subscription"]["status"] == "active"
    assert response.json()["data"]["logistics"]["subscription_status"] == "active"
    assert len(calls) == 1
