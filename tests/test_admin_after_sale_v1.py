from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import admin_api as admin_api_module
from app.admin_service import AdminService
from app.main import app
from app.order_service import OrderConflictError, OrderService, now_iso


client = TestClient(app)


def seed_paid_order(
    service: OrderService,
    *,
    order_id: str,
    user_id: str,
    status: str = "completed",
    total_fee: int = 12900,
) -> None:
    timestamp = now_iso()
    with service.connect() as connection:
        connection.execute(
            """
            INSERT INTO orders
            (order_id, out_trade_no, user_id, status, payment_status, total_amount, total_fee,
             currency, receiver_json, design_json, sequence_json, bom_json, remark, payment_json,
             created_at, updated_at, paid_at, after_sale_status, refund_status, refund_json,
             logistics_json, status_history_json, design_id)
            VALUES (?, ?, ?, ?, 'paid', ?, ?, 'CNY', ?, '{}', '[]', '[]', '', ?, ?, ?, ?, '', '',
                    '{}', '{}', ?, ?)
            """,
            (
                order_id,
                f"OUT-{order_id}",
                user_id,
                status,
                total_fee / 100,
                total_fee,
                json.dumps({"name": "测试用户", "phone": "13800000000"}, ensure_ascii=False),
                json.dumps({"transaction_id": f"WX-{order_id}"}, ensure_ascii=False),
                timestamp,
                timestamp,
                timestamp,
                json.dumps([{"status": status, "label": "订单已完成", "time": timestamp}], ensure_ascii=False),
                f"DESIGN-{order_id}",
            ),
        )


def create_case(
    service: OrderService,
    order_id: str,
    user_id: str,
    *,
    case_type: str = "return_refund",
    reason_code: str = "quality_issue",
    reason: str = "收到后发现主石有明显破损",
):
    return service.create_after_sale_case(
        order_id,
        user_id,
        case_type=case_type,
        reason_code=reason_code,
        reason=reason,
        evidence_urls=[],
        idempotency_key=f"admin-after-sale-{order_id}",
    )


def test_admin_service_case_uses_service_state_machine_and_keeps_order_fulfillment(tmp_path):
    service = OrderService(tmp_path / "admin-after-sale-service.db")
    seed_paid_order(service, order_id="ORDER-AS-SERVICE", user_id="user-service")
    case = create_case(
        service,
        "ORDER-AS-SERVICE",
        "user-service",
        case_type="resize",
        reason_code="size_small",
        reason="当前手围偏小，佩戴一段时间后比较紧",
    )

    listed = service.admin_list_after_sale_cases(keyword="测试用户", status="requested", case_type="resize")
    assert [item["case_id"] for item in listed] == [case["case_id"]]
    assert listed[0]["order"]["status"] == "completed"

    processing = service.review_after_sale_case(
        case["case_id"],
        "approve_service",
        operator="operator-a",
        note="已联系用户确认新手围",
    )
    assert processing["status"] == "service_processing"
    assert processing["order"]["status"] == "completed"
    assert processing["order"]["after_sale_status"] == "service_processing"

    resolved = service.review_after_sale_case(
        case["case_id"],
        "complete",
        operator="operator-a",
        note="修改完成并已寄回",
    )
    assert resolved["status"] == "resolved"
    assert resolved["order"]["status"] == "completed"
    assert resolved["order"]["after_sale_status"] == "resolved"
    assert [event["event_type"] for event in resolved["events"]] == [
        "submitted",
        "approve_service",
        "complete",
    ]


