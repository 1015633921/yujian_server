from decimal import Decimal

import pytest

from scripts.set_initial_accessory_prices import (
    EXPECTED_ACCESSORY_SKUS,
    EXPECTED_CATEGORY_COUNTS,
    build_pricing_rows,
    price_cents,
    price_for_accessory,
    validate_inventory,
)


def accessory(
    item_id: str,
    category: str,
    name: str,
    size: float,
    *,
    price: float = 10,
    enabled: int = 1,
):
    return {
        "id": item_id,
        "skuId": item_id,
        "category": category,
        "series": name,
        "material_code": "",
        "grade": "",
        "name": name,
        "size": size,
        "price": price,
        "price_cents": int(price * 100),
        "stock": 100,
        "enabled": enabled,
        "updated_at": "",
    }


def test_market_anchor_examples_are_stable():
    assert price_for_accessory(
        accessory("mat_accessory_metal_small", "隔珠", "小号银色素面圆珠", 2.7)
    ) == Decimal("2.00")
    assert price_for_accessory(
        accessory("mat_accessory_metal_zircon", "隔珠", "锆石排镶隔珠", 9.9)
    ) == Decimal("10.50")
    assert price_for_accessory(
        accessory("mat_accessory_metal_lotus", "花托", "莲花花托", 15.2)
    ) == Decimal("6.00")
    assert price_for_accessory(
        accessory("crystal_green_ghost", "方糖", "绿幽灵方糖", 10)
    ) == Decimal("27.00")
    assert price_for_accessory(
        accessory("crystal_triangle", "三角牌", "幽灵三角牌", 21.8)
    ) == Decimal("67.50")


def test_prices_are_whole_half_yuan_and_cents_match():
    samples = [
        accessory("mat_accessory_metal_plain", "隔珠", "银色素面圆珠", 6),
        accessory("mat_accessory_metal_flower", "花托", "繁花镂空花托", 8),
        accessory("crystal_cut", "切面珠", "幽灵切面珠", 15),
        accessory("crystal_tablet", "无事牌", "幽灵无事牌", 17),
        accessory("crystal_double", "双尖", "幽灵双尖", 21),
    ]
    for row in samples:
        price = price_for_accessory(row)
        assert price * 2 == (price * 2).to_integral_value()
        assert price_cents(price) == int(price * 100)


def test_premium_shapes_cost_more_than_simple_alloy_parts():
    simple = price_for_accessory(
        accessory("mat_accessory_metal_plain", "隔珠", "银色素面圆珠", 6)
    )
    zircon = price_for_accessory(
        accessory("mat_accessory_metal_zircon", "隔珠", "锆石排镶隔珠", 9.9)
    )
    ghost = price_for_accessory(accessory("crystal_ghost", "无事牌", "幽灵无事牌", 14))
    assert simple < zircon < ghost


def test_inventory_guard_requires_exact_category_counts():
    rows = []
    index = 0
    metal_categories = {"包珠隔片", "花托", "连接扣", "隔片", "隔珠"}
    for category, count in EXPECTED_CATEGORY_COUNTS.items():
        for _ in range(count):
            prefix = "mat_accessory_metal_" if category in metal_categories else "crystal_"
            rows.append(accessory(f"{prefix}{index}", category, category, 10))
            index += 1
    assert len(rows) == EXPECTED_ACCESSORY_SKUS
    assert validate_inventory(rows) == rows
    assert len(build_pricing_rows(rows)) == EXPECTED_ACCESSORY_SKUS

    with pytest.raises(ValueError, match="配饰 SKU 数"):
        validate_inventory(rows[:-1])

    changed = [dict(row) for row in rows]
    changed[0]["category"] = "意外分类"
    with pytest.raises(ValueError, match="配饰分类清单不一致"):
        validate_inventory(changed)


def test_unknown_shape_fails_closed():
    with pytest.raises(ValueError, match="未覆盖"):
        price_for_accessory(accessory("crystal_unknown", "未知造型", "未知造型", 10))
