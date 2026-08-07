from __future__ import annotations

import json
import sqlite3

from app.admin_service import AdminService
from app.migrations.runner import downgrade, upgrade
from app.order_service import OrderService
from app.repository import AssessmentRepository


def table_names(path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def columns(path, table: str) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def test_p1b_migration_backfills_stable_legacy_snapshot_and_round_trips(tmp_path):
    db_path = tmp_path / "p1b-migration.db"
    AdminService(db_path)
    OrderService(db_path)
    AssessmentRepository(db_path)
    upgrade("sqlite", db_path)
    assert downgrade("sqlite", db_path, steps=22) == [
        "20260807_25_material_catalog_v2",
        "20260807_24_material_rule_cleanup",
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
    ]

    legacy = {
        "assessment_id": "legacy-p1b",
        "created_at": "2026-07-01T12:00:00+08:00",
        "input_summary": {
            "user_id": "legacy-p1b-user",
            "name": "历史用户",
            "birthday": "1990-01-01",
            "birth_time": "10:00",
            "birth_place": "未知地点",
            "core_wishes": ["健康护身/保持专注"],
        },
        "final_energy_profile": {"木": 20, "火": 20, "土": 20, "金": 20, "水": 20},
        "interpretation": {"balance_index": 100, "headline": "历史报告"},
    }
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO energy_assessments
            (assessment_id, user_id, fingerprint, name, core_wish, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-p1b", "legacy-p1b-user", "legacy-source-hash", "历史用户",
                "健康护身/保持专注", json.dumps(legacy, ensure_ascii=False), legacy["created_at"],
            ),
        )

    assert upgrade("sqlite", db_path) == [
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
    with sqlite3.connect(db_path) as connection:
        first = connection.execute(
            "SELECT report_id, report_version, calibration_status, algorithm_version FROM report_snapshots WHERE assessment_id = ?",
            ("legacy-p1b",),
        ).fetchone()
    assert first[1:] == (1, "legacy_unknown", "legacy_unknown")
    first_report_id = first[0]
    assert upgrade("sqlite", db_path) == []

    assert downgrade("sqlite", db_path, steps=22) == [
        "20260807_25_material_catalog_v2",
        "20260807_24_material_rule_cleanup",
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
    ]
    assert "report_snapshots" not in table_names(db_path)
    assert "report_id" not in columns(db_path, "assessment_recommendations")
    assert upgrade("sqlite", db_path) == [
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
    with sqlite3.connect(db_path) as connection:
        second_report_id = connection.execute(
            "SELECT report_id FROM report_snapshots WHERE assessment_id = ?",
            ("legacy-p1b",),
        ).fetchone()[0]
    assert second_report_id == first_report_id