def test_return_review_prepares_refund_without_calling_wechat_and_requires_second_confirmation(
    tmp_path,
    monkeypatch,
):
    service = OrderService(tmp_path / "admin-after-sale-refund.db")
    seed_paid_order(service, order_id="ORDER-AS-REFUND", user_id="user-refund")
    case = create_case(service, "ORDER-AS-REFUND", "user-refund")
    refund_calls = []

    def fake_refund(order, out_refund_no, refund_fee, total_fee, reason, config):
        refund_calls.append((order["order_id"], out_refund_no, refund_fee, total_fee, reason))
        return {"status": "SUCCESS", "refund_id": "WX-REFUND-AS-1"}

    class FakeWechatPayConfig:
        ready = True
        missing: list[str] = []

    monkeypatch.setattr("app.order_service.WechatPayConfig", FakeWechatPayConfig)
    monkeypatch.setattr(service, "create_wechat_refund", fake_refund)

    waiting_return = service.review_after_sale_case(
        case["case_id"],
        "request_return",
        operator="operator-b",
        note="请用户寄回商品后退款",
    )
    assert waiting_return["status"] == "awaiting_return"
    assert refund_calls == []
    assert waiting_return["order"]["status"] == "completed"

    refund_pending = service.review_after_sale_case(
        case["case_id"],
        "confirm_return",
        operator="operator-b",
        note="已收到并核验退回商品",
    )
    assert refund_pending["status"] == "refund_pending"
    assert refund_pending["approved_refund_fee"] == 12900
    assert refund_pending["order"]["status"] == "refund_requested"
    assert refund_pending["order"]["refund_status"] == "approved"
    assert refund_pending["order"]["refund"]["after_sale_case_id"] == case["case_id"]
    assert refund_calls == []

    with pytest.raises(ValueError, match="售后审核页"):
        service.approve_refund("ORDER-AS-REFUND", operator="operator-b")
    with pytest.raises(ValueError, match="售后审核页"):
        service.reject_refund("ORDER-AS-REFUND", operator="operator-b", note="绕过工单拒绝")

    resolved = service.submit_after_sale_refund(
        case["case_id"],
        operator="operator-b",
        note="确认订单与退款金额无误",
    )
    assert len(refund_calls) == 1
    assert refund_calls[0][2:4] == (12900, 12900)
    assert resolved["status"] == "resolved"
    assert resolved["order"]["status"] == "refunded"
    assert resolved["order"]["payment_status"] == "refunded"
    assert resolved["order"]["after_sale_status"] == "resolved"


def test_direct_refund_approval_is_server_priced_and_cannot_be_replayed(tmp_path):
    service = OrderService(tmp_path / "admin-after-sale-direct.db")
    seed_paid_order(service, order_id="ORDER-AS-DIRECT", user_id="user-direct", total_fee=1)
    case = create_case(service, "ORDER-AS-DIRECT", "user-direct")

    pending = service.review_after_sale_case(
        case["case_id"],
        "prepare_direct_refund",
        operator="operator-c",
        note="低金额质量问题，批准免退",
    )

    assert pending["status"] == "refund_pending"
    assert pending["approved_refund_fee"] == 1
    assert pending["order"]["refund"]["refund_fee"] == 1
    assert pending["order"]["refund"]["out_refund_no"] == f"RF{case['case_id']}"
    with pytest.raises(ValueError, match="不能免退进入退款"):
        service.review_after_sale_case(
            case["case_id"],
            "prepare_direct_refund",
            operator="operator-c",
        )


def test_wechat_processing_has_a_distinct_after_sale_status(tmp_path, monkeypatch):
    service = OrderService(tmp_path / "admin-after-sale-refunding.db")
    seed_paid_order(service, order_id="ORDER-AS-REFUNDING", user_id="user-refunding")
    case = create_case(service, "ORDER-AS-REFUNDING", "user-refunding")
    service.review_after_sale_case(
        case["case_id"],
        "prepare_direct_refund",
        operator="operator-processing",
        note="批准免退退款",
    )

    class FakeWechatPayConfig:
        ready = True
        missing: list[str] = []

    monkeypatch.setattr("app.order_service.WechatPayConfig", FakeWechatPayConfig)
    monkeypatch.setattr(
        service,
        "create_wechat_refund",
        lambda *_args, **_kwargs: {"status": "PROCESSING", "refund_id": "WX-PROCESSING-1"},
    )

    processing = service.submit_after_sale_refund(
        case["case_id"],
        operator="operator-processing",
        note="确认发起原路退款",
    )

    assert processing["status"] == "refunding"
    assert processing["status_text"] == "退款处理中"
    assert processing["order"]["refund_status"] == "processing"
    assert processing["order"]["after_sale_status"] == "refunding"
    assert processing["events"][-1]["event_type"] == "refund_submitted"


