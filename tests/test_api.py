from fastapi.testclient import TestClient
import pytest
from uuid import uuid4

from app.main import app
from app.order_service import OrderService, generate_numeric_order_no, now_iso

client = TestClient(app)

PAYLOAD = {
    "user_id": "api-test-user",
    "name": "林安",
    "birthday": "1995-08-16",
    "birth_time": "09:30",
    "birth_place": "四川省成都市",
    "mbti": "INFJ",
    "core_wish": "健康护身/保持专注",
    "wrist_size_cm": 15.5,
    "bead_size_mm": 8,
}


def ensure_material_taxonomy(service, category: str, series: str, top: str = "bead") -> None:
    saved_category = service.save_material_category({"top": top, "name": category})
    service.save_material_series({"category_id": saved_category["id"], "name": series})


def test_options_support_form_rendering():
    response = client.get("/api/v1/assessment/options")
    assert response.status_code == 200
    assert len(response.json()["data"]["mbti_options"]) == 16
    assert response.json()["data"]["chakra_questions"]
    assert response.json()["data"]["mood_palettes"]


def test_compact_material_search_omits_catalog_metadata_and_honors_limit():
    response = client.get("/api/v1/materials?compact=true&limit=2")
    data = response.json()["data"]

    assert response.status_code == 200
    assert set(data) == {"materials"}
    assert len(data["materials"]) <= 2
    assert all(isinstance(item.get("image_urls"), list) for item in data["materials"])
    if data["materials"]:
        item = data["materials"][0]
        assert {"sku", "energy", "visual", "rules"}.issubset(item)
        assert item["sku"]["size_mm"]
        assert item["energy"]["primary_element"]
        assert isinstance(item["visual"]["image_urls"], list)
        assert isinstance(item["rules"]["allowed_roles"], list)


def test_admin_material_options_expose_field_governance_specs(tmp_path):
    from app.admin_service import AdminService

    service = AdminService(tmp_path / "material-options.db")
    payload = service.material_options_payload()

    specs = payload["field_specs"]
    option_specs = {item["key"]: item for item in specs["option_types"]}
    form_specs = {item["key"]: item for item in specs["material_fields"]}

    assert payload["option_types"][0]["control"]
    assert option_specs["wish_pools"]["control"] == "multi_select"
    assert option_specs["match_rules"]["value_kind"] == "rule_key"
    assert option_specs["bead_shapes"]["cardinality"] == "one"
    assert form_specs["primary_element"]["value_kind"] == "enum_key"
    assert form_specs["purchase_note"]["value_kind"] == "free_text"
    assert form_specs["thumbnail_url"]["control"] == "upload"
    assert specs["governance"]["enum_first"] is True


def test_admin_material_requires_option_values_to_exist_in_dictionary(tmp_path):
    from app.admin_service import AdminService

    service = AdminService(tmp_path / "material-option-validation.db")
    custom_effect = service.save_material_option_item(
        {"option_type": "effects", "label": "成长守护", "sort_order": 8}
    )
    ensure_material_taxonomy(service, "quartz", "Growth Guard Quartz")
    ensure_material_taxonomy(service, "quartz", "Bad Effect Quartz")

    saved = service.save_material(
        {
            "material_code": "growth_guard_quartz",
            "top": "bead",
            "category": "quartz",
            "series": "Growth Guard Quartz",
            "name": "Growth Guard Quartz",
            "primary_element": "wood",
            "effects": ["成长守护"],
            "price_per_bead": 3.8,
            "size_mm": 8,
            "weight_g": 1.1,
            "stock": 5,
            "thumbnail_url": "https://cdn-test.yustream.cn/materials/beads/growth.png",
        }
    )

    assert saved["energy"]["effects"] == [custom_effect["key"]]

    with pytest.raises(ValueError, match="未维护选项"):
        service.save_material(
            {
                "material_code": "bad_effect_quartz",
                "top": "bead",
                "category": "quartz",
                "series": "Bad Effect Quartz",
                "name": "Bad Effect Quartz",
                "primary_element": "wood",
                "effects": ["随手乱填标签"],
                "price_per_bead": 3.8,
                "size_mm": 8,
                "weight_g": 1.1,
                "stock": 5,
                "thumbnail_url": "https://cdn-test.yustream.cn/materials/beads/bad.png",
            }
        )


def test_admin_material_requires_taxonomy_before_sku_save(tmp_path):
    from app.admin_service import AdminService

    service = AdminService(tmp_path / "material-taxonomy-validation.db")
    payload = {
        "material_code": "taxonomy_guard_quartz",
        "top": "bead",
        "category": "unlisted-category",
        "series": "Unlisted Series",
        "name": "Unlisted Series",
        "primary_element": "water",
        "effects": ["focus"],
        "price_per_bead": 2.6,
        "size_mm": 8,
        "weight_g": 1,
        "stock": 5,
        "thumbnail_url": "https://cdn-test.yustream.cn/materials/beads/taxonomy.png",
    }

    with pytest.raises(ValueError, match="分类未维护"):
        service.save_material(payload)

    category = service.save_material_category({"top": "bead", "name": "unlisted-category"})
    with pytest.raises(ValueError, match="品种未维护"):
        service.save_material(payload)

    service.save_material_series({"category_id": category["id"], "name": "Unlisted Series"})
    saved = service.save_material(payload)

    assert saved["sku"]["category"] == "unlisted-category"
    assert saved["sku"]["series"] == "Unlisted Series"


def test_admin_material_spu_reports_size_coverage_and_missing_specs(tmp_path):
    from app.admin_service import AdminService

    service = AdminService(tmp_path / "material-spec-coverage.db")
    ensure_material_taxonomy(service, "quartz", "Coverage Quartz")
    ensure_material_taxonomy(service, "quartz", "Partial Quartz")

    def save_size(series: str, code: str, size: int) -> None:
        service.save_material(
            {
                "id": f"{code}_{size}",
                "skuId": f"{code}_{size}",
                "material_code": code,
                "top": "bead",
                "category": "quartz",
                "series": series,
                "name": series,
                "primary_element": "water",
                "effects": ["focus"],
                "price_per_bead": 1,
                "size_mm": size,
                "weight_g": 1,
                "stock": 3,
                "thumbnail_url": f"https://cdn-test.yustream.cn/materials/beads/{code}-{size}.png",
            }
        )

    for size in range(8, 16):
        save_size("Coverage Quartz", "coverage_quartz", size)
    for size in (8, 10):
        save_size("Partial Quartz", "partial_quartz", size)

    complete = service.list_material_spus(keyword="Coverage Quartz")[0]
    partial = service.list_material_spus(keyword="Partial Quartz")[0]

    assert complete["specStatus"] == "complete"
    assert complete["missingSizes"] == []
    assert complete["specCoverage"] == 1
    assert partial["specStatus"] == "partial"
    assert partial["missingSizes"] == [9, 11, 12, 13, 14, 15]
    assert partial["specCoverage"] == pytest.approx(0.25)
    assert [group["key"] for group in service.list_material_spus(keyword="Coverage Quartz", spec_state="complete")] == [
        "coverage_quartz"
    ]
    assert [group["key"] for group in service.list_material_spus(keyword="Partial Quartz", spec_state="incomplete")] == [
        "partial_quartz"
    ]


