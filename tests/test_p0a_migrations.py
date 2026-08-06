from __future__ import annotations

import sqlite3

from app.migrations.runner import downgrade, upgrade
from app.admin_service import AdminService
from app.order_service import OrderService
from app.repository import AssessmentRepository


def sqlite_tables(path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def sqlite_columns(path, table) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def test_p0a_migration_is_explicit_idempotent_and_reversible(tmp_path):
    db_path = tmp_path / "migration.db"
    OrderService(db_path)
    AdminService(db_path)
    AssessmentRepository(db_path)

    assert "user_sessions" not in sqlite_tables(db_path)
    assert "share_token_hash" not in sqlite_columns(db_path, "diy_designs")

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
    ]
    assert upgrade("sqlite", db_path) == []
    assert "user_sessions" in sqlite_tables(db_path)
    assert {
        "share_status",
        "share_token_hash",
        "share_published_at",
        "share_revoked_at",
    }.issubset(sqlite_columns(db_path, "diy_designs"))

    assert downgrade("sqlite", db_path) == [
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
        "20260712_02_p0b_order_integrity",
        "20260712_01_p0a_security",
    ]
    assert "user_sessions" not in sqlite_tables(db_path)
    assert "share_token_hash" not in sqlite_columns(db_path, "diy_designs")

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
    ]
