from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.material_knowledge import material_code_from_payload
from scripts.normalize_transparent_bead_assets import (
    image_metrics,
    make_contact_sheet,
    normalize_one,
    safe_rmtree,
    save_webp_under_size,
)


DEFAULT_SOURCE_ROOT = Path(r"C:\Users\10156\Downloads\水晶第二批照片\水晶第二批照片")
DEFAULT_APP_ROOT = ROOT / "static" / "materials" / "beads" / "second-batch-transparent"
DEFAULT_REPORT_ROOT = ROOT / "outputs" / "second-batch-transparent"
DEFAULT_UNNAMED_REVIEW = ROOT / "outputs" / "second-batch-unnamed-review.csv"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
GENERIC_NAME_RE = re.compile(r"^(IMG|DSC|PXL|WX|MMEXPORT|SCREENSHOT)[_ -]?\d+", re.I)


@dataclass(frozen=True)
class MaterialTarget:
    top: str
    final_category: str
    final_series: str
    material_code: str


TARGETS: dict[str, MaterialTarget] = {
    "六芒星光粉": MaterialTarget("bead", "粉红晶石", "六芒星光粉", "rose_quartz"),
    "冰橘粉": MaterialTarget("bead", "粉红晶石", "冰橘粉", "rose_quartz"),
    "四季幽灵": MaterialTarget("bead", "幽灵水晶", "四季幽灵", "four_seasons_phantom"),
    "四季幽灵半盆": MaterialTarget("bead", "幽灵水晶", "四季幽灵半盆", "four_seasons_phantom"),
    "幽灵方糖": MaterialTarget("bead", "幽灵水晶", "幽灵方糖", "colorful_phantom"),
    "幽灵无事牌": MaterialTarget("pendant", "吊坠", "幽灵无事牌", "colorful_phantom"),
    "彩闪灵": MaterialTarget("bead", "胶花水晶", "彩闪灵", "quartz_inclusion"),
    "拉长石": MaterialTarget("bead", "蓝色晶石", "拉长石", "labradorite"),
    "果冻马粉": MaterialTarget("bead", "粉红晶石", "马达加斯加粉晶果冻体", "rose_quartz"),
    "油画蓝晶": MaterialTarget("bead", "蓝色晶石", "油画蓝晶石", "kyanite"),
    "火烧云幽灵": MaterialTarget("bead", "幽灵水晶", "火烧云幽灵", "red_phantom"),
    "灰月光": MaterialTarget("bead", "白色晶石", "灰月光", "moonstone"),
    "猫眼彩兔毛": MaterialTarget("bead", "兔毛水晶", "彩兔毛水晶", "rabbit_hair_quartz"),
    "猫眼蓝晶石": MaterialTarget("bead", "蓝色晶石", "猫眼蓝晶石", "kyanite"),
    "玉化蓝晶": MaterialTarget("bead", "蓝色晶石", "玉化蓝晶石", "kyanite"),
    "白兔毛": MaterialTarget("bead", "兔毛水晶", "白兔毛水晶", "rabbit_hair_quartz"),
    "白幽灵": MaterialTarget("bead", "幽灵水晶", "白幽灵水晶高品", "white_phantom"),
    "白水三角型": MaterialTarget("bead", "白色晶石", "白水三角型", "clear_quartz"),
    "白水双尖": MaterialTarget("bead", "白色晶石", "白水双尖", "clear_quartz"),
    "白水方糖": MaterialTarget("bead", "白色晶石", "白水方糖", "clear_quartz"),
    "白水晶": MaterialTarget("bead", "白色晶石", "白水晶", "clear_quartz"),
    "白水桶珠": MaterialTarget("bead", "白色晶石", "白水桶珠", "clear_quartz"),
    "白水随型": MaterialTarget("bead", "白色晶石", "白水随型", "clear_quartz"),
    "粉水晶": MaterialTarget("bead", "粉红晶石", "粉水晶", "rose_quartz"),
    "红兔毛": MaterialTarget("bead", "兔毛水晶", "红兔毛水晶", "rabbit_hair_quartz"),
    "红幽灵": MaterialTarget("bead", "幽灵水晶", "红幽灵", "red_phantom"),
    "绿兔毛": MaterialTarget("bead", "兔毛水晶", "绿兔毛水晶", "rabbit_hair_quartz"),
    "绿发晶": MaterialTarget("bead", "绿色晶石", "绿发晶", "green_rutilated_quartz"),
    "绿幽灵": MaterialTarget("bead", "幽灵水晶", "绿幽灵", "green_phantom"),
    "蓝光灰月光": MaterialTarget("bead", "白色晶石", "蓝光灰月光", "moonstone"),
    "蓝光黑月光": MaterialTarget("bead", "白色晶石", "蓝光黑月光", "moonstone"),
    "西柚粉水晶": MaterialTarget("bead", "粉红晶石", "西柚粉水晶", "rose_quartz"),
    "钢丝彩兔毛": MaterialTarget("bead", "兔毛水晶", "钢丝彩兔毛", "rabbit_hair_quartz"),
    "银色条型吊坠": MaterialTarget("pendant", "吊坠", "银色条型吊坠", "silver_bar_pendant"),
    "闪灵胶花": MaterialTarget("bead", "胶花水晶", "闪灵胶花", "quartz_inclusion"),
    "马粉水晶": MaterialTarget("bead", "粉红晶石", "粉水晶马粉", "rose_quartz"),
    "黄兔毛": MaterialTarget("bead", "兔毛水晶", "黄兔毛水晶", "rabbit_hair_quartz"),
    "黑体灰月光": MaterialTarget("bead", "白色晶石", "黑体灰月光", "moonstone"),
    "黑闪灵": MaterialTarget("bead", "胶花水晶", "黑闪灵", "quartz_inclusion"),
    "红玛瑙": MaterialTarget("bead", "玛瑙", "红玛瑙", "mat_87f8ca3ff471c3a4"),
    "彩发晶": MaterialTarget("bead", "发晶", "彩发晶", "mat_02ed66d41de6605c"),
    "红铜发": MaterialTarget("bead", "发晶", "红铜发", "c58e5e42bc727230"),
    "薰衣草紫晶": MaterialTarget("bead", "紫水晶", "薰衣草紫晶", "mat_e6cb260f0670a194"),
    "红幽灵聚宝盆": MaterialTarget("bead", "幽灵水晶", "红幽灵聚宝盆", "red_phantom"),
    "鹰眼石": MaterialTarget("bead", "鹰眼石", "鹰眼石", "mat_c70ba9a2e0cef45b"),
    "黑发晶": MaterialTarget("bead", "发晶", "黑发晶", "black_rutilated_quartz"),
}