def test_admin_material_saves_structured_knowledge_without_legacy_required_fields(tmp_path):
    from app.admin_service import AdminService

    service = AdminService(tmp_path / "knowledge-materials.db")
    ensure_material_taxonomy(service, "test", "Moss Agate")
    saved = service.save_material(
        {
            "material_code": "test_moss_agate",
            "top": "bead",
            "category": "test",
            "series": "Moss Agate",
            "name": "Moss Agate",
            "primary_element": "wood",
            "secondary_elements": ["water"],
            "effects": ["career", "focus"],
            "chakras": ["heart"],
            "wish_pools": ["career"],
            "allowed_roles": ["primary", "support"],
            "price_per_bead": 3.5,
            "size_mm": 8,
            "weight_g": 1.1,
            "stock": 8,
            "thumbnail_url": "https://cdn-test.yustream.cn/materials/beads/moss.png",
            "color_hex": "#6fa56b",
            "shine_hex": "#d7eadc",
            "enabled": True,
        }
    )

    assert saved["sku"]["material_code"] == "test_moss_agate"
    assert saved["sku"]["price_per_bead"] == 3.5
    assert saved["energy"]["primary_element"] == "wood"
    assert saved["energy"]["effects"] == ["career", "focus"]
    assert saved["visual"]["thumbnail_url"].endswith("/moss.png")
    assert saved["rules"]["allowed_roles"] == ["primary", "support"]


def test_admin_material_keeps_ops_fields_internal_to_admin(tmp_path):
    from app.admin_service import AdminService
    from app.materials import normalize_db_material

    service = AdminService(tmp_path / "ops-materials.db")
    ensure_material_taxonomy(service, "quartz", "Rose Quartz")
    saved = service.save_material(
        {
            "material_code": "ops_rose_quartz",
            "top": "bead",
            "category": "quartz",
            "series": "Rose Quartz",
            "name": "Rose Quartz",
            "primary_element": "water",
            "secondary_elements": ["wood"],
            "effects": ["calm"],
            "material_params": {
                "bead_shape": "round",
                "surface_finish": "glossy",
                "transparency_level": "semi_transparent",
                "texture_features": ["cloud", "rutile"],
                "batch_variation": "medium",
                "hole_diameter_mm": "1.1",
                "size_tolerance_mm": 0.2,
                "origin_hint": "Brazil",
            },
            "price_per_bead": 2.8,
            "cost_price": 1.2,
            "safety_stock": 10,
            "supplier_name": "Studio A",
            "purchase_note": "Batch color is slightly pale.",
            "size_mm": 8,
            "weight_g": 1.0,
            "stock": 6,
            "enabled": True,
        }
    )

    assert saved["sku"]["cost_price"] == 1.2
    assert saved["sku"]["margin_amount"] == 1.6
    assert saved["sku"]["margin_rate"] == pytest.approx(0.5714)
    assert saved["sku"]["margin_status"] == "normal"
    assert saved["sku"]["inventory_cost_value"] == 7.2
    assert saved["sku"]["inventory_retail_value"] == 16.8
    assert saved["sku"]["inventory_margin_value"] == 9.6
    assert saved["sku"]["safety_stock"] == 10
    assert saved["sku"]["supplier_name"] == "Studio A"
    assert saved["sku"]["stock_status"] == "low"
    assert saved["ops"]["purchase_note"] == "Batch color is slightly pale."
    assert saved["visual"]["material_params"]["bead_shape"] == "round"
    assert saved["visual"]["material_params"]["surface_finish"] == "glossy"
    assert saved["visual"]["material_params"]["transparency_level"] == "semi_transparent"
    assert saved["visual"]["material_params"]["texture_features"] == ["cloud", "rutile"]
    assert saved["visual"]["material_params"]["batch_variation"] == "medium"
    assert saved["visual"]["material_params"]["hole_diameter_mm"] == 1.1
    assert saved["visual"]["material_params"]["size_tolerance_mm"] == 0.2
    assert saved["visual"]["material_params"]["origin_hint"] == "Brazil"
    assert saved["quality"]["ready_for_sale"] is False
    assert saved["quality"]["level"] == "risk"
    assert any(issue["key"] == "image_missing" for issue in saved["quality"]["issues"])

    groups = service.list_material_spus(keyword="Rose Quartz")
    assert groups[0]["qualityRiskCount"] == 1
    assert groups[0]["qualityIssueCount"] >= 1
    assert groups[0]["minMarginRate"] == pytest.approx(0.5714)
    assert groups[0]["marginRiskCount"] == 0
    assert groups[0]["inventoryCostValue"] == 7.2
    assert groups[0]["inventoryRetailValue"] == 16.8
    assert groups[0]["inventoryMarginValue"] == 9.6
    risk_items = service.list_materials(keyword="Rose Quartz", quality="risk")
    ready_items = service.list_materials(keyword="Rose Quartz", quality="ready")
    low_stock_items = service.list_materials(keyword="Rose Quartz", stock_state="low")
    normal_margin_items = service.list_materials(keyword="Rose Quartz", margin="normal")
    assert [item["sku"]["id"] for item in risk_items] == [saved["sku"]["id"]]
    assert ready_items == []
    assert [item["sku"]["id"] for item in low_stock_items] == [saved["sku"]["id"]]
    assert [item["sku"]["id"] for item in normal_margin_items] == [saved["sku"]["id"]]

    service.batch_update_materials([saved["sku"]["id"]], "safety_stock", 3)
    updated = service.get_material(saved["sku"]["id"])
    assert updated["sku"]["safety_stock"] == 3
    assert updated["sku"]["stock_status"] == "normal"
    assert [item["sku"]["id"] for item in service.list_materials(keyword="Rose Quartz", stock_state="normal")] == [
        saved["sku"]["id"]
    ]

    public = normalize_db_material(
        {
            "id": "ops_rose_quartz_8",
            "skuId": "ops_rose_quartz_8",
            "top": "bead",
            "category": "quartz",
            "name": "Rose Quartz",
            "price": 2.8,
            "size": 8,
            "weight": 1,
            "stock": 6,
            "cost_price": 1.2,
            "safety_stock": 10,
            "supplier_name": "Studio A",
            "purchase_note": "Batch color is slightly pale.",
        }
    )
    assert "cost_price" not in public
    assert "safety_stock" not in public
    assert "supplier_name" not in public
    assert "purchase_note" not in public


