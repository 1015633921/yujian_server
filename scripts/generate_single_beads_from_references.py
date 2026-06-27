from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


IMAGE_SIZE = 1024
BEAD_CENTER = (512, 520)
BEAD_RADIUS = 354


@dataclass
class Detection:
    source: Path
    center_x: float
    center_y: float
    radius: float
    score: float
    method: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从真实水晶参考图生成统一白底单珠商品图。")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, default=IMAGE_SIZE)
    parser.add_argument("--only", default="", help="只处理指定品类，多个名称用逗号分隔")
    return parser.parse_args()


def read_image(path: Path) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法读取图片：{path}")
    return image


def normalized_groups(source: Path) -> dict[str, list[Path]]:
    files = sorted(path for path in source.iterdir() if path.is_file())
    stems = {path.stem for path in files}
    groups: dict[str, list[Path]] = {}
    for path in files:
        name = path.stem.strip()
        if name.endswith("图片") and name[:-2] in stems:
            name = name[:-2]
        digit_match = re.match(r"^(.*?)([123])$", name)
        if digit_match and digit_match.group(1) in stems:
            name = digit_match.group(1)
        groups.setdefault(name, []).append(path)
    return groups


def detect_best_circle(path: Path) -> Detection:
    image = read_image(path)
    height, width = image.shape[:2]
    scale = min(1.0, 720.0 / max(width, height))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (9, 9), 1.6)

    candidates: list[tuple[float, float, float]] = []
    min_radius = max(22, int(min(sw, sh) * 0.075))
    max_radius = max(min_radius + 4, int(min(sw, sh) * 0.38))
    for threshold in (42, 34, 27):
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=max(35, min_radius),
            param1=110,
            param2=threshold,
            minRadius=min_radius,
            maxRadius=max_radius,
        )
        if circles is not None:
            candidates.extend(tuple(map(float, circle)) for circle in circles[0])
        if len(candidates) >= 3:
            break

    best: tuple[float, float, float, float] | None = None
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    edges = cv2.Canny(gray, 45, 130)
    for x, y, radius in candidates:
        if x - radius < 2 or y - radius < 2 or x + radius >= sw - 2 or y + radius >= sh - 2:
            continue
        mask = np.zeros((sh, sw), dtype=np.uint8)
        cv2.circle(mask, (round(x), round(y)), max(2, round(radius * 0.9)), 255, -1)
        texture = float(cv2.meanStdDev(gray, mask=mask)[1][0, 0])
        saturation = float(cv2.mean(hsv[:, :, 1], mask=mask)[0])
        edge_density = float(cv2.mean(edges, mask=mask)[0]) / 255.0
        ring_mask = np.zeros((sh, sw), dtype=np.uint8)
        cv2.circle(ring_mask, (round(x), round(y)), round(radius), 255, max(2, round(radius * 0.08)))
        boundary_strength = float(cv2.mean(edges, mask=ring_mask)[0]) / 255.0
        size_score = radius / min(sw, sh)
        center_distance = ((x - sw / 2) ** 2 + (y - sh / 2) ** 2) ** 0.5 / max(sw, sh)
        score = size_score * 2.6 + min(texture / 45.0, 1.2) + min(saturation / 110.0, 0.8)
        score += min(edge_density * 1.6, 0.7) + min(boundary_strength * 4.0, 1.5)
        score -= center_distance * 0.25
        if best is None or score > best[3]:
            best = (x, y, radius, score)

    if best is None:
        return detect_by_contour(path, image)

    x, y, radius, score = best
    return Detection(path, x / scale, y / scale, radius / scale, score, "hough-circle")


def detect_by_contour(path: Path, image: np.ndarray) -> Detection:
    height, width = image.shape[:2]
    scale = min(1.0, 720.0 / max(width, height))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (7, 7), 1.4), 35, 105)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < sw * sh * 0.012:
            continue
        (x, y), radius = cv2.minEnclosingCircle(contour)
        if radius < min(sw, sh) * 0.07 or radius > min(sw, sh) * 0.46:
            continue
        circularity = min(1.0, area / max(np.pi * radius * radius, 1))
        score = radius / min(sw, sh) * 4 + circularity
        if best is None or score > best[3]:
            best = (x, y, radius, score)
    if best is None:
        radius = min(width, height) * 0.32
        return Detection(path, width / 2, height * 0.45, radius, 0.1, "center-fallback")
    x, y, radius, score = best
    return Detection(path, x / scale, y / scale, radius / scale, score, "contour")


def crop_texture(detection: Detection) -> Image.Image:
    with Image.open(detection.source) as source:
        image = source.convert("RGB")
    padding = detection.radius * 0.98
    box = (
        int(detection.center_x - padding),
        int(detection.center_y - padding),
        int(detection.center_x + padding),
        int(detection.center_y + padding),
    )
    white = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), "white")
    source_box = (
        max(0, box[0]),
        max(0, box[1]),
        min(image.width, box[2]),
        min(image.height, box[3]),
    )
    cropped = image.crop(source_box)
    white.paste(cropped, (source_box[0] - box[0], source_box[1] - box[1]))
    return white


def radial_shading(size: int) -> Image.Image:
    y, x = np.ogrid[:size, :size]
    cx = cy = (size - 1) / 2
    nx = (x - cx) / (size / 2)
    ny = (y - cy) / (size / 2)
    distance = np.sqrt(nx * nx + ny * ny)
    vignette = np.clip((distance - 0.58) / 0.42, 0, 1)
    shade = (255 - vignette * 20).astype(np.uint8)
    shade = cv2.GaussianBlur(shade, (0, 0), 8)
    return Image.fromarray(shade, mode="L")


