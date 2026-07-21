from __future__ import annotations

import pytest

from scripts.split_alloy_accessory_images_to_test import (
    Asset,
    canonical_asset_key,
    deterministic_id,
    deterministic_sku_id,
    split_rows_are_canonical,
    unique_assets,
    validate_runtime,
)


def test_unique_assets_deduplicates_query_and_cos_aliases():
    values = [
        "https://cdn-test.yustream.cn/materials/beads/alloy/01-alloy.webp?v=1",
        "https://cdn-test.yustream.cn/materials/beads/alloy/01-alloy.webp",
        "https://legacy.cos.ap-guangzhou.myqcloud.com/materials/beads/alloy/01-alloy.webp",
        "https://cdn-test.yustream.cn/materials/beads/alloy/02-alloy.webp?v=1",
    ]

    assets = unique_assets(values)

    assert [asset.key for asset in assets] == [
        "materials/beads/alloy/01-alloy.webp",
        "materials/beads/alloy/02-alloy.webp",
    ]
    assert assets[0].url == "https://cdn-test.yustream.cn/materials/beads/alloy/01-alloy.webp"


def test_canonical_asset_key_handles_encoded_and_relative_paths():
    assert canonical_asset_key("https://cdn-test.yustream.cn/materials/a%20b.webp?v=1") == "materials/a b.webp"
    assert canonical_asset_key("materials/accessories/a.webp") == "materials/accessories/a.webp"


def test_generated_alloy_sku_identities_are_stable_and_distinct():
    first = Asset("materials/alloy/01.webp", "https://cdn-test.yustream.cn/materials/alloy/01.webp")
    second = Asset("materials/alloy/02.webp", "https://cdn-test.yustream.cn/materials/alloy/02.webp")

    assert deterministic_id(first, 1) == deterministic_id(first, 1)
    assert deterministic_sku_id(first, 1) == deterministic_sku_id(first, 1)
    assert deterministic_id(first, 1) != deterministic_id(second, 2)
    assert deterministic_sku_id(first, 1) != deterministic_sku_id(second, 2)
    assert len(deterministic_sku_id(first, 1)) == 13


def test_split_rows_are_canonical_requires_one_unversioned_url():
    asset = Asset(
        "materials/beads/alloy/01.webp",
        "https://cdn-test.yustream.cn/materials/beads/alloy/01.webp",
    )
    row = {
        "id": "alloy-01",
        "image_path": "beads/alloy/01.webp",
        "image_url": asset.url,
        "image_urls_json": f'["{asset.url}"]',
    }
    assert split_rows_are_canonical([row], [asset]) is True

    row["image_url"] = f"{asset.url}?v=1"
    row["image_urls_json"] = f'["{asset.url}?v=1"]'
    assert split_rows_are_canonical([row], [asset]) is False


@pytest.mark.parametrize(
    ("app_env", "database"),
    [("production", "yujian"), ("test", "yujian"), ("production", "yujian_test")],
)
def test_split_rejects_non_test_runtime(app_env, database):
    with pytest.raises(SystemExit, match="Refusing non-test split"):
        validate_runtime(app_env, database)


def test_split_accepts_exact_test_runtime():
    validate_runtime("test", "yujian_test")
