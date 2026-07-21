from __future__ import annotations

from argparse import Namespace

import pytest
from PIL import Image, ImageDraw

from scripts.process_accessory_assets import normalize_one


def processing_args(*, require_source_alpha: bool = True) -> Namespace:
    return Namespace(
        size=512,
        target_fill=0.985,
        alpha_threshold=8,
        background_threshold=18,
        edge_padding=2,
        max_bytes=200_000,
        quality=92,
        require_source_alpha=require_source_alpha,
    )


def test_normalizer_preserves_supplied_alpha_and_transparent_holes(tmp_path):
    source = tmp_path / "cutout.png"
    output = tmp_path / "cutout.webp"
    image = Image.new("RGBA", (200, 160), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((60, 40, 140, 120), fill=(160, 165, 170, 255))
    draw.ellipse((85, 65, 115, 95), fill=(0, 0, 0, 0))
    image.save(source)

    metrics = normalize_one(source, output, processing_args())

    with Image.open(output) as normalized:
        alpha = normalized.convert("RGBA").getchannel("A")
        assert normalized.size == (512, 512)
        assert alpha.getbbox() is not None
        assert alpha.getpixel((256, 256)) == 0
    assert metrics["mask_mode"] == "source_alpha"
    assert 0.98 <= metrics["fill_ratio"] <= 0.995
    assert abs(metrics["center_offset_x"]) <= 1
    assert abs(metrics["center_offset_y"]) <= 1


def test_normalizer_rejects_opaque_source_in_cutout_only_mode(tmp_path):
    source = tmp_path / "opaque.jpg"
    output = tmp_path / "opaque.webp"
    Image.new("RGB", (100, 100), "white").save(source)

    with pytest.raises(ValueError, match="opaque_source"):
        normalize_one(source, output, processing_args())
