from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.material_knowledge import material_code_from_payload


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
DEFAULT_APP_ROOT = ROOT / "static" / "materials" / "beads" / "transparent-processed"
DEFAULT_REPORT_ROOT = ROOT / "outputs" / "transparent-bead-assets"
CATEGORY_SLUG_OVERRIDES = {
    "一线天幽灵": "one-line-phantom",
    "千层幽灵": "layered-phantom",
    "合金配件": "alloy-accessory",
    "四季幽灵": "four-seasons-phantom",
    "彩兔毛": "colorful-rabbit-hair",
    "白幽灵": "white-phantom",
    "紫幽灵": "purple-phantom",
    "紫水晶": "amethyst",
    "红兔毛": "red-rabbit-hair",
    "红幽灵聚宝盆": "red-phantom-basin",
    "红泥骸骨幽灵": "red-mud-skeletal-phantom",
    "红铜发": "red-rutilated-quartz",
    "绿兔毛": "green-rabbit-hair",
    "绿发晶": "green-rutilated-quartz",
    "绿幽灵": "green-phantom",
    "绿幽灵满天星": "green-phantom-starry",
    "绿幽灵聚宝盆半盆": "green-phantom-half-basin",
    "胶花": "quartz-inclusion",
    "茶晶": "smoky-quartz",
    "金发晶": "gold-rutilated-quartz",
    "钛晶": "titanium-quartz",
    "雪花幽灵": "snowflake-phantom",
    "黄兔毛": "yellow-rabbit-hair",
    "黑发晶": "black-rutilated-quartz",
}
CATEGORY_TOP_OVERRIDES = {"合金配件": "accessory"}
CATEGORY_PARENT_OVERRIDES = {
    "一线天幽灵": "幽灵水晶",
    "千层幽灵": "幽灵水晶",
    "四季幽灵": "幽灵水晶",
    "白幽灵": "幽灵水晶",
    "紫幽灵": "幽灵水晶",
    "红幽灵聚宝盆": "幽灵水晶",
    "红泥骸骨幽灵": "幽灵水晶",
    "绿幽灵": "幽灵水晶",
    "绿幽灵满天星": "幽灵水晶",
    "绿幽灵聚宝盆半盆": "幽灵水晶",
    "雪花幽灵": "幽灵水晶",
    "彩兔毛": "兔毛水晶",
    "红兔毛": "兔毛水晶",
    "绿兔毛": "兔毛水晶",
    "黄兔毛": "兔毛水晶",
    "红铜发": "发晶",
    "绿发晶": "发晶",
    "金发晶": "发晶",
    "钛晶": "发晶",
    "黑发晶": "发晶",
    "胶花": "胶花水晶",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize transparent bead cutouts into app-ready 512px WebP assets."
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--app-root", type=Path, default=DEFAULT_APP_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--target-fill", type=float, default=0.992)
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--background-threshold", type=int, default=18)
    parser.add_argument("--edge-padding", type=int, default=2)
    parser.add_argument("--max-bytes", type=int, default=200_000)
    parser.add_argument("--quality", type=int, default=92)
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def digest_token(value: str, length: int = 10) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def material_code_for(category: str) -> str:
    slug = CATEGORY_SLUG_OVERRIDES.get(category)
    if slug:
        return slug.replace("-", "_")
    code = material_code_from_payload(
        {"top": "bead", "category": category, "series": category, "name": category}
    )
    if code and code != "material":
        return code
    return f"bead_{digest_token(category)}"


def slug_for(category: str) -> str:
    slug = CATEGORY_SLUG_OVERRIDES.get(category)
    if slug:
        return slug
    code = material_code_for(category)
    return code.replace("_", "-")


def top_for(category: str) -> str:
    return CATEGORY_TOP_OVERRIDES.get(category, "bead")


def parent_category_for(category: str) -> str:
    return CATEGORY_PARENT_OVERRIDES.get(category, category)


def safe_rmtree(path: Path, allowed_root: Path) -> None:
    if not path.exists():
        return
    resolved = path.resolve()
    allowed = allowed_root.resolve()
    if resolved == allowed or allowed not in resolved.parents:
        raise SystemExit(f"Refusing to remove path outside workspace: {resolved}")
    shutil.rmtree(resolved)


