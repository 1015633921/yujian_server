from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


DEFAULT_SOURCE = Path(r"C:\Users\10156\Pictures\水晶珠子\珠子抠图\WPS图片批量处理")
DEFAULT_OUTPUT = Path("generated/wps-transparent-beads")


def main() -> None:
    parser = argparse.ArgumentParser(description="为 WPS 白底圆珠生成柔和透明背景。")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--only", default="", help="逗号分隔的文件名或珠子名")
    parser.add_argument("--feather", type=float, default=3.0, help="边缘羽化像素")
    parser.add_argument("--inset", type=float, default=8.0, help="透明边界向珠体内收像素")
    parser.add_argument("--size", type=int, default=640, help="输出正方形图片尺寸")
    parser.add_argument("--padding", type=float, default=0.025, help="珠体四周透明留白比例")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    only = {item.strip() for item in args.only.split(",") if item.strip()}
    files = [
        path
        for path in sorted(args.source.iterdir())
        if path.is_file()
        and path.suffix.lower() == ".png"
        and (not only or path.name in only or strip_number(path.stem) in only)
    ]
    for path in files:
        make_transparent(
            path,
            args.output / path.name,
            feather=args.feather,
            inset=args.inset,
            output_size=args.size,
            padding_ratio=args.padding,
        )
    print(f"processed={len(files)} output={args.output.resolve()}")


def make_transparent(
    source: Path,
    output: Path,
    feather: float,
    inset: float,
    output_size: int = 640,
    padding_ratio: float = 0.025,
) -> None:
    image = Image.open(source).convert("RGBA")
    alpha = image.getchannel("A")
    if alpha.getextrema() == (255, 255):
        bbox = find_subject_bbox(image.convert("RGB"))
        if bbox is None:
            raise ValueError(f"Cannot locate bead: {source}")
        left, top, right, bottom = bbox
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        radius = max(right - left, bottom - top) / 2 - inset
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse(
            (
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
            ),
            fill=255,
        )
        if feather > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=max(0.4, feather)))
        image.putalpha(mask)

    subject_bbox = image.getchannel("A").getbbox()
    if subject_bbox is None:
        raise ValueError(f"Cannot locate visible bead pixels: {source}")
    subject = image.crop(subject_bbox)
    side = max(subject.size)
    padding = max(2, round(side * padding_ratio))
    square = Image.new("RGBA", (side + padding * 2, side + padding * 2), (0, 0, 0, 0))
    square.alpha_composite(
        subject,
        ((square.width - subject.width) // 2, (square.height - subject.height) // 2),
    )
    square = square.resize((output_size, output_size), Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    square.save(output, "PNG", optimize=True)


def find_subject_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    width, height = image.size
    pixels = image.load()
    xs: list[int] = []
    ys: list[int] = []
    # 白底像素接近 255；珠子即使很透明，也存在灰度或色差。
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if min(r, g, b) < 246 or max(r, g, b) - min(r, g, b) > 5:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def strip_number(value: str) -> str:
    return re.sub(r"^\d+[_\-\s]*", "", value).strip()


if __name__ == "__main__":
    main()