def test_admin_material_flags_loss_margin_as_pricing_risk(tmp_path):
    from app.admin_service import AdminService

    service = AdminService(tmp_path / "loss-margin-materials.db")
    ensure_material_taxonomy(service, "quartz", "Loss Margin Quartz")
    saved = service.save_material(
        {
            "material_code": "loss_margin_test",
            "top": "bead",
            "category": "quartz",
            "series": "Loss Margin Quartz",
            "name": "Loss Margin Quartz",
            "primary_element": "water",
            "effects": ["calm"],
            "price_per_bead": 2,
            "cost_price": 3,
            "size_mm": 8,
            "weight_g": 1,
            "stock": 5,
            "safety_stock": 1,
            "thumbnail_url": "https://cdn-test.yustream.cn/materials/beads/loss.png",
            "enabled": True,
        }
    )

    assert saved["sku"]["margin_amount"] == -1
    assert saved["sku"]["margin_rate"] == pytest.approx(-0.5)
    assert saved["sku"]["margin_status"] == "loss"
    assert saved["sku"]["inventory_cost_value"] == 15
    assert saved["sku"]["inventory_retail_value"] == 10
    assert saved["sku"]["inventory_margin_value"] == -5
    assert any(issue["key"] == "margin_loss" for issue in saved["quality"]["issues"])
    groups = service.list_material_spus(keyword="Loss Margin Quartz")
    assert groups[0]["marginLossCount"] == 1
    assert groups[0]["marginRiskCount"] == 1
    assert groups[0]["inventoryCostValue"] == 15
    assert groups[0]["inventoryRetailValue"] == 10
    assert groups[0]["inventoryMarginValue"] == -5
    loss_items = service.list_materials(keyword="Loss Margin Quartz", margin="loss")
    margin_risk_items = service.list_materials(keyword="Loss Margin Quartz", margin="risk")
    assert [item["sku"]["id"] for item in loss_items] == [saved["sku"]["id"]]
    assert [item["sku"]["id"] for item in margin_risk_items] == [saved["sku"]["id"]]


def test_admin_material_accepts_multiple_image_urls(tmp_path):
    from app.admin_service import AdminService

    service = AdminService(tmp_path / "multi-image-materials.db")
    ensure_material_taxonomy(service, "测试晶石", "多图测试珠")
    saved = service.save_material(
        {
            "id": "multiImageBead8",
            "skuId": "multiImageBead",
            "top": "bead",
            "category": "测试晶石",
            "name": "多图测试珠",
            "effect": "随机珠面",
            "element": "火",
            "price": 1,
            "size": 8,
            "weight": 1,
            "color": "#b95858",
            "shine": "#ffe1df",
            "image_url": "https://cdn-test.yustream.cn/materials/beads/a.png",
            "image_urls": [
                "https://cdn-test.yustream.cn/materials/beads/b.png",
                "https://cdn-test.yustream.cn/materials/beads/c.png",
            ],
        }
    )

    assert saved["image_url"].endswith("/a.png")
    assert saved["image_urls"] == [
        "https://cdn-test.yustream.cn/materials/beads/b.png",
        "https://cdn-test.yustream.cn/materials/beads/c.png",
        "https://cdn-test.yustream.cn/materials/beads/a.png",
    ]


def test_material_cdn_url_deduplicates_materials_prefix(monkeypatch):
    from app.materials import clean_image_urls, material_url_from_path

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("TENCENT_COS_CDN_BASE_URL", raising=False)

    assert material_url_from_path("materials/beads/wps-circle-v2/a.png") == (
        "https://cdn-test.yustream.cn/materials/beads/wps-circle-v2/a.png"
    )
    assert material_url_from_path("beads/wps-circle-v2/a.png") == (
        "https://cdn-test.yustream.cn/materials/beads/wps-circle-v2/a.png"
    )
    assert clean_image_urls(["https://cdn-test.yustream.cn/materials/materials/beads/a.png"]) == [
        "https://cdn-test.yustream.cn/materials/beads/a.png"
    ]
    assert clean_image_urls(["https://yujian-1258267288.cos.ap-guangzhou.myqcloud.com/materials/beads/a.png"]) == [
        "https://cdn-test.yustream.cn/materials/beads/a.png"
    ]
    assert clean_image_urls(
        [
            "https://cdn-test.yustream.cn/materials/beads/wps-circle-v2/南红玛瑙.png",
            "https://cdn-test.yustream.cn/materials/beads/wps-circle-v2/%E5%8D%97%E7%BA%A2%E7%8E%9B%E7%91%99.png",
        ]
    ) == [
        "https://cdn-test.yustream.cn/materials/beads/wps-circle-v2/%E5%8D%97%E7%BA%A2%E7%8E%9B%E7%91%99.png"
    ]


def test_admin_material_autogenerates_id_sku_and_disables_zero_stock(tmp_path):
    from app.admin_service import AdminService

    service = AdminService(tmp_path / "auto-materials.db")
    ensure_material_taxonomy(service, "test", "Auto Bead")
    saved = service.save_material(
        {
            "top": "bead",
            "category": "test",
            "name": "Auto Bead",
            "effect": "focus",
            "element": "water",
            "price": 1,
            "size": 8,
            "weight": 1,
            "stock": 0,
            "enabled": True,
        }
    )
    duplicate = service.save_material(
        {
            "top": "bead",
            "category": "test",
            "name": "Auto Bead",
            "effect": "focus",
            "element": "water",
            "price": 1,
            "size": 8,
            "weight": 1,
            "stock": 5,
            "enabled": True,
        }
    )

    assert saved["id"].startswith("mat_")
    assert saved["skuId"].isdigit()
    assert saved["skuId"].startswith("10")
    assert saved["enabled"] is False
    assert duplicate["skuId"] != saved["skuId"]
    assert duplicate["skuId"].isdigit()
    assert duplicate["enabled"] is True


def test_material_code_infers_crystal_family_from_chinese_series():
    from app.material_knowledge import material_code_from_payload, normalize_knowledge_payload

    payload = {"top": "bead", "category": "粉红晶石", "series": "莫桑比亚粉水晶", "name": "莫桑比亚粉水晶"}
    assert material_code_from_payload(payload) == "rose_quartz"

    knowledge = normalize_knowledge_payload(payload, payload)
    assert knowledge["code"] == "rose_quartz"
    assert knowledge["primary_element"] == "wood"
    assert "heart" in knowledge["chakras"]
    assert "love" in knowledge["wish_pools"]
    assert knowledge["material_params"]["transparency_level"] == "translucent"


def test_agate_variants_keep_separate_material_codes_and_category():
    from app.material_knowledge import material_code_from_payload
    from scripts.regenerate_material_skus_and_knowledge import canonical_category, canonical_material_code

    cases = {
        "南红玛瑙": "south_red_agate",
        "红玛瑙": "red_agate",
        "盐源玛瑙": "salt_source_agate",
        "阿拉善玛瑙": "alashan_agate",
        "条纹玛瑙": "banded_agate",
        "樱花玛瑙": "flower_agate",
    }
    for series, expected in cases.items():
        payload = {"top": "bead", "category": "红色晶石", "series": series, "name": series}
        assert material_code_from_payload(payload) == expected
        assert canonical_material_code({**payload, "material_code": "red_agate"}) == expected
        assert canonical_category(payload, expected) == "玛瑙"


def test_material_catalog_exposes_cache_version():
    response = client.get("/api/v1/materials")
    data = response.json()["data"]

    assert response.status_code == 200
    assert "version" in data
    assert "updated_at" in data


