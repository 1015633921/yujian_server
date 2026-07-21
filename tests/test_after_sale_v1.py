from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app.main import app
from app.order_service import OrderConflictError, OrderService, now_iso
from app.user_sessions import session_service


client = TestClient(app)


def seed_paid_order(
    service: OrderService,
    *,
    order_id: str,
    user_id: str,
    status: str = "completed",
    payment_status: str = "paid",
    total_fee: int = 12900,
) -> dict:
    timestamp = now_iso()
    with service.connect() as connection:
        connection.execute(
            """
            INSERT INTO orders
            (order_id, out_trade_no, user_id, status, payment_status, total_amount, total_fee,
             currency, receiver_json, design_json, sequence_json, bom_json, remark, payment_json,
             created_at, updated_at, paid_at, after_sale_status, refund_status, refund_json,
             logistics_json, status_history_json, design_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'CNY', ?, '{}', ?, '[]', '', '{}', ?, ?, ?, '', '',
                    '{}', '{}', ?, ?)
            """,
            (
                order_id,
                f"OUT-{order_id}",
                user_id,
                status,
                payment_status,
                total_fee / 100,
                total_fee,
                json.dumps({"name": "测试用户", "phone": "13800000000"}, ensure_ascii=False),
                json.dumps([{"name": "白水晶", "sku": "test-sku"}], ensure_ascii=False),
                timestamp,
                timestamp,
                timestamp if payment_status == "paid" else None,
                json.dumps([{"status": status, "label": "已完成", "time": timestamp}], ensure_ascii=False),
                f"DESIGN-{order_id}",
            ),
        )
    return service.get_order(order_id)


def create_case(service: OrderService, order_id: str, user_id: str, **updates):
    payload = {
        "case_type": "return_refund",
        "reason_code": "quality_issue",
        "reason": "收到后发现主石有明显破损",
        "evidence_urls": [],
        "idempotency_key": f"after-sale-{order_id}",
    }
    payload.update(updates)
    return service.create_after_sale_case(order_id, user_id, **payload)


def test_completed_order_creates_structured_after_sale_without_overwriting_fulfillment(tmp_path):
    service = OrderService(tmp_path / "after-sale.db")
    seed_paid_order(service, order_id="ORDER-AS-1", user_id="user-as-1")

    case = create_case(service, "ORDER-AS-1", "user-as-1")
    order = service.get_order("ORDER-AS-1")

    assert case["status"] == "requested"
    assert case["type"] == "return_refund"
    assert case["requested_refund_fee"] == 12900
    assert case["requested_refund_amount"] == "129.00"
    assert case["order_snapshot"]["status"] == "completed"
    assert order["status"] == "completed"
    assert order["after_sale_status"] == "requested"
    with service.connect() as connection:
        event = connection.execute(
            "SELECT * FROM after_sale_events WHERE case_id = ?",
            (case["case_id"],),
        ).fetchone()
    assert event["event_type"] == "submitted"
    assert event["operator_type"] == "user"


def test_non_refund_case_never_invents_requested_refund_amount(tmp_path):
    service = OrderService(tmp_path / "after-sale-other.db")
    seed_paid_order(service, order_id="ORDER-AS-2", user_id="user-as-2")

    case = create_case(
        service,
        "ORDER-AS-2",
        "user-as-2",
        case_type="resize",
        reason_code="size_small",
        reason="手围偏小，佩戴一段时间后比较紧",
    )

    assert case["type_text"] == "修改手围"
    assert case["requested_refund_fee"] == 0
    assert case["requested_refund_amount"] == "0.00"


def test_after_sale_submission_is_idempotent_and_blocks_another_active_case(tmp_path):
    service = OrderService(tmp_path / "after-sale-idempotent.db")
    seed_paid_order(service, order_id="ORDER-AS-3", user_id="user-as-3")

    first = create_case(service, "ORDER-AS-3", "user-as-3")
    replay = create_case(service, "ORDER-AS-3", "user-as-3")

    assert replay["case_id"] == first["case_id"]
    with pytest.raises(OrderConflictError, match="已有进行中的售后申请"):
        create_case(
            service,
            "ORDER-AS-3",
            "user-as-3",
            idempotency_key="after-sale-another-request",
        )


@pytest.mark.parametrize(
    ("status", "payment_status", "message"),
    [
        ("pending_ship", "paid", "当前订单状态暂不能申请售后"),
        ("completed", "unpaid", "只有已支付订单可以申请售后"),
    ],
)
def test_after_sale_rejects_ineligible_orders(tmp_path, status, payment_status, message):
    service = OrderService(tmp_path / f"after-sale-{status}-{payment_status}.db")
    seed_paid_order(
        service,
        order_id="ORDER-AS-BLOCKED",
        user_id="user-as-blocked",
        status=status,
        payment_status=payment_status,
    )

    with pytest.raises(ValueError, match=message):
        create_case(service, "ORDER-AS-BLOCKED", "user-as-blocked")


def test_after_sale_api_uses_authenticated_owner_and_returns_active_case(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "after-sale-api.db")
    user_id = "user-after-sale-api"
    seed_paid_order(service, order_id="ORDER-AS-API", user_id=user_id)
    monkeypatch.setattr(api_module, "order_service", service)
    session = session_service.create(user_id)
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    response = client.post(
        "/api/v1/orders/ORDER-AS-API/after-sales",
        headers=headers,
        json={
            "user_id": user_id,
            "type": "repair",
            "reason_code": "cord_loose",
            "reason": "弹力线已经明显松动，希望重新穿制",
            "evidence_urls": [],
            "idempotency_key": "after-sale-api-request",
        },
    )
    listed = client.get(
        f"/api/v1/orders/ORDER-AS-API/after-sales?user_id={user_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["type"] == "repair"
    assert listed.status_code == 200
    assert [item["case_id"] for item in listed.json()["data"]] == [response.json()["data"]["case_id"]]

    forged = client.post(
        "/api/v1/orders/ORDER-AS-API/after-sales",
        headers=headers,
        json={
            "user_id": "another-user",
            "type": "other",
            "reason_code": "other",
            "reason": "尝试伪造其他用户的售后申请",
            "evidence_urls": [],
            "idempotency_key": "after-sale-forged-user",
        },
    )
    assert forged.status_code == 403


def test_legacy_after_sale_route_is_not_exposed(tmp_path):
    service = OrderService(tmp_path / "after-sale-legacy-guard.db")
    seed_paid_order(service, order_id="ORDER-AS-LEGACY", user_id="user-as-legacy")
    session = session_service.create("user-as-legacy")

    response = client.post(
        "/api/v1/orders/ORDER-AS-LEGACY/after-sale",
        headers={"Authorization": f"Bearer {session['access_token']}"},
        json={"user_id": "user-as-legacy", "reason": "旧客户端发起售后"},
    )

    assert response.status_code == 404
    assert service.get_order("ORDER-AS-LEGACY")["status"] == "completed"
