from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.admin_service import AdminService
from app.main import app
from app.migrations.runner import upgrade
from app.money import money_to_cents
from app.order_service import (
    OrderService,
    PaymentWebhookError,
    WebhookEventConflictError,
)
from app.user_sessions import session_service


client = TestClient(app)


class FakeWechatPayConfig:
    app_id = "wx-p1a-app"
    mch_id = "p1a-mch"
    api_v3_key = "0" * 32
    ready = True
    missing: list[str] = []
    test_mode = False


def build_service(tmp_path) -> OrderService:
    db_path = tmp_path / f"p1a-{uuid4().hex}.db"
    AdminService(db_path)
    OrderService(db_path)
    upgrade("sqlite", db_path)
    service = OrderService(db_path)
    service.get_user = lambda _user_id: None
    return service


def add_sku(service: OrderService, sku_id: str = "p1a-sku", stock: int = 10, price: str = "12.34") -> None:
    with service.connect() as connection:
        connection.execute(
            """
            INSERT INTO managed_materials
            (id, skuId, top, category, series, material_code, grade, name, effect,
             element, price, price_cents, size, weight, cost_price, safety_stock, supplier_name,
             purchase_note, color, shine, image_path, image_url, image_urls_json,
             stock, reserved_stock, enabled, sort_order, created_at, updated_at)
            VALUES (?, ?, 'bead', 'test', 'P1A', ?, '', ?, '', '水', ?, ?, 8, 1,
                    0, 0, '', '', '#fff', '#fff', '', '', '[]', ?, 0, 1, 0, ?, ?)
            """,
            (
                sku_id,
                f"sku-{sku_id}",
                sku_id,
                f"测试 SKU {sku_id}",
                price,
                money_to_cents(price, field_name="测试价格"),
                stock,
                "2026-07-12T12:00:00+00:00",
                "2026-07-12T12:00:00+00:00",
            ),
        )


def create_order(
    service: OrderService,
    sku_id: str = "p1a-sku",
    user_id: str = "p1a-user",
    key: str | None = None,
    quantity: int = 1,
) -> dict:
    return service.create_order(
        {
            "idempotency_key": key or f"p1a-{uuid4().hex}",
            "user_id": user_id,
            "receiver": {"name": "测试用户", "phone": "13800000000", "address": "测试地址"},
            "design": {},
            "sequence": [{"id": sku_id, "price": "12.34", "quantity": quantity}],
            "bom": [],
        }
    )["order"]


def inventory(service: OrderService, sku_id: str = "p1a-sku") -> tuple[int, int]:
    with service.connect() as connection:
        row = connection.execute(
            "SELECT stock, reserved_stock FROM managed_materials WHERE id = ?", (sku_id,)
        ).fetchone()
    return int(row["stock"]), int(row["reserved_stock"])