def test_order_rejects_stale_material_price(tmp_path):
    from app.admin_service import AdminService

    db_path = tmp_path / "stale-material-price.db"
    admin = AdminService(db_path)
    ensure_material_taxonomy(admin, "test", "Price Check Bead")
    saved = admin.save_material(
        {
            "id": "priceCheckBead8",
            "skuId": "priceCheckBead8",
            "top": "bead",
            "category": "test",
            "name": "Price Check Bead",
            "effect": "focus",
            "element": "water",
            "price": 2,
            "size": 8,
            "weight": 1,
            "stock": 10,
            "enabled": True,
        }
    )
    service = OrderService(db_path)
    service.get_user = lambda _user_id: None

    with pytest.raises(ValueError, match="珠材价格已更新"):
        service.create_order(
            {
                "user_id": "price-check-user",
                "receiver": {
                    "name": "Test User",
                    "phone": "13800000000",
                    "address": "Test Address",
                },
                "design": {"summary": {"price": 1}},
                "sequence": [{"id": saved["id"], "sku": saved["skuId"], "name": saved["name"], "price": 1}],
                "bom": [],
            }
        )


def test_order_repairs_legacy_zero_price_without_snapshot(tmp_path, monkeypatch):
    from app.admin_service import AdminService

    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "false")
    db_path = tmp_path / "legacy-zero-price.db"
    admin = AdminService(db_path)
    ensure_material_taxonomy(admin, "test", "Legacy Zero Bead")
    saved = admin.save_material(
        {
            "id": "legacyZeroBead8",
            "skuId": "legacyZeroBead8",
            "top": "bead",
            "category": "test",
            "name": "Legacy Zero Bead",
            "effect": "focus",
            "element": "water",
            "price": 0.01,
            "size": 8,
            "weight": 1,
            "stock": 10,
            "enabled": True,
        }
    )
    service = OrderService(db_path)
    service.get_user = lambda _user_id: None

    result = service.create_order(
        {
            "user_id": "legacy-zero-user",
            "receiver": {
                "name": "Test User",
                "phone": "13800000000",
                "address": "Test Address",
            },
            "design": {"summary": {"price": 0}},
            "sequence": [{"id": saved["id"], "sku": saved["skuId"], "name": saved["name"], "price": 0}],
            "bom": [],
        }
    )
    order = result["order"]

    assert order["total_amount"] == 0.01
    assert order["sequence"][0]["price"] == 0.01


def test_order_uses_current_material_price_snapshot(tmp_path, monkeypatch):
    from app.admin_service import AdminService

    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "false")
    db_path = tmp_path / "current-material-price.db"
    admin = AdminService(db_path)
    ensure_material_taxonomy(admin, "test", "Current Price Bead")
    saved = admin.save_material(
        {
            "id": "currentPriceBead8",
            "skuId": "currentPriceBead8",
            "top": "bead",
            "category": "test",
            "name": "Current Price Bead",
            "effect": "focus",
            "element": "water",
            "price": 3.5,
            "size": 8,
            "weight": 1,
            "stock": 10,
            "enabled": True,
        }
    )
    service = OrderService(db_path)
    service.get_user = lambda _user_id: None
    result = service.create_order(
        {
            "user_id": "current-price-user",
            "receiver": {
                "name": "Test User",
                "phone": "13800000000",
                "address": "Test Address",
            },
            "design": {"summary": {"price": 999}},
            "sequence": [{"id": saved["id"], "sku": saved["skuId"], "name": saved["name"], "price": 3.5}],
            "bom": [],
        }
    )

    assert result["order"]["total_amount"] == 3.5
    assert result["order"]["bom"][0]["qty"] == 1


def test_order_material_snapshot_survives_material_update_and_delete(tmp_path, monkeypatch):
    from app.admin_service import AdminService

    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "false")
    db_path = tmp_path / "order-material-snapshot.db"
    admin = AdminService(db_path)
    ensure_material_taxonomy(admin, "original-category", "Original Series")
    ensure_material_taxonomy(admin, "changed-category", "Changed Series")
    saved = admin.save_material(
        {
            "id": "snapshotBead8",
            "skuId": "snapshotBead",
            "top": "bead",
            "category": "original-category",
            "series": "Original Series",
            "name": "Original Snapshot Bead",
            "effect": "original effect",
            "element": "water",
            "price": 8.8,
            "size": 8,
            "weight": 1.2,
            "stock": 10,
            "enabled": True,
            "image_url": "https://cdn-test.yustream.cn/materials/beads/original.png",
            "image_urls": [
                "https://cdn-test.yustream.cn/materials/beads/original.png",
                "https://cdn-test.yustream.cn/materials/beads/original-side.png",
            ],
        }
    )
    service = OrderService(db_path)
    service.get_user = lambda _user_id: None
    result = service.create_order(
        {
            "user_id": "snapshot-user",
            "receiver": {
                "name": "Test User",
                "phone": "13800000000",
                "address": "Test Address",
            },
            "design": {"summary": {"price": 999}},
            "sequence": [{"id": saved["id"], "sku": saved["skuId"], "name": "Frontend Name", "price": 8.8}],
            "bom": [],
        }
    )
    order_id = result["order"]["order_id"]

    admin.save_material(
        {
            **saved,
            "name": "Changed Bead",
            "category": "changed-category",
            "series": "Changed Series",
            "effect": "changed effect",
            "effects": ["vitality"],
            "element": "fire",
            "price": 99,
            "image_url": "https://cdn-test.yustream.cn/materials/beads/changed.png",
            "image_urls": ["https://cdn-test.yustream.cn/materials/beads/changed.png"],
            "stock": 10,
            "enabled": True,
        }
    )
    admin.delete_material(saved["id"])

    user_order = service.get_order(order_id)
    admin_order = admin.get_order(order_id)
    for order in (user_order, admin_order):
        item = order["sequence"][0]
        bom = order["bom"][0]
        assert order["total_amount"] == 8.8
        assert item["name"] == "Original Snapshot Bead"
        assert item["category"] == "original-category"
        assert item["series"] == "Original Series"
        assert item["effect"] == "original effect"
        assert item["element"] == "water"
        assert item["price"] == 8.8
        assert item["image_url"].endswith("/original.png")
        assert item["image_urls"] == [
            "https://cdn-test.yustream.cn/materials/beads/original.png",
            "https://cdn-test.yustream.cn/materials/beads/original-side.png",
        ]
        assert bom["name"] == "Original Snapshot Bead"
        assert bom["price"] == 8.8


def test_generated_order_numbers_are_numeric_fixed_length_and_unique():
    values = {generate_numeric_order_no() for _ in range(2000)}

    assert len(values) == 2000
    assert all(value.isdigit() and len(value) == 20 for value in values)


def test_created_order_uses_same_numeric_id_for_payment_trade_no(tmp_path):
    service = OrderService(tmp_path / "orders.db")
    service.get_user = lambda _user_id: None
    result = service.create_order(
        {
            "user_id": "numeric-order-user",
            "receiver": {
                "name": "测试用户",
                "phone": "13800000000",
                "address": "测试地址",
            },
            "design": {"summary": {"price": 18}},
            "sequence": [{"name": "测试珠子", "price": 18}],
            "bom": [],
        }
    )
    order = result["order"]

    assert order["order_id"].isdigit()
    assert len(order["order_id"]) == 20
    assert order["out_trade_no"] == order["order_id"]


