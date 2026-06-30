from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = Path(r"C:\Users\10156\xwechat_files\wxid_c62jovsqi9tu22_36ef\msg\file\2026-06\水晶图片")
OUTPUT_CSV = ROOT / "outputs" / "wps-bead-review.csv"

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif", ""}
GENERIC_PHOTO_RE = re.compile(r"^(IMG|DSC|PXL|WX|MMEXPORT|SCREENSHOT)[_ -]?\d+", re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a manual review CSV for WPS AI bead cutout workflow.")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--out", type=Path, default=OUTPUT_CSV)
    return parser.parse_args()


def clean_name(value: str) -> str:
    name = Path(value).stem.strip()
    name = re.sub(r"(?:图片|照片|实拍图?)$", "", name)
    name = re.sub(r"[\s_-]*\d+$", "", name)
    return name.strip()


def is_generic(value: str) -> bool:
    return bool(GENERIC_PHOTO_RE.match(Path(value).stem))


def iter_images(source_root: Path):
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        rel = path.relative_to(source_root)
        if len(rel.parts) < 2:
            continue
        yield path, rel


def main() -> None:
    args = parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for path, rel in iter_images(args.source_root):
        folder = rel.parts[0]
        stem = clean_name(path.name)
        suggested_series = folder if is_generic(path.name) or not stem else stem
        rows.append(
            {
                "source_rel": str(rel).replace("\\", "/"),
                "wps_expected_rel": str(rel.with_suffix(".png")).replace("\\", "/"),
                "suggested_category": folder,
                "suggested_series": suggested_series,
                "final_category": folder,
                "final_series": suggested_series,
                "material_code": "",
                "approved": "",
                "skip": "",
                "notes": "",
            }
        )
    with args.out.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote={args.out} rows={len(rows)}")


if __name__ == "__main__":
    main()