# PIL rotation degrees: positive is counterclockwise, negative is clockwise.
# Only rotate images whose drill opening is visibly not facing up.
ROTATION_OVERRIDES: dict[tuple[str, int], int] = {
    ("彩闪灵", 1): -90,
    ("猫眼蓝晶石", 6): 180,
    ("玉化蓝晶", 6): 180,
    ("玉化蓝晶", 7): 180,
    ("玉化蓝晶", 8): 180,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize the second flat transparent material image batch.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--app-root", type=Path, default=DEFAULT_APP_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument(
        "--unnamed-review-csv",
        type=Path,
        default=DEFAULT_UNNAMED_REVIEW,
        help="Optional CSV with filename/material_name rows for IMG_* files.",
    )
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--target-fill", type=float, default=0.985)
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--background-threshold", type=int, default=18)
    parser.add_argument("--edge-padding", type=int, default=2)
    parser.add_argument("--max-bytes", type=int, default=200_000)
    parser.add_argument("--quality", type=int, default=92)
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def clean_base_name(path: Path) -> str:
    stem = path.stem.strip()
    stem = re.sub(r"\(\d+\)$", "", stem)
    stem = re.sub(r"\d+$", "", stem)
    return stem.strip()


def has_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def digest_token(value: str, length: int = 8) -> str:
    import hashlib

    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def slugify(value: str, fallback: str) -> str:
    text = unicodedata.normalize("NFKD", value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or f"{fallback}-{digest_token(value)}"


def default_target(base_name: str) -> MaterialTarget:
    material_code = material_code_from_payload(
        {"top": "bead", "category": base_name, "series": base_name, "name": base_name}
    )
    if not material_code or material_code == "material":
        material_code = f"bead_{digest_token(base_name, 10)}"
    return MaterialTarget("bead", base_name, base_name, material_code)


def read_unnamed_review(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            filename = str(row.get("filename") or Path(str(row.get("source") or "")).name).strip()
            material_name = str(row.get("material_name") or "").strip()
            if filename and material_name:
                result[filename] = material_name
    return result


def read_unnamed_rotations(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    result: dict[str, int] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            filename = str(row.get("filename") or Path(str(row.get("source") or "")).name).strip()
            raw_degrees = str(row.get("rotation_degrees") or "").strip()
            if not filename or not raw_degrees:
                continue
            try:
                degrees = int(float(raw_degrees))
            except ValueError:
                continue
            if degrees % 360:
                result[filename] = degrees
    return result


def list_sources(source_root: Path, unnamed_map: dict[str, str]) -> tuple[dict[str, list[Path]], list[dict[str, str]]]:
    grouped: dict[str, list[Path]] = {}
    skipped: list[dict[str, str]] = []
    for path in sorted(source_root.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        base_name = clean_base_name(path)
        if not has_chinese(base_name) or GENERIC_NAME_RE.match(base_name):
            reviewed_name = unnamed_map.get(path.name, "").strip()
            if not reviewed_name:
                skipped.append({"source": str(path), "filename": path.name, "reason": "generic_or_unnamed"})
                continue
            base_name = clean_base_name(Path(reviewed_name))
        grouped.setdefault(base_name, []).append(path)
    return grouped, skipped


def make_review_sheet(rows: list[dict[str, object]], output: Path, columns: int = 5) -> None:
    if not rows:
        return
    thumb = 128
    gap = 12
    label_h = 44
    rows_count = math.ceil(len(rows) / columns)
    sheet = Image.new(
        "RGB",
        (columns * thumb + (columns + 1) * gap, rows_count * (thumb + label_h) + (rows_count + 1) * gap),
        "#eee9df",
    )
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        image = Image.open(str(row["app_webp"])).convert("RGBA")
        image.thumbnail((thumb - 10, thumb - 10), Image.Resampling.LANCZOS)
        col = index % columns
        line = index // columns
        x = gap + col * (thumb + gap)
        y = gap + line * (thumb + label_h + gap)
        cell = Image.new("RGB", (thumb, thumb), "#fbfaf7")
        cell.paste(image, ((thumb - image.width) // 2, (thumb - image.height) // 2), image)
        sheet.paste(cell, (x, y))
        label = f"{row['index']:02d} {row['source_group']}"[:18]
        draw.text((x + 5, y + thumb + 6), label, fill="#1c1a16")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def write_csv(rows: list[dict[str, object]], output: Path) -> None:
    if not rows:
        return
    fieldnames = [
        "top",
        "source_group",
        "category",
        "series",
        "final_category",
        "final_series",
        "index",
        "source",
        "app_webp",
        "rotation_degrees",
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


def copy_sources(grouped: dict[str, list[Path]], destination: Path) -> None:
    if destination.exists():
        safe_rmtree(destination, ROOT)
    for base_name, files in grouped.items():
        target = TARGETS.get(base_name, default_target(base_name))
        slug = slugify(target.final_series, target.material_code)
        folder = destination / slug
        folder.mkdir(parents=True, exist_ok=True)
        for index, source in enumerate(files, start=1):
            suffix = source.suffix.lower() or ".png"
            shutil.copy2(source, folder / f"{slug}-{index:02d}{suffix}")


def rotate_normalized_output(
    output: Path,
    args: argparse.Namespace,
    metrics: dict[str, object],
    rotation_degrees: int,
) -> dict[str, object]:
    image = Image.open(output).convert("RGBA")
    rotated = image.rotate(rotation_degrees, resample=Image.Resampling.BICUBIC, expand=False)
    file_size, quality = save_webp_under_size(rotated, output, args.quality, args.max_bytes)
    rotated_metrics = image_metrics(output, args.alpha_threshold)
    updated = dict(metrics)
    updated.update(
        {
            "output_width": rotated_metrics["width"],
            "output_height": rotated_metrics["height"],
            "output_bbox": rotated_metrics["bbox"],
            "fill_ratio": rotated_metrics["fill_ratio"],
            "center_offset_x": rotated_metrics["center_offset_x"],
            "center_offset_y": rotated_metrics["center_offset_y"],
            "file_size": file_size,
            "quality": quality,
        }
    )
    return updated


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

    unnamed_map = read_unnamed_review(args.unnamed_review_csv)
    unnamed_rotations = read_unnamed_rotations(args.unnamed_review_csv)
    grouped, skipped = list_sources(source_root, unnamed_map)
    all_rows: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    summary: list[dict[str, object]] = []

    for base_name, files in sorted(grouped.items(), key=lambda item: item[0]):
        target = TARGETS.get(base_name, default_target(base_name))
        slug = slugify(target.final_series, target.material_code)
        app_dir = args.app_root / slug
        report_dir = args.report_root / slug
        app_dir.mkdir(parents=True, exist_ok=True)
        report_dir.mkdir(parents=True, exist_ok=True)
        manifest: list[dict[str, object]] = []
        print(
            f"processing source={base_name} -> top={target.top} category={target.final_category} "
            f"series={target.final_series} files={len(files)}",
            flush=True,
        )
        for index, source in enumerate(files, start=1):
            output = app_dir / f"{slug}-{index:02d}.webp"
            try:
                metrics, warnings = normalize_one(source, output, args)
            except Exception as exc:
                failures.append({"source": str(source), "source_group": base_name, "reason": str(exc)})
                continue
            rotation_degrees = unnamed_rotations.get(source.name, ROTATION_OVERRIDES.get((base_name, index), 0))
            if rotation_degrees:
                metrics = rotate_normalized_output(output, args, metrics, rotation_degrees)
            row = {
                "top": target.top,
                "source_group": base_name,
                "category": target.final_category,
                "series": target.final_series,
                "series_label": target.final_series,
                "final_category": target.final_category,
                "final_series": target.final_series,
                "material_code": target.material_code,
                "slug": slug,
                "index": index,
                "source": str(source),
                "app_webp": str(output.resolve()),
                "rotation_degrees": rotation_degrees,
                "warning_text": ",".join(warnings),
                **metrics,
            }
            manifest.append(row)
            all_rows.append(row)
        (report_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        make_contact_sheet(manifest, report_dir / "_contact-sheet.jpg")
        make_review_sheet(manifest, report_dir / "_review-sheet.jpg")
        summary.append(
            {
                "source_group": base_name,
                "final_category": target.final_category,
                "final_series": target.final_series,
                "top": target.top,
                "material_code": target.material_code,
                "slug": slug,
                "processed": len(manifest),
                "failures": len([item for item in failures if item["source_group"] == base_name]),
                "warnings": sum(1 for item in manifest if item.get("warning_text")),
            }
        )

    make_contact_sheet(all_rows, args.report_root / "_contact-sheet-all.jpg", columns=8)
    make_review_sheet(all_rows, args.report_root / "_review-sheet-all.jpg", columns=8)
    write_csv(all_rows, args.report_root / "_qa.csv")
    (args.report_root / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.report_root / "_skipped.json").write_text(
        json.dumps(skipped, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if failures:
        (args.report_root / "_failures.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(
        f"processed={len(all_rows)} groups={len(summary)} skipped={len(skipped)} "
        f"failures={len(failures)} warnings={sum(1 for item in all_rows if item.get('warning_text'))}"
    )
    print(f"app_root={args.app_root.resolve()}")
    print(f"report_root={args.report_root.resolve()}")


if __name__ == "__main__":
    main()
