from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import product
from uuid import uuid4

import pytest

from app.admin_service import AdminService
from app.migrations.runner import upgrade
from app.money import money_to_cents
from app.order_service import ORDER_STATE_TRANSITIONS, OrderConflictError, OrderService, now_iso


USER_ID = "state-machine-user"
ORDER_STATES = tuple(ORDER_STATE_TRANSITIONS)
PAYMENT_STATUS_FOR_ORDER = {
    "pending_payment": "unpaid",
    "pending_ship": "paid",
    "shipped": "paid",
    "completed": "paid",
    "refund_requested": "paid",
    "refunded": "refunded",
    "closed": "cancelled",
}


@pytest.fixture
def service(tmp_path, monkeypatch) -> OrderService:
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")
    db_path = tmp_path / f"order-state-{uuid4().hex}.db"
    AdminService(db_path)
    OrderService(db_path)
    upgrade("sqlite", db_path)
    instance = OrderService(db_path)
    instance.get_user = lambda _user_id: None
    add_sku(instance, "state-sku", stock=40)
    return instance


def add_sku(service: OrderService, sku_id: str, *, stock: int) -> None:
    timestamp = now_iso()
    with service.connect() as connection:
        connection.execute(
            """
            INSERT INTO managed_materials
            (id, skuId, top, category, series, material_code, grade, name, effect,
             element, price, price_cents, size, weight, cost_price, safety_stock,
             supplier_name, purchase_note, color, shine, image_path, image_url,
             image_urls_json, stock, reserved_stock, enabled, sort_order, created_at, updated_at)
            VALUES (?, ?, 'bead', 'test', 'STATE', ?, '', ?, '', '水', '10.00', ?, 8, 1,
                    0, 0, '', '', '#ffffff', '#ffffff', '', '', '[]', ?, 0, 1, 0, ?, ?)
            """,
            (
                sku_id,
                f"sku-{sku_id}",
                sku_id,
                f"状态机珠子 {sku_id}",
                money_to_cents("10.00", field_name="测试价格"),
                stock,
                timestamp,
                timestamp,
            ),
        )


def create_order(
    service: OrderService,
    *,
    quantity: int = 1,
    key: str | None = None,
) -> dict:
    return service.create_order(
        {
            "idempotency_key": key or f"state-{uuid4().hex}",
            "user_id": USER_ID,
            "receiver": {
                "name": "状态机测试用户",
                "phone": "13800000000",
                "address": "状态机测试地址",
            },
            "design": {"summary": {"price": quantity * 10}},
            "sequence": [{"id": "state-sku", "price": "10.00", "quantity": quantity}],
            "bom": [],
        }
    )["order"]


def pay_order(service: OrderService, *, quantity: int = 1) -> dict:
    order = create_order(service, quantity=quantity)
    return service.mark_paid_for_dev(order["order_id"], USER_ID)


def ship_order(service: OrderService, *, quantity: int = 1, tracking_no: str | None = None) -> dict:
    paid = pay_order(service, quantity=quantity)
    return service.ship_paid_order(
        paid["order_id"],
        carrier="顺丰速运",
        carrier_code="shunfeng",
        tracking_no=tracking_no or f"SF{uuid4().hex[:14].upper()}",
        phone_tail="0000",
    )


def complete_order(service: OrderService, *, quantity: int = 1) -> dict:
    shipped = ship_order(service, quantity=quantity)
    return service.confirm_receipt(shipped["order_id"], USER_ID)


def inventory_state(service: OrderService) -> tuple[int, int]:
    with service.connect() as connection:
        row = connection.execute(
            "SELECT stock, reserved_stock FROM managed_materials WHERE id = 'state-sku'"
        ).fetchone()
    return int(row["stock"]), int(row["reserved_stock"])


def reservation_status(service: OrderService, order_id: str) -> str:
    with service.connect() as connection:
        row = connection.execute(
            "SELECT status FROM inventory_reservations WHERE order_id = ?",
            (order_id,),
        ).fetchone()
    return str(row["status"])