def test_failed_after_sale_refund_returns_to_pending_and_recovers_with_same_number(
    tmp_path,
    monkeypatch,
):
    service = OrderService(tmp_path / "admin-after-sale-refund-recovery.db")
    seed_paid_order(service, order_id="ORDER-AS-RECOVERY", user_id="user-recovery")
    case = create_case(service, "ORDER-AS-RECOVERY", "user-recovery")
    pending = service.review_after_sale_case(
        case["case_id"],
        "prepare_direct_refund",
        operator="operator-recovery",
        note="批准免退退款",
    )

    class FakeWechatPayConfig:
        ready = True
        missing: list[str] = []
        mch_id = "MCH-RECOVERY"

    refund_numbers: list[str] = []

    def fake_refund(_order, out_refund_no, *_args, **_kwargs):
        refund_numbers.append(out_refund_no)
        if len(refund_numbers) == 1:
            return {"status": "ABNORMAL", "refund_id": "WX-REFUND-FAILED"}
        return {"status": "SUCCESS", "refund_id": "WX-REFUND-RECOVERED"}

    monkeypatch.setattr("app.order_service.WechatPayConfig", FakeWechatPayConfig)
    monkeypatch.setattr(service, "create_wechat_refund", fake_refund)

    failed = service.submit_after_sale_refund(
        case["case_id"],
        operator="operator-recovery",
        note="首次提交",
    )
    original_refund_no = failed["order"]["refund"]["out_refund_no"]

    assert failed["status"] == "refund_pending"
    assert failed["order"]["refund_status"] == "abnormal"
    assert failed["events"][-1]["event_type"] == "refund_failed"
    with pytest.raises(OrderConflictError, match="退款恢复入口"):
        service.submit_after_sale_refund(
            case["case_id"],
            operator="operator-recovery",
            note="错误地再次点击普通退款入口",
        )

    monkeypatch.setattr(
        service,
        "query_wechat_refund",
        lambda out_refund_no, _config: {
            "mchid": "MCH-RECOVERY",
            "out_trade_no": pending["order"]["out_trade_no"],
            "transaction_id": pending["order"]["payment"]["transaction_id"],
            "out_refund_no": out_refund_no,
            "refund_id": "WX-REFUND-FAILED",
            "status": "ABNORMAL",
            "amount": {
                "total": pending["order"]["total_fee"],
                "refund": pending["order"]["total_fee"],
            },
        },
    )

    recovered = service.retry_after_sale_refund(
        case["case_id"],
        operator="operator-recovery",
        note="微信确认原退款异常，恢复提交",
    )

    assert recovered["status"] == "resolved"
    assert recovered["order"]["status"] == "refunded"
    assert recovered["order"]["refund_status"] == "success"
    assert recovered["order"]["refund"]["submission_attempts"] == 2
    assert refund_numbers == [original_refund_no, original_refund_no]


def test_admin_after_sale_api_requires_admin_and_exposes_real_case(tmp_path, monkeypatch):
    database = tmp_path / "admin-after-sale-api.db"
    service = OrderService(database)
    admin = AdminService(database)
    admin.register("after-sale-admin", "Strong-Password-2026")
    token = admin.login("after-sale-admin", "Strong-Password-2026")["token"]
    seed_paid_order(service, order_id="ORDER-AS-API-ADMIN", user_id="user-api-admin")
    case = create_case(
        service,
        "ORDER-AS-API-ADMIN",
        "user-api-admin",
        case_type="repair",
        reason_code="cord_loose",
        reason="弹力线已经明显松动，希望重新穿制",
    )
    monkeypatch.setattr(admin_api_module, "admin_service", admin)
    monkeypatch.setattr(admin_api_module, "order_service", service)

    unauthorized = client.get("/api/v1/admin/after-sales")
    assert unauthorized.status_code == 401

    headers = {"Authorization": f"Bearer {token}"}
    listed = client.get("/api/v1/admin/after-sales?status=requested&case_type=repair", headers=headers)
    reviewed = client.post(
        f"/api/v1/admin/after-sales/{case['case_id']}/review",
        headers=headers,
        json={"action": "approve_service", "note": "接受重新穿制服务"},
    )

    assert listed.status_code == 200
    assert listed.json()["data"][0]["case_id"] == case["case_id"]
    assert reviewed.status_code == 200
    assert reviewed.json()["data"]["status"] == "service_processing"
    assert reviewed.json()["data"]["reviewed_by"] == "after-sale-admin"


def test_manual_order_status_route_cannot_forge_refund_request(tmp_path):
    database = tmp_path / "admin-after-sale-status-guard.db"
    service = OrderService(database)
    admin = AdminService(database)
    seed_paid_order(service, order_id="ORDER-AS-GUARD", user_id="user-guard")

    assert not hasattr(admin, "update_order_status")
    assert "/api/v1/admin/orders/{order_id}/status" not in {
        route.path for route in app.routes if hasattr(route, "path")
    }
    assert service.get_order("ORDER-AS-GUARD")["status"] == "completed"


def test_shipping_is_idempotent_and_refund_request_blocks_fulfillment(tmp_path):
    service = OrderService(tmp_path / "shipping-state-guard.db")
    seed_paid_order(
        service,
        order_id="ORDER-SHIP-GUARD",
        user_id="user-ship-guard",
        status="pending_ship",
    )

    shipped = service.ship_paid_order(
        "ORDER-SHIP-GUARD",
        carrier="顺丰速运",
        tracking_no="SF1234567890",
        phone_tail="0000",
    )
    replay = service.ship_paid_order(
        "ORDER-SHIP-GUARD",
        carrier="顺丰速运",
        tracking_no="SF1234567890",
        phone_tail="0000",
    )

    assert shipped["status"] == "shipped"
    assert shipped["logistics"]["status"] == "awaiting_pickup"
    assert shipped["logistics"]["status_text"] == "已发货待揽收"
    assert replay["status_history"] == shipped["status_history"]
    with pytest.raises(OrderConflictError, match="不能更换快递单号"):
        service.ship_paid_order(
            "ORDER-SHIP-GUARD",
            carrier="顺丰速运",
            tracking_no="SF0987654321",
            phone_tail="0000",
        )

    seed_paid_order(
        service,
        order_id="ORDER-REFUND-BLOCK-SHIP",
        user_id="user-refund-block-ship",
        status="pending_ship",
    )
    service.request_refund(
        "ORDER-REFUND-BLOCK-SHIP",
        "user-refund-block-ship",
        "待发货退款",
    )
    with pytest.raises(ValueError, match="仅待发货订单可以发货"):
        service.ship_paid_order(
            "ORDER-REFUND-BLOCK-SHIP",
            carrier="顺丰速运",
            tracking_no="SF1122334455",
        )


