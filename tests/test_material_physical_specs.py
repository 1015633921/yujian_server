from __future__ import annotations

import json
import sqlite3

import pytest

from app.admin_service import AdminService
from app.material_knowledge import enrich_materials_with_knowledge
from app.material_options import normalize_material_params, public_material_options
from app.materials import normalize_db_material, slim_material
from app.migrations.runner import downgrade, upgrade
from app.order_service import OrderService
from app.repository import AssessmentRepository


def table_columns(path, table: str) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def test_sku_physical_specs_override_series_shape_without_leaking_between_sizes(tmp_path):
    db_path = tmp_path / "material-physical-specs.db"
    service = AdminService(db_path)
    category = service.save_material_category({"top": "accessory", "name": "异形测试"})
    service.save_material_series(
        {
            "category_id": category["id"],
            "name": "测试随形",
            "primary_element": "metal",
            "effects": ["focus"],
            "image_url": "https://cdn-test.yustream.cn/materials/test-irregular.webp",
            "material_params": {
                "bead_shape": "nugget",
                "placement_mode": "threaded",
                "image_string_axis_deg": 0,
            },
        }
    )

    base = {
        "top": "accessory",
        "category": "异形测试",
        "series": "测试随形",
        "name": "测试随形",
        "primary_element": "metal",
        "effects": ["focus"],
        "price_per_bead": "10.00",
        "weight_g": 1,
        "stock": 5,
        "thumbnail_url": "https://cdn-test.yustream.cn/materials/test-irregular.webp",
    }
    small = service.save_material(
        {
            **base,
            "size_mm": 8,
            "physical_specs": {
                "string_axis_width_mm": 4.2,
                "body_width_mm": 8,
                "body_height_mm": 6.5,
            },
        }
    )
    large = service.save_material(
        {
            **base,
            "size_mm": 15,
            "physical_specs": {
                "string_axis_width_mm": 8.1,
                "body_width_mm": 15,
                "body_height_mm": 11.8,
            },
        }
    )

    assert small["visual"]["material_params"] == {
        "bead_shape": "nugget",
        "placement_mode": "threaded",
        "image_string_axis_deg": 0.0,
        "string_axis_width_mm": 4.2,
        "body_width_mm": 8.0,
        "body_height_mm": 6.5,
    }
    assert large["visual"]["material_params"]["string_axis_width_mm"] == 8.1
    assert large["physical_specs"]["body_width_mm"] == 15.0

    incomplete = service.save_material({**base, "size_mm": 10})
    assert incomplete["quality"]["ready_for_sale"] is False
    assert "physical_specs_missing" in {
        issue["key"] for issue in incomplete["quality"]["issues"]
    }

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT size, physical_specs_json FROM managed_materials "
            "WHERE series=? AND physical_specs_json <> '{}' ORDER BY size",
            ("测试随形",),
        ).fetchall()
        knowledge = connection.execute(
            "SELECT material_params_json FROM material_knowledge WHERE code=?",
            (small["sku"]["material_code"],),
        ).fetchone()

    assert [json.loads(row[1])["string_axis_width_mm"] for row in rows] == [4.2, 8.1]
    assert "string_axis_width_mm" not in json.loads(knowledge[0])


def test_bead_cap_params_keep_side_attachment_and_compatibility_dimensions():
    params = normalize_material_params(
        {
            "bead_shape": "包珠隔片",
            "placement_mode": "单边吸附",
            "string_axis_width_mm": "1.2",
            "body_width_mm": "5",
            "body_height_mm": "2.4",
            "compatible_bead_size_mm": "8",
            "compatible_size_tolerance_mm": "0.5",
        }
    )

    assert params == {
        "bead_shape": "bead_cap",
        "placement_mode": "attached_side",
        "string_axis_width_mm": 1.2,
        "body_width_mm": 5.0,
        "body_height_mm": 2.4,
        "compatible_bead_size_mm": 8.0,
        "compatible_size_tolerance_mm": 0.5,
    }


def test_existing_sku_can_save_physical_specs_when_series_knowledge_is_incomplete(tmp_path):
    db_path = tmp_path / "material-incomplete-knowledge.db"
    service = AdminService(db_path)
    OrderService(db_path)
    AssessmentRepository(db_path)
    upgrade("sqlite", db_path)
    category = service.save_material_category({"top": "accessory", "name": "合金配件"})
    service.save_material_series(
        {
            "category_id": category["id"],
            "name": "合金配件 01",
            "material_code": "alloy_accessory_01",
        }
    )

    with service.connect() as connection:
        timestamp = "2026-07-20T00:00:00Z"
        connection.execute(
            """
            INSERT INTO managed_materials
            (id, skuId, top, category, series, material_code, grade, name, effect, element,
             price, price_cents, size, weight, color, shine, image_path, image_url,
             image_urls_json, physical_specs_json, stock, enabled, sort_order, created_at, updated_at)
            VALUES (?, ?, 'accessory', '合金配件', '合金配件 01', 'alloy_accessory_01', '',
                    '合金配件 01', '', '', 0.1, 10, 8, 1, '#dfe3e5', '#ffffff', '', '',
                    '[]', '{}', 5, 1, 1, ?, ?)
            """,
            ("alloy-01", "200000000001", timestamp, timestamp),
        )

    saved = service.save_material(
        {
            "id": "alloy-01",
            "skuId": "200000000001",
            "material_code": "alloy_accessory_01",
            "top": "accessory",
            "category": "合金配件",
            "series": "合金配件 01",
            "name": "合金配件 01",
            "effect": "",
            "element": "",
            "primary_element": "",
            "effects": [],
            "price_per_bead": 0.1,
            "size_mm": 8,
            "weight_g": 1,
            "stock": 5,
            "enabled": True,
            "physical_specs": {
                "string_axis_width_mm": 3.2,
                "body_width_mm": 10,
                "body_height_mm": 6,
            },
        },
        material_id="alloy-01",
    )

    assert saved["physical_specs"] == {
        "string_axis_width_mm": 3.2,
        "body_width_mm": 10.0,
        "body_height_mm": 6.0,
    }
    assert saved["energy"]["primary_element"] == ""
    assert saved["sku"]["price_per_bead"] == 0.1
    assert saved["sku"]["stock"] == 5
    assert saved["quality"]["ready_for_sale"] is False
    assert "primary_element_missing" in {issue["key"] for issue in saved["quality"]["issues"]}


