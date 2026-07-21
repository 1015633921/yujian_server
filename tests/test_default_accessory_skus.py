from __future__ import annotations

import json

import pytest

from scripts.create_default_accessory_skus_to_test import (
    DEFAULT_PRICE_CENTS,
    DEFAULT_PURCHASE_NOTE,
    default_sku_payload,
    is_safe_default_sku_row,
    load_targets,
)


def target(index: int = 1) -> dict[str, object]:
    return {
        "top": "accessory",
        "category": "隔珠",
        "name": "四叶花纹橄榄隔珠",
        "material_code": f"accessory_metal_20260720_{index:02d}",
        "color": "#aeb4b7",
        "shine": "#f6f8f9",
    }


def test_default_accessory_sku_is_safe_and_does_not_duplicate_variety_images():
    sku = default_sku_payload(target(), sort_order=1000)

    assert sku["id"] == "mat_accessory_metal_20260720_01_default"
    assert str(sku["skuId"]).isdigit()
    assert sku["top"] == "accessory"
    assert sku["price"] == "10.00"
    assert sku["price_cents"] == DEFAULT_PRICE_CENTS
    assert sku["size"] == 0
    assert sku["weight"] == 0
    assert sku["stock"] == 0
    assert sku["enabled"] == 0
    assert sku["image_path"] == ""
    assert sku["image_url"] == ""
    assert json.loads(str(sku["image_urls_json"])) == []
    assert json.loads(str(sku["physical_specs_json"])) == {}
    assert "待补充" in DEFAULT_PURCHASE_NOTE


def test_default_accessory_sku_ids_are_stable_and_unique_by_variety():
    first = default_sku_payload(target(1), sort_order=1000)
    repeated = default_sku_payload(target(1), sort_order=1000)
    second = default_sku_payload(target(2), sort_order=1001)

    assert first["skuId"] == repeated["skuId"]
    assert first["skuId"] != second["skuId"]
    assert first["id"] != second["id"]


def test_database_float_representation_of_decimal_price_passes_safety_verification():
    row = {
        **default_sku_payload(target(), sort_order=1000),
        "price": 10.0,
        "reserved_stock": 0,
    }

    assert is_safe_default_sku_row(row) is True

    row["price_cents"] = 1
    assert is_safe_default_sku_row(row) is False


def test_default_sku_manifest_requires_the_exact_28_catalog_codes(tmp_path):
    path = tmp_path / "manifest.json"
    rows = [
        {
            "category": "隔珠",
            "name": f"配饰 {index}",
            "material_code": f"accessory_metal_20260720_{index:02d}",
            "sources": [f"{index}-1.png", f"{index}-2.png"],
        }
        for index in range(1, 29)
    ]
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    assert len(load_targets(path)) == 28

    rows[-1]["material_code"] = "accessory_metal_20260720_99"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit, match="Target material codes mismatch"):
        load_targets(path)