def event_body(event_id: str, event_type: str, variant: str = "a") -> str:
    return json.dumps(
        {
            "id": event_id,
            "event_type": event_type,
            "create_time": "2026-07-12T12:00:00+08:00",
            "resource_type": "encrypt-resource",
            "resource": {"ciphertext": f"fixture-{variant}"},
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def headers() -> dict[str, str]:
    return {
        "wechatpay-serial": "PUB_KEY_ID_TEST",
        "wechatpay-timestamp": "1790000000",
        "wechatpay-nonce": "nonce",
        "wechatpay-signature": "signature",
    }


def payment_resource(order: dict, **updates) -> dict:
    resource = {
        "appid": FakeWechatPayConfig.app_id,
        "mchid": FakeWechatPayConfig.mch_id,
        "out_trade_no": order["out_trade_no"],
        "transaction_id": f"wx-tx-{order['order_id']}",
        "trade_state": "SUCCESS",
        "trade_state_desc": "支付成功",
        "success_time": "2026-07-12T12:01:00+08:00",
        "amount": {"total": order["total_fee"], "currency": "CNY"},
    }
    resource.update(updates)
    return resource


def refund_resource(order: dict, **updates) -> dict:
    refund = order.get("refund") or {}
    resource = {
        "mchid": FakeWechatPayConfig.mch_id,
        "out_trade_no": order["out_trade_no"],
        "transaction_id": order["payment"]["transaction_id"],
        "out_refund_no": refund.get("out_refund_no") or f"RF{order['order_id']}",
        "refund_id": f"wx-refund-{order['order_id']}",
        "refund_status": "SUCCESS",
        "success_time": "2026-07-12T12:05:00+08:00",
        "amount": {"total": order["total_fee"], "refund": order["total_fee"]},
    }
    resource.update(updates)
    return resource


def patch_webhook(monkeypatch, service: OrderService, resource: dict) -> None:
    monkeypatch.setattr("app.order_service.WechatPayConfig", FakeWechatPayConfig)
    monkeypatch.setattr(service, "verify_wechat_notify_signature", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "decrypt_wechat_resource", lambda *_args, **_kwargs: resource)


def webhook_events(service: OrderService) -> list[dict]:
    with service.connect() as connection:
        rows = connection.execute("SELECT * FROM payment_webhook_events ORDER BY created_at, id").fetchall()
    return [dict(row) for row in rows]


def test_payment_success_is_transactional_and_duplicate_is_side_effect_free(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service, stock=2)
    order = create_order(service)
    resource = payment_resource(order)
    patch_webhook(monkeypatch, service, resource)
    body = event_body("payment-success-001", "TRANSACTION.SUCCESS")

    first = service.handle_wechat_notify(headers(), body)
    paid = service.get_order(order["order_id"])
    history_size = len(paid["status_history"])
    replay = service.handle_wechat_notify(headers(), body)
    repeated = service.get_order(order["order_id"])

    assert first["processing_status"] == "succeeded"
    assert replay["duplicate"] is True
    assert paid["status"] == "pending_ship" and paid["payment_status"] == "paid"
    assert inventory(service) == (1, 0)
    assert len(repeated["status_history"]) == history_size
    assert len(webhook_events(service)) == 1


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"appid": "wrong-app"}, "appid_mismatch"),
        ({"mchid": "wrong-mch"}, "mchid_mismatch"),
        ({"amount": {"total": 1, "currency": "CNY"}}, "amount_mismatch"),
        ({"amount": {"total": 1234.5, "currency": "CNY"}}, "amount_invalid"),
        ({"amount": {"total": True, "currency": "CNY"}}, "amount_invalid"),
        ({"amount": {"total": 1234, "currency": "USD"}}, "currency_mismatch"),
        ({"out_trade_no": "missing-order"}, "order_missing"),
        ({"transaction_id": ""}, "transaction_id_missing"),
    ],
)
def test_payment_notification_validation_fails_closed(tmp_path, monkeypatch, updates, code):
    service = build_service(tmp_path)
    add_sku(service)
    order = create_order(service)
    resource = payment_resource(order, **updates)
    patch_webhook(monkeypatch, service, resource)

    with pytest.raises(PaymentWebhookError) as raised:
        service.handle_wechat_notify(headers(), event_body(f"invalid-{code}", "TRANSACTION.SUCCESS"))

    assert raised.value.code == code
    assert service.get_order(order["order_id"])["payment_status"] == "unpaid"
    assert inventory(service) == (10, 1)
    assert webhook_events(service)[0]["processing_status"] == "failed"
    assert webhook_events(service)[0]["failure_reason"] == code


