from pathlib import Path

from PIL import Image, ImageDraw

src = Path(".codex/acceptance-shots")
files = [
    "home",
    "custom-mode",
    "assessment-guide",
    "assessment",
    "report",
    "workspace",
    "community",
    "search",
    "cart",
    "profile",
    "my-plans",
    "favorites",
    "order-list",
    "daily-energy",
]
thumb_w, thumb_h = 220, 420
cols = 4
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + 34)), "white")
draw = ImageDraw.Draw(sheet)

for idx, name in enumerate(files):
    img = Image.open(src / f"{name}.png").convert("RGB")
    img.thumbnail((thumb_w, thumb_h), Image.LANCZOS)
    col = idx % cols
    row = idx // cols
    x = col * thumb_w + (thumb_w - img.width) // 2
    y = row * (thumb_h + 34) + 24
    draw.text((col * thumb_w + 8, row * (thumb_h + 34) + 4), name, fill=(0, 0, 0))
    sheet.paste(img, (x, y))

sheet.save(src / "contact-sheet.jpg", quality=92)
