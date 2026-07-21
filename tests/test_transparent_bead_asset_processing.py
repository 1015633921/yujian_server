from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from scripts.normalize_transparent_bead_assets import (
    fit_on_canvas,
    material_code_for,
    parent_category_for,
)


def test_fit_on_canvas_uses_subject_bounds_for_fill_and_centering():
    image = Image.new("RGBA", (240, 180), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((80, 50, 160, 130), fill=(130, 150, 160, 255))
    bbox = (80, 50, 161, 131)

    normalized = fit_on_canvas(image, bbox, 512, 0.985, 2)
    alpha = np.asarray(normalized.getchannel("A"), dtype=np.uint8)
    ys, xs = np.where(alpha > 8)

    fill = max(xs.max() - xs.min() + 1, ys.max() - ys.min() + 1) / 512
    center_x = (xs.min() + xs.max() + 1) / 2
    center_y = (ys.min() + ys.max() + 1) / 2
    assert 0.98 <= fill <= 0.995
    assert abs(center_x - 256) <= 1
    assert abs(center_y - 256) <= 1


def test_july_grouped_material_mappings_match_catalog_codes():
    assert material_code_for("银发晶") == "mat_4ffa5cb3f1f4c2a1"
    assert parent_category_for("银发晶") == "发晶"
    assert material_code_for("天河石") == "mat_9c46e803c52855b0"
    assert parent_category_for("天河石") == "天河石"
    assert material_code_for("魔鬼蓝") == "mat_dd0f228569f9284d"
    assert parent_category_for("魔鬼蓝") == "海蓝宝"
