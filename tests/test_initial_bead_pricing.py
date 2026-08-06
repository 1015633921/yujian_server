from decimal import Decimal

import pytest

from scripts.set_initial_bead_prices import (
    EXPECTED_ACTIVE_SKUS,
    REQUIRED_SIZES,
    SERIES_8MM_ANCHORS,
    price_cents,
    price_for_series_size,
    validate_inventory,
)


def test_every_active_series_has_eight_strictly_increasing_prices():
    assert EXPECTED_ACTIVE_SKUS == len(SERIES_8MM_ANCHORS) * len(REQUIRED_SIZES) == 312
    for series in SERIES_8MM_ANCHORS:
        prices = [price_for_series_size(series, size) for size in REQUIRED_SIZES]
        assert prices == sorted(prices)
        assert len(set(prices)) == len(REQUIRED_SIZES)
        assert all(price_cents(price) == int(price * 100) for price in prices)


def test_market_anchor_examples_are_stable():
    assert price_for_series_size("红玛瑙", 8) == Decimal("2.00")
    assert price_for_series_size("红玛瑙", 10) == Decimal("3.00")
    assert price_for_series_size("白阿塞", 10) == Decimal("6.00")
    assert price_for_series_size("绿幽灵", 10) == Decimal("15.00")
    assert price_for_series_size("钛晶", 15) == Decimal("96.50")


def test_premium_families_keep_higher_8mm_anchors():
    assert price_for_series_size("红兔毛", 8) == Decimal("9.00")
    assert price_for_series_size("绿幽灵", 8) == Decimal("9.00")
    assert price_for_series_size("黑发晶", 8) == Decimal("8.00")
    assert price_for_series_size("金发晶", 8) == Decimal("16.50")


@pytest.mark.parametrize("size", [7, 8.5, 16])
def test_price_rejects_unsupported_sizes(size):
    with pytest.raises(ValueError, match="8-15mm"):
        price_for_series_size("白水晶", size)


def test_price_rejects_unknown_series():
    with pytest.raises(ValueError, match="没有定价锚点"):
        price_for_series_size("未审核新品种", 10)


def test_inventory_guard_requires_exact_active_whitelist():
    rows = []
    for index, (series, _) in enumerate(SERIES_8MM_ANCHORS.items()):
        for size in REQUIRED_SIZES:
            rows.append({"id": f"{index}-{size}", "series": series, "size": size})
    assert len(validate_inventory(rows)) == EXPECTED_ACTIVE_SKUS

    with pytest.raises(ValueError, match="启用珠子 SKU 数"):
        validate_inventory(rows[:-1])

    changed = [dict(row) for row in rows]
    changed[0]["series"] = "意外启用品种"
    with pytest.raises(ValueError, match="品种白名单不一致"):
        validate_inventory(changed)
