from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageChops


DEFAULT_SOURCE_DIR = Path(r"C:\Users\10156\Pictures\水晶珠子\水晶珠子图片_已命名打包")
DEFAULT_OUTPUT_DIR = Path("generated/bead-thumbnails")


def main() -> None:
    parser = argparse.ArgumentParser(description="Crop bead product images for mini-program thumbnails.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_DIR, help="原始珠子图片目录")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR, help="缩略图输出目录")
    parser.add_argument("--size", type=int, default=640, help="输出缩略图尺寸")
    args = parser.parse_args()

    source_dir = args.source
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(
        path for path in source_dir.iterdir()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    if not files:
        raise SystemExit(f"No images found in {source_dir}")

    for path in files:
        output_path = output_dir / f"{slug_from_name(path.stem)}.png"
        crop_bead_image(path, output_path, args.size)

    print(f"processed={len(files)} output={output_dir.resolve()}")


def crop_bead_image(source: Path, output: Path, size: int) -> None:
    image = Image.open(source).convert("RGB")
    width, height = image.size

    # The source pack has the bead centered in the upper part and text at the bottom.
    # Cropping to the upper 78% removes the name label before auto-trimming the bead area.
    upper = image.crop((0, 0, width, int(height * 0.78)))
    bbox = find_non_background_bbox(upper)
    if bbox is None:
        bbox = (
            int(width * 0.14),
            int(height * 0.08),
            int(width * 0.86),
            int(height * 0.78),
        )

    left, top, right, bottom = pad_to_square(bbox, upper.size, padding_ratio=0.08)
    cropped = upper.crop((left, top, right, bottom))
    cropped.thumbnail((size, size), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    cropped_rgba = cropped.convert("RGBA")
    x = (size - cropped_rgba.width) // 2
    y = (size - cropped_rgba.height) // 2
    canvas.alpha_composite(cropped_rgba, (x, y))
    canvas.save(output)


def find_non_background_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    width, height = image.size
    # Use a corner-sampled background color, then trim regions that differ enough.
    corner = image.crop((0, 0, max(16, width // 12), max(16, height // 12)))
    background = corner.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
    bg = Image.new("RGB", image.size, background)
    diff = ImageChops.difference(image, bg).convert("L")
    mask = diff.point(lambda value: 255 if value > 16 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return None

    left, top, right, bottom = bbox
    # Ignore tiny specks and keep the dominant bead region.
    if (right - left) < width * 0.25 or (bottom - top) < height * 0.25:
        return None
    return left, top, right, bottom


def pad_to_square(
    bbox: tuple[int, int, int, int],
    bounds: tuple[int, int],
    padding_ratio: float,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = bbox
    width, height = bounds
    box_width = right - left
    box_height = bottom - top
    side = int(max(box_width, box_height) * (1 + padding_ratio * 2))
    center_x = (left + right) // 2
    center_y = (top + bottom) // 2
    left = center_x - side // 2
    top = center_y - side // 2
    right = left + side
    bottom = top + side

    if left < 0:
        right -= left
        left = 0
    if top < 0:
        bottom -= top
        top = 0
    if right > width:
        left -= right - width
        right = width
    if bottom > height:
        top -= bottom - height
        bottom = height

    return max(0, left), max(0, top), min(width, right), min(height, bottom)


def slug_from_name(name: str) -> str:
    clean = re.sub(r"^\d+[_-]*", "", name).strip()
    safe = re.sub(r"[^\w\u4e00-\u9fff]+", "-", clean, flags=re.UNICODE).strip("-")
    return safe or name


if __name__ == "__main__":
    main()