def test_new_sku_does_not_require_recommendation_knowledge(tmp_path):
    service = AdminService(tmp_path / "new-material-knowledge-gate.db")
    category = service.save_material_category({"top": "accessory", "name": "合金配件"})
    service.save_material_series(
        {
            "category_id": category["id"],
            "name": "合金配件 02",
            "material_code": "alloy_accessory_02",
        }
    )

    saved = service.save_material(
        {
            "top": "accessory",
            "category": "合金配件",
            "series": "合金配件 02",
            "name": "合金配件 02",
            "price_per_bead": 0.1,
            "size_mm": 8,
            "weight_g": 1,
            "stock": 5,
            "physical_specs": {
                "string_axis_width_mm": 3.2,
                "body_width_mm": 10,
                "body_height_mm": 6,
            },
        }
    )

    assert saved["energy"]["primary_element"] == ""
    assert saved["energy"]["effects"] == []
    assert saved["physical_specs"]["string_axis_width_mm"] == 3.2

    with pytest.raises(ValueError, match="主五行.*包含未维护选项"):
        service.save_material(
            {
                "top": "accessory",
                "category": "合金配件",
                "series": "合金配件 02",
                "name": "非法五行合金配件",
                "primary_element": "mars",
                "effects": ["focus"],
                "price_per_bead": 0.1,
                "size_mm": 8,
                "weight_g": 1,
                "stock": 5,
            }
        )


def test_single_terminated_shape_is_a_stable_material_option():
    shapes = {item["key"]: item["label"] for item in public_material_options()["bead_shapes"]}

    assert shapes["single_terminated"] == "单尖"
    assert normalize_material_params({"bead_shape": "单尖"})["bead_shape"] == "single_terminated"


def test_material_physical_specs_migration_round_trip(tmp_path):
    db_path = tmp_path / "material-physical-migration.db"
    AdminService(db_path)
    OrderService(db_path)
    AssessmentRepository(db_path)
    upgrade("sqlite", db_path)

    assert "physical_specs_json" in table_columns(db_path, "managed_materials")
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
    assert "physical_specs_json" in table_columns(db_path, "managed_materials")
    assert downgrade("sqlite", db_path, steps=1) == ["20260714_10_material_physical_specs"]
    assert "physical_specs_json" not in table_columns(db_path, "managed_materials")
    assert upgrade("sqlite", db_path) == [
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
    ]
    assert "physical_specs_json" in table_columns(db_path, "managed_materials")


def test_public_slim_material_exposes_series_shape_and_sku_dimensions(monkeypatch):
    row = {
        "id": "irregular-8",
        "skuId": "irregular-8",
        "material_code": "irregular",
        "top": "accessory",
        "category": "异形测试",
        "series": "测试随形",
        "name": "测试随形",
        "price": 10,
        "price_cents": 1000,
        "size": 8,
        "weight": 1,
        "stock": 5,
        "enabled": 1,
        "sort_order": 1,
        "image_url": "https://cdn-prod.yustream.cn/materials/test-irregular.webp",
        "image_urls_json": "[]",
        "physical_specs_json": json.dumps({
            "string_axis_width_mm": 4.2,
            "body_width_mm": 8,
            "body_height_mm": 6.5,
        }),
    }
    normalized = normalize_db_material(row)

    monkeypatch.setattr(
        "app.material_knowledge.fetch_knowledge_map",
        lambda *_args, **_kwargs: {
            "irregular": {
                "material_params": {
                    "bead_shape": "nugget",
                    "placement_mode": "threaded",
                    "image_string_axis_deg": 0,
                }
            }
        },
    )
    monkeypatch.setattr(
        "app.material_knowledge.fetch_size_map",
        lambda *_args, **_kwargs: {"irregular": [8.0]},
    )

    public = enrich_materials_with_knowledge([normalized])[0]
    slim = slim_material(public)

    assert "physical_specs_json" not in normalized
    assert slim["physical_specs"] == {
        "string_axis_width_mm": 4.2,
        "body_width_mm": 8.0,
        "body_height_mm": 6.5,
    }
    assert slim["material_params"] == {
        "bead_shape": "nugget",
        "placement_mode": "threaded",
        "image_string_axis_deg": 0,
        **slim["physical_specs"],
    }