def seed_state_order(service: OrderService, status: str, payment_status: str) -> dict:
    order_id = f"STATE-{status}-{uuid4().hex[:10]}"
    timestamp = now_iso()
    payment = {
        "transaction_id": f"WX-{order_id}",
        "trade_state": "SUCCESS",
    } if payment_status in {"paid", "refunded"} else {}
    with service.connect() as connection:
        connection.execute(
            """
            INSERT INTO orders
            (order_id, out_trade_no, user_id, status, payment_status, total_amount, total_fee,
             currency, receiver_json, design_json, sequence_json, bom_json, remark, payment_json,
             created_at, updated_at, paid_at, after_sale_status, refund_status, refund_json,
             logistics_json, status_history_json, design_id)
            VALUES (?, ?, ?, ?, ?, 10.00, 1000, 'CNY', ?, '{}', '[]', '[]', '', ?, ?, ?, ?, '', '',
                    '{}', '{}', ?, ?)
            """,
            (
                order_id,
                order_id,
                USER_ID,
                status,
                payment_status,
                json.dumps({"name": "测试用户", "phone": "13800000000"}, ensure_ascii=False),
                json.dumps(payment, ensure_ascii=False),
                timestamp,
                timestamp,
                timestamp if payment_status in {"paid", "refunded"} else None,
                json.dumps(
                    [{"status": status, "label": f"种子状态 {status}", "time": timestamp}],
                    ensure_ascii=False,
                ),
                f"DESIGN-{order_id}",
            ),
        )
    return service.get_order(order_id)


def install_successful_refund(monkeypatch, service: OrderService) -> list[str]:
    class FakeWechatPayConfig:
        ready = True
        missing: list[str] = []
        test_mode = True

    calls: list[str] = []

    def successful_refund(_order, out_refund_no, *_args, **_kwargs):
        calls.append(out_refund_no)
        return {"status": "SUCCESS", "refund_id": f"WX-{out_refund_no}"}

    monkeypatch.setattr("app.order_service.WechatPayConfig", FakeWechatPayConfig)
    monkeypatch.setattr(service, "create_wechat_refund", successful_refund)
    return calls


@pytest.mark.parametrize(
    ("source", "target"),
    list(product(ORDER_STATES, ORDER_STATES)),
    ids=lambda value: value,
)
def test_all_order_state_pairs_follow_the_central_transition_matrix(service, source, target):
    order = seed_state_order(service, source, PAYMENT_STATUS_FOR_ORDER[source])
    expected_allowed = target == source or target in ORDER_STATE_TRANSITIONS[source]

    with service.connect() as connection:
        service.begin_order_transaction(connection)
        if expected_allowed:
            service.transition_order(
                order,
                target,
                event_label=f"矩阵测试 {source} -> {target}",
                connection=connection,
                payment_status=PAYMENT_STATUS_FOR_ORDER[target],
            )
        else:
            with pytest.raises(ValueError, match="订单状态不能从"):
                service.transition_order(
                    order,
                    target,
                    event_label=f"非法矩阵测试 {source} -> {target}",
                    connection=connection,
                    payment_status=PAYMENT_STATUS_FOR_ORDER[target],
                )

    updated = service.get_order(order["order_id"])
    assert updated["status"] == (target if expected_allowed else source)
    assert updated["payment_status"] == (
        PAYMENT_STATUS_FOR_ORDER[target] if expected_allowed else PAYMENT_STATUS_FOR_ORDER[source]
    )


@pytest.mark.parametrize(
    ("status", "payment_status", "valid"),
    [
        (status, payment_status, payment_status in allowed)
        for status, allowed in {
            "pending_payment": {"unpaid", "processing"},
            "pending_ship": {"paid"},
            "shipped": {"paid"},
            "completed": {"paid"},
            "refund_requested": {"paid"},
            "refunded": {"refunded"},
            "closed": {"cancelled", "expired", "failed"},
        }.items()
        for payment_status in (
            "unpaid", "processing", "paid", "refunded", "cancelled", "expired", "failed"
        )
    ],
)
def test_all_order_and_payment_status_pairs_are_validated(status, payment_status, valid):
    if valid:
        OrderService.validate_order_state(status, payment_status)
    else:
        with pytest.raises(ValueError, match="履约状态与支付状态不一致"):
            OrderService.validate_order_state(status, payment_status)


