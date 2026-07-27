from __future__ import annotations

import sqlite3

import pytest

from app.admin_service import AdminService
from app.migrations.runner import downgrade, upgrade
from app.money import cents_to_text, money_to_cents, stored_cents
from app.order_service import OrderPricingError, OrderService


def test_money_parser_uses_exact_integer_cents():
    assert money_to_cents("12.34") == 1234
    assert money_to_cents(12) == 1200
    assert cents_to_text(1234) == "12.34"
    assert stored_cents("1234") == 1234

    for invalid in (None, "", True, "nan", "inf", "12.345", -1):
        with pytest.raises(ValueError):
            money_to_cents(invalid)
    for invalid in (None, "", True, "12.5", -1, 100_000_000_000):
        with pytest.raises(ValueError):
            stored_cents(invalid)


def test_two_single_side_bead_caps_are_priced_as_two_independent_sku_lines():
    sequence = [
        {"id": "bead-8", "sku": "bead-8", "unit_price_cents": 1000, "subtotal_cents": 1000},
        {"id": "cap-8", "sku": "cap-8", "unit_price_cents": 250, "subtotal_cents": 250},
        {"id": "cap-8", "sku": "cap-8", "unit_price_cents": 250, "subtotal_cents": 250},
    ]

    bom = OrderService.rebuild_bom_from_sequence(sequence)
    cap_line = next(item for item in bom if item["sku"] == "cap-8")

    assert cap_line["qty"] == 2
    assert cap_line["subtotal_cents"] == 500
    assert OrderService.calculate_sequence_total(sequence) == 15


def test_bead_cap_attachment_slots_reject_invalid_and_duplicate_sides():
    bead = {"id": "bead-8", "sku": "bead-8"}
    cap = {
        "id": "cap-8",
        "sku": "cap-8",
        "placement_mode": "attached_side",
        "attachment_mode": "bead_cap",
        "attachment": {"mode": "bead_cap", "host_index": 1, "side": "right"},
    }

    OrderService.validate_attachment_sequence([bead, cap])
    with pytest.raises(ValueError, match="不能重复安装"):
        OrderService.validate_attachment_sequence([bead, cap, dict(cap)])
    with pytest.raises(ValueError, match="主珠位置无效"):
        OrderService.validate_attachment_sequence([
            bead,
            {**cap, "attachment": {"mode": "bead_cap", "host_index": 2, "side": "left"}},
        ])


def test_price_cents_migration_backfills_only_exact_positive_legacy_prices(tmp_path):
    db_path = tmp_path / "price-migration.db"
    AdminService(db_path)
    OrderService(db_path)
    upgrade("sqlite", db_path)
    assert downgrade("sqlite", db_path, steps=11) == [
        "20260727_16_custom_design_workbench",
        "20260727_15_report_codes",
        "20260727_14_custom_design_service",
        "20260724_13_web_login_pairing",
        "20260723_12_ai_material_annotations",
        "20260715_11_material_types",
        "20260714_10_material_physical_specs",
        "20260714_09_after_sale_return_flow",
        "20260713_08_after_sale_cases",
        "20260713_07_order_receipt_completion",
        "20260712_06_p1_material_price_cents",
    ]

    with sqlite3.connect(db_path) as connection:
        ids = [row[0] for row in connection.execute("SELECT id FROM managed_materials ORDER BY id LIMIT 3")]
        assert len(ids) == 3
        connection.execute("UPDATE managed_materials SET price = 12.34 WHERE id = ?", (ids[0],))
        connection.execute("UPDATE managed_materials SET price = 12.345 WHERE id = ?", (ids[1],))
        connection.execute("UPDATE managed_materials SET price = 0 WHERE id = ?", (ids[2],))

    assert upgrade("sqlite", db_path) == [
        "20260712_06_p1_material_price_cents",
        "20260713_07_order_receipt_completion",
        "20260713_08_after_sale_cases",
        "20260714_09_after_sale_return_flow",
        "20260714_10_material_physical_specs",
        "20260715_11_material_types",
        "20260723_12_ai_material_annotations",
        "20260724_13_web_login_pairing",
        "20260727_14_custom_design_service",
        "20260727_15_report_codes",
        "20260727_16_custom_design_workbench",
    ]
    assert upgrade("sqlite", db_path) == []
    with sqlite3.connect(db_path) as connection:
        values = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT id, price_cents FROM managed_materials WHERE id IN (?, ?, ?)", ids
            )
        }
    assert values[ids[0]] == 1234
    assert values[ids[1]] is None
    assert values[ids[2]] is None

    assert downgrade("sqlite", db_path, steps=11) == [
        "20260727_16_custom_design_workbench",
        "20260727_15_report_codes",
        "20260727_14_custom_design_service",
        "20260724_13_web_login_pairing",
        "20260723_12_ai_material_annotations",
        "20260715_11_material_types",
        "20260714_10_material_physical_specs",
        "20260714_09_after_sale_return_flow",
        "20260713_08_after_sale_cases",
        "20260713_07_order_receipt_completion",
        "20260712_06_p1_material_price_cents",
    ]
    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(managed_materials)")}
        legacy_price = connection.execute("SELECT price FROM managed_materials WHERE id = ?", (ids[0],)).fetchone()[0]
    assert "price_cents" not in columns
    assert legacy_price == pytest.approx(12.34)


