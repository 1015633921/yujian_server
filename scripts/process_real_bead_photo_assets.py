from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:
    pass


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_ROOT = Path(
    r"C:\Users\10156\xwechat_files\wxid_c62jovsqi9tu22_36ef\msg\file\2026-06\水晶图片"
)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif", ""}


SERIES_SLUGS = {
    "乌拉圭紫水晶": "uruguay-amethyst",
    "千层幽灵": "layered-phantom",
    "四季幽灵": "colorful-phantom",
    "巴西紫水晶": "brazil-amethyst",
    "幽灵穿发": "phantom-rutilated",
    "彩兔毛": "colorful-rabbit-hair",
    "彩发晶": "colorful-rutilated-quartz",
    "抹茶幽灵": "matcha-phantom",
    "曼波绿幽灵": "mambo-green-phantom",
    "特殊幽灵": "special-phantom",
    "特殊矿": "special-mineral",
    "玉石": "jade",
    "玛瑙": "agate",
    "白兔毛": "white-rabbit-hair",
    "白幽灵": "white-phantom",
    "白水": "clear-quartz",
    "白阿塞": "white-azeztulite",
    "粉水晶": "rose-quartz",
    "紫兔毛": "purple-rabbit-hair",
    "紫幽灵": "purple-phantom",
    "红兔毛": "red-rabbit-hair",
    "红幽灵": "red-phantom",
    "红幽灵聚宝盆": "red-phantom-basin",
    "红泥骸骨幽灵": "red-mud-skeletal-phantom",
    "红铜发": "red-rutilated-quartz",
    "绿兔毛": "green-rabbit-hair",
    "绿发晶": "green-rutilated-quartz",
    "绿幽灵": "green-phantom",
    "绿幽灵满天星": "green-phantom-starry",
    "绿幽灵聚宝盆半盆": "green-phantom-half-basin",
    "绿幽灵金字塔": "green-phantom-pyramid",
    "翠幽灵": "emerald-phantom",
    "胶花": "quartz-inclusion",
    "茶晶": "smoky-quartz",
    "草莓晶": "strawberry-quartz",
    "萤石": "fluorite",
    "蓝兔毛": "blue-rabbit-hair",
    "金发晶": "gold-rutilated-quartz",
    "银发晶": "silver-rutilated-quartz",
    "随型": "freeform",
    "雪花幽灵": "snowflake-phantom",
    "黄兔毛": "yellow-rabbit-hair",
    "黄水晶": "citrine",
    "黑发晶": "black-rutilated-quartz",
    "黑耀石": "obsidian",
    "黑曜石": "obsidian",
}


@dataclass(frozen=True)
class Circle:
    x: float
    y: float
    r: float
    score: float
    source: str


