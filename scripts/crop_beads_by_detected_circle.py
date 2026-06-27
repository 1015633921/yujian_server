from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect each bead's real circular edge and export a tightly cropped transparent PNG."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, default=640)
    parser.add_argument("--edge-contract", type=float, default=5.0)
    parser.add_argument("--feather", type=float, default=1.2)
    args = parser.parse_args()

    files = sorted(args.source.glob("*.png"))
    if not files:
        raise SystemExit(f"No PNG files found in {args.source}")
    args.output.mkdir(parents=True, exist_ok=True)

    measurements = []
    for path in files:
        center_x, center_y, radius = detect_circle(path)
        export_circle(
            path,
            args.output / path.name,
            center_x,
            center_y,
            radius,
            args.size,
            args.edge_contract,
            args.feather,
        )
        measurements.append((path.name, round(center_x, 1), round(center_y, 1), round(radius, 1)))

    print(
        f"processed={len(files)} radius_min={min(item[3] for item in measurements)} "
        f"radius_max={max(item[3] for item in measurements)} output={args.output.resolve()}"
    )


def detect_circle(path: Path) -> tuple[float, float, float]:
    rgb = np.array(Image.open(path).convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (9, 9), 2)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=200,
        param1=60,
        param2=40,
        minRadius=int(min(gray.shape) * 0.24),
        maxRadius=int(min(gray.shape) * 0.46),
    )
    if circles is None:
        raise ValueError(f"Cannot detect bead circle: {path}")

    height, width = gray.shape
    target_radius = min(width, height) * 0.35
    circle = min(
        circles[0],
        key=lambda item: (
            math.hypot(item[0] - width / 2, item[1] - height / 2)
            + abs(item[2] - target_radius) * 0.25
        ),
    )
    return float(circle[0]), float(circle[1]), float(circle[2])


def export_circle(
    source: Path,
    output: Path,
    center_x: float,
    center_y: float,
    radius: float,
    output_size: int,
    edge_contract: float,
    feather: float,
) -> None:
    image = Image.open(source).convert("RGBA")
    visible_radius = max(1.0, radius - edge_contract)
    margin = max(2, math.ceil(feather * 3))
    crop_radius = visible_radius + margin
    crop_box = (
        math.floor(center_x - crop_radius),
        math.floor(center_y - crop_radius),
        math.ceil(center_x + crop_radius),
        math.ceil(center_y + crop_radius),
    )
    cropped = image.crop(crop_box)

    local_center_x = center_x - crop_box[0]
    local_center_y = center_y - crop_box[1]
    mask = Image.new("L", cropped.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse(
        (
            local_center_x - visible_radius,
            local_center_y - visible_radius,
            local_center_x + visible_radius,
            local_center_y + visible_radius,
        ),
        fill=255,
    )
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    cropped.putalpha(mask)

    alpha_bbox = cropped.getchannel("A").getbbox()
    if alpha_bbox is None:
        raise ValueError(f"Empty alpha result: {source}")
    cropped = cropped.crop(alpha_bbox)
    cropped = cropped.resize((output_size, output_size), Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(output, "PNG", optimize=True)


def strip_number(value: str) -> str:
    return re.sub(r"^\d+[_\-\s]*", "", value).strip()


if __name__ == "__main__":
    main()