def test_happy_path_preserves_inventory_logistics_history_and_idempotency(service):
    created = create_order(service, quantity=2)
    order_id = created["order_id"]
    assert (created["status"], created["payment_status"]) == ("pending_payment", "unpaid")
    assert inventory_state(service) == (40, 2)
    assert reservation_status(service, order_id) == "reserved"

    paid = service.mark_paid_for_dev(order_id, USER_ID)
    assert (paid["status"], paid["payment_status"]) == ("pending_ship", "paid")
    assert inventory_state(service) == (38, 0)
    assert reservation_status(service, order_id) == "confirmed"
    assert service.mark_paid_for_dev(order_id, USER_ID)["status"] == "pending_ship"

    shipped = service.ship_paid_order(
        order_id,
        carrier="顺丰速运",
        carrier_code="shunfeng",
        tracking_no="SF-STATE-HAPPY-001",
        phone_tail="0000",
    )
    assert shipped["status"] == "shipped"
    assert shipped["logistics"]["status"] == "awaiting_pickup"
    assert shipped["logistics"]["status_text"] == "已发货待揽收"
    history_size = len(shipped["status_history"])
    replay = service.ship_paid_order(
        order_id,
        carrier="顺丰速运",
        carrier_code="shunfeng",
        tracking_no="SF-STATE-HAPPY-001",
        phone_tail="0000",
    )
    assert len(replay["status_history"]) == history_size
    with pytest.raises(OrderConflictError, match="不能更换快递单号"):
        service.ship_paid_order(
            order_id,
            carrier="顺丰速运",
            carrier_code="shunfeng",
            tracking_no="SF-STATE-HAPPY-CHANGED",
            phone_tail="0000",
        )

    signed_at = datetime.now(timezone.utc).replace(microsecond=0)
    logistics = service.update_logistics(
        order_id,
        {
            "status": "signed",
            "status_text": "已签收",
            "tracking_no": "SF-STATE-HAPPY-001",
            "updated_at": signed_at.isoformat(),
            "traces": [{"time": signed_at.isoformat(), "desc": "快件已签收"}],
        },
    )
    assert logistics["status"] == "signed"
    assert service.complete_signed_order_if_due(order_id, signed_at + timedelta(days=6)) is False
    assert service.get_order(order_id)["status"] == "shipped"

    completed = service.confirm_receipt(order_id, USER_ID)
    assert completed["status"] == "completed"
    completed_history_size = len(completed["status_history"])
    assert service.confirm_receipt(order_id, USER_ID)["status"] == "completed"
    assert len(service.get_order(order_id)["status_history"]) == completed_history_size
    assert [item["status"] for item in completed["status_history"]] == [
        "pending_payment", "pending_ship", "shipped", "completed"
    ]


def test_pending_order_cancel_is_terminal_and_releases_inventory_once(service):
    created = create_order(service, quantity=3)
    order_id = created["order_id"]
    service.update_order_receiver(
        order_id,
        USER_ID,
        {"name": "修改后用户", "phone": "13900000000", "address": "修改后地址"},
    )
    canceled = service.cancel_order(order_id, USER_ID, "不再购买")
    assert (canceled["status"], canceled["payment_status"]) == ("closed", "cancelled")
    assert inventory_state(service) == (40, 0)
    assert reservation_status(service, order_id) == "released"
    history_size = len(canceled["status_history"])
    assert service.cancel_order(order_id, USER_ID)["status"] == "closed"
    assert len(service.get_order(order_id)["status_history"]) == history_size

    with pytest.raises(ValueError):
        service.mark_paid_for_dev(order_id, USER_ID)
    with pytest.raises(ValueError, match="仅待发货订单"):
        service.ship_paid_order(order_id, "顺丰速运", "SF-CLOSED")
    with pytest.raises(ValueError, match="尚未发货"):
        service.confirm_receipt(order_id, USER_ID)
    with pytest.raises(ValueError, match="未支付订单不能申请退款"):
        service.request_refund(order_id, USER_ID)