class SkipImage(ValueError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cut real bead photos into centered transparent 512px WebP assets."
    )
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--outputs-root", type=Path, default=ROOT / "outputs" / "real-bead-photos")
    parser.add_argument("--app-root", type=Path, default=ROOT / "static" / "materials" / "beads" / "real-photos")
    parser.add_argument("--series", default="all", help="Comma separated folder names or slugs; default all.")
    parser.add_argument("--limit-per-series", type=int, default=0)
    parser.add_argument("--max-dimension", type=int, default=1200)
    parser.add_argument("--app-size", type=int, default=512)
    parser.add_argument("--archive-size", type=int, default=1024)
    parser.add_argument("--target-fill", type=float, default=0.985)
    parser.add_argument("--mask-contract", type=float, default=0.012)
    parser.add_argument("--mask-feather", type=float, default=1.1)
    parser.add_argument("--min-circle-score", type=float, default=0)
    parser.add_argument("--quality", type=int, default=92)
    parser.add_argument("--max-kb", type=int, default=200)
    parser.add_argument("--max-aspect-ratio", type=float, default=1.85)
    parser.add_argument("--exclude-name-regex", default="品种|品类|说明|各种形态|各类")
    parser.add_argument("--clean", action="store_true", help="Remove selected output/app folders before writing.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def safe_slug(name: str) -> str:
    if name in SERIES_SLUGS:
        return SERIES_SLUGS[name]
    text = unicodedata.normalize("NFKD", name).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "bead"


def selected_dirs(source_root: Path, series_arg: str) -> list[Path]:
    dirs = sorted([item for item in source_root.iterdir() if item.is_dir()], key=lambda path: path.name)
    wanted = {item.strip() for item in series_arg.split(",") if item.strip()}
    if not wanted or "all" in wanted:
        return dirs
    result = []
    for item in dirs:
        if item.name in wanted or safe_slug(item.name) in wanted:
            result.append(item)
    missing = sorted(wanted - {item.name for item in result} - {safe_slug(item.name) for item in result})
    if missing:
        raise SystemExit(f"Unknown series folders/slugs: {', '.join(missing)}")
    return result


def list_images(directory: Path, exclude_pattern: re.Pattern[str] | None = None) -> list[Path]:
    return sorted(
        [
            path
            for path in directory.rglob("*")
            if path.is_file()
            and not path.name.startswith(".")
            and path.suffix.lower() in IMAGE_EXTENSIONS
            and not (exclude_pattern and exclude_pattern.search(path.stem))
        ],
        key=lambda path: path.name.lower(),
    )


def read_image(path: Path, max_dimension: int) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if max(image.size) > max_dimension:
        scale = max_dimension / max(image.size)
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
    return image


def gradient_image(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(gx, gy)
    return gray, grad


def circle_ring_mask(shape: tuple[int, int], circle: tuple[float, float, float], width: float = 0.08) -> np.ndarray:
    h, w = shape
    yy, xx = np.ogrid[:h, :w]
    cx, cy, r = circle
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    return np.abs(dist - r) <= max(2, r * width)


def disk_mask(shape: tuple[int, int], circle: tuple[float, float, float], scale: float = 1.0) -> np.ndarray:
    h, w = shape
    yy, xx = np.ogrid[:h, :w]
    cx, cy, r = circle
    return (xx - cx) ** 2 + (yy - cy) ** 2 <= (r * scale) ** 2


def score_circle(gray: np.ndarray, grad: np.ndarray, circle: tuple[float, float, float], source: str) -> Circle | None:
    h, w = gray.shape
    cx, cy, r = circle
    if r <= 8:
        return None
    if cx - r < -r * 0.08 or cy - r < -r * 0.08 or cx + r > w + r * 0.08 or cy + r > h + r * 0.08:
        return None
    radius_ratio = r / max(1, min(h, w))
    if not 0.055 <= radius_ratio <= 0.34:
        return None
    ring = circle_ring_mask(gray.shape, circle, 0.055)
    inside = disk_mask(gray.shape, circle, 0.88)
    outside = circle_ring_mask(gray.shape, (cx, cy, r * 1.14), 0.08)
    if ring.sum() == 0 or inside.sum() == 0:
        return None
    ring_edge = float(np.percentile(grad[ring], 78))
    inside_std = float(gray[inside].std())
    contrast = 0.0
    if outside.sum() > 0:
        contrast = abs(float(gray[inside].mean()) - float(gray[outside].mean()))
    center_penalty = math.hypot((cx - w / 2) / w, (cy - h * 0.54) / h) * 34
    edge_penalty = 0.0
    if cx - r < 4 or cy - r < 4 or cx + r > w - 4 or cy + r > h - 4:
        edge_penalty = 20
    size_bonus = 10 * min(radius_ratio / 0.22, 1.2)
    score = ring_edge * 0.7 + inside_std * 0.55 + contrast * 0.35 + size_bonus - center_penalty - edge_penalty
    return Circle(cx, cy, r, score, source)


def detect_hough(gray: np.ndarray) -> list[tuple[float, float, float]]:
    blurred = cv2.medianBlur(gray, 5)
    h, w = gray.shape
    min_radius = max(18, int(min(h, w) * 0.055))
    max_radius = max(min_radius + 8, int(min(h, w) * 0.34))
    found: list[tuple[float, float, float]] = []
    for param1, param2, dp in ((80, 28, 1.2), (70, 24, 1.15), (60, 21, 1.1), (95, 32, 1.25)):
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=dp,
            minDist=max(80, int(min(h, w) * 0.18)),
            param1=param1,
            param2=param2,
            minRadius=min_radius,
            maxRadius=max_radius,
        )
        if circles is None:
            continue
        for x, y, r in circles[0]:
            found.append((float(x), float(y), float(r)))
    return found


def detect_contours(gray: np.ndarray) -> list[tuple[float, float, float]]:
    edges = cv2.Canny(gray, 45, 135)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape
    result: list[tuple[float, float, float]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min(h, w) ** 2 * 0.006:
            continue
        (cx, cy), r = cv2.minEnclosingCircle(contour)
        if r <= 0:
            continue
        circle_area = math.pi * r * r
        fill = area / circle_area if circle_area else 0
        if 0.18 <= fill <= 1.08:
            result.append((float(cx), float(cy), float(r)))
    return result


def merge_close(candidates: list[Circle]) -> list[Circle]:
    candidates = sorted(candidates, key=lambda item: item.score, reverse=True)
    kept: list[Circle] = []
    for item in candidates:
        duplicate = False
        for prev in kept:
            if math.hypot(item.x - prev.x, item.y - prev.y) < max(item.r, prev.r) * 0.22:
                duplicate = True
                break
        if not duplicate:
            kept.append(item)
    return kept


def detect_bead_circle(image: Image.Image) -> Circle:
    rgb = np.array(image)
    gray, grad = gradient_image(rgb)
    circles = [*detect_hough(gray), *detect_contours(gray)]
    scored = [
        candidate
        for raw in circles
        if (candidate := score_circle(gray, grad, raw, "auto")) is not None
    ]
    scored = merge_close(scored)
    if scored:
        return scored[0]
    h, w = gray.shape
    return Circle(w / 2, h / 2, min(w, h) * 0.32, 0.0, "fallback-center")


def crop_circle(image: Image.Image, circle: Circle, output_size: int, target_fill: float, contract: float, feather: float) -> Image.Image:
    cx, cy, r = circle.x, circle.y, circle.r
    crop_side = max(1, int(round((r * 2) / max(0.1, target_fill))))
    left = int(round(cx - crop_side / 2))
    top = int(round(cy - crop_side / 2))
    square = Image.new("RGB", (crop_side, crop_side), (255, 255, 255))
    source_box = (
        max(0, left),
        max(0, top),
        min(image.width, left + crop_side),
        min(image.height, top + crop_side),
    )
    paste_x = max(0, -left)
    paste_y = max(0, -top)
    square.paste(image.crop(source_box), (paste_x, paste_y))
    resized = square.resize((output_size, output_size), Image.Resampling.LANCZOS).convert("RGBA")

    inset = output_size * (1 - target_fill) / 2 + output_size * contract
    alpha = Image.new("L", (output_size, output_size), 0)
    draw = ImageDraw.Draw(alpha)
    draw.ellipse((inset, inset, output_size - inset, output_size - inset), fill=255)
    if feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather))
    resized.putalpha(alpha)
    return resized