def test_admin_material_writes_exact_price_cents_and_rejects_extra_precision(tmp_path):
    db_path = tmp_path / "admin-price-cents.db"
    service = AdminService(db_path)
    OrderService(db_path)
    upgrade("sqlite", db_path)
    category = service.save_material_category({"top": "bead", "name": "价格测试"})
    service.save_material_series({"category_id": category["id"], "name": "整数分测试"})
    payload = {
        "id": "price-cents-material",
        "top": "bead",
        "category": "价格测试",
        "series": "整数分测试",
        "name": "整数分测试",
        "effect": "测试",
        "element": "水",
        "price_per_bead": "12.34",
        "size_mm": 8,
        "weight_g": 1,
        "stock": 5,
    }

    service.save_material(payload)
    with sqlite3.connect(db_path) as connection:
        price, price_cents = connection.execute(
            "SELECT price, price_cents FROM managed_materials WHERE id = ?",
            (payload["id"],),
        ).fetchone()
    assert price == pytest.approx(12.34)
    assert price_cents == 1234

    service.batch_update_materials([payload["id"]], "price", "8.80")
    with sqlite3.connect(db_path) as connection:
        price, price_cents = connection.execute(
            "SELECT price, price_cents FROM managed_materials WHERE id = ?",
            (payload["id"],),
        ).fetchone()
    assert price == pytest.approx(8.8)
    assert price_cents == 880

    with pytest.raises(ValueError, match="最多保留两位小数"):
        service.save_material({**payload, "id": "invalid-price-material", "price_per_bead": "1.234"})
    with pytest.raises(ValueError, match="最多保留两位小数"):
        service.batch_update_materials([payload["id"]], "price", "1.234")


def test_order_uses_only_price_cents_and_fails_closed_without_it(tmp_path):
    db_path = tmp_path / "order-price-authority.db"
    AdminService(db_path)
    OrderService(db_path)
    upgrade("sqlite", db_path)
    service = OrderService(db_path)
    service.get_user = lambda _user_id: None
    timestamp = "2026-07-12T12:00:00+00:00"
    with service.connect() as connection:
        connection.execute(
            """
            INSERT INTO managed_materials
            (id, skuId, top, category, series, material_code, grade, name, effect,
             element, price, price_cents, size, weight, cost_price, safety_stock, supplier_name,
             purchase_note, color, shine, image_path, image_url, image_urls_json,
             stock, reserved_stock, enabled, sort_order, created_at, updated_at)
            VALUES ('authority-sku', 'authority-sku', 'bead', 'test', 'test', 'authority', '',
                    '权威价格', '', '水', 0.01, 1234, 8, 1, 0, 0, '', '', '#fff', '#fff', '', '',
                    '[]', 3, 0, 1, 0, ?, ?)
            """,
            (timestamp, timestamp),
        )
        connection.execute(
            """
            INSERT INTO managed_materials
            (id, skuId, top, category, series, material_code, grade, name, effect,
             element, price, price_cents, size, weight, cost_price, safety_stock, supplier_name,
             purchase_note, color, shine, image_path, image_url, image_urls_json,
             stock, reserved_stock, enabled, sort_order, created_at, updated_at)
            VALUES ('legacy-only-sku', 'legacy-only-sku', 'bead', 'test', 'test', 'legacy', '',
                    '旧价格', '', '水', 12.34, NULL, 8, 1, 0, 0, '', '', '#fff', '#fff', '', '',
                    '[]', 3, 0, 1, 0, ?, ?)
            """,
            (timestamp, timestamp),
        )

    payload = {
        "idempotency_key": "authority-price-key",
        "user_id": "authority-user",
        "receiver": {"name": "测试", "phone": "13800000000", "address": "测试地址"},
        "design": {},
        "sequence": [{"id": "authority-sku", "price": "12.34", "quantity": 1}],
        "bom": [],
    }
    result = service.create_order(payload)
    assert result["order"]["total_fee"] == 1234
    assert result["order"]["sequence"][0]["unit_price_cents"] == 1234

    with pytest.raises(OrderPricingError, match="缺少有效价格"):
        service.create_order(
            {
                **payload,
                "idempotency_key": "legacy-price-key",
                "sequence": [{"id": "legacy-only-sku", "price": "12.34", "quantity": 1}],
            }
        )
