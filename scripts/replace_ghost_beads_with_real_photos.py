from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from generate_single_beads_from_references import detect_best_circle


SOURCE_DIR = Path(r"C:\Users\10156\Downloads\图片类")
OUTPUT_DIR = Path("outputs/宇涧水晶单珠白底图_100款")
SIZE = 1024
BEAD_SIZE = 720

SOURCES = {
    "四季幽灵": "四季幽灵.png",
    "巴西白幽灵千层水晶": "巴西白幽灵千层水晶.jpg",
    "巴西白幽灵水晶半盆": "巴西白幽灵水晶半盆.jpg",
    "幽灵水晶": "幽灵水晶各种形态.jpg",
    "幽灵水晶各种形态": "幽灵水晶各种形态.jpg",
    "彩幽灵蛋面": "彩幽灵蛋面.jpg",
    "彩幽灵魔盒": "彩幽灵魔盒.jpg",
    "白幽灵水晶高品": "白幽灵水晶高品.jpg",
    "粉幽灵": "粉幽灵.jpg",
    "紫幽灵": "紫幽灵.jpg",
    "红幽灵": "红幽灵.jpg",
    "红幽灵聚宝盆": "红幽灵聚宝盆.jpg",
    "绿幽灵": "绿幽灵2.jpg",
    "雪花白幽灵水晶": "雪花白幽灵水晶.jpg",
    "黄幽灵": "黄幽灵.jpg",
}

# 单颗实拍图可直接使用更准确的人工坐标；其余由圆检测选择。
FORCED = {
    "四季幽灵": (400, 505, 285),
    "巴西白幽灵千层水晶": (750, 1050, 340),
    "巴西白幽灵水晶半盆": (1100, 850, 500),
    "幽灵水晶": (680, 370, 120),
    "幽灵水晶各种形态": (850, 1650, 180),
    "彩幽灵蛋面": (1050, 330, 125),
    "彩幽灵魔盒": (335, 330, 135),
    "白幽灵水晶高品": (1000, 965, 500),
    "粉幽灵": (1450, 1500, 245),
    "紫幽灵": (1600, 1340, 1010),
    "红幽灵聚宝盆": (1040, 1100, 500),
    "绿幽灵": (1360, 1030, 580),
    "黄幽灵": (1010, 850, 540),
}


def locate_output(name: str) -> Path:
    matches = list(OUTPUT_DIR.glob(f"*_{name}.png"))
    if len(matches) != 1:
        raise ValueError(f"{name} 对应成品文件数量异常：{len(matches)}")
    return matches[0]


def crop_real_bead(source: Path, cx: int, cy: int, radius: int) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
    radius = max(20, int(radius * 0.96))
    crop = image.crop((cx - radius, cy - radius, cx + radius, cy + radius))
    crop = crop.resize((BEAD_SIZE, BEAD_SIZE), Image.Resampling.LANCZOS)
    mask = Image.new("L", (BEAD_SIZE, BEAD_SIZE), 0)
    ImageDraw.Draw(mask).ellipse((2, 2, BEAD_SIZE - 3, BEAD_SIZE - 3), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.1))
    bead = Image.new("RGBA", (BEAD_SIZE, BEAD_SIZE), (255, 255, 255, 0))
    bead.paste(crop, (0, 0), mask)
    return bead


def render(bead: Image.Image, output: Path) -> None:
    canvas = Image.new("RGBA", (SIZE, SIZE), "white")
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    draw.ellipse((250, 790, 775, 895), fill=(62, 54, 47, 32))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(28)))
    bead_x = (SIZE - BEAD_SIZE) // 2
    bead_y = 145
    canvas.alpha_composite(bead, (bead_x, bead_y))
    hole = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(hole)
    hole_y = bead_y + 72
    draw.ellipse((468, hole_y - 18, 556, hole_y + 18), fill=(45, 43, 40, 150), outline=(255, 255, 255, 135), width=3)
    draw.ellipse((486, hole_y - 7, 538, hole_y + 8), fill=(220, 218, 212, 165))
    canvas.alpha_composite(hole.filter(ImageFilter.GaussianBlur(0.7)))
    canvas.convert("RGB").save(output, quality=97)


def main() -> None:
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, source_name in SOURCES.items():
        source = SOURCE_DIR / source_name
        if name in FORCED:
            cx, cy, radius = FORCED[name]
            method = "real-photo-manual"
        else:
            detection = detect_best_circle(source)
            cx, cy, radius = round(detection.center_x), round(detection.center_y), round(detection.radius)
            method = f"real-photo-{detection.method}"
        output = locate_output(name)
        render(crop_real_bead(source, cx, cy, radius), output)
        for row in manifest:
            if row["name"] == name:
                row["source"] = method
                row["reference"] = source_name
                row["circle"] = [cx, cy, radius]
                break
        print(f"{name} <- {source_name} ({cx},{cy},r={radius})")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