def list_sources(source_root: Path) -> list[Path]:
    return sorted(
        path
        for path in source_root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def category_for(source_root: Path, path: Path) -> str:
    rel = path.relative_to(source_root)
    return rel.parts[0] if len(rel.parts) > 1 else source_root.name


def components_mask(mask: np.ndarray) -> np.ndarray:
    if not np.any(mask):
        return mask
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    if count <= 1:
        return mask
    areas = stats[1:, cv2.CC_STAT_AREA]
    if areas.size == 0:
        return mask
    largest = int(areas.max())
    min_area = max(16, round(largest * 0.003))
    keep_ids = [index + 1 for index, area in enumerate(areas) if int(area) >= min_area]
    return np.isin(labels, keep_ids)


def mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask)
    if xs.size == 0 or ys.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def padded_bbox(
    bbox: tuple[int, int, int, int],
    image_size: tuple[int, int],
    padding: int,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = bbox
    return (
        max(0, left - padding),
        max(0, top - padding),
        min(image_size[0], right + padding),
        min(image_size[1], bottom + padding),
    )


def border_background_color(rgb: Image.Image) -> tuple[int, int, int]:
    arr = np.asarray(rgb.convert("RGB"), dtype=np.uint8)
    top = arr[0, :, :]
    bottom = arr[-1, :, :]
    left = arr[:, 0, :]
    right = arr[:, -1, :]
    border = np.concatenate([top, bottom, left, right], axis=0)
    median = np.median(border, axis=0)
    return tuple(int(v) for v in median)


def connected_background_mask(close_to_bg: np.ndarray) -> np.ndarray:
    count, labels, _, _ = cv2.connectedComponentsWithStats(
        close_to_bg.astype(np.uint8), connectivity=8
    )
    if count <= 1:
        return np.zeros_like(close_to_bg, dtype=bool)
    edge_labels = set(int(value) for value in labels[0, :])
    edge_labels.update(int(value) for value in labels[-1, :])
    edge_labels.update(int(value) for value in labels[:, 0])
    edge_labels.update(int(value) for value in labels[:, -1])
    edge_labels.discard(0)
    if not edge_labels:
        return np.zeros_like(close_to_bg, dtype=bool)
    return np.isin(labels, list(edge_labels))


def foreground_from_flat_background(
    image: Image.Image,
    threshold: int,
) -> tuple[np.ndarray, str]:
    rgb = image.convert("RGB")
    bg = border_background_color(rgb)
    arr = np.asarray(rgb, dtype=np.int16)
    diff = np.abs(arr - np.array(bg, dtype=np.int16)).max(axis=2)
    close_to_bg = diff <= threshold
    bg_connected = connected_background_mask(close_to_bg)
    mask = components_mask(~bg_connected)
    mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)) > 0
    return components_mask(mask), f"flat_background:{bg}"


def alpha_subject_mask(
    image: Image.Image,
    threshold: int,
    bg_threshold: int,
) -> tuple[np.ndarray, str]:
    rgba = image.convert("RGBA")
    alpha = np.asarray(rgba.getchannel("A"), dtype=np.uint8)
    if alpha.min() < 250:
        return components_mask(alpha > threshold), "alpha"
    return foreground_from_flat_background(rgba, bg_threshold)