def test_direct_refund_rejection_returns_to_single_pending_ship_state(tmp_path):
    service = OrderService(tmp_path / "refund-rejection-state.db")
    seed_paid_order(
        service,
        order_id="ORDER-REFUND-REJECT",
        user_id="user-refund-reject",
        status="pending_ship",
    )

    requested = service.request_refund("ORDER-REFUND-REJECT", "user-refund-reject", "想取消")
    replay = service.request_refund("ORDER-REFUND-REJECT", "user-refund-reject", "网络重试")
    assert replay["order_id"] == requested["order_id"]
    assert replay["status_history"] == requested["status_history"]
    restored = service.reject_refund(
        "ORDER-REFUND-REJECT",
        operator="operator-refund",
        note="定制已开始，已与用户确认继续制作",
    )

    assert restored["status"] == "pending_ship"
    assert restored["payment_status"] == "paid"
    assert restored["refund_status"] == "rejected"
    assert restored["after_sale_status"] == ""
    assert restored["status_history"][-1]["status"] == "pending_ship"


def test_return_shipment_and_cancel_follow_structured_after_sale_state_machine(tmp_path):
    service = OrderService(tmp_path / "after-sale-return-state.db")
    seed_paid_order(service, order_id="ORDER-RETURN", user_id="user-return")
    case = create_case(service, "ORDER-RETURN", "user-return")
    waiting = service.review_after_sale_case(
        case["case_id"],
        "request_return",
        operator="operator-return",
        note="请寄回商品核验",
    )
    assert waiting["status"] == "awaiting_return"

    with pytest.raises(ValueError, match="无权操作该订单"):
        service.submit_after_sale_return_shipment(
            "ORDER-RETURN",
            case["case_id"],
            "another-user",
            "顺丰速运",
            "SF1234567890",
        )
    returning = service.submit_after_sale_return_shipment(
        "ORDER-RETURN",
        case["case_id"],
        "user-return",
        "顺丰速运",
        "SF1234567890",
    )
    replay = service.submit_after_sale_return_shipment(
        "ORDER-RETURN",
        case["case_id"],
        "user-return",
        "顺丰速运",
        "SF1234567890",
    )

    assert returning["status"] == "returning"
    assert replay["return_tracking_no"] == "SF1234567890"
    with pytest.raises(OrderConflictError, match="不能更换快递单号"):
        service.submit_after_sale_return_shipment(
            "ORDER-RETURN",
            case["case_id"],
            "user-return",
            "顺丰速运",
            "SF0987654321",
        )
    with pytest.raises(ValueError, match="不能取消"):
        service.cancel_after_sale_case(
            "ORDER-RETURN",
            case["case_id"],
            "user-return",
        )
    events = service.admin_get_after_sale_case(case["case_id"])["events"]
    assert [event["event_type"] for event in events].count("return_shipped") == 1

    seed_paid_order(service, order_id="ORDER-CANCEL-AS", user_id="user-cancel-as")
    cancel_case = create_case(service, "ORDER-CANCEL-AS", "user-cancel-as")
    service.review_after_sale_case(
        cancel_case["case_id"],
        "request_return",
        operator="operator-return",
        note="等待用户决定是否寄回",
    )
    canceled = service.cancel_after_sale_case(
        "ORDER-CANCEL-AS",
        cancel_case["case_id"],
        "user-cancel-as",
        "暂时不处理",
    )
    replay_cancel = service.cancel_after_sale_case(
        "ORDER-CANCEL-AS",
        cancel_case["case_id"],
        "user-cancel-as",
        "重复点击",
    )
    assert canceled["status"] == "canceled"
    assert replay_cancel["canceled_at"] == canceled["canceled_at"]
    assert service.get_order("ORDER-CANCEL-AS")["status"] == "completed"
    assert service.get_order("ORDER-CANCEL-AS")["after_sale_status"] == "canceled"