def test_signature_and_decryption_failures_do_not_change_order(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service)
    order = create_order(service)
    monkeypatch.setattr("app.order_service.WechatPayConfig", FakeWechatPayConfig)
    monkeypatch.setattr(
        service,
        "verify_wechat_notify_signature",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("signature invalid")),
    )
    with pytest.raises(ValueError, match="signature invalid"):
        service.handle_wechat_notify(headers(), event_body("bad-signature", "TRANSACTION.SUCCESS"))
    assert webhook_events(service) == []

    monkeypatch.setattr(service, "verify_wechat_notify_signature", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service,
        "decrypt_wechat_resource",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("decrypt invalid")),
    )
    with pytest.raises(PaymentWebhookError) as raised:
        service.handle_wechat_notify(headers(), event_body("bad-decrypt", "TRANSACTION.SUCCESS"))
    assert raised.value.code == "decrypt_failed"
    assert service.get_order(order["order_id"])["payment_status"] == "unpaid"
    assert webhook_events(service)[0]["failure_reason"] == "decrypt_failed"


def test_oversized_verified_event_id_is_rejected_before_ledger_write(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service)
    order = create_order(service)
    patch_webhook(monkeypatch, service, payment_resource(order))

    with pytest.raises(PaymentWebhookError) as raised:
        service.handle_wechat_notify(headers(), event_body("x" * 161, "TRANSACTION.SUCCESS"))

    assert raised.value.code == "event_id_invalid"
    assert webhook_events(service) == []
    assert service.get_order(order["order_id"])["payment_status"] == "unpaid"


def test_same_event_id_with_different_payload_records_security_conflict(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service)
    order = create_order(service)
    patch_webhook(monkeypatch, service, payment_resource(order))
    service.handle_wechat_notify(headers(), event_body("payload-conflict", "TRANSACTION.SUCCESS", "a"))

    with pytest.raises(WebhookEventConflictError) as raised:
        service.handle_wechat_notify(headers(), event_body("payload-conflict", "TRANSACTION.SUCCESS", "b"))

    assert raised.value.code == "payload_hash_mismatch"
    event = webhook_events(service)[0]
    assert event["processing_status"] == "succeeded"
    assert event["conflict_count"] == 1 and event["security_alert_at"]


def test_transaction_failure_rolls_back_then_same_event_retries(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service, stock=2)
    order = create_order(service)
    patch_webhook(monkeypatch, service, payment_resource(order))
    body = event_body("retry-after-rollback", "TRANSACTION.SUCCESS")
    original = service.finalize_webhook_event

    def fail_once(*_args, **_kwargs):
        monkeypatch.setattr(service, "finalize_webhook_event", original)
        raise sqlite3.OperationalError("injected failure")

    monkeypatch.setattr(service, "finalize_webhook_event", fail_once)
    with pytest.raises(sqlite3.OperationalError, match="injected"):
        service.handle_wechat_notify(headers(), body)
    assert service.get_order(order["order_id"])["payment_status"] == "unpaid"
    assert inventory(service) == (2, 1)
    assert webhook_events(service)[0]["processing_status"] == "failed"

    monkeypatch.setattr(service, "finalize_webhook_event", original)
    retried = service.handle_wechat_notify(headers(), body)
    assert retried["processing_status"] == "succeeded"
    assert service.get_order(order["order_id"])["payment_status"] == "paid"
    assert inventory(service) == (1, 0)


def test_two_workers_concurrently_process_one_event_once(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service, stock=2)
    order = create_order(service)
    resource = payment_resource(order)
    monkeypatch.setattr("app.order_service.WechatPayConfig", FakeWechatPayConfig)
    body = event_body("concurrent-event", "TRANSACTION.SUCCESS")

    def attempt(_index: int):
        worker = OrderService(service.db_path)
        worker.verify_wechat_notify_signature = lambda *_args, **_kwargs: None
        worker.decrypt_wechat_resource = lambda *_args, **_kwargs: resource
        return worker.handle_wechat_notify(headers(), body)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))

    paid = service.get_order(order["order_id"])
    assert sum(result.get("processing_status") == "succeeded" and not result.get("duplicate") for result in results) == 1
    assert len(webhook_events(service)) == 1
    assert inventory(service) == (1, 0)
    assert len([row for row in paid["status_history"] if row["status"] == "pending_ship"]) == 1


