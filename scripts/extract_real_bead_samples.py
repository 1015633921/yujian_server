from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps


SOURCE = Path(r"C:\Users\10156\Downloads\图片类")
OUTPUT = Path("outputs/real-bead-samples")
SIZE = 1024
BEAD_SIZE = 720


# 坐标均来自用户提供的真实照片，只裁切实拍珠体，不生成或改写矿物包体。
SAMPLES = {
    "绿幽灵": ("绿幽灵3.jpg", 415, 1901, 345),
    "四季幽灵": ("四季幽灵.jpg", 1850, 750, 220),
    "白幽灵水晶高品": ("白幽灵水晶高品.jpg", 1000, 965, 525),
    "红幽灵": ("红幽灵.jpg", 1120, 1000, 270),
}


def extract_circle(source: Path, cx: int, cy: int, radius: int) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
    box = (cx - radius, cy - radius, cx + radius, cy + radius)
    crop = image.crop(box).resize((BEAD_SIZE, BEAD_SIZE), Image.Resampling.LANCZOS)
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).ellipse((2, 2, BEAD_SIZE - 3, BEAD_SIZE - 3), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    result = Image.new("RGBA", crop.size, (255, 255, 255, 0))
    result.paste(crop, (0, 0), mask)
    return result


def add_drilled_hole(canvas: Image.Image, center_x: int, center_y: int, radius: int) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    hole_y = center_y - int(radius * 0.83)
    width = int(radius * 0.28)
    height = int(radius * 0.13)
    draw.ellipse(
        (center_x - width // 2, hole_y - height // 2, center_x + width // 2, hole_y + height // 2),
        fill=(39, 39, 37, 125),
        outline=(255, 255, 255, 120),
        width=3,
    )
    draw.ellipse(
        (
            center_x - int(width * 0.30),
            hole_y - int(height * 0.20),
            center_x + int(width * 0.30),
            hole_y + int(height * 0.20),
        ),
        fill=(210, 209, 204, 145),
    )
    layer = layer.filter(ImageFilter.GaussianBlur(0.8))
    canvas.alpha_composite(layer)


def render(name: str, source_name: str, cx: int, cy: int, radius: int) -> None:
    canvas = Image.new("RGBA", (SIZE, SIZE), "white")
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    draw.ellipse((245, 790, 790, 902), fill=(55, 48, 42, 36))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    canvas.alpha_composite(shadow)

    bead = extract_circle(SOURCE / source_name, cx, cy, radius)
    x = (SIZE - BEAD_SIZE) // 2
    y = 145
    canvas.alpha_composite(bead, (x, y))
    add_drilled_hole(canvas, SIZE // 2, y + BEAD_SIZE // 2, BEAD_SIZE // 2)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(OUTPUT / f"{name}.png", quality=97)


def main() -> None:
    for name, (source_name, cx, cy, radius) in SAMPLES.items():
        render(name, source_name, cx, cy, radius)
        print(f"{name} <- {source_name}")


if __name__ == "__main__":
    main()
