from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent.parent
SERIES = ("green-phantom", "red-phantom", "colorful-phantom")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate phantom bead assets with real transparent edges."
    )
    parser.add_argument("--outputs-root", type=Path, default=ROOT / "outputs")
    parser.add_argument("--app-root", type=Path, default=ROOT / "static" / "materials" / "beads" / "real")
    parser.add_argument("--app-size", type=int, default=512)
    parser.add_argument("--archive-size", type=int, default=1024)
    parser.add_argument("--target-fill", type=float, default=0.88)
    parser.add_argument("--edge-contract", type=float, default=0.038)
    parser.add_argument("--feather", type=float, default=1.6)
    parser.add_argument("--quality", type=int, default=92)
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
      return list(csv.DictReader(handle))


def expand_box(
    left: int,
    top: int,
    right: int,
    bottom: int,
    image_size: tuple[int, int],
    padding: float,
) -> tuple[int, int, int, int]:
    width = right - left
    height = bottom - top
    pad = round(max(width, height) * padding)
    return (
        max(0, left - pad),
        max(0, top - pad),
        min(image_size[0], right + pad),
        min(image_size[1], bottom + pad),
    )


def transparent_bead(
    source: Path,
    row: dict[str, str],
    size: int,
    target_fill: float,
    edge_contract: float,
    feather: float,
) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(source)).convert("RGBA")
    left = int(float(row["bbox_left"]))
    top = int(float(row["bbox_top"]))
    right = int(float(row["bbox_right"]))
    bottom = int(float(row["bbox_bottom"]))
    subject_side = max(right - left, bottom - top)
    crop_box = expand_box(left, top, right, bottom, image.size, padding=0.12)
    crop = image.crop(crop_box)

    cx = (left + right) / 2 - crop_box[0]
    cy = (top + bottom) / 2 - crop_box[1]
    radius = subject_side / 2 * (1 - edge_contract)

    mask = Image.new("L", crop.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=255)
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(max(0.3, feather)))
    crop.putalpha(mask)

    alpha_box = crop.getchannel("A").getbbox()
    if alpha_box is None:
        raise ValueError(f"Empty bead alpha: {source}")
    crop = crop.crop(alpha_box)
    crop.thumbnail(
        (round(size * target_fill), round(size * target_fill)),
        Image.Resampling.LANCZOS,
    )

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(crop, ((size - crop.width) // 2, (size - crop.height) // 2))
    return canvas


def save_contact_sheet(paths: list[Path], destination: Path) -> None:
    thumb = 150
    label = 26
    columns = min(6, max(1, len(paths)))
    rows = math.ceil(len(paths) / columns)
    sheet = Image.new("RGB", (columns * thumb, rows * (thumb * 2 + label)), "#f6f3ed")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGBA")
        image.thumbnail((thumb - 12, thumb - 12), Image.Resampling.LANCZOS)
        x = (index % columns) * thumb
        y = (index // columns) * (thumb * 2 + label)
        for offset, bg in enumerate(("#f7f7f4", "#292929")):
            cell = Image.new("RGB", (thumb, thumb), bg)
            cell.paste(image, ((thumb - image.width) // 2, (thumb - image.height) // 2), image)
            sheet.paste(cell, (x, y + offset * thumb))
        draw.text((x + 8, y + thumb * 2 + 5), path.stem[-2:], fill="#171411")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=92)


def process_series(slug: str, args: argparse.Namespace) -> list[dict[str, object]]:
    output_dir = args.outputs_root / f"{slug}-final-assets"
    source_dir = args.outputs_root / f"{slug}-wps-cutout-source"
    archive_png_dir = output_dir / "png-transparent"
    archive_webp_dir = output_dir / "webp-transparent"
    app_dir = args.app_root / slug
    archive_png_dir.mkdir(parents=True, exist_ok=True)
    archive_webp_dir.mkdir(parents=True, exist_ok=True)
    app_dir.mkdir(parents=True, exist_ok=True)

    rows = read_manifest(output_dir / "manifest.csv")
    written: list[Path] = []
    manifest: list[dict[str, object]] = []
    for row in rows:
        index = int(row["index"])
        stem = f"{slug}-{index:02d}"
        source = source_dir / row["source"]
        archive_image = transparent_bead(
            source,
            row,
            args.archive_size,
            args.target_fill,
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
        written.append(app_webp)
        manifest.append(
            {
                "index": index,
                "source": str(source),
                "archive_png": str(archive_png),
                "archive_webp": str(archive_webp),
                "app_webp": str(app_webp),
                "edge_contract": args.edge_contract,
                "feather": args.feather,
            }
        )
        print(f"{stem} <- {source.name}")

    (output_dir / "transparent-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    save_contact_sheet(written, output_dir / "_transparent-contact-sheet.jpg")
    return manifest


def main() -> None:
    args = parse_args()
    all_rows: list[dict[str, object]] = []
    for slug in SERIES:
        all_rows.extend(process_series(slug, args))
    print(f"processed={len(all_rows)}")


if __name__ == "__main__":
    main()
