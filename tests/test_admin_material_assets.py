from __future__ import annotations

import json
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app import admin_api as admin_api_module
from app.admin_service import AdminService
from app.main import app
from app.material_asset_upload import (
    inspect_webp,
    validate_material_asset_key,
    validate_material_ready_webp,
)


client = TestClient(app)


def material_webp(*, size: tuple[int, int] = (512, 512), transparent: bool = True) -> bytes:
    mode = "RGBA" if transparent else "RGB"
    background = (0, 0, 0, 0) if transparent else (240, 240, 240)
    image = Image.new(mode, size, background)
    draw = ImageDraw.Draw(image)
    inset = max(2, round(min(size) * 0.05))
    color = (91, 132, 101, 255) if transparent else (91, 132, 101)
    draw.ellipse((inset, inset, size[0] - inset, size[1] - inset), fill=color)
    output = BytesIO()
    image.save(output, "WEBP", quality=92)
    return output.getvalue()


def animated_material_webp() -> bytes:
    frames = [
        Image.new("RGBA", (512, 512), (0, 0, 0, 0)),
        Image.new("RGBA", (512, 512), (0, 0, 0, 0)),
    ]
    for index, frame in enumerate(frames):
        ImageDraw.Draw(frame).ellipse((24 + index, 24, 488, 488), fill=(91, 132, 101, 255))
    output = BytesIO()
    frames[0].save(output, "WEBP", save_all=True, append_images=frames[1:], duration=100, loop=0)
    return output.getvalue()


def test_material_asset_validator_accepts_only_ready_transparent_webp():
    content = material_webp()

    inspection = validate_material_ready_webp(content)

    assert inspection.width == 512
    assert inspection.height == 512
    assert inspection.has_alpha is True
    assert inspection.animated is False
    assert inspection.bytes == len(content)

    with pytest.raises(ValueError, match="透明背景"):
        validate_material_ready_webp(material_webp(transparent=False))
    with pytest.raises(ValueError, match="512×512"):
        validate_material_ready_webp(material_webp(size=(400, 512)))
    with pytest.raises(ValueError, match="WebP"):
        validate_material_ready_webp(b"not-an-image")
    with pytest.raises(ValueError, match="动画"):
        validate_material_ready_webp(animated_material_webp())


def test_material_asset_validator_rejects_truncated_webp_and_unsafe_keys():
    content = material_webp()
    with pytest.raises(ValueError, match="不完整"):
        inspect_webp(content[:80])
    with pytest.raises(ValueError, match="长度异常"):
        inspect_webp(content + b"trailing-data")

    assert (
        validate_material_asset_key("materials/processed/operator/abc.webp")
        == "materials/processed/operator/abc.webp"
    )
    for key in (
        "admin/materials/abc.webp",
        "materials/processed/../private.webp",
        "/materials/processed/abc.webp",
        "materials/processed/abc.png",
    ):
        with pytest.raises(ValueError):
            validate_material_asset_key(key)


