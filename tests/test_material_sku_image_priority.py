from __future__ import annotations

from app.admin_service import AdminService
from app.materials import normalize_db_material, series_asset_key


def test_public_catalog_ignores_legacy_sku_images_and_uses_series_images():
    sku_image = "https://cdn-test.yustream.cn/materials/accessories/alloy/sku-02.webp"
    series_image = "https://cdn-test.yustream.cn/materials/accessories/alloy/series.webp"
    gallery_image = "https://cdn-test.yustream.cn/materials/accessories/alloy/gallery.webp"
    row = {
        "id": "alloy-02",
        "skuId": "alloy-02",
        "top": "accessory",
        "category": "合金配件",
        "series": "合金配件",
        "material_code": "alloy_accessory",
        "name": "合金配件 02",
        "price": 10,
        "price_cents": 1000,
        "size": 3,
        "weight": 0.4,
        "stock": 99,
        "enabled": 1,
        "image_url": sku_image,
        "image_urls_json": f'["{sku_image}"]',
    }
    series_assets = {
        series_asset_key(row): {
            "image_path": "accessories/alloy/series.webp",
            "image_url": series_image,
            "image_urls": [series_image, gallery_image],
            "color": "#c49a42",
            "shine": "#ffffff",
        }
    }

    material = normalize_db_material(row, series_assets)

    assert material["image_url"] == series_image
    assert material["image_urls"] == [gallery_image]
    assert material["image_pool"] == [gallery_image]
    assert material["color"] == "#c49a42"


def test_public_catalog_falls_back_to_series_image_when_sku_has_no_image():
    series_image = "https://cdn-test.yustream.cn/materials/accessories/alloy/series.webp"
    row = {
        "id": "alloy-empty",
        "skuId": "alloy-empty",
        "top": "accessory",
        "category": "合金配件",
        "series": "合金配件",
        "material_code": "alloy_accessory",
        "name": "合金配件",
        "price": 10,
        "price_cents": 1000,
        "size": 3,
        "weight": 0.4,
        "stock": 99,
        "enabled": 1,
        "image_url": "",
        "image_urls_json": "[]",
    }
    series_assets = {
        series_asset_key(row): {
            "image_url": series_image,
            "image_urls": [series_image],
        }
    }

    material = normalize_db_material(row, series_assets)

    assert material["image_url"] == series_image
    assert material["image_urls"] == []


def test_legacy_sku_image_payload_is_promoted_to_the_series(tmp_path):
    sku_image = "https://cdn-test.yustream.cn/materials/accessories/alloy/sku-02.webp"
    series_image = "https://cdn-test.yustream.cn/materials/accessories/alloy/series.webp"
    service = AdminService(tmp_path / "sku-image-priority.db")
    category = service.save_material_category({"top": "accessory", "name": "合金配件"})
    service.save_material_series(
        {
            "category_id": category["id"],
            "name": "合金配件",
            "material_code": "alloy_accessory",
            "image_url": series_image,
            "image_urls": [series_image],
        }
    )

    saved = service.save_material(
        {
            "id": "alloy-02",
            "skuId": "alloy-02",
            "top": "accessory",
            "category": "合金配件",
            "series": "合金配件",
            "material_code": "alloy_accessory",
            "name": "合金配件 02",
            "primary_element": "metal",
            "effects": ["focus"],
            "price_per_bead": 10,
            "size_mm": 3,
            "weight_g": 0.4,
            "stock": 99,
            "thumbnail_url": sku_image,
            "image_urls": [sku_image],
        }
    )

    assert saved["visual"]["thumbnail_url"] == sku_image
    assert saved["visual"]["image_urls"] == [sku_image]
    assert saved["visual"]["image_source"] == "series"
    assert saved["visual"]["sku_image_urls"] == []
    taxonomy = service.list_material_taxonomy(top="accessory", include_disabled=True)
    assert taxonomy[0]["series"][0]["image_url"] == sku_image


def test_series_image_update_clears_legacy_sku_overrides_and_updates_all_skus(tmp_path):
    service = AdminService(tmp_path / "series-image-sync.db")
    category = service.save_material_category({"top": "bead", "name": "同步测试晶石"})
    series = service.save_material_series(
        {
            "category_id": category["id"],
            "name": "同步绿幽灵",
            "image_url": "https://cdn.example.com/series-old.webp",
            "image_urls": ["https://cdn.example.com/series-old.webp"],
            "primary_element": "wood",
            "effects": ["focus"],
        }
    )
    service.save_material(
        {
            "id": "green-phantom-8",
            "top": "bead",
            "category": "同步测试晶石",
            "series": "同步绿幽灵",
            "name": "同步绿幽灵 8mm",
            "price": 10,
            "size": 8,
            "weight": 1,
            "stock": 10,
            "enabled": True,
            "image_url": "https://cdn.example.com/sku-old.webp",
            "image_urls": ["https://cdn.example.com/sku-old.webp"],
        }
    )
    with service.connect() as connection:
        connection.execute(
            """
            UPDATE managed_materials
            SET image_url=?, image_urls_json=?
            WHERE id=?
            """,
            (
                "https://cdn.example.com/sku-old.webp",
                '["https://cdn.example.com/sku-old.webp"]',
                "green-phantom-8",
            ),
        )

    updated = service.save_material_series(
        {
            "id": series["id"],
            "category_id": category["id"],
            "name": "同步绿幽灵",
            "image_url": "https://cdn.example.com/series-new.webp",
            "image_urls": ["https://cdn.example.com/series-new.webp"],
            "sync_sku_images": False,
        }
    )
    assert updated["synced_sku_count"] == 1
    material = service.get_material("green-phantom-8")
    assert material["visual"]["image_source"] == "series"
    assert material["visual"]["thumbnail_url"] == "https://cdn.example.com/series-new.webp"
    assert material["visual"]["sku_image_url"] == ""
    assert material["visual"]["sku_image_urls"] == []
    with service.connect() as connection:
        row = connection.execute(
            "SELECT image_path, image_url, image_urls_json FROM managed_materials WHERE id=?",
            ("green-phantom-8",),
        ).fetchone()
    assert row["image_path"] == ""
    assert row["image_url"] == ""
    assert row["image_urls_json"] == "[]"
