from __future__ import annotations

import json

import pytest
from PIL import Image, ImageDraw

from scripts.import_accessory_varieties_to_test import (
    load_catalog_manifest,
    object_key,
    split_display_and_gallery_urls,
)
from scripts.process_grouped_accessory_assets import (
    trim_external_support_spikes,
)


def test_grouped_manifest_requires_exactly_two_images_and_unique_varieties(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "category": "隔珠",
                    "name": "测试隔珠",
                    "material_code": "accessory_test_01",
                    "sources": ["front.png", "side.png"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rows = load_catalog_manifest(manifest)

    assert rows[0]["top"] == "accessory"
    assert rows[0]["sources"] == ["front.png", "side.png"]

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload[0]["sources"] = ["front.png"]
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit, match="exactly two"):
        load_catalog_manifest(manifest)


def test_support_spike_trim_keeps_body_and_hole_but_removes_fixture_line(tmp_path):
    source = tmp_path / "source.png"
    prepared = tmp_path / "prepared.png"
    image = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.line((120, 10, 120, 230), fill=(180, 180, 180, 255), width=3)
    draw.ellipse((55, 70, 185, 170), fill=(160, 165, 170, 255))
    draw.ellipse((100, 100, 140, 140), fill=(0, 0, 0, 0))
    image.save(source)

    keep = trim_external_support_spikes(source, prepared, 8)

    with Image.open(prepared) as result:
        alpha = result.convert("RGBA").getchannel("A")
        bbox = alpha.getbbox()
        assert bbox is not None
        assert bbox[1] > 10
        assert bbox[3] < 230
        assert alpha.getpixel((120, 120)) == 0
        assert alpha.getpixel((80, 120)) > 0
    assert keep[1] > 10
    assert keep[3] < 230


def test_accessory_object_keys_are_content_hashed_and_variety_scoped(tmp_path):
    first = tmp_path / "first.webp"
    second = tmp_path / "second.webp"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    first_key = object_key("materials/accessories/test", "accessory_test_01", 1, first)
    second_key = object_key("materials/accessories/test", "accessory_test_01", 2, second)

    assert first_key.startswith("materials/accessories/test/accessory_test_01/01-")
    assert second_key.startswith("materials/accessories/test/accessory_test_01/02-")
    assert first_key != second_key


def test_accessory_primary_image_is_not_part_of_random_gallery():
    primary, gallery = split_display_and_gallery_urls(
        [
            "https://cdn-test.example/materials/accessory/main.webp",
            "https://cdn-test.example/materials/accessory/side.webp",
        ]
    )

    assert primary.endswith("/main.webp")
    assert gallery == ["https://cdn-test.example/materials/accessory/side.webp"]
