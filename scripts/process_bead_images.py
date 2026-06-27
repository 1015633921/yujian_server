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
    parser.add_argument("--transparent", action="store_true", help="将浅色拍摄背景处理为透明背景")
    parser.add_argument("--white-background", action="store_true", help="使用纯白背景，只保留珠子主体")
    parser.add_argument("--preserve-filename", action="store_true", help="保留源文件名，便于原位替换")
    parser.add_argument("--circle-mask", action="store_true", help="keep only the round bead body")
    parser.add_argument("--fixed-crop", action="store_true", help="use a fixed crop box for same-layout source images")
    parser.add_argument("--crop-left", type=float, default=0.12, help="fixed crop left ratio")
    parser.add_argument("--crop-top", type=float, default=0.04, help="fixed crop top ratio")
    parser.add_argument("--crop-size", type=float, default=0.76, help="fixed square crop size ratio")
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
        output_name = f"{path.stem}.png" if args.preserve_filename else f"{slug_from_name(path.stem)}.png"
        output_path = output_dir / output_name
        crop_bead_image(
            path,
            output_path,
            args.size,
            transparent=args.transparent,
            white_background=args.white_background,
            circle_mask=args.circle_mask,
            fixed_crop=args.fixed_crop,
            crop_left=args.crop_left,
            crop_top=args.crop_top,
            crop_size=args.crop_size,
        )

    print(f"processed={len(files)} output={output_dir.resolve()}")


def crop_bead_image(
    source: Path,
    output: Path,
    size: int,
    transparent: bool = False,
    white_background: bool = False,
    circle_mask: bool = False,
    fixed_crop: bool = False,
    crop_left: float = 0.12,
    crop_top: float = 0.04,
    crop_size: float = 0.76,
) -> None:
    image = Image.open(source).convert("RGB")
    width, height = image.size

    if fixed_crop:
        side = int(min(width, height) * crop_size)
        left = int(width * crop_left)
        top = int(height * crop_top)
        right = min(width, left + side)
        bottom = min(height, top + side)
        cropped = image.crop((left, top, right, bottom))
    else:
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
    if transparent:
        cropped = remove_light_background(cropped)
    if circle_mask:
        cropped = apply_soft_circle_mask(cropped)

    background = (255, 255, 255, 255) if white_background else (255, 255, 255, 0)
    canvas = Image.new("RGBA", (size, size), background)
    cropped_rgba = cropped.convert("RGBA")
    x = (size - cropped_rgba.width) // 2
    y = (size - cropped_rgba.height) // 2
    canvas.alpha_composite(cropped_rgba, (x, y))
    canvas.save(output)


def apply_soft_circle_mask(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    center_x = (width - 1) / 2
    center_y = (height - 1) / 2
    radius = min(width, height) * 0.425
    feather = max(2.0, min(width, height) * 0.018)

    for y in range(height):
        for x in range(width):
            r, g, b, alpha = pixels[x, y]
            distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
            if distance >= radius:
                alpha = 0
            elif distance > radius - feather:
                alpha = int(alpha * (radius - distance) / feather)
            pixels[x, y] = (r, g, b, max(0, min(255, alpha)))

    return rgba


def remove_light_background(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()

    corners = [
        pixels[0, 0],
        pixels[width - 1, 0],
        pixels[0, height - 1],
        pixels[width - 1, height - 1],
    ]
    bg = tuple(sum(color[i] for color in corners) // len(corners) for i in range(3))

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            distance = ((r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2) ** 0.5
            brightness = (r + g + b) / 3
            # Bright, background-like pixels become transparent; bead highlights stay visible
            # because they differ more strongly from the sampled corner color.
            if brightness > 210 and distance < 42:
                alpha = 0
            elif brightness > 190 and distance < 70:
                alpha = int(min(255, max(0, (distance - 28) * 5)))
            else:
                alpha = a
            pixels[x, y] = (r, g, b, alpha)

    return rgba


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
