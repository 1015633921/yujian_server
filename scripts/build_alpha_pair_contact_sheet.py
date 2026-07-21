from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a pair-oriented contact sheet from transparent product cutouts."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pairs-per-row", type=int, default=2)
    parser.add_argument("--cell-size", type=int, default=360)
    return parser.parse_args()


def natural_key(path: Path) -> tuple[object, ...]:
    return tuple(
        int(token) if token.isdigit() else token.lower()
        for token in re.split(r"(\d+)", path.name)
    )


def fitted_cutout(path: Path, cell_size: int) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        raise ValueError(f"Transparent image has no visible content: {path}")
    subject = image.crop(bbox)
    subject.thumbnail((cell_size - 28, cell_size - 28), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (cell_size, cell_size), "#202020")
    x = (cell_size - subject.width) // 2
    y = (cell_size - subject.height) // 2
    canvas.paste(subject, (x, y), subject)
    return canvas


def main() -> None:
    args = parse_args()
    images = sorted(
        (path for path in args.source.iterdir() if path.suffix.lower() in {".png", ".webp"}),
        key=natural_key,
    )
    if not images or len(images) % 2:
        raise SystemExit("The source directory must contain a non-empty even number of images.")

    pairs = [images[index : index + 2] for index in range(0, len(images), 2)]
    label_height = 52
    pair_width = args.cell_size * 2
    rows = (len(pairs) + args.pairs_per_row - 1) // args.pairs_per_row
    sheet = Image.new(
        "RGB",
        (pair_width * args.pairs_per_row, rows * (args.cell_size + label_height)),
        "#f2eee6",
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)

    for pair_index, pair in enumerate(pairs, start=1):
        column = (pair_index - 1) % args.pairs_per_row
        row = (pair_index - 1) // args.pairs_per_row
        x = column * pair_width
        y = row * (args.cell_size + label_height)
        for image_index, path in enumerate(pair):
            sheet.paste(fitted_cutout(path, args.cell_size), (x + image_index * args.cell_size, y))
        label = f"{pair_index:02d}  {pair[0].name} + {pair[1].name}"
        draw.text((x + 12, y + args.cell_size + 14), label, fill="#171717", font=font)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, quality=94)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
