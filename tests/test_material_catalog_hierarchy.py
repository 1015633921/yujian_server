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


def test_only_empty_material_categories_can_be_deleted_in_a_batch(tmp_path):
    service = AdminService(tmp_path / "empty-category-delete.db")
    empty = service.save_material_category({"top": "bead", "name": "待删除空分类"})
    in_use = service.save_material_category({"top": "bead", "name": "仍在使用分类"})
    service.save_material_series({"category_id": in_use["id"], "name": "仍在使用品种"})

    with pytest.raises(ValueError, match="仍在使用分类（含1 个品种）"):
        service.delete_empty_material_categories([empty["id"], in_use["id"]])

    taxonomy_ids = {item["id"] for item in service.list_material_taxonomy(top="bead", include_disabled=True)}
    assert empty["id"] in taxonomy_ids
    assert in_use["id"] in taxonomy_ids

    deleted = service.delete_empty_material_categories([empty["id"]])

    assert deleted["count"] == 1
    taxonomy_ids = {item["id"] for item in service.list_material_taxonomy(top="bead", include_disabled=True)}
    assert empty["id"] not in taxonomy_ids


def test_empty_material_types_and_series_can_be_deleted(tmp_path):
    service = AdminService(tmp_path / "empty-directory-delete.db")
    empty_type = service.save_material_type({"code": "empty_type", "name": "空类型"})
    used_type = service.save_material_type({"code": "used_type", "name": "使用中类型"})
    category = service.save_material_category({"top": used_type["code"], "name": "使用中分类"})
    empty_series = service.save_material_series({"category_id": category["id"], "name": "空品种"})

    with pytest.raises(ValueError, match="使用中类型（含2 个目录项）"):
        service.delete_empty_material_types([empty_type["code"], used_type["code"]])
    assert service.delete_empty_material_series([empty_series["id"]])["count"] == 1
    assert service.delete_empty_material_types([empty_type["code"]])["count"] == 1


def test_deleted_empty_default_material_type_is_not_seeded_again(tmp_path):
    service = AdminService(tmp_path / "deleted-default-material-type.db")

    assert "incense" in {item["code"] for item in service.list_material_types(include_disabled=True)}
    assert service.delete_empty_material_types(["incense"])["count"] == 1
    assert "incense" not in {item["code"] for item in service.list_material_types(include_disabled=True)}

    service.save_material_type({"code": "incense", "name": "合香珠", "enabled": True})
    assert "incense" in {item["code"] for item in service.list_material_types(include_disabled=True)}


def test_only_disabled_skus_can_be_deleted(tmp_path):
    service = AdminService(tmp_path / "disabled-sku-delete.db")
    category = service.save_material_category({"top": "bead", "name": "删除 SKU 分类"})
    service.save_material_series({"category_id": category["id"], "name": "删除 SKU 品种"})
    active = service.save_material(
        {
            "id": "active-delete-guard",
            "top": "bead",
            "category": "删除 SKU 分类",
            "series": "删除 SKU 品种",
            "name": "启用 SKU",
            "price": 10,
            "size": 8,
            "weight": 1,
            "stock": 1,
            "enabled": True,
        }
    )
    disabled = service.save_material(
        {
            "id": "disabled-delete-allowed",
            "top": "bead",
            "category": "删除 SKU 分类",
            "series": "删除 SKU 品种",
            "name": "停用 SKU",
            "price": 10,
            "size": 10,
            "weight": 1,
            "stock": 1,
            "enabled": False,
        }
    )

    service.delete_material(disabled["sku"]["id"])
    with pytest.raises(ValueError, match="材料不存在"):
        service.get_material(disabled["sku"]["id"])


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


def test_series_move_and_rename_does_not_duplicate_during_sku_sync(tmp_path):
    service = AdminService(tmp_path / "series-move-rename.db")
    old_category = service.save_material_category({"top": "accessory", "name": "隔珠"})
    series = service.save_material_series(
        {
            "category_id": old_category["id"],
            "name": "繁花圆片隔珠",
            "material_code": "accessory_metal_test_03",
            "image_url": "https://cdn-test.yustream.cn/materials/accessories/flower.webp",
            "image_urls": ["https://cdn-test.yustream.cn/materials/accessories/flower-gallery.webp"],
        }
    )
    service.save_material(
        {
            "id": "flower-spacer-default",
            "skuId": "flower-spacer-default",
            "top": "accessory",
            "category": "隔珠",
            "series": "繁花圆片隔珠",
            "material_code": "accessory_metal_test_03",
            "name": "繁花圆片隔珠",
            "price_per_bead": 10,
            "size_mm": 8,
            "weight_g": 1,
            "stock": 10,
        }
    )
    new_category = service.save_material_category({"top": "accessory", "name": "隔片"})

    service.save_material_series(
        {
            "id": series["id"],
            "category_id": new_category["id"],
            "name": "繁花圆片隔片",
            "sort_order": 20,
            "enabled": True,
        }
    )
    payload = service.material_options_payload()

    matches = [
        item
        for category in payload["taxonomy"]
        for item in category.get("series", [])
        if item["name"] == "繁花圆片隔片"
    ]
    assert len(matches) == 1
    assert matches[0]["id"] == series["id"]
    assert matches[0]["material_code"] == "accessory_metal_test_03"
    assert matches[0]["image_url"] == "https://cdn-test.yustream.cn/materials/accessories/flower.webp"
    with service.connect() as connection:
        duplicate_count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM material_taxonomy
            WHERE kind='series' AND parent_id=? AND name=?
            """,
            (new_category["id"], "繁花圆片隔片"),
        ).fetchone()["total"]
        sku = connection.execute(
            "SELECT category, series FROM managed_materials WHERE id=?",
            ("flower-spacer-default",),
        ).fetchone()
    assert duplicate_count == 1
    assert sku["category"] == "隔片"
    assert sku["series"] == "繁花圆片隔片"


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