def render_bead(texture: Image.Image, output: Path, size: int) -> None:
    radius = round(size * BEAD_RADIUS / IMAGE_SIZE)
    center = (round(size * BEAD_CENTER[0] / IMAGE_SIZE), round(size * BEAD_CENTER[1] / IMAGE_SIZE))
    diameter = radius * 2

    canvas = Image.new("RGB", (size, size), "white")
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse(
        (
            center[0] - radius * 0.78,
            center[1] + radius * 0.72,
            center[0] + radius * 0.82,
            center[1] + radius * 1.03,
        ),
        fill=(64, 54, 45, 48),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(8, size * 0.025)))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow)

    texture = texture.resize((diameter, diameter), Image.Resampling.LANCZOS)
    circle_mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(circle_mask).ellipse((2, 2, diameter - 3, diameter - 3), fill=255)
    circle_mask = circle_mask.filter(ImageFilter.GaussianBlur(max(1, size * 0.0016)))

    shade = radial_shading(diameter)
    shaded = Image.composite(
        Image.new("RGB", (diameter, diameter), (235, 235, 235)),
        texture,
        Image.eval(shade, lambda value: 255 - value),
    )
    shaded = Image.blend(texture, shaded, 0.16)

    bead = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    bead.paste(shaded, (0, 0), circle_mask)

    gloss = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    gloss_draw = ImageDraw.Draw(gloss)
    gloss_draw.ellipse(
        (diameter * 0.18, diameter * 0.10, diameter * 0.48, diameter * 0.32),
        fill=(255, 255, 255, 78),
    )
    gloss_draw.arc(
        (diameter * 0.05, diameter * 0.05, diameter * 0.95, diameter * 0.95),
        205,
        345,
        fill=(255, 255, 255, 70),
        width=max(2, diameter // 120),
    )
    gloss = gloss.filter(ImageFilter.GaussianBlur(max(2, size * 0.012)))
    bead = Image.alpha_composite(bead, gloss)

    rim = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    ImageDraw.Draw(rim).ellipse(
        (2, 2, diameter - 3, diameter - 3),
        outline=(92, 88, 84, 34),
        width=max(1, diameter // 260),
    )
    bead = Image.alpha_composite(bead, rim)
    canvas.alpha_composite(bead, (center[0] - radius, center[1] - radius))

    hole = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hole_draw = ImageDraw.Draw(hole)
    hole_x = center[0]
    hole_y = center[1] - round(radius * 0.82)
    hole_w = round(radius * 0.31)
    hole_h = round(radius * 0.145)
    hole_draw.ellipse(
        (hole_x - hole_w // 2, hole_y - hole_h // 2, hole_x + hole_w // 2, hole_y + hole_h // 2),
        fill=(55, 50, 47, 155),
        outline=(255, 255, 255, 130),
        width=max(2, size // 300),
    )
    hole_draw.ellipse(
        (
            hole_x - round(hole_w * 0.31),
            hole_y - round(hole_h * 0.22),
            hole_x + round(hole_w * 0.31),
            hole_y + round(hole_h * 0.25),
        ),
        fill=(230, 228, 224, 185),
    )
    hole = hole.filter(ImageFilter.GaussianBlur(max(0.6, size * 0.0012)))
    canvas = Image.alpha_composite(canvas, hole)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=96)


def build_contact_sheet(outputs: list[Path], destination: Path) -> None:
    thumb = 170
    label_height = 34
    columns = 8
    rows = (len(outputs) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb, rows * (thumb + label_height)), "#f5f3ef")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(outputs):
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb - 10, thumb - 10), Image.Resampling.LANCZOS)
        x = (index % columns) * thumb + (thumb - image.width) // 2
        y = (index // columns) * (thumb + label_height) + (thumb - image.height) // 2
        sheet.paste(image, (x, y))
        # Windows 的默认 Pillow 字体不可靠显示中文；编号与文件清单配合质检。
        draw.text((x + 5, y + image.height - 20), f"{index + 1:03d}", fill="#544c43")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=92)


def main() -> None:
    args = parse_args()
    groups = normalized_groups(args.source)
    only = {name.strip() for name in args.only.split(",") if name.strip()}
    if only:
        groups = {name: paths for name, paths in groups.items() if name in only}
    args.output.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, object]] = []
    outputs: list[Path] = []
    for index, (name, paths) in enumerate(sorted(groups.items()), start=1):
        detections = []
        for path in paths:
            try:
                detections.append(detect_best_circle(path))
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] {path.name}: {exc}")
        if not detections:
            print(f"[SKIP] {name}: 没有可读取参考图")
            continue
        best = max(detections, key=lambda item: item.score)
        output = args.output / f"{name}.png"
        render_bead(crop_texture(best), output, args.size)
        outputs.append(output)
        manifest.append(
            {
                "index": index,
                "name": name,
                "output": output.name,
                "source": best.source.name,
                "method": best.method,
                "score": round(best.score, 4),
                "references": [path.name for path in paths],
            }
        )
        print(f"[{index:03d}/{len(groups):03d}] {name} <- {best.source.name} ({best.method})")

    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (args.output / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["index", "name", "output", "source", "method", "score", "references"],
        )
        writer.writeheader()
        for row in manifest:
            writer.writerow({**row, "references": " | ".join(row["references"])})
    build_contact_sheet(outputs, args.output / "_contact-sheet.jpg")
    print(f"generated={len(outputs)} output={args.output.resolve()}")


if __name__ == "__main__":
    main()
