from __future__ import annotations

import argparse
import json
import shutil
import sys
from statistics import median
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize reviewed accessory photos into app-ready transparent WebP assets."
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--app-root", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--target-fill", type=float, default=0.985)
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--background-threshold", type=int, default=18)
    parser.add_argument("--edge-padding", type=int, default=2)
    parser.add_argument("--max-bytes", type=int, default=200_000)
    parser.add_argument("--quality", type=int, default=92)
    parser.add_argument(
        "--require-source-alpha",
        action="store_true",
        help="Reject opaque source images instead of attempting background removal.",
    )
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit("Accessory manifest must be a JSON array.")
    required = {"source", "name", "material_code", "category", "top"}
    rows: list[dict[str, object]] = []
    seen_codes: set[str] = set()
    for raw in payload:
        if not isinstance(raw, dict):
            raise SystemExit("Accessory manifest rows must be JSON objects.")
        missing = sorted(key for key in required if not str(raw.get(key) or "").strip())
        if missing:
            raise SystemExit(f"Accessory manifest row is missing: {', '.join(missing)}")
        top = str(raw["top"]).strip().lower()
        if top not in {"accessory", "pendant"}:
            raise SystemExit(f"Unsupported accessory top: {top}")
        material_code = str(raw["material_code"]).strip()
        if material_code in seen_codes:
            raise SystemExit(f"Duplicate material_code: {material_code}")
        seen_codes.add(material_code)
        if str(raw.get("skip") or "").strip():
            continue
        rows.append(dict(raw))
    return rows


def safe_rmtree(path: Path) -> None:
    if not path.exists():
        return
    resolved = path.resolve()
    if resolved == ROOT or ROOT not in resolved.parents:
        raise SystemExit(f"Refusing to remove path outside workspace: {resolved}")
    shutil.rmtree(resolved)


