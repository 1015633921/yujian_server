from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path("outputs/宇涧水晶单珠白底图_100款")


def build(rows: list[dict], destination: Path, columns: int, thumb: int = 250) -> None:
    label_height = 34
    rows_count = (len(rows) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb, rows_count * (thumb + label_height)), "#f3f1ed")
    draw = ImageDraw.Draw(sheet)
    for offset, row in enumerate(rows):
        image = Image.open(ROOT / row["file"]).convert("RGB")
        image.thumbnail((thumb - 10, thumb - 10), Image.Resampling.LANCZOS)
        x = offset % columns * thumb + (thumb - image.width) // 2
        y = offset // columns * (thumb + label_height) + (thumb - image.height) // 2
        sheet.paste(image, (x, y))
        draw.text((x + 6, y + image.height - 24), f"{row['index']:03d}", fill="#3d3934")
    sheet.save(destination, quality=93)


def main() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    build(manifest, ROOT / "_全部100款总览.jpg", columns=8, thumb=190)
    ghosts = [row for row in manifest if "幽灵" in row["name"]]
    build(ghosts, ROOT / "_幽灵类总览.jpg", columns=4, thumb=300)
    print(f"all={len(manifest)} ghosts={len(ghosts)}")


if __name__ == "__main__":
    main()
