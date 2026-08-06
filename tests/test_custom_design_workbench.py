from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app import admin_api
from app.admin_api import CustomDesignWorkbenchPayload, validated_custom_design_workbench
from app.admin_service import AdminService
from app.custom_design_service import CustomDesignService
from app.migrations.runner import upgrade
from app.money import money_to_cents
from app.order_service import OrderService, WechatPayConfig
from app.repository import AssessmentRepository


def build_services(tmp_path):
    database = tmp_path / f"custom-workbench-{uuid4().hex}.db"
    AssessmentRepository(database)
    AdminService(database)
    OrderService(database)
    upgrade("sqlite", database)
    orders = OrderService(database)
    orders.get_user = lambda _user_id: None
    custom = CustomDesignService(database, order_service=orders)
    return custom, orders


def add_material(orders: OrderService, material_id: str = "designer-bead") -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with orders.connect() as connection:
        connection.execute(
            """
            INSERT INTO managed_materials
            (id, skuId, top, category, series, material_code, grade, name, effect,
             element, price, price_cents, size, weight, cost_price, safety_stock,
             supplier_name, purchase_note, color, shine, image_path, image_url,
             image_urls_json, stock, reserved_stock, enabled, sort_order, created_at, updated_at)
            VALUES (?, ?, 'bead', 'test', 'DESIGN', ?, '', '设计师测试珠', '', '水',
                    '10.00', ?, 8, 1, 0, 0, '', '', '#ffffff', '#ffffff', '', '',
                    '[]', 40, 0, 1, 0, ?, ?)
            """,
            (
                material_id,
                f"sku-{material_id}",
                material_id,
                money_to_cents("10.00", field_name="测试价格"),
                timestamp,
                timestamp,
            ),
        )


def request_payload() -> dict:
    return {
        "report_id": "report-for-designer",
        "report_version": 1,
        "assessment_id": None,
        "wrist_size_cm": 16,
        "bead_size_mm": 8,
        "budget": "100–200 元",
        "style_preference": "清透自然",
        "color_preference": "蓝白",
        "accessory_preference": "少量银饰",
        "wear_scene": "日常",
        "note": "",
    }


def workbench(material_id: str = "designer-bead", count: int = 24) -> dict:
    layout = [
        {
            "id": material_id,
            "material_id": material_id,
            "quantity": 1,
            "price": "10.00",
            "image_url": "",
            "selected_image_url": "",
        }
        for _ in range(count)
    ]
    return {
        "schema_version": 1,
        "wrist_size_cm": 16,
        "bead_size_mm": 8,
        "layout": layout,
        "selected": [material_id] * len(layout),
        "summary": {"count": len(layout), "price": f"{count * 10:.2f}", "total_fee": count * 1000},
    }


def test_admin_workbench_uses_gallery_asset_instead_of_primary_image(monkeypatch):
    class FakeOrderService:
        @staticmethod
        def validate_and_refresh_material_prices(_layout):
            return [{
                "id": "gallery-bead",
                "name": "图库测试珠",
                "image_url": "https://cdn.example.com/primary.webp",
                "gallery_image_urls": [
                    "https://cdn.example.com/gallery-1.webp",
                    "https://cdn.example.com/gallery-2.webp",
                ],
                "price": "10.00",
                "subtotal_cents": 1000,
            }]

        @staticmethod
        def cents_text(value):
            return f"{value / 100:.2f}"

    monkeypatch.setattr(admin_api, "order_service", FakeOrderService())
    payload = CustomDesignWorkbenchPayload(
        wrist_size_cm=16,
        bead_size_mm=8,
        layout=[{"material_id": "gallery-bead"}],
    )

    result = validated_custom_design_workbench(payload)

    assert result["layout"][0]["selected_image_url"] == "https://cdn.example.com/gallery-1.webp"
    assert result["layout"][0]["image_url"] != "https://cdn.example.com/primary.webp"