def test_wechat_pay_test_mode_forces_one_cent(tmp_path, monkeypatch):
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")
    service = OrderService(tmp_path / "orders-test-pay.db")
    service.get_user = lambda _user_id: None
    result = service.create_order(
        {
            "user_id": "one-cent-user",
            "receiver": {
                "name": "测试用户",
                "phone": "13800000000",
                "address": "测试地址",
            },
            "design": {"summary": {"price": 999}},
            "sequence": [{"name": "测试珠子", "price": 999}],
            "bom": [],
        }
    )

    assert result["order"]["total_amount"] == 0.01
    assert result["order"]["total_fee"] == 1


def test_wechat_login_profile_and_phone_flow_without_secret(monkeypatch):
    from app.api import auth_service

    class DisabledAvatarStorage:
        enabled = False

    monkeypatch.setattr(auth_service, "avatar_storage", DisabledAvatarStorage())
    monkeypatch.setattr(auth_service, "app_id", None)
    monkeypatch.setattr(auth_service, "app_secret", None)
    monkeypatch.setenv("ALLOW_MANUAL_PHONE_BIND", "true")
    login_code = f"unit-test-login-code-{uuid4()}"
    login = client.post("/api/v1/auth/wechat-login", json={"code": login_code})
    user = login.json()["data"]

    assert login.status_code == 200
    assert user["user_id"].isdigit()
    assert user["openid"].startswith("dev_")
    assert user["has_profile"] is False

    profile = client.post(
        "/api/v1/auth/profile",
        json={
            "user_id": user["user_id"],
            "nickname": "Test User",
            "avatar_url": "https://example.com/avatar.png",
            "gender": "1",
        },
    )
    updated = profile.json()["data"]

    assert profile.status_code == 200
    assert updated["nickname"] == "Test User"
    assert updated["has_profile"] is True

    phone = client.post(
        "/api/v1/auth/phone",
        json={"user_id": user["user_id"], "phone_number": "13800000000"},
    )

    assert phone.status_code == 200
    assert phone.json()["data"]["has_phone"] is True

    repeat = client.post("/api/v1/auth/wechat-login", json={"code": login_code})
    repeat_user = repeat.json()["data"]

    assert repeat.status_code == 200
    assert repeat_user["user_id"] == user["user_id"]


def test_profile_avatar_is_persisted_to_cos_when_storage_enabled(tmp_path):
    from app.auth_service import WechatAuthService
    from app.avatar_storage import AvatarUploadResult
    from app.repository import AssessmentRepository
    from app.schemas import UserProfileUpdateRequest

    class FakeAvatarStorage:
        enabled = True

        def is_managed_url(self, url):
            return False

        def upload_url(self, user_id, avatar_url):
            assert user_id == "avatar-user"
            assert avatar_url == "https://thirdwx.qlogo.cn/avatar.png"
            return AvatarUploadResult(
                key="users/avatars/avatar-user/avatar.webp",
                avatar_url="https://cdn-test.yustream.cn/users/avatars/avatar-user/avatar.webp",
            )

    service = WechatAuthService(
        AssessmentRepository(tmp_path / "avatar-profile.db"),
        avatar_storage=FakeAvatarStorage(),
    )
    user = service.update_profile(
        UserProfileUpdateRequest(
            user_id="avatar-user",
            nickname="头像用户",
            avatar_url="https://thirdwx.qlogo.cn/avatar.png",
        )
    )

    assert user["avatar_url"] == "https://cdn-test.yustream.cn/users/avatars/avatar-user/avatar.webp"