def test_out_of_order_and_closed_order_events_never_downgrade_paid_state(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service, stock=3)
    order = create_order(service, key="paid-order-key")
    patch_webhook(monkeypatch, service, payment_resource(order))
    service.handle_wechat_notify(headers(), event_body("paid-first", "TRANSACTION.SUCCESS"))
    paid_history = len(service.get_order(order["order_id"])["status_history"])

    closed_resource = payment_resource(order, trade_state="CLOSED", transaction_id="")
    patch_webhook(monkeypatch, service, closed_resource)
    ignored = service.handle_wechat_notify(headers(), event_body("late-closed", "TRANSACTION.CLOSED"))
    assert ignored["processing_status"] == "ignored"
    assert service.get_order(order["order_id"])["payment_status"] == "paid"
    assert len(service.get_order(order["order_id"])["status_history"]) == paid_history

    cancelled = create_order(service, key="cancelled-order-key", user_id="cancelled-user")
    service.cancel_order(cancelled["order_id"], "cancelled-user")
    patch_webhook(monkeypatch, service, payment_resource(cancelled))
    compensation = service.handle_wechat_notify(
        headers(), event_body("closed-order-paid", "TRANSACTION.SUCCESS")
    )
    assert compensation["processing_status"] == "compensation_required"
    assert service.get_order(cancelled["order_id"])["status"] == "closed"


def test_terminal_payment_failure_releases_reservation_once(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service, stock=2)
    order = create_order(service)
    resource = payment_resource(order, trade_state="PAYERROR", transaction_id="")
    patch_webhook(monkeypatch, service, resource)
    body = event_body("payment-error", "TRANSACTION.PAYERROR")

    service.handle_wechat_notify(headers(), body)
    service.handle_wechat_notify(headers(), body)

    closed = service.get_order(order["order_id"])
    assert closed["status"] == "closed" and closed["payment_status"] == "failed"
    assert inventory(service) == (2, 0)


def test_processing_then_success_and_expiry_cannot_release_confirmed_stock(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service, stock=2)
    order = create_order(service)
    processing = payment_resource(order, trade_state="USERPAYING", transaction_id="")
    patch_webhook(monkeypatch, service, processing)
    service.handle_wechat_notify(
        headers(), event_body("payment-processing", "TRANSACTION.USERPAYING")
    )
    assert service.get_order(order["order_id"])["payment_status"] == "processing"
    assert inventory(service) == (2, 1)
    with pytest.raises(ValueError, match="仅待付款订单"):
        service.cancel_order(order["order_id"], "p1a-user")

    patch_webhook(monkeypatch, service, payment_resource(order))
    service.handle_wechat_notify(
        headers(), event_body("payment-after-processing", "TRANSACTION.SUCCESS")
    )
    with service.connect() as connection:
        connection.execute(
            "UPDATE inventory_reservations SET expires_at = '2000-01-01T00:00:00+00:00' WHERE order_id = ?",
            (order["order_id"],),
        )
    released = service.release_expired_reservations(timestamp="2026-07-12T12:30:00+00:00")
    assert released["released_reservations"] == 0
    assert service.get_order(order["order_id"])["payment_status"] == "paid"
    assert inventory(service) == (1, 0)


def test_unsupported_event_and_reused_transaction_fail_closed(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service, stock=3)
    first = create_order(service, key="first-transaction-owner", user_id="first-owner")
    patch_webhook(monkeypatch, service, payment_resource(first))
    with pytest.raises(PaymentWebhookError) as unsupported:
        service.handle_wechat_notify(
            headers(), event_body("unsupported-event", "TRANSACTION.UNKNOWN")
        )
    assert unsupported.value.code == "event_type_unsupported"

    transaction = payment_resource(first)
    service.handle_wechat_notify(headers(), event_body("first-transaction", "TRANSACTION.SUCCESS"))
    second = create_order(service, key="second-transaction-owner", user_id="second-owner")
    reused = payment_resource(second, transaction_id=transaction["transaction_id"])
    patch_webhook(monkeypatch, service, reused)
    with pytest.raises(PaymentWebhookError) as conflict:
        service.handle_wechat_notify(
            headers(), event_body("reused-transaction", "TRANSACTION.SUCCESS")
        )
    assert conflict.value.code == "transaction_id_reused"
    assert service.get_order(second["order_id"])["payment_status"] == "unpaid"
    assert inventory(service) == (2, 1)


