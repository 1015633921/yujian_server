from __future__ import annotations

import json

import pytest

from app.custom_design_service import CustomDesignService
from app.order_service import OrderService, WechatPayConfig, now_iso


def configure_wechat(monkeypatch, environment: str = "test") -> None:
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("WECHAT_PAY_APP_ID", "wx-test-amount")
    monkeypatch.setenv("WECHAT_PAY_MCH_ID", "mch-test-amount")
    monkeypatch.setenv("WECHAT_PAY_SERIAL_NO", "serial-test-amount")
    monkeypatch.setenv("WECHAT_PAY_NOTIFY_URL", "https://test.example.com/wechat-pay/notify")
    monkeypatch.setenv("WECHAT_PAY_PRIVATE_KEY", "test-private-key")
    monkeypatch.setenv("WECHAT_PAYMENT_ENABLED", "true")


def test_test_environment_sends_one_cent_for_order_payment_and_refund(tmp_path, monkeypatch):
    configure_wechat(monkeypatch)
    service = OrderService(tmp_path / "test-payment-amount.db")
    requests = []
    monkeypatch.setattr(service, "wechat_request", lambda method, path, body, *_args, **_kwargs: requests.append((method, path, body)) or {"prepay_id": "wx-prepay"})
    monkeypatch.setattr(service, "build_miniprogram_pay_params", lambda *_args: {"package": "prepay_id=wx-prepay"})
    monkeypatch.setattr(service, "update_payment", lambda *_args, **_kwargs: None)
    order = {
        "order_id": "TEST-ORDER-1",
        "out_trade_no": "TEST-ORDER-1",
        "openid": "openid-test",
        "payment_status": "unpaid",
        "total_fee": 18900,
        "currency": "CNY",
        "payment": {"transaction_id": "WX-TEST-1"},
    }

    service.create_wechat_payment(order)
    service.create_wechat_refund(order, "RF-TEST-1", 18900, 18900, "测试退款", WechatPayConfig())

    assert requests[0][2]["amount"] == {"total": 1, "currency": "CNY"}
    assert requests[1][2]["amount"] == {"refund": 1, "total": 1, "currency": "CNY"}


def test_test_environment_uses_one_cent_for_custom_design_payment_and_refund_callbacks(tmp_path, monkeypatch):
    configure_wechat(monkeypatch)
    order_service = OrderService(tmp_path / "test-deposit-amount.db")
    service = CustomDesignService(tmp_path / "test-deposit-amount.db", order_service=order_service)
    timestamp = now_iso()
    with service.connect() as connection:
        connection.execute(
            "INSERT INTO custom_design_requests (request_id, user_id, report_id, report_version, request_json, status, first_draft_due_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'deposit_pending', NULL, ?, ?)",
            ("REQ-TEST-1", "user-test-1", "REPORT-TEST-1", 1, "{}", timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO custom_design_deposits (deposit_id, request_id, user_id, out_trade_no, amount_fee, currency, status, payment_json, refund_json, created_at, updated_at) VALUES (?, ?, ?, ?, 990, 'CNY', 'unpaid', '{}', '{}', ?, ?)",
            ("DEP-TEST-1", "REQ-TEST-1", "user-test-1", "TRADE-TEST-1", timestamp, timestamp),
        )
    requests = []
    monkeypatch.setattr(order_service, "get_user", lambda _user_id: {"openid": "openid-test"})
    monkeypatch.setattr(order_service, "wechat_request", lambda method, path, body, *_args, **_kwargs: requests.append((method, path, body)) or {"prepay_id": "wx-deposit"})
    monkeypatch.setattr(order_service, "build_miniprogram_pay_params", lambda *_args: {"package": "prepay_id=wx-deposit"})
    monkeypatch.setattr(service, "get_for_user", lambda *_args: {"deposit": {"deposit_id": "DEP-TEST-1", "status": "refunded"}})

    service.request_deposit_payment("REQ-TEST-1", "user-test-1")
    assert requests[0][2]["amount"] == {"total": 1, "currency": "CNY"}

    config = WechatPayConfig()
    service.handle_wechat_payment_transaction({
        "out_trade_no": "TRADE-TEST-1", "trade_state": "SUCCESS", "transaction_id": "WX-DEPOSIT-1",
        "appid": config.app_id, "mchid": config.mch_id, "amount": {"total": 1, "currency": "CNY"},
    }, config)
    with service.connect() as connection:
        connection.execute(
            "UPDATE custom_design_deposits SET status = 'refund_submitting', out_refund_no = 'RF-DEPOSIT-1' WHERE deposit_id = 'DEP-TEST-1'"
        )
    service.handle_wechat_refund_result({
        "out_trade_no": "TRADE-TEST-1", "out_refund_no": "RF-DEPOSIT-1", "refund_status": "SUCCESS",
        "transaction_id": "WX-DEPOSIT-1", "mchid": config.mch_id,
        "amount": {"total": 1, "refund": 1, "currency": "CNY"},
    }, config)

    with service.connect() as connection:
        row = connection.execute("SELECT status FROM custom_design_deposits WHERE deposit_id = 'DEP-TEST-1'").fetchone()
    assert row["status"] == "refunded"


@pytest.mark.parametrize(("environment", "expected"), [("production", 990), ("", 990), ("test", 1), ("testing", 1)])
def test_one_cent_settlement_is_limited_to_test_environments(monkeypatch, environment, expected):
    configure_wechat(monkeypatch, environment)
    assert WechatPayConfig().settlement_fee(990) == expected