def test_admin_user_avatar_sync_updates_legacy_avatar_url(tmp_path, monkeypatch):
    import app.admin_service as admin_service_module
    from app.admin_service import AdminService
    from app.avatar_storage import AvatarUploadResult
    from app.repository import AssessmentRepository

    class FakeAvatarStorage:
        enabled = True

        def is_managed_url(self, url):
            return "cdn-test.yustream.cn/users/avatars" in url

        def upload_url(self, user_id, avatar_url):
            assert user_id == "legacy-avatar-user"
            assert avatar_url == "https://thirdwx.qlogo.cn/legacy.png"
            return AvatarUploadResult(
                key="users/avatars/legacy-avatar-user/avatar.webp",
                avatar_url="https://cdn-test.yustream.cn/users/avatars/legacy-avatar-user/avatar.webp",
            )

    monkeypatch.setattr(admin_service_module, "AvatarStorage", FakeAvatarStorage)
    db_path = tmp_path / "admin-avatar-sync.db"
    AssessmentRepository(db_path)
    service = AdminService(db_path)
    timestamp = now_iso()
    with service.connect() as connection:
        connection.execute(
            """
            INSERT INTO users
            (user_id, openid, nickname, avatar_url, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-avatar-user",
                "openid-legacy-avatar",
                "旧头像用户",
                "https://thirdwx.qlogo.cn/legacy.png",
                "wechat",
                timestamp,
                timestamp,
            ),
        )

    result = service.sync_user_avatars_to_cos(limit=10)
    with service.connect() as connection:
        row = connection.execute(
            "SELECT avatar_url FROM users WHERE user_id = ?",
            ("legacy-avatar-user",),
        ).fetchone()

    assert result["synced"] == 1
    assert result["skipped"] == 0
    assert result["failed"] == []
    assert row["avatar_url"] == "https://cdn-test.yustream.cn/users/avatars/legacy-avatar-user/avatar.webp"


def test_legacy_openid_user_id_is_migrated_to_numeric(tmp_path):
    from app.auth_service import WechatAuthService
    from app.repository import AssessmentRepository

    repository = AssessmentRepository(tmp_path / "legacy-user-id.db")
    service = WechatAuthService(repository)
    legacy_user_id = "ov_legacy_openid_user"
    now = service.now()
    repository.upsert_user(
        {
            "user_id": legacy_user_id,
            "openid": legacy_user_id,
            "source": "wechat",
            "updated_at": now,
        }
    )
    with repository.connect() as connection:
        connection.execute(
            """
            INSERT INTO energy_assessments
            (assessment_id, user_id, fingerprint, name, core_wish, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("legacy-assessment", legacy_user_id, "legacy-fp", "Legacy", "Wish", "{}", now),
        )

    numeric_user_id = service.resolve_numeric_user_id({"openid": legacy_user_id}, service.now())

    assert numeric_user_id.isdigit()
    assert repository.get_user_by_openid(legacy_user_id)["user_id"] == numeric_user_id
    assert repository.get_user(legacy_user_id) is None
    with repository.connect() as connection:
        row = connection.execute(
            "SELECT user_id FROM energy_assessments WHERE assessment_id = ?",
            ("legacy-assessment",),
        ).fetchone()
    assert row["user_id"] == numeric_user_id


def test_manual_phone_binding_is_disabled_by_default(monkeypatch):
    from app.api import auth_service

    monkeypatch.delenv("ALLOW_MANUAL_PHONE_BIND", raising=False)
    monkeypatch.setattr(auth_service, "app_id", None)
    monkeypatch.setattr(auth_service, "app_secret", None)
    login = client.post("/api/v1/auth/wechat-login", json={"code": f"manual-phone-{uuid4()}"})
    user = login.json()["data"]

    response = client.post(
        "/api/v1/auth/phone",
        json={"user_id": user["user_id"], "phone_number": "13800000000"},
    )

    assert response.status_code == 400
    assert "仅支持微信授权手机号" in response.json()["detail"]


def test_order_detail_checks_owner(tmp_path):
    service = OrderService(tmp_path / "order-detail.db")
    service.get_user = lambda _user_id: None
    result = service.create_order(
        {
            "user_id": "detail-owner",
            "receiver": {"name": "测试用户", "phone": "13800000000", "address": "测试地址"},
            "design": {"summary": {"price": 18}},
            "sequence": [{"name": "测试珠子", "price": 18}],
            "bom": [],
        }
    )
    order = result["order"]

    service.ensure_order_owner(service.get_order(order["order_id"]), "detail-owner")
    try:
        service.ensure_order_owner(service.get_order(order["order_id"]), "another-user")
    except ValueError as exc:
        assert "无权操作" in str(exc)
    else:
        raise AssertionError("another user should not access the order")


def test_pending_order_can_be_cancelled(tmp_path):
    service = OrderService(tmp_path / "order-cancel.db")
    service.get_user = lambda _user_id: None
    result = service.create_order(
        {
            "user_id": "cancel-owner",
            "receiver": {"name": "测试用户", "phone": "13800000000", "address": "测试地址"},
            "design": {"summary": {"price": 18}},
            "sequence": [{"name": "测试珠子", "price": 18}],
            "bom": [],
        }
    )

    cancelled = service.cancel_order(
        result["order"]["order_id"],
        "cancel-owner",
        "用户改变主意",
    )

    assert cancelled["status"] == "closed"
    assert cancelled["payment_status"] == "cancelled"
    assert cancelled["status_history"][-1]["status"] == "closed"


def test_order_receiver_can_only_change_before_shipping(tmp_path, monkeypatch):
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")
    service = OrderService(tmp_path / "order-receiver.db")
    service.get_user = lambda _user_id: None
    result = service.create_order(
        {
            "user_id": "receiver-owner",
            "receiver": {"name": "测试用户", "phone": "13800000000", "address": "旧地址"},
            "design": {"summary": {"price": 18}},
            "sequence": [{"name": "测试珠子", "price": 18}],
            "bom": [],
        }
    )
    order_id = result["order"]["order_id"]

    pending = service.update_order_receiver(
        order_id,
        "receiver-owner",
        {"name": "测试用户", "phone": "13800000001", "address": "待付款新地址"},
    )
    assert pending["receiver"]["address"] == "待付款新地址"

    service.mark_paid_for_dev(order_id, "receiver-owner")
    paid = service.update_order_receiver(
        order_id,
        "receiver-owner",
        {"name": "测试用户", "phone": "13800000002", "address": "待发货新地址"},
    )
    assert paid["receiver"]["address"] == "待发货新地址"

    service.mark_shipped_for_dev(order_id, "receiver-owner", phone_tail="0002")
    with pytest.raises(ValueError, match="订单已发货"):
        service.update_order_receiver(
            order_id,
            "receiver-owner",
            {"name": "测试用户", "phone": "13800000003", "address": "已发货新地址"},
        )


def test_admin_approval_submits_wechat_refund_and_marks_order_refunded(tmp_path, monkeypatch):
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")
    service = OrderService(tmp_path / "order-refund.db")
    service.get_user = lambda _user_id: None
    result = service.create_order(
        {
            "user_id": "refund-owner",
            "receiver": {"name": "测试用户", "phone": "13800000000", "address": "测试地址"},
            "design": {"summary": {"price": 18}},
            "sequence": [{"name": "测试珠子", "price": 18}],
            "bom": [],
        }
    )
    order_id = result["order"]["order_id"]
    service.mark_paid_for_dev(order_id, "refund-owner")
    requested = service.request_refund(order_id, "refund-owner", "用户取消定制")

    assert requested["status"] == "refund_requested"
    assert requested["refund"]["reason"] == "用户取消定制"

    class FakeWechatPayConfig:
        ready = True
        missing: list[str] = []

    monkeypatch.setattr("app.order_service.WechatPayConfig", FakeWechatPayConfig)
    refund_calls = []

    def fake_wechat_refund(order, out_refund_no, refund_fee, total_fee, reason, config):
        refund_calls.append(
            {
                "order_id": order["order_id"],
                "out_refund_no": out_refund_no,
                "refund_fee": refund_fee,
                "total_fee": total_fee,
                "reason": reason,
                "config": config,
            }
        )
        return {"status": "SUCCESS", "refund_id": "wx-refund-001"}

    monkeypatch.setattr(service, "create_wechat_refund", fake_wechat_refund)
    approved = service.approve_refund(order_id, operator="admin", note="核实后同意")

    assert approved["status"] == "refunded"
    assert approved["payment_status"] == "refunded"
    assert approved["refund_status"] == "success"
    assert approved["refund"]["wechat_response"]["refund_id"] == "wx-refund-001"
    assert approved["refund"]["approved_by"] == "admin"
    assert refund_calls[0]["refund_fee"] == approved["total_fee"]


def test_wechat_refund_notify_marks_processing_order_refunded(tmp_path, monkeypatch):
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")
    service = OrderService(tmp_path / "order-refund-notify.db")
    service.get_user = lambda _user_id: None
    result = service.create_order(
        {
            "user_id": "refund-notify-owner",
            "receiver": {"name": "测试用户", "phone": "13800000000", "address": "测试地址"},
            "design": {"summary": {"price": 18}},
            "sequence": [{"name": "测试珠子", "price": 18}],
            "bom": [],
        }
    )
    order_id = result["order"]["order_id"]
    paid = service.mark_paid_for_dev(order_id, "refund-notify-owner")
    requested = service.request_refund(order_id, "refund-notify-owner", "用户取消定制")

    class FakeWechatPayConfig:
        mch_id = "1746874094"
        api_v3_key = "0" * 32

    refund_result = {
        "mchid": "1746874094",
        "out_trade_no": paid["out_trade_no"],
        "transaction_id": "wx-transaction-001",
        "out_refund_no": requested["refund"]["out_refund_no"] if requested["refund"].get("out_refund_no") else f"RF{order_id}",
        "refund_id": "wx-refund-001",
        "refund_status": "SUCCESS",
        "success_time": "2026-06-26T12:00:00+08:00",
        "amount": {
            "total": requested["total_fee"],
            "refund": requested["total_fee"],
            "payer_refund": requested["total_fee"],
        },
    }

    monkeypatch.setattr("app.order_service.WechatPayConfig", FakeWechatPayConfig)
    monkeypatch.setattr(service, "verify_wechat_notify_signature", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "decrypt_wechat_resource", lambda _resource, _key: refund_result)

    service.handle_wechat_refund_notify(
        {
            "wechatpay-serial": "PUB_KEY_ID_TEST",
            "wechatpay-timestamp": "1790000000",
            "wechatpay-nonce": "nonce",
            "wechatpay-signature": "signature",
        },
        '{"resource":{"ciphertext":"mock"}}',
    )
    updated = service.get_order(order_id)

    assert updated["status"] == "refunded"
    assert updated["payment_status"] == "refunded"
    assert updated["refund_status"] == "success"
    assert updated["refund"]["wechat_status"] == "SUCCESS"
    assert updated["refund"]["refund_id"] == "wx-refund-001"


def test_sync_wechat_refund_accepts_query_status_field(tmp_path, monkeypatch):
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")
    service = OrderService(tmp_path / "order-refund-sync-status.db")
    service.get_user = lambda _user_id: None
    result = service.create_order(
        {
            "user_id": "refund-sync-owner",
            "receiver": {"name": "测试用户", "phone": "13800000000", "address": "测试地址"},
            "design": {"summary": {"price": 18}},
            "sequence": [{"name": "测试珠子", "price": 18}],
            "bom": [],
        }
    )
    order_id = result["order"]["order_id"]
    paid = service.mark_paid_for_dev(order_id, "refund-sync-owner")
    requested = service.request_refund(order_id, "refund-sync-owner", "用户取消定制")

    class FakeWechatPayConfig:
        ready = True
        mch_id = "1746874094"
        missing: list[str] = []

    monkeypatch.setattr("app.order_service.WechatPayConfig", FakeWechatPayConfig)
    monkeypatch.setattr(
        service,
        "query_wechat_refund",
        lambda out_refund_no, config: {
            "mchid": "1746874094",
            "out_trade_no": paid["out_trade_no"],
            "transaction_id": "wx-transaction-001",
            "out_refund_no": out_refund_no,
            "refund_id": "wx-refund-sync-001",
            "status": "SUCCESS",
            "success_time": "2026-06-26T12:00:00+08:00",
            "amount": {
                "total": requested["total_fee"],
                "refund": requested["total_fee"],
                "payer_refund": requested["total_fee"],
            },
        },
    )

    synced = service.sync_wechat_refund(order_id, operator="admin")

    assert synced["status"] == "refunded"
    assert synced["payment_status"] == "refunded"
    assert synced["refund_status"] == "success"
    assert synced["refund"]["wechat_status"] == "SUCCESS"
    assert synced["refund"]["refund_id"] == "wx-refund-sync-001"


def test_mock_payment_is_disabled_outside_test_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("WECHAT_PAY_TEST_MODE", raising=False)
    service = OrderService(tmp_path / "mock-disabled.db")
    service.get_user = lambda _user_id: None
    result = service.create_order(
        {
            "user_id": "mock-disabled-user",
            "receiver": {"name": "测试用户", "phone": "13800000000", "address": "测试地址"},
            "design": {"summary": {"price": 18}},
            "sequence": [{"name": "测试珠子", "price": 18}],
            "bom": [],
        }
    )

    try:
        service.mark_paid_for_dev(result["order"]["order_id"], "mock-disabled-user")
    except ValueError as exc:
        assert "禁用模拟支付" in str(exc)
    else:
        raise AssertionError("production mode must reject mock payment")


def test_diy_design_list_and_delete(tmp_path):
    service = OrderService(tmp_path / "design-assets.db")
    saved = service.save_design(
        {
            "user_id": "design-user",
            "design": {"summary": {"price": 128}},
            "sequence": [{"name": "南红玛瑙", "size": 8}],
        }
    )

    designs = service.list_designs("design-user")
    assert [item["design_id"] for item in designs] == [saved["design_id"]]
    assert designs[0]["sequence"][0]["name"] == "南红玛瑙"

    deleted = service.delete_design(saved["design_id"], "design-user")
    assert deleted["deleted"] is True
    assert service.list_designs("design-user") == []


def test_cart_items_can_be_created_updated_and_cleared(tmp_path):
    service = OrderService(tmp_path / "cart-assets.db")
    item = service.save_cart_item(
        {
            "user_id": "cart-user",
            "item_type": "plan",
            "item_id": "plan-001",
            "item": {"name": "温柔守护方案", "price": 299},
            "quantity": 1,
        }
    )

    assert item["quantity"] == 1
    assert service.list_cart_items("cart-user")[0]["item"]["name"] == "温柔守护方案"

    updated = service.update_cart_item(item["cart_item_id"], "cart-user", {"quantity": 2})
    assert updated["quantity"] == 2

    service.delete_cart_item(item["cart_item_id"], "cart-user")
    assert service.list_cart_items("cart-user") == []


def test_community_favorites_are_user_scoped_and_mutable(tmp_path):
    service = OrderService(tmp_path / "community-favorites.db")
    saved = service.save_community_favorite(
        {
            "user_id": "favorite-user",
            "post_id": "post-001",
            "item": {"title": "Morning crystal inspiration", "recipe": ["clearQuartz"]},
        }
    )

    assert saved["id"] == "post-001"
    assert saved["title"] == "Morning crystal inspiration"
    assert service.list_community_favorites("other-user") == []
    assert service.list_community_favorites("favorite-user")[0]["post_id"] == "post-001"

    deleted = service.delete_community_favorite("favorite-user", "post-001")
    assert deleted["deleted"] is True
    assert service.list_community_favorites("favorite-user") == []


def test_diy_design_rekeys_when_design_id_belongs_to_another_user(tmp_path):
    service = OrderService(tmp_path / "design-id-conflict.db")
    first = service.save_design(
        {
            "user_id": "design-user-a",
            "design_id": "shared-local-design-id",
            "design": {"summary": {"price": 88}},
            "sequence": [{"name": "白水晶", "size": 8}],
        }
    )
    second = service.save_design(
        {
            "user_id": "design-user-b",
            "design_id": "shared-local-design-id",
            "design": {"summary": {"price": 99}},
            "sequence": [{"name": "彩幽灵", "size": 8}],
        }
    )

    assert first["design_id"] == "shared-local-design-id"
    assert second["design_id"] != "shared-local-design-id"
    assert second["user_id"] == "design-user-b"
    assert service.get_design("shared-local-design-id")["user_id"] == "design-user-a"


def test_user_addresses_keep_single_default(tmp_path):
    service = OrderService(tmp_path / "address-assets.db")
    first = service.save_address(
        {
            "user_id": "address-user",
            "name": "张三",
            "phone": "13800000000",
            "region": ["重庆市", "重庆市", "渝中区"],
            "detail_address": "解放碑 1 号",
        }
    )
    second = service.save_address(
        {
            "user_id": "address-user",
            "name": "李四",
            "phone": "13900000000",
            "region": ["四川省", "成都市", "锦江区"],
            "detail_address": "春熙路 2 号",
            "is_default": True,
        }
    )

    assert first["is_default"] is True
    addresses = service.list_addresses("address-user")
    assert addresses[0]["address_id"] == second["address_id"]
    assert addresses[0]["is_default"] is True
    assert addresses[1]["is_default"] is False

    service.set_default_address(first["address_id"], "address-user")
    addresses = service.list_addresses("address-user")
    assert addresses[0]["address_id"] == first["address_id"]


def test_available_coupons_filter_by_status_amount_and_expiry(tmp_path):
    service = OrderService(tmp_path / "coupon-assets.db")
    timestamp = now_iso()
    with service.connect() as connection:
        connection.execute(
            """
            INSERT INTO user_coupons
            (coupon_id, user_id, title, coupon_type, value, min_amount, status, expires_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("coupon-ok", "coupon-user", "新客券", "amount", 20, 100, "unused", "2099-01-01T00:00:00+00:00", timestamp, timestamp),
        )
        connection.execute(
            """
            INSERT INTO user_coupons
            (coupon_id, user_id, title, coupon_type, value, min_amount, status, expires_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("coupon-high", "coupon-user", "高门槛券", "amount", 50, 999, "unused", "2099-01-01T00:00:00+00:00", timestamp, timestamp),
        )

    assert [coupon["coupon_id"] for coupon in service.available_coupons("coupon-user", 199)] == ["coupon-ok"]


def test_calculate_returns_ui_ready_result():
    response = client.post("/api/v1/assessment/calculate", json={**PAYLOAD, "force_recalculate": True})
    data = response.json()["data"]

    assert response.status_code == 200
    assert data["chart"]["type"] == "radar"
    assert data["primary_crystal"]["role"] == "主石"
    assert data["bracelet_plan"]["layout"]


def test_two_step_energy_to_diy_workbench_flow():
    energy_response = client.post(
        "/api/v1/assessment/energy",
        json={**PAYLOAD, "force_recalculate": True},
    )
    energy_data = energy_response.json()["data"]

    assert energy_response.status_code == 200
    assert energy_data["status"] == "energy_ready"
    assert energy_data["next_step"]["action"] == "open_wrist_size_form"
    assert "bracelet_plan" not in energy_data

    recommendation_response = client.post(
        f"/api/v1/assessment/{energy_data['assessment_id']}/diy-recommendation",
        json={"wrist_size_cm": 16.5, "bead_size_mm": 8},
    )
    recommendation_data = recommendation_response.json()["data"]

    assert recommendation_response.status_code == 200
    assert recommendation_data["status"] == "diy_ready"
    assert recommendation_data["next_step"]["action"] == "navigate_to_diy_workbench"
    assert recommendation_data["workbench_payload"]["wrist_size_cm"] == 16.5
    assert recommendation_data["workbench_payload"]["bracelet_plan"]["layout"]


def test_invalid_mbti_is_rejected():
    response = client.post("/api/v1/assessment/calculate", json={**PAYLOAD, "mbti": "NOPE"})
    assert response.status_code == 422
    assert response.json()["code"] == 422


def test_optional_mbti_and_three_core_wishes_are_accepted():
    response = client.post(
        "/api/v1/assessment/energy",
        json={
            **PAYLOAD,
            "mbti": None,
            "core_wish": None,
            "core_wishes": [
                "招财进宝/事业腾飞",
                "正缘桃花/人际和合",
                "健康护身/保持专注",
            ],
            "chakra_answers": ["state_expression", "need_clarity"],
            "mood_palette_id": "sea_salt_blue",
            "force_recalculate": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["input_summary"]["mbti"] is None
    assert len(response.json()["data"]["input_summary"]["core_wishes"]) == 3
    assert response.json()["data"]["chakra_analysis"]["primary_chakra"] == "throat"
    assert response.json()["data"]["mood_analysis"]["palette_id"] == "sea_salt_blue"


def test_more_than_three_core_wishes_are_rejected():
    response = client.post(
        "/api/v1/assessment/energy",
        json={
            **PAYLOAD,
            "core_wish": None,
            "core_wishes": [
                "招财进宝/事业腾飞",
                "正缘桃花/人际和合",
                "辟邪防小人/消除焦虑",
                "健康护身/保持专注",
            ],
        },
    )

    assert response.status_code == 422


def test_first_time_user_gets_starter_daily_energy_and_same_day_is_cached():
    user_id = "daily-starter-user-v3"
    first = client.get(f"/api/v1/daily-energy/today?user_id={user_id}&force_recalculate=true")
    second = client.get(f"/api/v1/daily-energy/today?user_id={user_id}")

    assert first.status_code == 200
    assert first.json()["data"]["mode"] == "starter"
    assert first.json()["data"]["personalized"] is False
    assert first.json()["data"]["guide"]["route"] == "/pages/assessment/assessment"
    assert first.json()["data"]["recommended_stone"]
    assert len(first.json()["data"]["recommended_crystals"]) >= 2
    assert first.json()["data"]["commerce_entry"]["source"] == "daily_energy"
    assert first.json()["data"]["workbench_payload"]["source"] == "daily_energy"
    assert first.json()["data"]["workbench_payload"]["bracelet_plan"]["layout"]
    assert first.json()["data"]["rules_version"]
    assert first.json()["data"]["state_context"]["source"] == "live_selection"
    assert second.json()["data"]["cache_hit"] is True
    assert second.json()["data"]["score"] == first.json()["data"]["score"]


def test_assessed_user_gets_personalized_daily_energy():
    user_id = "daily-personalized-user"
    client.post(
        "/api/v1/assessment/energy",
        json={**PAYLOAD, "user_id": user_id, "force_recalculate": True},
    )
    response = client.get(f"/api/v1/daily-energy/today?user_id={user_id}&force_recalculate=true")
    data = response.json()["data"]

    assert response.status_code == 200
    assert data["mode"] == "personalized"
    assert data["personalized"] is True
    assert data["assessment_id"]
    assert data["guide"] is None
    assert data["workbench_payload"]["source_context"]["assessment_id"] == data["assessment_id"]
    assert data["commerce_entry"]["button_text"] == "一键生成今日手串"


def test_daily_options_and_live_tags_are_used_on_recalculation():
    user_id = "daily-checkin-user"
    options = client.get("/api/v1/daily-energy/options")
    checkin = client.post(
        "/api/v1/daily-energy/check-in?checkin_date=2026-06-04",
        json={"user_id": user_id, "mood": 5, "sleep": 5, "stress": 1},
    )
    response = client.get(
        f"/api/v1/daily-energy/2026-06-04?user_id={user_id}"
        "&status_tags=money&scene_key=deadline&goal_keys=wealth&force_recalculate=true"
    )

    assert options.status_code == 200
    assert options.json()["data"]["status_tags"]
    first_status_tag = options.json()["data"]["status_tags"][0]
    assert first_status_tag["short_label"]
    assert "priority" in first_status_tag
    assert "featured" in first_status_tag
    assert options.json()["data"]["scenes"]
    assert options.json()["data"]["goals"]
    assert checkin.status_code == 200
    assert response.status_code == 200
    assert response.json()["data"]["state_context"]["source"] == "live_selection"
    assert response.json()["data"]["state_context"]["selected_status_tags"][0]["key"] == "money"
    assert response.json()["data"]["state_context"]["selected_scene"]["key"] == "deadline"
