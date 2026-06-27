from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class Detection:
    source: str
    center_x: float
    center_y: float
    radius: float
    score: float
    method: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract single bead photos into transparent app-ready bead assets."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--webp-output", type=Path)
    parser.add_argument("--prefix", default="bead")
    parser.add_argument("--png-size", type=int, default=1024)
    parser.add_argument("--webp-size", type=int, default=512)
    parser.add_argument("--edge-contract", type=float, default=3.0)
    parser.add_argument("--feather", type=float, default=1.1)
    parser.add_argument("--quality", type=int, default=92)
    return parser.parse_args()


def read_bgr(path: Path) -> np.ndarray:
    try:
        image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Cannot read image: {path}") from exc
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def list_images(source: Path) -> list[Path]:
    return sorted(path for path in source.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)


def detect_bead(path: Path) -> Detection:
    image = read_bgr(path)
    height, width = image.shape[:2]
    scale = min(1.0, 900.0 / max(width, height))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (9, 9), 1.8)
    edges = cv2.Canny(gray, 40, 130)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

    candidates: list[tuple[float, float, float]] = []
    min_radius = max(40, int(min(sw, sh) * 0.11))
    max_radius = max(min_radius + 8, int(min(sw, sh) * 0.27))
    for threshold in (44, 38, 32, 26, 21):
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1.18,
            minDist=max(80, min_radius),
            param1=115,
            param2=threshold,
            minRadius=min_radius,
            maxRadius=max_radius,
        )
        if circles is not None:
            candidates.extend(tuple(map(float, circle)) for circle in circles[0])
        if len(candidates) >= 8:
            break

    best: tuple[float, float, float, float] | None = None
    for x, y, radius in candidates:
        if x - radius < 1 or y - radius < 1 or x + radius >= sw - 1 or y + radius >= sh - 1:
            continue

        mask = np.zeros((sh, sw), dtype=np.uint8)
        cv2.circle(mask, (round(x), round(y)), max(3, round(radius * 0.88)), 255, -1)
        ring_mask = np.zeros((sh, sw), dtype=np.uint8)
        cv2.circle(ring_mask, (round(x), round(y)), round(radius), 255, max(2, round(radius * 0.07)))

        texture = float(cv2.meanStdDev(gray, mask=mask)[1][0, 0])
        saturation = float(cv2.mean(hsv[:, :, 1], mask=mask)[0])
        edge_density = float(cv2.mean(edges, mask=mask)[0]) / 255.0
        boundary_strength = float(cv2.mean(edges, mask=ring_mask)[0]) / 255.0
        size_ratio = radius / min(sw, sh)
        target_size = 0.19
        size_score = 1.0 - min(abs(size_ratio - target_size) / target_size, 1.0)
        center_distance = math.hypot(x - sw / 2, y - sh / 2) / max(sw, sh)

        score = size_score * 2.8
        score += min(texture / 34.0, 1.5)
        score += min(saturation / 90.0, 0.6)
        score += min(edge_density * 1.3, 0.5)
        score += min(boundary_strength * 5.0, 1.8)
        score -= center_distance * 0.18
        if best is None or score > best[3]:
            best = (x, y, radius, score)

    if best is None:
        return detect_by_contour(path, image)

    x, y, radius, score = best
    return Detection(
        source=path.name,
        center_x=x / scale,
        center_y=y / scale,
        radius=radius / scale,
        score=round(score, 4),
        method="hough-circle",
    )


def detect_by_contour(path: Path, image: np.ndarray) -> Detection:
    height, width = image.shape[:2]
    scale = min(1.0, 900.0 / max(width, height))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (7, 7), 1.4), 32, 110)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best: tuple[float, float, float, float] | None = None
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < sw * sh * 0.012:
            continue
        (x, y), radius = cv2.minEnclosingCircle(contour)
        if radius < min(sw, sh) * 0.10 or radius > min(sw, sh) * 0.29:
            continue
        if x - radius < 1 or y - radius < 1 or x + radius >= sw - 1 or y + radius >= sh - 1:
            continue
        circularity = min(1.0, area / max(math.pi * radius * radius, 1))
        score = radius / min(sw, sh) * 4.0 + circularity
        if best is None or score > best[3]:
            best = (x, y, radius, score)

    if best is None:
        radius = min(width, height) * 0.22
        return Detection(path.name, width / 2, height / 2, radius, 0.1, "center-fallback")

    x, y, radius, score = best
    return Detection(path.name, x / scale, y / scale, radius / scale, round(score, 4), "contour")


