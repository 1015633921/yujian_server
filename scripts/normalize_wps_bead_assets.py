from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize WPS white-background bead cutouts for app assets.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--archive-output", type=Path, required=True)
    parser.add_argument("--app-output", type=Path, required=True)
    parser.add_argument("--prefix", default="bead")
    parser.add_argument("--archive-size", type=int, default=1024)
    parser.add_argument("--app-size", type=int, default=512)
    parser.add_argument("--white-threshold", type=int, default=246)
    parser.add_argument("--padding", type=float, default=0.10)
    parser.add_argument("--target-fill", type=float, default=0.86)
    return parser.parse_args()


def list_images(source: Path) -> list[Path]:
    return sorted(
        path
        for path in source.iterdir()
        if path.is_file() and not path.name.startswith("_") and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def subject_bbox(image: Image.Image, threshold: int) -> tuple[int, int, int, int]:
    rgb = np.asarray(image.convert("RGB"))
    mask = np.min(rgb, axis=2) < threshold
    ys, xs = np.where(mask)
    if not len(xs) or not len(ys):
        raise ValueError("Cannot find non-white bead subject")
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def expand_bbox(
    bbox: tuple[int, int, int, int],
    image_size: tuple[int, int],
    padding: float,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = bbox
    width = right - left
    height = bottom - top
    pad = round(max(width, height) * padding)
    return (
        max(0, left - pad),
        max(0, top - pad),
        min(image_size[0], right + pad),
        min(image_size[1], bottom + pad),
    )


def normalize_image(
    source: Path,
    output_size: int,
    threshold: int,
    padding: float,
    target_fill: float,
) -> tuple[Image.Image, dict[str, object]]:
    image = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
    bbox = subject_bbox(image, threshold)
    crop_box = expand_bbox(bbox, image.size, padding)
    crop = image.crop(crop_box)
    max_subject_side = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
    crop_scale = output_size * target_fill / max_subject_side
    resized_size = (
        max(1, round(crop.width * crop_scale)),
        max(1, round(crop.height * crop_scale)),
    )
    crop = crop.resize(resized_size, Image.Resampling.LANCZOS)
    crop.thumbnail((output_size, output_size), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (output_size, output_size), "white")
    canvas.paste(crop, ((output_size - crop.width) // 2, (output_size - crop.height) // 2))

    center_x = (bbox[0] + bbox[2]) / 2 / image.width
    center_y = (bbox[1] + bbox[3]) / 2 / image.height
    metrics = {
        "source": source.name,
        "source_width": image.width,
        "source_height": image.height,
        "bbox_left": bbox[0],
        "bbox_top": bbox[1],
        "bbox_right": bbox[2],
        "bbox_bottom": bbox[3],
        "center_x_pct": round(center_x, 4),
        "center_y_pct": round(center_y, 4),
        "offset_x_pct": round(center_x - 0.5, 4),
        "offset_y_pct": round(center_y - 0.5, 4),
        "subject_width": bbox[2] - bbox[0],
        "subject_height": bbox[3] - bbox[1],
    }
    return canvas, metrics


def build_contact_sheet(paths: list[Path], destination: Path) -> None:
    thumb = 170
    label_height = 28
    columns = min(6, max(1, len(paths)))
    rows = math.ceil(len(paths) / columns)
    sheet = Image.new("RGB", (columns * thumb, rows * (thumb + label_height)), "#f7f4ee")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths, start=1):
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb - 10, thumb - 10), Image.Resampling.LANCZOS)
        x0 = ((index - 1) % columns) * thumb
        y0 = ((index - 1) // columns) * (thumb + label_height)
        cell = Image.new("RGB", (thumb, thumb), "white")
        cell.paste(image, ((thumb - image.width) // 2, (thumb - image.height) // 2))
        sheet.paste(cell, (x0, y0))
        draw.text((x0 + 8, y0 + thumb + 6), f"{index:02d}", fill="#171411")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=92)


def write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with (path / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    files = list_images(args.source)
    if not files:
        raise SystemExit(f"No images found in {args.source}")

    archive_png_dir = args.archive_output / "png"
    archive_webp_dir = args.archive_output / "webp"
    archive_png_dir.mkdir(parents=True, exist_ok=True)
    archive_webp_dir.mkdir(parents=True, exist_ok=True)
    args.app_output.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, object]] = []
    app_paths: list[Path] = []
    for index, source in enumerate(files, start=1):
        stem = f"{args.prefix}-{index:02d}"
        archive_image, metrics = normalize_image(
            source,
            args.archive_size,
            args.white_threshold,
            args.padding,
            args.target_fill,
        )
        archive_png = archive_png_dir / f"{stem}.png"
        archive_webp = archive_webp_dir / f"{stem}.webp"
        archive_image.save(archive_png, "PNG", optimize=True)
        archive_image.save(archive_webp, "WEBP", quality=94, method=6)

        app_image = archive_image.resize((args.app_size, args.app_size), Image.Resampling.LANCZOS)
        app_path = args.app_output / f"{stem}.webp"
        app_image.save(app_path, "WEBP", quality=92, method=6)
        app_paths.append(app_path)

        manifest.append(
            {
                "index": index,
                "archive_png": str(archive_png),
                "archive_webp": str(archive_webp),
                "app_webp": str(app_path),
                **metrics,
            }
        )
        print(f"[{index:02d}/{len(files):02d}] {source.name} -> {app_path.name}")

    write_manifest(args.archive_output, manifest)
    build_contact_sheet(app_paths, args.archive_output / "_contact-sheet.jpg")
    print(f"archive_output={args.archive_output.resolve()}")
    print(f"app_output={args.app_output.resolve()}")


if __name__ == "__main__":
    main()
