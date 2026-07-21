from __future__ import annotations

import pytest

from scripts.import_accessory_assets_to_test import (
    exact_price,
    material_values,
    positive_stock,
    validate_replacement_scope,
)


def accessory_group(*, code: str = "metal_spacer_test", price: object = "10.25", stock: object = 99):
    return {
        "row": {
            "price": price,
            "stock": stock,
            "element": "metal",
            "color": "#a5aab1",
            "shine": "#ffffff",
        },
        "code": code,
        "series": "测试隔珠",
        "category": "金属配饰",
        "keys": ["materials/accessories/test/metal_spacer_test/01.webp"],
        "urls": ["https://cdn-test.example/materials/accessories/test/metal_spacer_test/01.webp"],
    }


def test_accessory_material_values_store_exact_price_cents_and_positive_stock():
    values = material_values(accessory_group(), "2026-07-14T00:00:00+00:00", 901)

    assert values["price"] == 10.25
    assert values["price_cents"] == 1025
    assert values["stock"] == 99
    assert values["image_path"] == "accessories/test/metal_spacer_test/01.webp"


@pytest.mark.parametrize("value", [None, True, 0, -1, "1.001", "nan", "inf"])
def test_accessory_price_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        exact_price(value)


@pytest.mark.parametrize("value", [None, True, 0, -1, "1.5", "099"])
def test_accessory_stock_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        positive_stock(value)


def test_metal_replacement_scope_rejects_non_metal_codes():
    validate_replacement_scope([accessory_group()])
    with pytest.raises(ValueError, match="non-metal"):
        validate_replacement_scope([accessory_group(code="crystal_charm_test")])