def test_refund_webhook_is_deduplicated_and_old_event_cannot_downgrade(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service, stock=2)
    order = create_order(service)
    payment = payment_resource(order)
    patch_webhook(monkeypatch, service, payment)
    service.handle_wechat_notify(headers(), event_body("refund-payment", "TRANSACTION.SUCCESS"))
    requested = service.request_refund(order["order_id"], "p1a-user", "测试退款")
    refund = refund_resource(requested)
    patch_webhook(monkeypatch, service, refund)
    body = event_body("refund-success", "REFUND.SUCCESS")

    first = service.handle_wechat_refund_notify(headers(), body)
    repeated = service.handle_wechat_refund_notify(headers(), body)
    history_size = len(service.get_order(order["order_id"])["status_history"])
    assert first["processing_status"] == "succeeded" and repeated["duplicate"] is True
    assert service.get_order(order["order_id"])["payment_status"] == "refunded"

    processing = {**refund, "refund_status": "PROCESSING"}
    patch_webhook(monkeypatch, service, processing)
    old = service.handle_wechat_refund_notify(
        headers(), event_body("refund-old-processing", "REFUND.PROCESSING")
    )
    assert old["processing_status"] == "ignored"
    final = service.get_order(order["order_id"])
    assert final["payment_status"] == "refunded"
    assert len(final["status_history"]) == history_size


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"mchid": "wrong-mch"}, "mchid_mismatch"),
        ({"transaction_id": "wrong-transaction"}, "transaction_id_mismatch"),
        ({"amount": {"total": 1234.5, "refund": 1234}}, "refund_amount_invalid"),
        ({"amount": {"total": 1234, "refund": True}}, "refund_amount_invalid"),
        ({"amount": {"total": 1, "refund": 1234}}, "amount_mismatch"),
        ({"amount": {"total": 1234, "refund": 1}}, "refund_amount_mismatch"),
    ],
)
def test_refund_notification_validation_fails_closed(tmp_path, monkeypatch, updates, code):
    service = build_service(tmp_path)
    add_sku(service, stock=2)
    order = create_order(service)
    patch_webhook(monkeypatch, service, payment_resource(order))
    service.handle_wechat_notify(headers(), event_body(f"refund-setup-{code}", "TRANSACTION.SUCCESS"))
    requested = service.request_refund(order["order_id"], "p1a-user", "测试退款")
    patch_webhook(monkeypatch, service, refund_resource(requested, **updates))

    provider_event_id = f"invalid-refund-{code}"
    with pytest.raises(PaymentWebhookError) as raised:
        service.handle_wechat_refund_notify(
            headers(),
            event_body(provider_event_id, "REFUND.SUCCESS"),
        )

    assert raised.value.code == code
    current = service.get_order(order["order_id"])
    assert current["status"] == "refund_requested"
    assert current["payment_status"] == "paid"
    failed_event = next(
        event for event in webhook_events(service)
        if event["provider_event_id"] == provider_event_id
    )
    assert failed_event["processing_status"] == "failed"
    assert failed_event["failure_reason"] == code


