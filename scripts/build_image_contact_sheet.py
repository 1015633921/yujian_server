from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a numbered contact sheet for image QA.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--thumb-width", type=int, default=220)
    parser.add_argument("--thumb-height", type=int, default=300)
    parser.add_argument("--columns", type=int, default=4)
    args = parser.parse_args()

    files = sorted(path for path in args.source.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)
    if not files:
        raise SystemExit(f"No images found in {args.source}")

    label_height = 34
    cell_width = args.thumb_width + 20
    cell_height = args.thumb_height + label_height + 16
    rows = math.ceil(len(files) / args.columns)
    sheet = Image.new("RGB", (args.columns * cell_width, rows * cell_height), "#f7f4ee")
    draw = ImageDraw.Draw(sheet)

    for index, path in enumerate(files, start=1):
        image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        image.thumbnail((args.thumb_width, args.thumb_height), Image.Resampling.LANCZOS)
        x0 = ((index - 1) % args.columns) * cell_width
        y0 = ((index - 1) // args.columns) * cell_height
        sheet.paste(image, (x0 + (cell_width - image.width) // 2, y0 + 8))
        draw.text((x0 + 10, y0 + args.thumb_height + 14), f"{index:02d}", fill="#171411")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, quality=92)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