def test_binding_material_assets_preserves_profile_and_supports_append(tmp_path):
    service = AdminService(tmp_path / "material-assets.db")
    category = service.save_material_category({"top": "accessory", "name": "幽灵随形"})
    series = service.save_material_series(
        {
            "category_id": category["id"],
            "name": "绿幽灵随形",
            "image_url": "https://cdn.example.com/cover.webp",
            "image_urls": ["https://cdn.example.com/original.webp"],
            "primary_element": "wood",
            "effects": ["focus"],
            "material_params": {"bead_shape": "nugget", "placement_mode": "threaded"},
        }
    )
    actor = {"admin_id": "operator-1", "username": "operator", "role": "operator"}
    service.save_material(
        {
            "id": "green-phantom-01",
            "top": "accessory",
            "category": "幽灵随形",
            "series": "绿幽灵随形",
            "name": "绿幽灵随形 01",
            "price": 10,
            "size": 10,
            "weight": 1,
            "stock": 1,
            "enabled": True,
        }
    )

    replaced = service.bind_material_series_images(
        series["id"],
        [
            "https://cdn.example.com/materials/processed/a.webp",
            "https://cdn.example.com/materials/processed/b.webp",
        ],
        mode="replace",
        sync_sku_images=True,
        actor=actor,
    )
    assert replaced["image_urls"] == [
        "https://cdn.example.com/materials/processed/a.webp",
        "https://cdn.example.com/materials/processed/b.webp",
    ]
    assert replaced["image_url"] == "https://cdn.example.com/cover.webp"
    assert replaced["synced_sku_count"] == 0
    synced_sku = service.get_material("green-phantom-01")
    assert synced_sku["visual"]["image_source"] == "series"
    assert synced_sku["visual"]["image_urls"] == replaced["image_urls"]
    assert synced_sku["visual"]["sku_image_urls"] == []

    appended = service.bind_material_series_images(
        series["id"],
        [
            "https://cdn.example.com/materials/processed/b.webp",
            "https://cdn.example.com/materials/processed/c.webp",
        ],
        mode="append",
        sync_sku_images=True,
        actor=actor,
    )
    assert appended["image_urls"] == [
        "https://cdn.example.com/materials/processed/a.webp",
        "https://cdn.example.com/materials/processed/b.webp",
        "https://cdn.example.com/materials/processed/c.webp",
    ]
    assert appended["image_url"] == "https://cdn.example.com/cover.webp"
    assert service.get_material("green-phantom-01")["visual"]["image_urls"] == appended["image_urls"]
    assert service.get_material("green-phantom-01")["visual"]["sku_image_urls"] == []

    # Binding a gallery must never infer or replace the separately managed cover.
    assert appended["image_url"] == "https://cdn.example.com/cover.webp"

    saved = service.list_material_taxonomy(top="accessory", include_disabled=True)[0]["series"][0]
    assert saved["energy"]["primary_element"] == "wood"
    assert saved["energy"]["effects"] == ["focus"]
    assert saved["material_params"]["bead_shape"] == "nugget"

    with pytest.raises(PermissionError, match="只读账号"):
        service.bind_material_series_images(
            series["id"],
            ["https://cdn.example.com/materials/processed/d.webp"],
            actor={"role": "viewer"},
        )


def test_bead_series_are_always_exposed_as_round_while_accessory_shape_is_preserved(tmp_path):
    service = AdminService(tmp_path / "bead-series-round.db")
    bead_category = service.save_material_category({"top": "bead", "name": "水晶"})
    service.save_material_series(
        {
            "category_id": bead_category["id"],
            "name": "测试珠子",
            "material_params": {"bead_shape": "cube"},
        }
    )
    service.save_material(
        {
            "id": "test-round-bead-01",
            "top": "bead",
            "category": "水晶",
            "series": "测试珠子",
            "name": "测试珠子 8mm",
            "price": 10,
            "size": 8,
            "stock": 1,
            "enabled": True,
        }
    )
    accessory_category = service.save_material_category({"top": "accessory", "name": "隔珠"})
    service.save_material_series(
        {
            "category_id": accessory_category["id"],
            "name": "测试隔珠",
            "material_params": {"bead_shape": "nugget"},
        }
    )

    bead = service.list_material_taxonomy(top="bead", include_disabled=True)[0]["series"][0]
    accessory = service.list_material_taxonomy(top="accessory", include_disabled=True)[0]["series"][0]

    assert bead["material_params"]["bead_shape"] == "round"
    assert accessory["material_params"]["bead_shape"] == "nugget"
    assert service.get_material("test-round-bead-01")["material_params"]["bead_shape"] == "round"


def test_primary_and_gallery_images_are_stored_independently(tmp_path):
    service = AdminService(tmp_path / "material-gallery-primary.db")
    category = service.save_material_category({"top": "accessory", "name": "隔珠"})
    series = service.save_material_series(
        {
            "category_id": category["id"],
            "name": "测试隔珠",
            "image_url": "https://cdn.example.com/main.webp",
            "image_urls": [
                "https://cdn.example.com/main.webp",
                "https://cdn.example.com/side.webp",
            ],
        }
    )

    initially_saved = service.list_material_taxonomy(top="accessory", include_disabled=True)[0]["series"][0]
    assert initially_saved["image_url"] == "https://cdn.example.com/main.webp"
    assert initially_saved["image_urls"] == [
        "https://cdn.example.com/main.webp",
        "https://cdn.example.com/side.webp",
    ]

    saved = service.save_material_series(
        {
            "id": series["id"],
            "category_id": category["id"],
            "name": "测试隔珠",
            "image_url": "https://cdn.example.com/main.webp",
            "image_urls": [
                "https://cdn.example.com/main.webp",
                "https://cdn.example.com/side.webp",
            ],
        }
    )

    assert saved["image_url"] == "https://cdn.example.com/main.webp"
    assert saved["image_urls"] == [
        "https://cdn.example.com/main.webp",
        "https://cdn.example.com/side.webp",
    ]
    stored = service.list_material_taxonomy(top="accessory", include_disabled=True)[0]["series"][0]
    assert stored["image_url"] == "https://cdn.example.com/main.webp"
    assert stored["image_urls"] == [
        "https://cdn.example.com/main.webp",
        "https://cdn.example.com/side.webp",
    ]
    with service.connect() as connection:
        row = connection.execute(
            "SELECT image_url,image_urls_json FROM material_taxonomy WHERE item_id=?",
            (series["id"],),
        ).fetchone()
    assert row["image_url"] == "https://cdn.example.com/main.webp"
    assert json.loads(row["image_urls_json"]) == [
        "https://cdn.example.com/main.webp",
        "https://cdn.example.com/side.webp",
    ]


