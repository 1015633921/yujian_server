from __future__ import annotations

import sqlite3

import pytest

from app.admin_service import AdminService
from app.migrations.versions import v20260715_11_material_types


def test_material_directory_is_managed_separately_from_skus(tmp_path):
    service = AdminService(tmp_path / "material-directory.db")

    assert {item["code"] for item in service.list_material_types()} >= {"bead", "accessory"}
    material_type = service.save_material_type(
        {"code": "thread", "name": "线材", "description": "测试目录"}
    )
    category = service.save_material_category(
        {"top": material_type["code"], "name": "弹力线"}
    )
    variety = service.save_material_series(
        {"category_id": category["id"], "name": "透明弹力线"}
    )

    taxonomy = service.list_material_taxonomy(top="thread", include_disabled=True)
    assert taxonomy[0]["name"] == "弹力线"
    assert taxonomy[0]["series"][0]["id"] == variety["id"]


def test_disabled_material_type_fails_closed_for_category_and_sku_creation(tmp_path):
    service = AdminService(tmp_path / "disabled-material-type.db")
    category = service.save_material_category({"top": "bead", "name": "幽灵水晶"})
    service.save_material_series(
        {
            "category_id": category["id"],
            "name": "绿幽灵",
            "primary_element": "wood",
            "effects": ["focus"],
        }
    )
    service.disable_material_type("bead")

    with pytest.raises(ValueError, match="材料类型已停用"):
        service.save_material_category({"top": "bead", "name": "白水晶"})

    with pytest.raises(ValueError, match="材料类型未维护或已停用"):
        service.save_material(
            {
                "top": "bead",
                "category": "幽灵水晶",
                "series": "绿幽灵",
                "name": "绿幽灵 8mm",
                "primary_element": "wood",
                "effects": ["focus"],
                "price_per_bead": "10.00",
                "size_mm": 8,
                "weight_g": 1,
                "stock": 10,
            }
        )


def test_basic_variety_edit_preserves_optional_profile(tmp_path):
    service = AdminService(tmp_path / "variety-profile.db")
    category = service.save_material_category({"top": "accessory", "name": "幽灵随形"})
    variety = service.save_material_series(
        {
            "category_id": category["id"],
            "name": "红幽灵随形",
            "image_url": "https://cdn-test.yustream.cn/materials/red-phantom.webp",
            "primary_element": "fire",
            "effects": ["vitality"],
            "material_params": {"bead_shape": "nugget", "placement_mode": "threaded"},
        }
    )

    service.save_material_series(
        {
            "id": variety["id"],
            "category_id": category["id"],
            "name": "红幽灵随形精品",
            "sort_order": 20,
            "enabled": True,
        }
    )

    saved = service.list_material_taxonomy(top="accessory", include_disabled=True)[0]["series"][0]
    assert saved["name"] == "红幽灵随形精品"
    assert saved["image_url"] == "https://cdn-test.yustream.cn/materials/red-phantom.webp"
    assert saved["energy"]["primary_element"] == "fire"
    assert saved["energy"]["effects"] == ["vitality"]
    assert saved["material_params"]["bead_shape"] == "nugget"


def test_material_type_code_is_immutable(tmp_path):
    service = AdminService(tmp_path / "immutable-material-type.db")
    with pytest.raises(ValueError, match="编码创建后不可修改"):
        service.save_material_type(
            {"id": "bead", "code": "renamed-bead", "name": "珠子"}
        )


def test_material_type_migration_seeds_defaults_and_existing_top(tmp_path):
    db_path = tmp_path / "material-type-migration.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE managed_materials (top TEXT NOT NULL)")
    connection.execute("INSERT INTO managed_materials(top) VALUES ('legacy_type')")

    v20260715_11_material_types.upgrade(connection, "sqlite")
    codes = {
        row["type_code"]
        for row in connection.execute("SELECT type_code FROM material_types").fetchall()
    }
    assert {"bead", "accessory", "legacy_type"} <= codes

    v20260715_11_material_types.downgrade(connection, "sqlite")
    assert not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='material_types'"
    ).fetchone()
    connection.close()
