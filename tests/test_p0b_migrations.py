from __future__ import annotations

import sqlite3

from app.admin_service import AdminService
from app.migrations.runner import downgrade, upgrade
from app.order_service import OrderService


def columns(path, table: str) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def tables(path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_p0b_migration_is_additive_idempotent_and_independently_reversible(tmp_path):
    db_path = tmp_path / "p0b-migration.db"
    AdminService(db_path)
    OrderService(db_path)

    assert upgrade("sqlite", db_path) == [
        "20260712_01_p0a_security",
        "20260712_02_p0b_order_integrity",
        "20260712_03_p1a_payment_events",
        "20260712_04_p1b_report_snapshots",
        "20260712_05_p1c_runtime_tasks",
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

        "20260806_17_custom_design_deposits",
        "20260806_18_custom_design_queue_indexes",
        "20260806_19_material_series_identity",
        "20260806_20_material_asset_versions",
        "20260806_21_material_sku_revisions",
        "20260806_22_material_catalog_indexes",
        "20260807_23_community_post_image_gallery",
        "20260807_24_material_rule_cleanup",
        "20260807_25_material_catalog_v2",
    ]
    assert upgrade("sqlite", db_path) == []
    assert {"idempotency_key", "request_hash", "reservation_expires_at"}.issubset(columns(db_path, "orders"))
    assert "reserved_stock" in columns(db_path, "managed_materials")
    assert {"order_requests", "inventory_reservations", "user_sessions"}.issubset(tables(db_path))

    assert downgrade("sqlite", db_path, steps=1) == ["20260807_25_material_catalog_v2"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260807_24_material_rule_cleanup"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260807_23_community_post_image_gallery"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260806_22_material_catalog_indexes"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260806_21_material_sku_revisions"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260806_20_material_asset_versions"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260806_19_material_series_identity"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260806_18_custom_design_queue_indexes"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260806_17_custom_design_deposits"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260727_16_custom_design_workbench"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260727_15_report_codes"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260727_14_custom_design_service"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260724_13_web_login_pairing"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260723_12_ai_material_annotations"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260715_11_material_types"]
    assert downgrade("sqlite", db_path, steps=1) == ["20260714_10_material_physical_specs"]
    assert "physical_specs_json" not in columns(db_path, "managed_materials")
    assert downgrade("sqlite", db_path, steps=1) == ["20260714_09_after_sale_return_flow"]
    assert "after_sale_cases" in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260713_08_after_sale_cases"]
    assert "after_sale_cases" not in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260713_07_order_receipt_completion"]
    assert "order_requests" in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260712_06_p1_material_price_cents"]
    assert "order_requests" in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260712_05_p1c_runtime_tasks"]
    assert "order_requests" in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260712_04_p1b_report_snapshots"]
    assert "order_requests" in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260712_03_p1a_payment_events"]
    assert "order_requests" in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260712_02_p0b_order_integrity"]
    assert "user_sessions" in tables(db_path)
    assert "order_requests" not in tables(db_path)
    assert "reserved_stock" not in columns(db_path, "managed_materials")

    assert upgrade("sqlite", db_path) == [
        "20260712_02_p0b_order_integrity",
        "20260712_03_p1a_payment_events",
        "20260712_04_p1b_report_snapshots",
        "20260712_05_p1c_runtime_tasks",
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
        "20260806_17_custom_design_deposits",
        "20260806_18_custom_design_queue_indexes",
        "20260806_19_material_series_identity",
        "20260806_20_material_asset_versions",
        "20260806_21_material_sku_revisions",
        "20260806_22_material_catalog_indexes",
        "20260807_23_community_post_image_gallery",
        "20260807_24_material_rule_cleanup",
        "20260807_25_material_catalog_v2",
    ]