def test_series_primary_image_can_be_cleared_without_changing_gallery(tmp_path):
    service = AdminService(tmp_path / "clear-material-primary.db")
    category = service.save_material_category({"top": "accessory", "name": "隔珠"})
    series = service.save_material_series(
        {
            "category_id": category["id"],
            "name": "可清空主图隔珠",
            "image_url": "https://cdn.example.com/main.webp",
            "image_urls": ["https://cdn.example.com/gallery-a.webp", "https://cdn.example.com/gallery-b.webp"],
        }
    )

    saved = service.save_material_series(
        {
            "id": series["id"],
            "category_id": category["id"],
            "name": "可清空主图隔珠",
            "image_url": "",
            "image_urls": ["https://cdn.example.com/gallery-a.webp", "https://cdn.example.com/gallery-b.webp"],
        }
    )

    assert saved["image_url"] == ""
    assert saved["image_urls"] == [
        "https://cdn.example.com/gallery-a.webp",
        "https://cdn.example.com/gallery-b.webp",
    ]


def test_material_spu_search_normalizes_invisible_characters_in_chinese_keywords(tmp_path):
    service = AdminService(tmp_path / "material-search-keyword.db")
    category = service.save_material_category({"top": "accessory", "name": "隔珠"})
    service.save_material_series({"category_id": category["id"], "name": "八吉祥圆珠隔珠"})
    service.save_material(
        {
            "id": "eight-auspicious-spacer",
            "top": "accessory",
            "category": "隔珠",
            "series": "八吉祥圆珠隔珠",
            "name": "八吉祥圆珠隔珠",
            "price": 10,
            "size": 8,
            "weight": 1,
            "stock": 1,
            "enabled": True,
        }
    )

    result = service.list_material_spus_paginated(keyword="八吉\u200b祥", page=1, page_size=20)

    assert result["pagination"]["total"] == 1
    assert result["items"][0]["sku"]["series"] == "八吉祥圆珠隔珠"


def test_editing_sku_keeps_its_material_code_and_rejects_a_missing_target(tmp_path):
    service = AdminService(tmp_path / "material-edit-identity.db")
    category = service.save_material_category({"top": "bead", "name": "发晶"})
    service.save_material_series(
        {
            "category_id": category["id"],
            "name": "蓝发晶",
            "material_code": "blue_rutilated_quartz",
        }
    )
    legacy_code = "mat_legacy_blue_rutilated"
    base = {
        "id": "blue-rutilated-10",
        "material_code": legacy_code,
        "top": "bead",
        "category": "发晶",
        "series": "蓝发晶",
        "name": "蓝发晶",
        "effects": ["calm"],
        "price": 10,
        "size": 10,
        "weight": 1,
        "stock": 3,
        "enabled": True,
    }
    service.save_material(base)
    new_size = service.save_material(
        {**base, "id": "blue-rutilated-12", "material_code": "", "size": 12}
    )
    assert new_size["sku"]["material_code"] == "blue_rutilated_quartz"
    with service.connect() as connection:
        service._ensure_material_columns(connection)
        connection.execute(
            "UPDATE managed_materials SET material_code=? WHERE id=?",
            (legacy_code, base["id"]),
        )

    updated = service.save_material({**base, "price": 12}, material_id=base["id"])

    assert updated["sku"]["material_code"] == legacy_code
    with pytest.raises(ValueError, match="待更新的 SKU 不存在"):
        service.save_material({**base, "id": "missing-blue-rutilated"}, material_id="missing-blue-rutilated")