def border_color(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    step = max(1, min(width, height) // 180)
    samples = []
    for x in range(0, width, step):
        samples.extend((rgb.getpixel((x, 0)), rgb.getpixel((x, height - 1))))
    for y in range(0, height, step):
        samples.extend((rgb.getpixel((0, y)), rgb.getpixel((width - 1, y))))
    return tuple(int(median(channel)) for channel in zip(*samples, strict=True))


def alpha_mask(image: Image.Image, threshold: int) -> Image.Image:
    background = Image.new("RGB", image.size, border_color(image))
    difference = ImageChops.difference(image.convert("RGB"), background)
    red, green, blue = difference.split()
    contrast = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    mask = contrast.point(lambda value: 255 if value > threshold else 0)
    # Remove isolated paper texture, then close small gaps in reflective metal.
    return (
        mask.filter(ImageFilter.MedianFilter(5))
        .filter(ImageFilter.MaxFilter(7))
        .filter(ImageFilter.MinFilter(7))
    )


def subject_search_box(image: Image.Image) -> tuple[int, int, int, int]:
    """Locate the photographed object before estimating its local background."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    blur_radius = max(10, min(width, height) // 28)
    difference = ImageChops.difference(rgb, rgb.filter(ImageFilter.GaussianBlur(blur_radius)))
    red, green, blue = difference.split()
    detail = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    saliency = detail.filter(ImageFilter.GaussianBlur(max(4, min(width, height) // 110)))

    margin_x = max(1, width // 20)
    margin_y = max(1, height // 20)
    inner = saliency.crop((margin_x, margin_y, width - margin_x, height - margin_y))
    pixels = inner.tobytes()
    peak_index = max(range(len(pixels)), key=pixels.__getitem__)
    peak_x = margin_x + peak_index % inner.width
    peak_y = margin_y + peak_index // inner.width

    search_width = min(width, max(280, round(width * 0.52)))
    search_height = min(height, max(280, round(height * 0.6)))
    left = max(0, min(width - search_width, round(peak_x - search_width / 2)))
    top = max(0, min(height - search_height, round(peak_y - search_height / 2)))
    return left, top, left + search_width, top + search_height


def normalize_one(
    source: Path,
    output: Path,
    args: argparse.Namespace,
    background_threshold: int | None = None,
) -> dict[str, object]:
    opened = ImageOps.exif_transpose(Image.open(source))
    image = opened.convert("RGBA")
    # The app output is 512px. Reducing source photos first keeps the masking
    # pass light enough for a full batch while preserving more than enough detail.
    image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    source_alpha = image.getchannel("A")
    has_source_alpha = source_alpha.getextrema()[0] < 255
    if args.require_source_alpha and not has_source_alpha:
        raise ValueError(f"opaque_source: {source}")

    if has_source_alpha:
        search_box = (0, 0, image.width, image.height)
        localized = image
        mask = source_alpha.point(lambda value: 255 if value > args.alpha_threshold else 0)
        mask_mode = "source_alpha"
    else:
        search_box = subject_search_box(image)
        localized = image.crop(search_box)
        mask = alpha_mask(localized, background_threshold or args.background_threshold)
        mask_mode = f"localized_border_color:{border_color(localized)}"
    bbox = mask.getbbox()
    if not bbox:
        raise ValueError(f"empty_subject: {source}")
    padding = max(args.edge_padding, int(max(bbox[2] - bbox[0], bbox[3] - bbox[1]) * 0.04))
    crop_box = (
        max(0, bbox[0] - padding),
        max(0, bbox[1] - padding),
        min(localized.width, bbox[2] + padding),
        min(localized.height, bbox[3] + padding),
    )
    cropped = localized.crop(crop_box)
    if has_source_alpha:
        # Preserve the supplied cutout, including translucent antialiased edges
        # and holes. Re-segmenting shiny metal would erase real reflections.
        cropped.putalpha(source_alpha.crop(crop_box))
    else:
        cropped_mask = mask.crop(crop_box).filter(ImageFilter.GaussianBlur(0.8))
        cropped.putalpha(cropped_mask)
    target_edge = max(1, round(args.size * args.target_fill))
    subject_width = bbox[2] - bbox[0]
    subject_height = bbox[3] - bbox[1]
    scale = target_edge / max(subject_width, subject_height)
    resized = cropped.resize(
        (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale))),
        Image.Resampling.LANCZOS,
    )
    subject_center_x = ((bbox[0] + bbox[2]) / 2 - crop_box[0]) * scale
    subject_center_y = ((bbox[1] + bbox[3]) / 2 - crop_box[1]) * scale
    paste_x = round(args.size / 2 - subject_center_x)
    paste_y = round(args.size / 2 - subject_center_y)
    canvas = Image.new("RGBA", (args.size, args.size), (0, 0, 0, 0))
    canvas.alpha_composite(resized, (paste_x, paste_y))
    canvas_bbox = canvas.getchannel("A").point(
        lambda value: 255 if value > args.alpha_threshold else 0
    ).getbbox()
    if canvas_bbox:
        offset_x = round(args.size / 2 - (canvas_bbox[0] + canvas_bbox[2]) / 2)
        offset_y = round(args.size / 2 - (canvas_bbox[1] + canvas_bbox[3]) / 2)
        if offset_x or offset_y:
            centered = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            centered.alpha_composite(canvas, (offset_x, offset_y))
            canvas = centered
    output.parent.mkdir(parents=True, exist_ok=True)
    quality = args.quality
    for candidate in (args.quality, 88, 84, 80, 76, 72):
        canvas.save(output, "WEBP", quality=candidate, method=6, alpha_quality=100, exact=True)
        quality = candidate
        if output.stat().st_size <= args.max_bytes:
            break
    final_mask = canvas.getchannel("A").point(lambda value: 255 if value > args.alpha_threshold else 0)
    final_bbox = final_mask.getbbox()
    if not final_bbox:
        raise ValueError(f"empty_output: {source}")
    fill_ratio = max(final_bbox[2] - final_bbox[0], final_bbox[3] - final_bbox[1]) / args.size
    return {
        "source_width": image.width,
        "source_height": image.height,
        "source_search_box": list(search_box),
        "source_bbox": [
            search_box[0] + bbox[0],
            search_box[1] + bbox[1],
            search_box[0] + bbox[2],
            search_box[1] + bbox[3],
        ],
        "mask_mode": mask_mode,
        "output_width": args.size,
        "output_height": args.size,
        "output_bbox": list(final_bbox),
        "fill_ratio": round(fill_ratio, 4),
        "center_offset_x": round((final_bbox[0] + final_bbox[2]) / 2 - args.size / 2, 2),
        "center_offset_y": round((final_bbox[1] + final_bbox[3]) / 2 - args.size / 2, 2),
        "file_size": output.stat().st_size,
        "quality": quality,
    }


def make_contact_sheet(rows: list[dict[str, object]], output: Path) -> None:
    columns = 6
    thumb = 126
    label_height = 34
    gap = 12
    row_count = (len(rows) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (columns * thumb + (columns + 1) * gap, row_count * (thumb * 2 + label_height) + (row_count + 1) * gap),
        "#eee9df",
    )
    from PIL import ImageDraw

    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        image = Image.open(str(row["app_webp"])).convert("RGBA")
        image.thumbnail((thumb - 10, thumb - 10), Image.Resampling.LANCZOS)
        x = gap + (index % columns) * (thumb + gap)
        y = gap + (index // columns) * (thumb * 2 + label_height + gap)
        for offset, background in enumerate(("#f8f7f2", "#242424")):
            cell = Image.new("RGB", (thumb, thumb), background)
            cell.paste(image, ((thumb - image.width) // 2, (thumb - image.height) // 2), image)
            sheet.paste(cell, (x, y + offset * thumb))
        draw.text((x + 4, y + thumb * 2 + 7), f"{int(row['index']):02d}", fill="#1c1a16")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def main() -> None:
    args = parse_args()
    rows = read_manifest(args.manifest)
    if args.clean:
        for folder in (args.app_root, args.report_root):
            safe_rmtree(folder)
    args.app_root.mkdir(parents=True, exist_ok=True)
    args.report_root.mkdir(parents=True, exist_ok=True)

    processed: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        source = args.source_root / str(row["source"])
        if not source.is_file():
            raise SystemExit(f"Missing source image: {source}")
        material_code = str(row["material_code"])
        output = args.app_root / material_code / f"{material_code}-01.webp"
        threshold = row.get("background_threshold")
        metrics = normalize_one(
            source,
            output,
            args,
            int(threshold) if threshold is not None else None,
        )
        item = {
            **row,
            "index": index,
            "app_webp": str(output),
            "final_category": str(row["category"]),
            "final_series": str(row["name"]),
            "warning_text": "",
            **metrics,
        }
        processed.append(item)
        report_dir = args.report_root / material_code
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "manifest.json").write_text(
            json.dumps([item], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    make_contact_sheet(processed, args.report_root / "_contact-sheet.jpg")
    (args.report_root / "_summary.json").write_text(
        json.dumps(processed, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    invalid = [
        item
        for item in processed
        if item["output_width"] != args.size
        or item["output_height"] != args.size
        or int(item["file_size"]) > args.max_bytes
        or not 0.975 <= float(item["fill_ratio"]) <= 0.995
        or abs(float(item["center_offset_x"])) > 2
        or abs(float(item["center_offset_y"])) > 2
        or not Image.open(str(item["app_webp"])).convert("RGBA").getchannel("A").getbbox()
    ]
    if invalid:
        raise SystemExit(f"Asset validation failed for {len(invalid)} item(s).")
    print(f"processed={len(processed)} output={args.app_root} report={args.report_root}")


if __name__ == "__main__":
    main()
