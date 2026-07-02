from __future__ import annotations

import argparse
import csv
import math
import re
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET_DIRS = (
    ROOT / "static" / "materials" / "beads",
    ROOT / "static" / "materials" / "rendered_beads",
)
DEFAULT_REPORT_ROOT = ROOT / "outputs" / "phantom-bead-hole-rotation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rotate phantom bead PNG assets so the drilled opening becomes vertical."
    )
    parser.add_argument(
        "--target-dir",
        action="append",
        type=Path,
        help="Directory to scan non-recursively. Defaults to app bead PNG asset directories.",
    )
    parser.add_argument("--name-regex", default=r"幽灵|满天星|phantom|ghost|youling|starry|mantianxing")
    parser.add_argument(
        "--direction",
        choices=("clockwise", "counterclockwise"),
        default="clockwise",
    )
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--apply", action="store_true", help="Overwrite matched PNGs.")
    return parser.parse_args()


def safe_relative(path: Path) -> Path:
    resolved = path.resolve()
    root = ROOT.resolve()
    if resolved == root or root not in resolved.parents:
        raise SystemExit(f"Refusing path outside workspace: {resolved}")
    return resolved.relative_to(root)


def selected_files(target_dirs: list[Path], name_regex: str) -> list[Path]:
    pattern = re.compile(name_regex, re.I)
    files: list[Path] = []
    for directory in target_dirs:
        resolved_dir = directory.resolve()
        if not resolved_dir.exists():
            continue
        if ROOT.resolve() not in resolved_dir.parents:
            raise SystemExit(f"Refusing target directory outside workspace: {resolved_dir}")
        files.extend(
            sorted(
                path
                for path in resolved_dir.glob("*.png")
                if pattern.search(path.name)
            )
        )
    return files


def rotate_image(image: Image.Image, direction: str) -> Image.Image:
    transposed = ImageOps.exif_transpose(image)
    if direction == "clockwise":
        return transposed.transpose(Image.Transpose.ROTATE_270)
    return transposed.transpose(Image.Transpose.ROTATE_90)


def copy_original(path: Path, backup_root: Path) -> Path:
    rel = safe_relative(path)
    destination = backup_root / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    return destination


def make_contact_sheet(rows: list[dict[str, str]], key: str, destination: Path) -> None:
    if not rows:
        return
    thumb = 126
    label_h = 28
    gap = 12
    columns = min(6, max(1, len(rows)))
    sheet_rows = math.ceil(len(rows) / columns)
    sheet = Image.new(
        "RGB",
        (
            columns * thumb + (columns + 1) * gap,
            sheet_rows * (thumb * 2 + label_h) + (sheet_rows + 1) * gap,
        ),
        "#eee9df",
    )
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        path = Path(row[key])
        image = Image.open(path).convert("RGBA")
        image.thumbnail((thumb - 10, thumb - 10), Image.Resampling.LANCZOS)
        col = index % columns
        line = index // columns
        x = gap + col * (thumb + gap)
        y = gap + line * (thumb * 2 + label_h + gap)
        for offset, bg in enumerate(("#f8f7f2", "#242424")):
            cell = Image.new("RGB", (thumb, thumb), bg)
            cell.paste(image, ((thumb - image.width) // 2, (thumb - image.height) // 2), image)
            sheet.paste(cell, (x, y + offset * thumb))
        draw.text((x + 6, y + thumb * 2 + 7), f"{index + 1:02d}", fill="#1c1a16")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=92)


def write_manifest(rows: list[dict[str, str]], destination: Path) -> None:
    if not rows:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "path",
        "backup_path",
        "direction",
        "width",
        "height",
        "before_bytes",
        "after_bytes",
    ]
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    target_dirs = [path.resolve() for path in (args.target_dir or DEFAULT_TARGET_DIRS)]
    files = selected_files(target_dirs, args.name_regex)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root = args.report_root.resolve() / timestamp
    backup_root = run_root / "before"
    rows: list[dict[str, str]] = []

    for path in files:
        with Image.open(path) as source:
            original = ImageOps.exif_transpose(source)
            rotated = rotate_image(original, args.direction)
            if rotated.size != original.size:
                raise SystemExit(f"Unexpected size change for {path}: {original.size} -> {rotated.size}")
            backup_path = copy_original(path, backup_root) if args.apply else path
            before_bytes = path.stat().st_size
            if args.apply:
                rotated.save(path, "PNG", optimize=True)
            after_bytes = path.stat().st_size if args.apply else before_bytes
        rows.append(
            {
                "path": str(path),
                "backup_path": str(backup_path),
                "direction": args.direction,
                "width": str(rotated.width),
                "height": str(rotated.height),
                "before_bytes": str(before_bytes),
                "after_bytes": str(after_bytes),
            }
        )

    write_manifest(rows, run_root / "manifest.csv")
    if args.apply:
        make_contact_sheet(rows, "backup_path", run_root / "before-contact-sheet.jpg")
        make_contact_sheet(rows, "path", run_root / "after-contact-sheet.jpg")

    print(f"matched={len(files)}")
    print(f"applied={bool(args.apply)}")
    print(f"direction={args.direction}")
    print(f"report_root={run_root}")


if __name__ == "__main__":
    main()