def save_webp_under_limit(image: Image.Image, path: Path, quality: int, max_kb: int) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    chosen_quality = quality
    for current_quality in range(quality, 73, -4):
        image.save(path, "WEBP", quality=current_quality, method=6)
        if path.stat().st_size <= max_kb * 1024:
            chosen_quality = current_quality
            break
        chosen_quality = current_quality
    return chosen_quality, path.stat().st_size


def save_contact_sheet(items: list[dict[str, Any]], destination: Path) -> None:
    if not items:
        return
    thumb = 132
    label_h = 34
    columns = min(6, max(1, len(items)))
    rows = math.ceil(len(items) / columns)
    sheet = Image.new("RGB", (columns * thumb, rows * (thumb * 2 + label_h)), "#f6f1ea")
    draw = ImageDraw.Draw(sheet)
    for index, item in enumerate(items):
        path = Path(item["app_webp"])
        image = Image.open(path).convert("RGBA")
        image.thumbnail((thumb - 8, thumb - 8), Image.Resampling.LANCZOS)
        x = (index % columns) * thumb
        y = (index // columns) * (thumb * 2 + label_h)
        for offset, bg in enumerate(("#fbfaf7", "#242424")):
            cell = Image.new("RGB", (thumb, thumb), bg)
            cell.paste(image, ((thumb - image.width) // 2, (thumb - image.height) // 2), image)
            sheet.paste(cell, (x, y + offset * thumb))
        label = f"{item['index']:02d} {item['circle_source']} {item['circle_score']:.0f}"
        draw.text((x + 6, y + thumb * 2 + 7), label[:22], fill="#1e1b18")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=92)


def process_series(directory: Path, args: argparse.Namespace) -> dict[str, Any]:
    slug = safe_slug(directory.name)
    exclude_pattern = re.compile(args.exclude_name_regex) if args.exclude_name_regex else None
    files = list_images(directory, exclude_pattern)
    if args.limit_per_series > 0:
        files = files[: args.limit_per_series]
    output_dir = args.outputs_root / slug
    app_dir = args.app_root / slug
    archive_dir = output_dir / "archive-1024"
    if args.clean and not args.dry_run:
        shutil.rmtree(output_dir, ignore_errors=True)
        shutil.rmtree(app_dir, ignore_errors=True)
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for index, source in enumerate(files, start=1):
        stem = f"{slug}-{index:02d}"
        try:
            image = read_image(source, args.max_dimension)
            aspect = max(image.width / max(1, image.height), image.height / max(1, image.width))
            if aspect > args.max_aspect_ratio:
                raise SkipImage(f"non-single-bead aspect_ratio={aspect:.2f}")
            circle = detect_bead_circle(image)
            if circle.score < args.min_circle_score:
                raise SkipImage(f"low circle score={circle.score:.1f}")
            app_image = crop_circle(
                image,
                circle,
                args.app_size,
                args.target_fill,
                args.mask_contract,
                args.mask_feather,
            )
            archive_image = crop_circle(
                image,
                circle,
                args.archive_size,
                args.target_fill,
                args.mask_contract,
                args.mask_feather * 2,
            )
            app_path = app_dir / f"{stem}.webp"
            archive_path = archive_dir / f"{stem}.webp"
            if not args.dry_run:
                q, size_bytes = save_webp_under_limit(app_image, app_path, args.quality, args.max_kb)
                archive_dir.mkdir(parents=True, exist_ok=True)
                archive_image.save(archive_path, "WEBP", quality=max(86, q), method=6)
            else:
                q, size_bytes = args.quality, 0
            row = {
                "index": index,
                "series": directory.name,
                "slug": slug,
                "source": str(source),
                "app_webp": str(app_path),
                "archive_webp": str(archive_path),
                "quality": q,
                "bytes": size_bytes,
                "circle": {"x": round(circle.x, 2), "y": round(circle.y, 2), "r": round(circle.r, 2)},
                "circle_score": round(circle.score, 2),
                "circle_source": circle.source,
            }
            rows.append(row)
            print(f"{directory.name}/{stem} score={circle.score:.1f} bytes={size_bytes} <- {source.name}", flush=True)
        except SkipImage as exc:
            skipped.append({"source": str(source), "reason": str(exc)})
            print(f"SKIP {source}: {exc}", flush=True)
        except Exception as exc:
            failures.append({"source": str(source), "error": str(exc)})
            print(f"FAILED {source}: {exc}", file=sys.stderr, flush=True)

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        if failures:
            (output_dir / "failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        if skipped:
            (output_dir / "skipped.json").write_text(json.dumps(skipped, ensure_ascii=False, indent=2), encoding="utf-8")
        save_contact_sheet(rows, output_dir / "_contact-sheet.jpg")
    return {"series": directory.name, "slug": slug, "processed": len(rows), "failed": len(failures), "skipped": len(skipped)}


def main() -> None:
    args = parse_args()
    if not args.source_root.exists():
        raise SystemExit(f"Source root not found: {args.source_root}")
    summaries = [process_series(directory, args) for directory in selected_dirs(args.source_root, args.series)]
    if not args.dry_run:
        args.outputs_root.mkdir(parents=True, exist_ok=True)
        (args.outputs_root / "_summary.json").write_text(
            json.dumps(summaries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    total = sum(item["processed"] for item in summaries)
    failed = sum(item["failed"] for item in summaries)
    skipped = sum(item["skipped"] for item in summaries)
    print(f"processed={total} failed={failed} skipped={skipped} series={len(summaries)}")


if __name__ == "__main__":
    main()