def test_structured_draft_publish_confirms_design_refunds_deposit_then_creates_one_pending_order(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")
    custom, orders = build_services(tmp_path)
    add_material(orders)
    created = custom.create("designer-user", request_payload())
    paid = custom.mark_deposit_paid_for_dev(created["request_id"], "designer-user")
    assert paid["status"] == "submitted"
    assert paid["deposit"]["status"] == "paid"

    drafted = custom.save_draft(created["request_id"], "designer-1", workbench())
    assert drafted["status"] == "designing"
    assert drafted["draft"]["draft_version"] == 1
    assert drafted["draft"]["workbench"]["selected"] == ["designer-bead"] * 24

    published = custom.publish_proposal(
        created["request_id"],
        "designer-1",
        {
            "title": "清透专属款",
            "description": "二十四颗测试珠",
            "image_urls": [],
            "workbench": workbench(),
        },
    )
    assert published["status"] == "proposed"
    assert published["draft"] is None

    confirmed = custom.user_response(
        created["request_id"],
        "designer-user",
        "confirm",
    )
    assert confirmed["status"] == "completed"
    assert confirmed["deposit"]["status"] == "refunded"
    assert "order" not in confirmed

    order_created = custom.create_order_from_proposal(created["request_id"], "designer-user")
    order = order_created["order"]
    assert order["status"] == "pending_payment"
    assert order["payment_status"] == "unpaid"
    assert order["receiver"] == {}
    assert order["design"]["selected"] == ["designer-bead"] * 24
    assert len(order["sequence"]) == 24

    replay = custom.create_order_from_proposal(
        created["request_id"],
        "designer-user",
    )
    assert replay["order"]["order_id"] == order["order_id"]
    assert replay["idempotent_replay"] is True

    with orders.connect() as connection:
        row = connection.execute(
            "SELECT reserved_stock FROM managed_materials WHERE id = 'designer-bead'"
        ).fetchone()
        count = connection.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
    assert int(row["reserved_stock"]) == 24
    assert int(count) == 1

    with pytest.raises(ValueError, match="收货人"):
        orders.request_payment(order["order_id"], "designer-user")
    orders.update_order_receiver(
        order["order_id"],
        "designer-user",
        {"name": "测试用户", "phone": "13800000000", "address": "测试地址"},
    )
    payment = orders.request_payment(order["order_id"], "designer-user")
    assert payment["order"]["order_id"] == order["order_id"]


def test_deposit_payment_webhook_is_idempotent_and_rejects_reused_transaction(tmp_path, monkeypatch):
    monkeypatch.setenv("WECHAT_PAY_APP_ID", "wx-test")
    monkeypatch.setenv("WECHAT_PAY_MCH_ID", "mch-test")
    custom, _orders = build_services(tmp_path)
    first = custom.create("designer-user-a", request_payload())
    second = custom.create("designer-user-b", {**request_payload(), "report_id": "report-for-designer-b"})
    transaction_id = "wx-transaction-1"
    config = WechatPayConfig()

    def out_trade_no(request):
        with custom.connect() as connection:
            row = connection.execute(
                "SELECT out_trade_no FROM custom_design_deposits WHERE request_id = ?",
                (request["request_id"],),
            ).fetchone()
        return row["out_trade_no"]

    def transaction(request):
        return {
            "out_trade_no": out_trade_no(request),
            "trade_state": "SUCCESS",
            "transaction_id": transaction_id,
            "success_time": "2026-08-06T00:00:00Z",
            "appid": "wx-test",
            "mchid": "mch-test",
            "amount": {"total": request["deposit"]["amount_fee"], "currency": "CNY"},
        }

    first_result = custom.handle_wechat_payment_transaction(transaction(first), config)
    assert first_result["processing_status"] == "succeeded"
    assert custom.get_for_user(first["request_id"], "designer-user-a")["status"] == "submitted"
    assert custom.handle_wechat_payment_transaction(transaction(first), config)["processing_status"] == "succeeded"

    with pytest.raises(ValueError, match="已属于其他保证金"):
        custom.handle_wechat_payment_transaction(transaction(second), config)