def fit_on_canvas(
    image: Image.Image,
    bbox: tuple[int, int, int, int],
    size: int,
    target_fill: float,
    padding: int,
) -> Image.Image:
    crop_box = padded_bbox(bbox, image.size, padding)
    crop = image.crop(crop_box).convert("RGBA")
    max_edge = max(crop.width, crop.height)
    target_edge = max(1, round(size * target_fill))
    scale = target_edge / max_edge
    resized = crop.resize(
        (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    return canvas


def apply_clean_alpha(image: Image.Image, mask: np.ndarray, mode: str) -> Image.Image:
    rgba = image.convert("RGBA")
    arr = np.asarray(rgba).copy()
    if mode.startswith("alpha"):
        alpha = arr[:, :, 3]
        alpha[~mask] = 0
        arr[:, :, 3] = alpha
        return Image.fromarray(arr, "RGBA")
    mask_img = Image.fromarray((mask.astype(np.uint8) * 255), "L")
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(0.9))
    rgba.putalpha(mask_img)
    return rgba


def save_webp_under_size(
    image: Image.Image,
    destination: Path,
    quality: int,
    max_bytes: int,
) -> tuple[int, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    qualities = [quality, 88, 84, 80, 76, 72, 68, 64]
    used_quality = qualities[-1]
    for candidate in qualities:
        used_quality = candidate
        image.save(
            destination,
            "WEBP",
            quality=candidate,
            method=6,
            alpha_quality=100,
            exact=True,
        )
        if destination.stat().st_size <= max_bytes:
            break
    return destination.stat().st_size, used_quality


def image_metrics(path: Path, alpha_threshold: int) -> dict[str, object]:
    image = Image.open(path).convert("RGBA")
    alpha = np.asarray(image.getchannel("A"), dtype=np.uint8)
    mask = alpha > alpha_threshold
    bbox = mask_bbox(mask)
    if not bbox:
        return {
            "width": image.width,
            "height": image.height,
            "bbox": None,
            "fill_ratio": 0,
            "center_offset_x": None,
            "center_offset_y": None,
        }
    left, top, right, bottom = bbox
    bbox_w = right - left
    bbox_h = bottom - top
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    return {
        "width": image.width,
        "height": image.height,
        "bbox": [left, top, right, bottom],
        "fill_ratio": round(max(bbox_w, bbox_h) / max(image.width, image.height), 4),
        "center_offset_x": round(center_x - image.width / 2, 2),
        "center_offset_y": round(center_y - image.height / 2, 2),
    }


def normalize_one(
    source: Path,
    output: Path,
    args: argparse.Namespace,
) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    opened = ImageOps.exif_transpose(Image.open(source))
    rgba = opened.convert("RGBA")
    mask, mask_mode = alpha_subject_mask(rgba, args.alpha_threshold, args.background_threshold)
    bbox = mask_bbox(mask)
    if bbox is None:
        raise ValueError("empty_subject")
    cleaned = apply_clean_alpha(rgba, mask, mask_mode)
    normalized = fit_on_canvas(cleaned, bbox, args.size, args.target_fill, args.edge_padding)
    file_size, quality = save_webp_under_size(normalized, output, args.quality, args.max_bytes)
    metrics = image_metrics(output, args.alpha_threshold)
    if metrics["width"] != args.size or metrics["height"] != args.size:
        warnings.append("bad_dimensions")
    fill_ratio = float(metrics["fill_ratio"])
    if fill_ratio < 0.975:
        warnings.append("underfilled")
    if fill_ratio > 0.995:
        warnings.append("near_edge")
    if abs(float(metrics["center_offset_x"] or 0)) > 2 or abs(float(metrics["center_offset_y"] or 0)) > 2:
        warnings.append("off_center")
    if file_size > args.max_bytes:
        warnings.append("over_200kb")
    if not mask_mode.startswith("alpha"):
        warnings.append("background_removed_from_opaque_source")
    return (
        {
            "source_width": rgba.width,
            "source_height": rgba.height,
            "source_bbox": list(bbox),
            "mask_mode": mask_mode,
            "output_width": metrics["width"],
            "output_height": metrics["height"],
            "output_bbox": metrics["bbox"],
            "fill_ratio": metrics["fill_ratio"],
            "center_offset_x": metrics["center_offset_x"],
            "center_offset_y": metrics["center_offset_y"],
            "file_size": file_size,
            "quality": quality,
        },
        warnings,
    )


def make_contact_sheet(rows: list[dict[str, object]], output: Path, columns: int = 6) -> None:
    if not rows:
        return
    thumb = 126
    label_h = 34
    gap = 12
    rows_count = math.ceil(len(rows) / columns)
    sheet = Image.new(
        "RGB",
        (columns * thumb + (columns + 1) * gap, rows_count * (thumb * 2 + label_h) + (rows_count + 1) * gap),
        "#eee9df",
    )
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        image = Image.open(str(row["app_webp"])).convert("RGBA")
        image.thumbnail((thumb - 10, thumb - 10), Image.Resampling.LANCZOS)
        col = index % columns
        line = index // columns
        x = gap + col * (thumb + gap)
        y = gap + line * (thumb * 2 + label_h + gap)
        for offset, bg in enumerate(("#f8f7f2", "#242424")):
            cell = Image.new("RGB", (thumb, thumb), bg)
            cell.paste(image, ((thumb - image.width) // 2, (thumb - image.height) // 2), image)
            sheet.paste(cell, (x, y + offset * thumb))
        label = f"{int(row['index']):02d} {row.get('warning_text') or ''}"[:18]
        draw.text((x + 6, y + thumb * 2 + 7), label, fill="#1c1a16")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def write_csv(rows: list[dict[str, object]], output: Path) -> None:
    if not rows:
        return
    fieldnames = [
        "top",
        "source_category",
        "category",
        "series",
        "final_category",
        "final_series",
        "index",
        "source",
        "app_webp",
        "material_code",
        "slug",
        "fill_ratio",
        "center_offset_x",
        "center_offset_y",
        "file_size",
        "quality",
        "mask_mode",
        "warning_text",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def main() -> None:
    args = parse_args()
    source_root = args.source_root.resolve()
    if not source_root.exists():
        raise SystemExit(f"Source root not found: {source_root}")
    if args.clean:
        safe_rmtree(args.app_root, ROOT)
        safe_rmtree(args.report_root, ROOT)
    args.app_root.mkdir(parents=True, exist_ok=True)
    args.report_root.mkdir(parents=True, exist_ok=True)

    sources = list_sources(source_root)
    grouped: dict[str, list[Path]] = defaultdict(list)
    for source in sources:
        grouped[category_for(source_root, source)].append(source)

    all_rows: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    summary: list[dict[str, object]] = []
    seen_slugs: dict[str, str] = {}
    for category, files in sorted(grouped.items()):
        material_code = material_code_for(category)
        slug = slug_for(category)
        top = top_for(category)
        parent_category = parent_category_for(category)
        previous_category = seen_slugs.setdefault(slug, category)
        if previous_category != category:
            raise SystemExit(f"Slug collision: {slug} maps both {previous_category} and {category}")
        print(
            f"processing category={parent_category} series={category} top={top} files={len(files)} slug={slug}",
            flush=True,
        )
        app_dir = args.app_root / slug
        report_dir = args.report_root / slug
        app_dir.mkdir(parents=True, exist_ok=True)
        report_dir.mkdir(parents=True, exist_ok=True)
        manifest: list[dict[str, object]] = []
        for index, source in enumerate(sorted(files), start=1):
            output = app_dir / f"{slug}-{index:02d}.webp"
            try:
                metrics, warnings = normalize_one(source, output, args)
            except Exception as exc:
                failures.append({"source": str(source), "category": category, "reason": str(exc)})
                continue
            row = {
                "category": parent_category,
                "top": top,
                "series": category,
                "series_label": category,
                "source_category": category,
                "final_category": parent_category,
                "final_series": category,
                "material_code": material_code,
                "slug": slug,
                "index": index,
                "source": str(source),
                "app_webp": str(output.resolve()),
                "warning_text": ",".join(warnings),
                **metrics,
            }
            manifest.append(row)
            all_rows.append(row)
            if index == 1 or index % 20 == 0 or index == len(files):
                print(f"  processed {index}/{len(files)} {category}", flush=True)
        (report_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        make_contact_sheet(manifest, report_dir / "_contact-sheet.jpg")
        summary.append(
            {
                "category": category,
                "final_category": parent_category,
                "slug": slug,
                "material_code": material_code,
                "top": top,
                "processed": len(manifest),
                "failures": len([item for item in failures if item["category"] == category]),
                "warnings": sum(1 for item in manifest if item.get("warning_text")),
            }
        )

    make_contact_sheet(all_rows, args.report_root / "_contact-sheet-all.jpg", columns=8)
    write_csv(all_rows, args.report_root / "_qa.csv")
    (args.report_root / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if failures:
        (args.report_root / "_failures.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(
        f"processed={len(all_rows)} groups={len(summary)} "
        f"failures={len(failures)} warnings={sum(1 for item in all_rows if item.get('warning_text'))}"
    )
    print(f"app_root={args.app_root.resolve()}")
    print(f"report_root={args.report_root.resolve()}")


if __name__ == "__main__":
    main()
