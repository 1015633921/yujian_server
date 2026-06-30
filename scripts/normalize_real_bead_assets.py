from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class BeadSeries:
    slug: str
    source_parts: tuple[str, ...]


SERIES = (
    BeadSeries("green-phantom", ("绿幽灵抠图", "WPS图片批量处理")),
    BeadSeries("red-phantom", ("红幽灵抠图", "WPS图片批量处理")),
    BeadSeries("colorful-phantom", ("彩幽灵抠图", "WPS图片批量处理")),
    BeadSeries("mantianxing", ("满天星抠图", "WPS图片批量处理")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize real bead cutouts to a consistent transparent square canvas."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path.home() / "Pictures" / "水晶珠子",
    )
    parser.add_argument("--outputs-root", type=Path, default=ROOT / "outputs")
    parser.add_argument("--app-root", type=Path, default=ROOT / "static" / "materials" / "beads" / "real")
    parser.add_argument("--series", default="green-phantom,red-phantom,colorful-phantom")
    parser.add_argument("--app-size", type=int, default=512)
    parser.add_argument("--archive-size", type=int, default=1024)
    parser.add_argument("--target-fill", type=float, default=0.99)
    parser.add_argument("--edge-contract", type=float, default=0.07)
    parser.add_argument("--feather", type=float, default=0.7)
    parser.add_argument("--alpha-threshold", type=int, default=10)
    parser.add_argument("--white-threshold", type=int, default=244)
    parser.add_argument("--chroma-threshold", type=int, default=10)
    parser.add_argument("--subject-padding", type=float, default=0.08)
    parser.add_argument("--quality", type=int, default=92)
    return parser.parse_args()


def selected_series(value: str) -> list[BeadSeries]:
    wanted = {item.strip() for item in value.split(",") if item.strip()}
    if not wanted or "all" in wanted:
        return list(SERIES)
    by_slug = {item.slug: item for item in SERIES}
    unknown = sorted(wanted - set(by_slug))
    if unknown:
        raise SystemExit(f"Unknown series: {', '.join(unknown)}")
    return [by_slug[slug] for slug in wanted]


def list_sources(source_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.png", "*.webp", "*.jpg", "*.jpeg"):
        files.extend(source_dir.glob(pattern))
    return sorted(files)


def alpha_bbox(image: Image.Image, alpha_threshold: int) -> tuple[int, int, int, int] | None:
    alpha = image.getchannel("A")
    mask = alpha.point(lambda value: 255 if value > alpha_threshold else 0)
    return mask.getbbox()


def fallback_content_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    rgb = image.convert("RGB")
    bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    diff = ImageChops.difference(rgb, bg).convert("L")
    mask = diff.point(lambda value: 255 if value > 12 else 0)
    return mask.getbbox()


def color_subject_bbox(
    image: Image.Image,
    alpha_threshold: int,
    white_threshold: int,
    chroma_threshold: int,
) -> tuple[int, int, int, int] | None:
    rgba = image.convert("RGBA")
    red, green, blue, alpha = rgba.split()
    alpha_mask = alpha.point(lambda value: 255 if value > alpha_threshold else 0)
    max_rgb = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    min_rgb = ImageChops.darker(ImageChops.darker(red, green), blue)
    chroma = ImageChops.subtract(max_rgb, min_rgb)
    colored = chroma.point(lambda value: 255 if value > chroma_threshold else 0)
    dark = min_rgb.point(lambda value: 255 if value < white_threshold else 0)
    content = ImageChops.multiply(alpha_mask, ImageChops.lighter(colored, dark))
    return content.getbbox()


def expand_bbox(
    bbox: tuple[int, int, int, int],
    image_size: tuple[int, int],
    padding_ratio: float,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = bbox
    side = max(right - left, bottom - top)
    padding = round(side * padding_ratio)
    return (
        max(0, left - padding),
        max(0, top - padding),
        min(image_size[0], right + padding),
        min(image_size[1], bottom + padding),
    )


def square_source_box(
    bbox: tuple[int, int, int, int],
    image_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    left, top, right, bottom = bbox
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    side = max(right - left, bottom - top)
    box_left = round(center_x - side / 2)
    box_top = round(center_y - side / 2)
    box_right = box_left + side
    box_bottom = box_top + side
    shift_x = min(0, box_left) + max(0, box_right - image_size[0])
    shift_y = min(0, box_top) + max(0, box_bottom - image_size[1])
    box_left -= shift_x
    box_right -= shift_x
    box_top -= shift_y
    box_bottom -= shift_y
    return (
        max(0, box_left),
        max(0, box_top),
        min(image_size[0], box_right),
        min(image_size[1], box_bottom),
    )


def square_crop_subject(
    image: Image.Image,
    bbox: tuple[int, int, int, int],
    alpha_threshold: int,
    edge_contract: float,
    feather: float,
) -> Image.Image:
    source_box = square_source_box(bbox, image.size)
    crop = image.crop(source_box)
    side = max(crop.width, crop.height)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(crop, ((side - crop.width) // 2, (side - crop.height) // 2))

    alpha = square.getchannel("A").point(lambda value: 255 if value > alpha_threshold else 0)
    circle = Image.new("L", (side, side), 0)
    draw = ImageDraw.Draw(circle)
    inset = side * edge_contract
    draw.ellipse((inset, inset, side - inset, side - inset), fill=255)
    if feather > 0:
        circle = circle.filter(ImageFilter.GaussianBlur(feather))
    square.putalpha(ImageChops.multiply(alpha, circle))

    trimmed = alpha_bbox(square, alpha_threshold)
    if not trimmed:
        raise ValueError("empty bead after circular trim")
    return square.crop(trimmed)


def fit_to_canvas(subject: Image.Image, size: int, target_fill: float) -> Image.Image:
    max_side = max(1, round(size * target_fill))
    scale = max_side / max(1, max(subject.width, subject.height))
    bead = subject.resize(
        (
            max(1, round(subject.width * scale)),
            max(1, round(subject.height * scale)),
        ),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(bead, ((size - bead.width) // 2, (size - bead.height) // 2))
    return canvas


def normalize_one(
    source: Path,
    size: int,
    target_fill: float,
    alpha_threshold: int,
    white_threshold: int,
    chroma_threshold: int,
    subject_padding: float,
    edge_contract: float,
    feather: float,
) -> tuple[Image.Image, dict[str, object]]:
    image = ImageOps.exif_transpose(Image.open(source)).convert("RGBA")
    bbox = (
        color_subject_bbox(
            image,
            alpha_threshold,
            white_threshold=white_threshold,
            chroma_threshold=chroma_threshold,
        )
        or alpha_bbox(image, alpha_threshold)
        or fallback_content_bbox(image)
    )
    if not bbox:
        raise ValueError(f"no subject found: {source}")
    bbox = expand_bbox(bbox, image.size, subject_padding)
    subject = square_crop_subject(image, bbox, alpha_threshold, edge_contract, feather)
    output = fit_to_canvas(subject, size, target_fill)
    out_bbox = alpha_bbox(output, alpha_threshold)
    coverage = 0.0
    if out_bbox:
        coverage = max(out_bbox[2] - out_bbox[0], out_bbox[3] - out_bbox[1]) / size
    return output, {
        "source": str(source),
        "source_size": image.size,
        "source_bbox": bbox,
        "subject_size": subject.size,
        "output_coverage": round(coverage, 4),
    }


def save_contact_sheet(paths: list[Path], destination: Path) -> None:
    thumb = 150
    label = 28
    columns = min(6, max(1, len(paths)))
    rows = math.ceil(len(paths) / columns)
    sheet = Image.new("RGB", (columns * thumb, rows * (thumb * 2 + label)), "#f5f0e8")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGBA")
        image.thumbnail((thumb - 10, thumb - 10), Image.Resampling.LANCZOS)
        x = (index % columns) * thumb
        y = (index // columns) * (thumb * 2 + label)
        for offset, bg in enumerate(("#faf8f3", "#2b2b2b")):
            cell = Image.new("RGB", (thumb, thumb), bg)
            cell.paste(image, ((thumb - image.width) // 2, (thumb - image.height) // 2), image)
            sheet.paste(cell, (x, y + offset * thumb))
        draw.text((x + 8, y + thumb * 2 + 6), path.stem[-2:], fill="#191714")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=92)


def process_series(series: BeadSeries, args: argparse.Namespace) -> list[dict[str, object]]:
    source_dir = args.source_root.joinpath(*series.source_parts)
    files = list_sources(source_dir)
    if not files:
        raise SystemExit(f"No source images found: {source_dir}")

    output_dir = args.outputs_root / f"{series.slug}-normalized-assets"
    archive_png_dir = output_dir / "png-transparent"
    archive_webp_dir = output_dir / "webp-transparent"
    app_dir = args.app_root / series.slug
    archive_png_dir.mkdir(parents=True, exist_ok=True)
    archive_webp_dir.mkdir(parents=True, exist_ok=True)
    app_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, object]] = []
    app_paths: list[Path] = []
    for index, source in enumerate(files, start=1):
        stem = f"{series.slug}-{index:02d}"
        archive_image, meta = normalize_one(
            source,
            args.archive_size,
            args.target_fill,
            args.alpha_threshold,
            args.white_threshold,
            args.chroma_threshold,
            args.subject_padding,
            args.edge_contract,
            args.feather,
        )
        app_image = archive_image.resize((args.app_size, args.app_size), Image.Resampling.LANCZOS)
        archive_png = archive_png_dir / f"{stem}.png"
        archive_webp = archive_webp_dir / f"{stem}.webp"
        app_webp = app_dir / f"{stem}.webp"
        archive_image.save(archive_png, "PNG", optimize=True)
        archive_image.save(archive_webp, "WEBP", quality=args.quality, method=6)
        app_image.save(app_webp, "WEBP", quality=args.quality, method=6)
        app_paths.append(app_webp)
        manifest.append(
            {
                "index": index,
                "app_webp": str(app_webp),
                "archive_png": str(archive_png),
                "archive_webp": str(archive_webp),
                **meta,
            }
        )
        print(f"{stem} coverage={meta['output_coverage']} <- {source.name}", flush=True)

    (output_dir / "normalized-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    save_contact_sheet(app_paths, output_dir / "_normalized-contact-sheet.jpg")
    return manifest


def main() -> None:
    args = parse_args()
    all_rows: list[dict[str, object]] = []
    for series in selected_series(args.series):
        all_rows.extend(process_series(series, args))
    print(f"processed={len(all_rows)} target_fill={args.target_fill}")


if __name__ == "__main__":
    main()