def test_direct_refund_success_restocks_before_shipping_and_is_terminal(service, monkeypatch):
    calls = install_successful_refund(monkeypatch, service)
    paid = pay_order(service, quantity=2)
    order_id = paid["order_id"]
    assert inventory_state(service) == (38, 0)

    requested = service.request_refund(order_id, USER_ID, "待发货退款")
    repeated = service.request_refund(order_id, USER_ID, "网络重试")
    assert repeated["refund"]["out_refund_no"] == requested["refund"]["out_refund_no"]
    refunded = service.approve_refund(order_id, operator="state-admin", note="同意退款")

    assert (refunded["status"], refunded["payment_status"]) == ("refunded", "refunded")
    assert refunded["refund"]["inventory_disposition"] == "restocked"
    assert inventory_state(service) == (40, 0)
    assert reservation_status(service, order_id) == "restocked"
    assert calls == [requested["refund"]["out_refund_no"]]
    refund_history = [item["status"] for item in refunded["status_history"]]
    assert refund_history[:3] == ["pending_payment", "pending_ship", "refund_requested"]
    assert refund_history[-1] == "refunded"
    assert refund_history.count("refund_requested") == 2
    assert any("退款指令已登记" in item["label"] for item in refunded["status_history"])

    with pytest.raises(ValueError, match="仅退款申请中的订单"):
        service.approve_refund(order_id, operator="state-admin")
    with pytest.raises(ValueError, match="仅待发货订单"):
        service.ship_paid_order(order_id, "顺丰速运", "SF-REFUNDED")
    with pytest.raises(ValueError, match="尚未发货"):
        service.confirm_receipt(order_id, USER_ID)


def test_direct_refund_rejection_restores_one_pending_ship_state_then_can_ship(service):
    paid = pay_order(service)
    order_id = paid["order_id"]
    service.request_refund(order_id, USER_ID, "改变主意")
    rejected = service.reject_refund(order_id, operator="state-admin", note="已与用户确认继续制作")
    assert (rejected["status"], rejected["payment_status"]) == ("pending_ship", "paid")
    assert rejected["refund_status"] == "rejected"
    shipped = service.ship_paid_order(order_id, "顺丰速运", "SF-AFTER-REJECT")
    assert shipped["status"] == "shipped"
    assert [item["status"] for item in shipped["status_history"]] == [
        "pending_payment", "pending_ship", "refund_requested", "pending_ship", "shipped"
    ]


@pytest.mark.parametrize("starting_status", ["shipped", "completed"])
def test_return_refund_keeps_fulfillment_history_and_waits_for_manual_stock_inspection(
    service,
    monkeypatch,
    starting_status,
):
    calls = install_successful_refund(monkeypatch, service)
    order = ship_order(service, quantity=2, tracking_no=f"SF-RETURN-{starting_status}")
    if starting_status == "completed":
        order = service.confirm_receipt(order["order_id"], USER_ID)
    order_id = order["order_id"]
    stock_after_payment = inventory_state(service)

    case = service.create_after_sale_case(
        order_id,
        USER_ID,
        case_type="return_refund",
        reason_code="quality_issue",
        reason="商品存在质量问题，需要退货退款",
        evidence_urls=[],
        idempotency_key=f"return-{starting_status}-{uuid4().hex}",
    )
    awaiting = service.review_after_sale_case(
        case["case_id"], "request_return", operator="state-admin", note="同意寄回"
    )
    assert awaiting["status"] == "awaiting_return"
    returning = service.submit_after_sale_return_shipment(
        order_id,
        case["case_id"],
        USER_ID,
        carrier="顺丰速运",
        tracking_no="SF-USER-RETURN-001",
    )
    assert returning["status"] == "returning"
    pending = service.review_after_sale_case(
        case["case_id"], "confirm_return", operator="state-admin", note="已收到退货"
    )
    assert pending["status"] == "refund_pending"
    assert pending["order"]["status"] == "refund_requested"

    resolved = service.submit_after_sale_refund(
        case["case_id"], operator="state-admin", note="确认原路退款"
    )
    assert resolved["status"] == "resolved"
    assert resolved["order"]["status"] == "refunded"
    assert resolved["order"]["refund"]["source_order_status"] == starting_status
    assert resolved["order"]["refund"]["inventory_disposition"] == "pending_manual_inspection"
    assert inventory_state(service) == stock_after_payment
    assert reservation_status(service, order_id) == "confirmed"
    assert len(calls) == 1
    history = [item["status"] for item in resolved["order"]["status_history"]]
    assert "shipped" in history
    assert history[-2:] == ["refund_requested", "refunded"]


