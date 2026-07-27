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
from app.order_service import OrderService
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
                    '[]', 20, 0, 1, 0, ?, ?)
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


def workbench(material_id: str = "designer-bead") -> dict:
    layout = [
        {
            "id": material_id,
            "material_id": material_id,
            "quantity": 1,
            "price": "10.00",
            "image_url": "",
            "selected_image_url": "",
        }
        for _ in range(3)
    ]
    return {
        "schema_version": 1,
        "wrist_size_cm": 16,
        "bead_size_mm": 8,
        "layout": layout,
        "selected": [material_id] * len(layout),
        "summary": {"count": len(layout), "price": "30.00", "total_fee": 3000},
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


def test_structured_draft_publish_and_confirm_creates_one_pending_order(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")
    custom, orders = build_services(tmp_path)
    add_material(orders)
    created = custom.create("designer-user", request_payload())

    drafted = custom.save_draft(created["request_id"], "designer-1", workbench())
    assert drafted["status"] == "designing"
    assert drafted["draft"]["draft_version"] == 1
    assert drafted["draft"]["workbench"]["selected"] == ["designer-bead"] * 3

    published = custom.publish_proposal(
        created["request_id"],
        "designer-1",
        {
            "title": "清透专属款",
            "description": "三颗测试珠",
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
    order = confirmed["order"]
    assert confirmed["status"] == "confirmed"
    assert order["status"] == "pending_payment"
    assert order["payment_status"] == "unpaid"
    assert order["receiver"] == {}
    assert order["design"]["selected"] == ["designer-bead"] * 3
    assert len(order["sequence"]) == 3

    replay = custom.user_response(
        created["request_id"],
        "designer-user",
        "confirm",
    )
    assert replay["order"]["order_id"] == order["order_id"]
    assert replay["idempotent_replay"] is True

    with orders.connect() as connection:
        row = connection.execute(
            "SELECT reserved_stock FROM managed_materials WHERE id = 'designer-bead'"
        ).fetchone()
        count = connection.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
    assert int(row["reserved_stock"]) == 3
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
