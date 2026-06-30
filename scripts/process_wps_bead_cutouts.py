from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WPS_ROOT = ROOT / "outputs" / "wps-bead-cutouts"
DEFAULT_REVIEW_CSV = ROOT / "outputs" / "wps-bead-review.csv"
DEFAULT_APP_ROOT = ROOT / "static" / "materials" / "beads" / "wps-white"
DEFAULT_REPORT_ROOT = ROOT / "outputs" / "wps-bead-white"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
APP_SIZE = 512
CONTENT_RATIO = 0.92


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize WPS AI cutout bead images into white-background app assets.")
    parser.add_argument("--wps-root", type=Path, default=DEFAULT_WPS_ROOT)
    parser.add_argument("--review-csv", type=Path, default=DEFAULT_REVIEW_CSV)
    parser.add_argument("--app-root", type=Path, default=DEFAULT_APP_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--allow-unapproved", action="store_true", help="Process rows even if approved is empty.")
    return parser.parse_args()


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    return text or "material"


def approved(row: dict[str, str], allow_unapproved: bool) -> bool:
    if allow_unapproved:
        return not truthy(row.get("skip", ""))
    return truthy(row.get("approved", "")) and not truthy(row.get("skip", ""))


def truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "y", "yes", "true", "ok", "approve", "approved", "保留", "通过", "是"}


def read_review_rows(path: Path, allow_unapproved: bool) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing review CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        rows = [dict(row) for row in csv.DictReader(fp)]
    return [row for row in rows if approved(row, allow_unapproved)]


def find_wps_file(wps_root: Path, row: dict[str, str]) -> Path | None:
    expected = str(row.get("wps_expected_rel") or row.get("source_rel") or "").strip()
    candidates: list[Path] = []
    if expected:
        rel = Path(expected)
        candidates.extend(wps_root / rel.with_suffix(suffix) for suffix in IMAGE_SUFFIXES if suffix)
    source_stem = Path(str(row.get("source_rel") or "")).stem
    if source_stem:
        candidates.extend(sorted(wps_root.rglob(f"{source_stem}.*")))
    for candidate in candidates:
        if candidate.exists() and candidate.suffix.lower() in IMAGE_SUFFIXES:
            return candidate
    return None


def content_bbox(rgba: Image.Image) -> tuple[int, int, int, int] | None:
    alpha_bbox = rgba.getchannel("A").getbbox()
    if alpha_bbox:
        return alpha_bbox
    rgb = rgba.convert("RGB")
    bg = Image.new("RGB", rgb.size, "white")
    diff = ImageChops.difference(rgb, bg).convert("L")
    mask = diff.point(lambda v: 255 if v > 10 else 0)
    return mask.getbbox()


def normalize_image(path: Path) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGBA")
    bbox = content_bbox(image)
    if bbox:
        left, top, right, bottom = bbox
        pad = max(8, int(max(right - left, bottom - top) * 0.04))
        left = max(0, left - pad)
        top = max(0, top - pad)
        right = min(image.width, right + pad)
        bottom = min(image.height, bottom + pad)
        image = image.crop((left, top, right, bottom))
    white = Image.new("RGBA", image.size, "white")
    white.alpha_composite(image)
    image = white.convert("RGB")
    max_edge = int(APP_SIZE * CONTENT_RATIO)
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (APP_SIZE, APP_SIZE), "white")
    x = (APP_SIZE - image.width) // 2
    y = (APP_SIZE - image.height) // 2
    canvas.paste(image, (x, y))
    return canvas


def make_contact_sheet(rows: list[dict], out: Path) -> None:
    thumb = 132
    gap = 14
    cols = 5
    label_h = 38
    rows_count = max(1, (len(rows) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * thumb + (cols + 1) * gap, rows_count * (thumb + label_h) + (rows_count + 1) * gap), "#f5f1ea")
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        img = Image.open(row["app_webp"]).convert("RGB")
        img.thumbnail((thumb, thumb), Image.Resampling.LANCZOS)
        col = index % cols
        line = index // cols
        x = gap + col * (thumb + gap)
        y = gap + line * (thumb + label_h + gap)
        sheet.paste(img, (x + (thumb - img.width) // 2, y + (thumb - img.height) // 2))
        draw.text((x, y + thumb + 4), str(row["series"])[:14], fill="#333333")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=90)


def main() -> None:
    args = parse_args()
    if args.clean:
        for folder in (args.app_root, args.report_root):
            if folder.exists():
                import shutil

                shutil.rmtree(folder)
    args.app_root.mkdir(parents=True, exist_ok=True)
    args.report_root.mkdir(parents=True, exist_ok=True)
    rows = read_review_rows(args.review_csv, args.allow_unapproved)
    grouped: dict[str, list[dict]] = defaultdict(list)
    failures = []
    for row in rows:
        wps_file = find_wps_file(args.wps_root, row)
        if not wps_file:
            failures.append({"source_rel": row.get("source_rel"), "reason": "wps_file_not_found"})
            continue
        series = (row.get("final_series") or row.get("suggested_series") or Path(wps_file).stem).strip()
        category = (row.get("final_category") or row.get("suggested_category") or "").strip()
        material_code = (row.get("material_code") or "").strip()
        group_key = material_code or series
        grouped[group_key].append({**row, "wps_file": str(wps_file), "series": series, "category": category, "material_code": material_code})

    summary = []
    for group_key, items in sorted(grouped.items()):
        slug = slugify(group_key)
        app_dir = args.app_root / slug
        report_dir = args.report_root / slug
        app_dir.mkdir(parents=True, exist_ok=True)
        report_dir.mkdir(parents=True, exist_ok=True)
        manifest = []
        for index, item in enumerate(items, start=1):
            image = normalize_image(Path(item["wps_file"]))
            out = app_dir / f"{slug}-{index:02d}.webp"
            image.save(out, "WEBP", quality=88, method=6)
            manifest.append(
                {
                    "source": item.get("source_rel", ""),
                    "wps_file": item["wps_file"],
                    "app_webp": str(out),
                    "series": item["category"],
                    "series_label": item["series"],
                    "final_category": item["category"],
                    "final_series": item["series"],
                    "material_code": item["material_code"],
                    "mode": "wps_white",
                }
            )
        (report_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        make_contact_sheet(manifest, report_dir / "_contact-sheet.jpg")
        summary.append({"key": group_key, "slug": slug, "processed": len(manifest)})
    (args.report_root / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if failures:
        (args.report_root / "_failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"processed={sum(item['processed'] for item in summary)} groups={len(summary)} failures={len(failures)}")


if __name__ == "__main__":
    main()