@pytest.mark.parametrize(
    ("case_type", "reason_code"),
    [
        ("resize", "size_small"),
        ("repair", "cord_loose"),
        ("resend", "item_missing"),
        ("other", "care_question"),
    ],
)
def test_non_refund_after_sale_branches_resolve_without_changing_completed_order(
    service,
    case_type,
    reason_code,
):
    completed = complete_order(service)
    case = service.create_after_sale_case(
        completed["order_id"],
        USER_ID,
        case_type=case_type,
        reason_code=reason_code,
        reason=f"测试 {case_type} 售后服务分支",
        evidence_urls=[],
        idempotency_key=f"service-{case_type}-{uuid4().hex}",
    )
    processing = service.review_after_sale_case(
        case["case_id"], "approve_service", operator="state-admin", note="开始处理"
    )
    resolved = service.review_after_sale_case(
        case["case_id"], "complete", operator="state-admin", note="处理完成"
    )
    assert processing["status"] == "service_processing"
    assert resolved["status"] == "resolved"
    assert resolved["order"]["status"] == "completed"
    assert resolved["order"]["payment_status"] == "paid"
    assert [event["event_type"] for event in resolved["events"]] == [
        "submitted", "approve_service", "complete"
    ]


def test_after_sale_reject_cancel_and_return_submission_guards(service):
    completed = complete_order(service)
    order_id = completed["order_id"]

    rejected_case = service.create_after_sale_case(
        order_id,
        USER_ID,
        case_type="other",
        reason_code="other",
        reason="先测试拒绝售后申请",
        evidence_urls=[],
        idempotency_key=f"reject-{uuid4().hex}",
    )
    rejected = service.review_after_sale_case(
        rejected_case["case_id"], "reject", operator="state-admin", note="不符合售后条件"
    )
    assert rejected["status"] == "rejected"

    requested_case = service.create_after_sale_case(
        order_id,
        USER_ID,
        case_type="return_refund",
        reason_code="not_as_expected",
        reason="测试申请阶段取消售后",
        evidence_urls=[],
        idempotency_key=f"cancel-requested-{uuid4().hex}",
    )
    canceled = service.cancel_after_sale_case(
        order_id, requested_case["case_id"], USER_ID, "暂不退货"
    )
    assert canceled["status"] == "canceled"

    return_case = service.create_after_sale_case(
        order_id,
        USER_ID,
        case_type="return_refund",
        reason_code="not_as_expected",
        reason="测试寄回阶段取消与限制",
        evidence_urls=[],
        idempotency_key=f"cancel-return-{uuid4().hex}",
    )
    service.review_after_sale_case(
        return_case["case_id"], "request_return", operator="state-admin", note="同意寄回"
    )
    canceled_awaiting = service.cancel_after_sale_case(
        order_id, return_case["case_id"], USER_ID, "决定保留商品"
    )
    assert canceled_awaiting["status"] == "canceled"

    final_case = service.create_after_sale_case(
        order_id,
        USER_ID,
        case_type="return_refund",
        reason_code="quality_issue",
        reason="测试寄回后不能取消",
        evidence_urls=[],
        idempotency_key=f"returning-guard-{uuid4().hex}",
    )
    service.review_after_sale_case(
        final_case["case_id"], "request_return", operator="state-admin", note="同意寄回"
    )
    service.submit_after_sale_return_shipment(
        order_id,
        final_case["case_id"],
        USER_ID,
        carrier="顺丰速运",
        tracking_no="SF-RETURN-GUARD-001",
    )
    with pytest.raises(ValueError, match="不能取消"):
        service.cancel_after_sale_case(order_id, final_case["case_id"], USER_ID)
    with pytest.raises(OrderConflictError, match="不能更换"):
        service.submit_after_sale_return_shipment(
            order_id,
            final_case["case_id"],
            USER_ID,
            carrier="顺丰速运",
            tracking_no="SF-RETURN-GUARD-CHANGED",
        )