def test_refund_success_cannot_refund_unpaid_order(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service)
    order = create_order(service)
    refund = {
        "mchid": FakeWechatPayConfig.mch_id,
        "out_trade_no": order["out_trade_no"],
        "transaction_id": "unknown-transaction",
        "out_refund_no": f"RF{order['order_id']}",
        "refund_id": "refund-unpaid",
        "refund_status": "SUCCESS",
        "amount": {"total": order["total_fee"], "refund": order["total_fee"]},
    }
    patch_webhook(monkeypatch, service, refund)
    with pytest.raises(PaymentWebhookError):
        service.handle_wechat_refund_notify(
            headers(), event_body("refund-unpaid", "REFUND.SUCCESS")
        )
    assert service.get_order(order["order_id"])["payment_status"] == "unpaid"
    assert inventory(service) == (10, 1)


def test_payment_status_endpoint_is_owner_scoped(tmp_path, monkeypatch):
    from app import api as api_module

    service = build_service(tmp_path)
    add_sku(service)
    order = create_order(service, user_id="payment-owner")
    monkeypatch.setattr(api_module, "order_service", service)
    owner = session_service.create("payment-owner")
    other = session_service.create("payment-other")

    own_response = client.get(
        f"/api/v1/orders/{order['order_id']}/payment-status",
        headers={"Authorization": f"Bearer {owner['access_token']}"},
    )
    other_response = client.get(
        f"/api/v1/orders/{order['order_id']}/payment-status",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert own_response.status_code == 200
    assert own_response.json()["data"]["paid"] is False
    assert other_response.status_code == 404


def test_webhook_api_returns_success_for_verified_duplicate(tmp_path, monkeypatch):
    from app import api as api_module

    service = build_service(tmp_path)
    add_sku(service, stock=2)
    order = create_order(service)
    patch_webhook(monkeypatch, service, payment_resource(order))
    monkeypatch.setattr(api_module, "order_service", service)
    body = event_body("api-duplicate", "TRANSACTION.SUCCESS")
    callback_headers = {
        "Wechatpay-Serial": "PUB_KEY_ID_TEST",
        "Wechatpay-Timestamp": "1790000000",
        "Wechatpay-Nonce": "nonce",
        "Wechatpay-Signature": "signature",
        "Content-Type": "application/json",
    }

    first = client.post("/api/v1/wechat-pay/notify", headers=callback_headers, content=body)
    duplicate = client.post("/api/v1/wechat-pay/notify", headers=callback_headers, content=body)
    assert first.status_code == 200 and first.json()["code"] == "SUCCESS"
    assert duplicate.status_code == 200 and duplicate.json()["code"] == "SUCCESS"


def test_payment_switch_prevents_real_payment_request(tmp_path, monkeypatch):
    from app import api as api_module

    monkeypatch.delenv("WECHAT_PAYMENT_ENABLED", raising=False)
    service = build_service(tmp_path)
    add_sku(service)
    monkeypatch.setattr(
        service,
        "wechat_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("real payment must stay disabled")),
    )
    order = create_order(service)
    assert order["payment_status"] == "unpaid"
    monkeypatch.setattr(api_module, "order_service", service)
    monkeypatch.setenv("COMMERCE_CHECKOUT_ENABLED", "true")
    session = session_service.create("p1a-user")
    response = client.post(
        f"/api/v1/orders/{order['order_id']}/pay",
        headers={"Authorization": f"Bearer {session['access_token']}"},
        json={"user_id": "p1a-user"},
    )
    assert response.status_code == 503


def test_active_payment_query_is_an_internal_mockable_abstraction(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    calls = []
    monkeypatch.setattr(
        service,
        "wechat_request",
        lambda method, path, body, config, error_label="": calls.append(
            (method, path, body, error_label)
        ) or {"trade_state": "SUCCESS"},
    )
    result = service.query_wechat_transaction("ORDER123", FakeWechatPayConfig())
    assert result["trade_state"] == "SUCCESS"
    assert calls == [
        (
            "GET",
            "/v3/pay/transactions/out-trade-no/ORDER123?mchid=p1a-mch",
            {},
            "微信支付订单查询失败",
        )
    ]