def export_cutout(
    source: Path,
    detection: Detection,
    output: Path,
    size: int,
    edge_contract: float,
    feather: float,
) -> None:
    image = ImageOps.exif_transpose(Image.open(source)).convert("RGBA")
    visible_radius = max(4.0, detection.radius - edge_contract)
    crop_radius = visible_radius + max(6, feather * 5)
    crop_box = (
        math.floor(detection.center_x - crop_radius),
        math.floor(detection.center_y - crop_radius),
        math.ceil(detection.center_x + crop_radius),
        math.ceil(detection.center_y + crop_radius),
    )

    crop_width = crop_box[2] - crop_box[0]
    crop_height = crop_box[3] - crop_box[1]
    crop = Image.new("RGBA", (crop_width, crop_height), (0, 0, 0, 0))
    source_box = (
        max(0, crop_box[0]),
        max(0, crop_box[1]),
        min(image.width, crop_box[2]),
        min(image.height, crop_box[3]),
    )
    crop.paste(image.crop(source_box), (source_box[0] - crop_box[0], source_box[1] - crop_box[1]))

    local_x = detection.center_x - crop_box[0]
    local_y = detection.center_y - crop_box[1]
    mask = Image.new("L", crop.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse(
        (
            local_x - visible_radius,
            local_y - visible_radius,
            local_x + visible_radius,
            local_y + visible_radius,
        ),
        fill=255,
    )
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    crop.putalpha(mask)

    alpha_bbox = crop.getchannel("A").getbbox()
    if alpha_bbox is None:
        raise ValueError(f"Empty alpha result: {source}")
    crop = crop.crop(alpha_bbox)
    crop.thumbnail((round(size * 0.88), round(size * 0.88)), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(crop, ((size - crop.width) // 2, (size - crop.height) // 2))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "PNG", optimize=True)


def save_webp(source_png: Path, destination: Path, size: int, quality: int) -> None:
    image = Image.open(source_png).convert("RGBA")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(image, ((size - image.width) // 2, (size - image.height) // 2))
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, "WEBP", quality=quality, method=6)


def build_contact_sheet(pngs: list[Path], detections: list[Detection], destination: Path) -> None:
    thumb = 180
    label_height = 44
    columns = min(4, max(1, len(pngs)))
    rows = math.ceil(len(pngs) / columns)
    cell_h = thumb + label_height
    sheet = Image.new("RGB", (columns * thumb, rows * cell_h), "#f7f4ee")
    draw = ImageDraw.Draw(sheet)

    checker = Image.new("RGB", (thumb, thumb), "#ffffff")
    checker_draw = ImageDraw.Draw(checker)
    step = 18
    for y in range(0, thumb, step):
        for x in range(0, thumb, step):
            if (x // step + y // step) % 2:
                checker_draw.rectangle((x, y, x + step - 1, y + step - 1), fill="#e8e3da")

    for index, path in enumerate(pngs):
        image = Image.open(path).convert("RGBA")
        image.thumbnail((thumb - 18, thumb - 18), Image.Resampling.LANCZOS)
        x0 = (index % columns) * thumb
        y0 = (index // columns) * cell_h
        sheet.paste(checker, (x0, y0))
        sheet.paste(image, (x0 + (thumb - image.width) // 2, y0 + (thumb - image.height) // 2), image)
        label = f"{index + 1:02d} {detections[index].method}"
        draw.text((x0 + 10, y0 + thumb + 7), label, fill="#2f2b25")
        draw.text((x0 + 10, y0 + thumb + 24), f"r={detections[index].radius:.0f}", fill="#756d62")

    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=94)


def write_manifest(output: Path, rows: list[dict[str, object]]) -> None:
    (output / "manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    files = list_images(args.source)
    if not files:
        raise SystemExit(f"No images found in {args.source}")

    args.output.mkdir(parents=True, exist_ok=True)
    detections: list[Detection] = []
    pngs: list[Path] = []
    manifest: list[dict[str, object]] = []
    for index, source in enumerate(files, start=1):
        detection = detect_bead(source)
        output_name = f"{args.prefix}-{index:02d}.png"
        png_output = args.output / output_name
        export_cutout(source, detection, png_output, args.png_size, args.edge_contract, args.feather)
        webp_name = ""
        if args.webp_output:
            webp_name = f"{args.prefix}-{index:02d}.webp"
            save_webp(png_output, args.webp_output / webp_name, args.webp_size, args.quality)
        alpha = Image.open(png_output).getchannel("A")
        alpha_bbox = alpha.getbbox()
        visible_pixels = int(np.array(alpha).astype(bool).sum())
        detections.append(detection)
        pngs.append(png_output)
        manifest.append(
            {
                "index": index,
                "source": source.name,
                "png": output_name,
                "webp": webp_name,
                "alpha_bbox": list(alpha_bbox or ()),
                "visible_pixels": visible_pixels,
                **asdict(detection),
            }
        )
        print(f"[{index:02d}/{len(files):02d}] {source.name} -> {output_name} ({detection.method})")

    write_manifest(args.output, manifest)
    build_contact_sheet(pngs, detections, args.output / "_contact-sheet.jpg")
    print(f"processed={len(pngs)} output={args.output.resolve()}")
    if args.webp_output:
        print(f"webp_output={args.webp_output.resolve()}")


if __name__ == "__main__":
    main()