@pytest.mark.parametrize("attempt", range(5))
def test_shipping_and_direct_refund_race_has_one_winner(service, attempt):
    paid = pay_order(service)
    order_id = paid["order_id"]
    barrier = threading.Barrier(2)

    def ship():
        barrier.wait()
        return service.ship_paid_order(
            order_id,
            "顺丰速运",
            f"SF-RACE-{attempt}",
            carrier_code="shunfeng",
        )

    def refund():
        barrier.wait()
        return service.request_refund(order_id, USER_ID, "并发退款")

    outcomes = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(ship), executor.submit(refund)]
        for future in futures:
            try:
                outcomes.append(("success", future.result(timeout=5)["status"]))
            except ValueError as exc:
                outcomes.append(("rejected", str(exc)))

    final = service.get_order(order_id)
    assert len([item for item in outcomes if item[0] == "success"]) == 1
    assert final["status"] in {"shipped", "refund_requested"}
    if final["status"] == "shipped":
        assert final["logistics"]["tracking_no"] == f"SF-RACE-{attempt}"
        assert final["refund_status"] == ""
    else:
        assert not final["logistics"].get("tracking_no")
        assert final["refund_status"] == "requested"


@pytest.mark.parametrize("attempt", range(5))
def test_payment_and_cancel_race_keeps_order_inventory_consistent(service, attempt):
    created = create_order(service, quantity=1, key=f"pay-cancel-{attempt}-{uuid4().hex}")
    order_id = created["order_id"]
    barrier = threading.Barrier(2)

    def pay():
        barrier.wait()
        return service.mark_paid_for_dev(order_id, USER_ID)

    def cancel():
        barrier.wait()
        return service.cancel_order(order_id, USER_ID, "并发取消")

    outcomes = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(pay), executor.submit(cancel)]
        for future in futures:
            try:
                outcomes.append(("success", future.result(timeout=5)["status"]))
            except ValueError as exc:
                outcomes.append(("rejected", str(exc)))

    final = service.get_order(order_id)
    assert len([item for item in outcomes if item[0] == "success"]) == 1
    if final["status"] == "pending_ship":
        assert final["payment_status"] == "paid"
        assert reservation_status(service, order_id) == "confirmed"
        assert inventory_state(service)[1] == 0
    else:
        assert (final["status"], final["payment_status"]) == ("closed", "cancelled")
        assert reservation_status(service, order_id) == "released"
        assert inventory_state(service)[1] == 0


def test_user_cannot_operate_another_users_order_at_any_business_stage(service):
    other_user = "different-user"
    created = create_order(service)
    order_id = created["order_id"]
    with pytest.raises(ValueError, match="无权"):
        service.ensure_order_owner(service.get_order(order_id), other_user)
    with pytest.raises(ValueError, match="无权"):
        service.cancel_order(order_id, other_user)
    with pytest.raises(ValueError, match="无权"):
        service.update_order_receiver(
            order_id,
            other_user,
            {"name": "越权用户", "phone": "13800000001", "address": "越权地址"},
        )

    paid = service.mark_paid_for_dev(order_id, USER_ID)
    with pytest.raises(ValueError, match="无权"):
        service.request_refund(paid["order_id"], other_user)
    shipped = service.ship_paid_order(paid["order_id"], "顺丰速运", "SF-OWNER-GUARD")
    with pytest.raises(ValueError, match="无权"):
        service.confirm_receipt(shipped["order_id"], other_user)
    with pytest.raises(ValueError, match="无权"):
        service.create_after_sale_case(
            shipped["order_id"],
            other_user,
            case_type="other",
            reason_code="other",
            reason="尝试越权创建售后工单",
            evidence_urls=[],
            idempotency_key=f"owner-guard-{uuid4().hex}",
        )
