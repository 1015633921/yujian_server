from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.process_accessory_assets import normalize_one, safe_rmtree


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize paired accessory cutouts into variety-level image galleries."
    )
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
    parser.add_argument("--require-source-alpha", action="store_true")
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def load_manifest(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise SystemExit("Grouped accessory manifest must be a non-empty JSON array.")
    required = {"category", "name", "material_code", "sources"}
    rows: list[dict[str, object]] = []
    seen_names: set[str] = set()
    seen_codes: set[str] = set()
    for raw in payload:
        if not isinstance(raw, dict):
            raise SystemExit("Grouped accessory manifest rows must be objects.")
        missing = sorted(key for key in required if not raw.get(key))
        if missing:
            raise SystemExit("Manifest row is missing: " + ", ".join(missing))
        sources = raw.get("sources")
        if not isinstance(sources, list) or len(sources) != 2:
            raise SystemExit(f"{raw.get('name')}: exactly two source images are required")
        name = str(raw["name"]).strip()
        code = str(raw["material_code"]).strip()
        if name in seen_names or code in seen_codes:
            raise SystemExit(f"Duplicate variety name or material code: {name} / {code}")
        seen_names.add(name)
        seen_codes.add(code)
        rows.append({**raw, "top": "accessory"})
    return rows


def render_preview(image_path: Path, size: int, background: str) -> Image.Image:
    image = Image.open(image_path).convert("RGBA")
    image.thumbnail((size - 18, size - 18), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), background)
    canvas.paste(image, ((size - image.width) // 2, (size - image.height) // 2), image)
    return canvas


def trim_external_support_spikes(source: Path, output: Path, alpha_threshold: int) -> list[int]:
    """Remove thin fixture lines outside the accessory body without altering its interior pixels."""
    image = ImageOps.exif_transpose(Image.open(source)).convert("RGBA")
    alpha = image.getchannel("A")
    mask = alpha.point(lambda value: 255 if value > alpha_threshold else 0)
    bbox = mask.getbbox()
    if not bbox:
        raise ValueError(f"empty_subject: {source}")
    local = mask.crop(bbox)
    pixels = local.tobytes()
    row_counts = [
        sum(1 for value in pixels[y * local.width : (y + 1) * local.width] if value)
        for y in range(local.height)
    ]
    column_counts = [
        sum(1 for value in pixels[x::local.width] if value)
        for x in range(local.width)
    ]
    row_floor = max(4, round(max(row_counts) * 0.12))
    column_floor = max(4, round(max(column_counts) * 0.12))
    body_rows = [index for index, count in enumerate(row_counts) if count >= row_floor]
    body_columns = [index for index, count in enumerate(column_counts) if count >= column_floor]
    if not body_rows or not body_columns:
        raise ValueError(f"support_trim_failed: {source}")
    core = (
        bbox[0] + body_columns[0],
        bbox[1] + body_rows[0],
        bbox[0] + body_columns[-1] + 1,
        bbox[1] + body_rows[-1] + 1,
    )
    padding = max(3, round(max(core[2] - core[0], core[3] - core[1]) * 0.015))
    keep = (
        max(0, core[0] - padding),
        max(0, core[1] - padding),
        min(image.width, core[2] + padding),
        min(image.height, core[3] + padding),
    )
    alpha.paste(0, (0, 0, image.width, keep[1]))
    alpha.paste(0, (0, keep[3], image.width, image.height))
    alpha.paste(0, (0, keep[1], keep[0], keep[3]))
    alpha.paste(0, (keep[2], keep[1], image.width, keep[3]))
    image.putalpha(alpha)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return list(keep)


def make_contact_sheet(rows: list[dict[str, object]], output: Path) -> None:
    pairs_per_row = 2
    preview_size = 176
    label_height = 52
    pair_width = preview_size * 2
    pair_height = preview_size * 2 + label_height
    row_count = (len(rows) + pairs_per_row - 1) // pairs_per_row
    sheet = Image.new("RGB", (pair_width * pairs_per_row, pair_height * row_count), "#eee9df")
    draw = ImageDraw.Draw(sheet)
    font_path = Path("/System/Library/Fonts/PingFang.ttc")
    font = ImageFont.truetype(str(font_path), 15) if font_path.is_file() else ImageFont.load_default(size=15)
    for index, row in enumerate(rows):
        column = index % pairs_per_row
        line = index // pairs_per_row
        base_x = column * pair_width
        base_y = line * pair_height
        images = [Path(value) for value in row["processed_images"]]
        for image_index, image_path in enumerate(images):
            x = base_x + image_index * preview_size
            sheet.paste(render_preview(image_path, preview_size, "#f8f7f2"), (x, base_y))
            sheet.paste(
                render_preview(image_path, preview_size, "#242424"),
                (x, base_y + preview_size),
            )
        label = f"{index + 1:02d} {row['category']} / {row['name']}"
        draw.text((base_x + 8, base_y + preview_size * 2 + 13), label, fill="#171717", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=94)


def main() -> None:
    args = parse_args()
    rows = load_manifest(args.manifest)
    if args.clean:
        safe_rmtree(args.app_root)
        safe_rmtree(args.report_root)
    args.app_root.mkdir(parents=True, exist_ok=True)
    args.report_root.mkdir(parents=True, exist_ok=True)

    processed: list[dict[str, object]] = []
    for row in rows:
        code = str(row["material_code"])
        output_dir = args.app_root / code
        prepared_dir = args.report_root / "_prepared" / code
        images: list[str] = []
        metrics: list[dict[str, object]] = []
        for index, source_value in enumerate(row["sources"], start=1):
            source = Path(str(source_value)).expanduser().resolve()
            if not source.is_file():
                raise SystemExit(f"Missing source image: {source}")
            prepared = prepared_dir / f"{code}-{index:02d}.png"
            trim_box = trim_external_support_spikes(source, prepared, args.alpha_threshold)
            output = output_dir / f"{code}-{index:02d}.webp"
            item_metrics = normalize_one(prepared, output, args)
            images.append(str(output.resolve()))
            metrics.append(
                {
                    **item_metrics,
                    "source": str(source),
                    "support_trim_box": trim_box,
                }
            )
        item = {**row, "processed_images": images, "metrics": metrics}
        processed.append(item)
        report_dir = args.report_root / code
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "manifest.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    invalid = [
        (row["name"], metric)
        for row in processed
        for metric in row["metrics"]
        if metric["output_width"] != args.size
        or metric["output_height"] != args.size
        or int(metric["file_size"]) > args.max_bytes
        or not 0.975 <= float(metric["fill_ratio"]) <= 0.995
        or abs(float(metric["center_offset_x"])) > 2
        or abs(float(metric["center_offset_y"])) > 2
    ]
    if invalid:
        raise SystemExit(f"Asset validation failed for {len(invalid)} image(s): {invalid[:3]}")

    make_contact_sheet(processed, args.report_root / "_contact-sheet.jpg")
    (args.report_root / "_summary.json").write_text(
        json.dumps(processed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"processed_varieties={len(processed)} processed_images={len(processed) * 2} "
        f"output={args.app_root} report={args.report_root}"
    )


if __name__ == "__main__":
    main()
