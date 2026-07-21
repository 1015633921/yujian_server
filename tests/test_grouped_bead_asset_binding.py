from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from scripts.bind_grouped_bead_assets_to_test import (
    load_asset_groups,
    material_image_path,
    public_url,
)


def args_for(tmp_path: Path, expected_groups: int = 1) -> Namespace:
    return Namespace(
        manifest_root=tmp_path / "manifests",
        assets_root=None,
        cos_prefix="materials/beads/20260716-grouped",
        cdn_base_url="https://cdn-test.yustream.cn",
        operation_id="20260716_120000",
        url_version="",
        expected_groups=expected_groups,
        assets_per_group=9,
    )


def write_group(tmp_path: Path, *, count: int = 9) -> None:
    manifest_dir = tmp_path / "manifests" / "silver"
    asset_dir = tmp_path / "assets"
    manifest_dir.mkdir(parents=True)
    asset_dir.mkdir(parents=True)
    rows = []
    for index in range(1, count + 1):
        asset = asset_dir / f"silver-{index:02d}.webp"
        asset.write_bytes(f"asset-{index}".encode())
        rows.append(
            {
                "top": "bead",
                "final_series": "银发晶",
                "final_category": "发晶",
                "material_code": "mat_4ffa5cb3f1f4c2a1",
                "slug": "silver-rutilated-quartz",
                "index": index,
                "app_webp": str(asset),
                "warning_text": "",
            }
        )
    (manifest_dir / "manifest.json").write_text(
        json.dumps(rows, ensure_ascii=False), encoding="utf-8"
    )


def test_load_asset_groups_requires_exact_nine_asset_mapping(tmp_path):
    write_group(tmp_path)
    groups = load_asset_groups(args_for(tmp_path))

    assert len(groups) == 1
    assert groups[0].series == "银发晶"
    assert groups[0].category == "发晶"
    assert groups[0].material_code == "mat_4ffa5cb3f1f4c2a1"
    assert len(groups[0].files) == 9
    assert len(set(groups[0].keys)) == 9


def test_load_asset_groups_fails_closed_on_incomplete_group(tmp_path):
    write_group(tmp_path, count=8)

    with pytest.raises(SystemExit, match="Expected 9 assets"):
        load_asset_groups(args_for(tmp_path))


def test_public_path_helpers_keep_test_cdn_and_material_prefix():
    url = public_url(
        "https://cdn-test.yustream.cn",
        "materials/beads/20260716-grouped/code/01.webp",
    )
    assert url == (
        "https://cdn-test.yustream.cn/materials/beads/20260716-grouped/"
        "code/01.webp"
    )
    assert public_url(
        "https://cdn-test.yustream.cn",
        "materials/beads/20260716-grouped/code/01.webp",
        "20260716_120000",
    ).endswith("?v=20260716_120000")
    assert material_image_path("materials/beads/20260716-grouped/code/01.webp") == (
        "beads/20260716-grouped/code/01.webp"
    )
