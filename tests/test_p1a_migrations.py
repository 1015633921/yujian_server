from __future__ import annotations

import sqlite3

from app.admin_service import AdminService
from app.migrations.runner import downgrade, upgrade
from app.order_service import OrderService
from app.repository import AssessmentRepository


def columns(path, table: str) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def tables(path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def indexes(path, table: str) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA index_list({table})")}


def test_p1a_migration_is_additive_idempotent_and_independently_reversible(tmp_path):
    db_path = tmp_path / "p1a-migration.db"
    AdminService(db_path)
    OrderService(db_path)
    AssessmentRepository(db_path)

    assert "payment_webhook_events" not in tables(db_path)
    applied = upgrade("sqlite", db_path)
    assert "20260712_03_p1a_payment_events" in applied
    assert upgrade("sqlite", db_path) == []
    assert "payment_webhook_events" in tables(db_path)
    assert "payload" not in columns(db_path, "payment_webhook_events")
    assert "body" not in columns(db_path, "payment_webhook_events")
    assert {
        "payment_provider",
        "payment_transaction_id",
        "payment_appid",
        "payment_mchid",
        "payment_currency",
        "payment_confirmed_at",
    }.issubset(columns(db_path, "orders"))
    assert {
        "ux_payment_webhook_provider_event",
        "idx_payment_webhook_order_received",
        "idx_payment_webhook_status_updated",
        "idx_payment_webhook_transaction",
    }.issubset(indexes(db_path, "payment_webhook_events"))

    assert downgrade("sqlite", db_path, steps=21) == [
        "20260807_23_community_post_image_gallery",
        "20260806_22_material_catalog_indexes",
        "20260806_21_material_sku_revisions",
        "20260806_20_material_asset_versions",
        "20260806_19_material_series_identity",
        "20260806_18_custom_design_queue_indexes",
        "20260806_17_custom_design_deposits",
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
        "20260712_05_p1c_runtime_tasks",
        "20260712_04_p1b_report_snapshots",
        "20260712_03_p1a_payment_events",
    ]
    assert "payment_webhook_events" not in tables(db_path)
    assert "order_requests" in tables(db_path)
    AdminService(db_path)
    OrderService(db_path)
    assert upgrade("sqlite", db_path) == [
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
    ]