def test_batch_enable_requires_stock_for_every_selected_sku(tmp_path):
    service = AdminService(tmp_path / "batch-enable-stock.db")
    category = service.save_material_category({"top": "bead", "name": "测试分类"})
    service.save_material_series({"category_id": category["id"], "name": "测试品种"})
    empty = service.save_material(
        {
            "id": "batch-empty",
            "top": "bead",
            "category": "测试分类",
            "series": "测试品种",
            "name": "缺货 SKU",
            "price": 10,
            "size": 8,
            "weight": 1,
            "stock": 0,
            "enabled": False,
        }
    )
    ready = service.save_material(
        {
            "id": "batch-ready",
            "top": "bead",
            "category": "测试分类",
            "series": "测试品种",
            "name": "有货 SKU",
            "price": 10,
            "size": 10,
            "weight": 1,
            "stock": 3,
            "enabled": False,
        }
    )

    with pytest.raises(ValueError, match="库存为 0，请先补充库存后再批量启用：缺货 SKU"):
        service.batch_update_materials([empty["sku"]["id"], ready["sku"]["id"]], "enable")

    assert service.get_material(empty["sku"]["id"])["sku"]["enabled"] is False
    assert service.get_material(ready["sku"]["id"])["sku"]["enabled"] is False


def test_material_asset_upload_endpoint_validates_before_cos(monkeypatch):
    uploads: list[dict] = []
    monkeypatch.setattr(
        admin_api_module,
        "require_admin",
        lambda _authorization: {"admin_id": "operator-1", "username": "operator", "role": "operator"},
    )

    def fake_upload_media(**kwargs):
        uploads.append(kwargs)
        return SimpleNamespace(
            key="materials/processed/operator-1/hash.webp",
            url="https://cdn.example.com/materials/processed/operator-1/hash.webp",
        )

    monkeypatch.setattr(admin_api_module.media_storage, "upload_media", fake_upload_media)

    response = client.post(
        "/api/v1/admin/material-assets/upload",
        headers={"Authorization": "Bearer test"},
        files={"file": ("cutout.webp", material_webp(), "image/webp")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["inspection"]["width"] == 512
    assert uploads[0]["content_type"] == "image/webp"
    assert uploads[0]["prefix"] == "materials/processed"

    invalid = client.post(
        "/api/v1/admin/material-assets/upload",
        headers={"Authorization": "Bearer test"},
        files={"file": ("opaque.webp", material_webp(transparent=False), "image/webp")},
    )
    assert invalid.status_code == 400
    assert len(uploads) == 1


def test_material_asset_bind_endpoint_uses_server_built_urls(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        admin_api_module,
        "require_admin",
        lambda _authorization: {"admin_id": "operator-1", "username": "operator", "role": "operator"},
    )
    monkeypatch.setattr(
        admin_api_module.media_storage,
        "public_url",
        lambda key: f"https://cdn.example.com/{key}",
    )

    def fake_bind(series_id, urls, *, mode, sync_sku_images, actor):
        calls.append(
            {
                "series_id": series_id,
                "urls": urls,
                "mode": mode,
                "sync_sku_images": sync_sku_images,
                "actor": actor,
            }
        )
        return {"id": series_id, "image_urls": urls, "bound_count": len(urls)}

    monkeypatch.setattr(admin_api_module.admin_service, "bind_material_series_images", fake_bind)
    response = client.post(
        "/api/v1/admin/material-assets/bind",
        headers={"Authorization": "Bearer test"},
        json={
            "series_id": "series-green-phantom",
            "asset_keys": ["materials/processed/operator-1/a.webp"],
            "mode": "replace",
            "sync_sku_images": True,
        },
    )

    assert response.status_code == 200
    assert calls == [
        {
            "series_id": "series-green-phantom",
            "urls": ["https://cdn.example.com/materials/processed/operator-1/a.webp"],
            "mode": "replace",
            "sync_sku_images": True,
            "actor": {"admin_id": "operator-1", "username": "operator", "role": "operator"},
        }
    ]


def test_material_asset_endpoints_block_viewer(monkeypatch):
    monkeypatch.setattr(
        admin_api_module,
        "require_admin",
        lambda _authorization: {"admin_id": "viewer-1", "username": "viewer", "role": "viewer"},
    )
    upload = client.post(
        "/api/v1/admin/material-assets/upload",
        headers={"Authorization": "Bearer test"},
        files={"file": ("cutout.webp", material_webp(), "image/webp")},
    )
    bind = client.post(
        "/api/v1/admin/material-assets/bind",
        headers={"Authorization": "Bearer test"},
        json={
            "series_id": "series-green-phantom",
            "asset_keys": ["materials/processed/viewer-1/a.webp"],
            "mode": "replace",
        },
    )
    assert upload.status_code == 403
    assert bind.status_code == 403
