from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from render_blender_bead import (  # noqa: E402
    add_camera,
    add_lighting,
    configure_render,
    create_bead,
    hex_to_rgba,
    make_glass_material,
    reset_scene,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch render bead catalog PNGs in Blender.")
    parser.add_argument("--catalog", default="data/bead_render_catalog.tsv")
    parser.add_argument("--output-dir", default="static/materials/rendered_beads")
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--samples", type=int, default=40)
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args(get_script_args())


def get_script_args() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1 :]


def read_catalog(path: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        category, series = [part.strip() for part in line.split("\t", 1)]
        if series in seen:
            continue
        seen.add(series)
        pairs.append((category, series))
    return pairs


def profile_for(category: str, series: str) -> dict[str, object]:
    text = f"{category}{series}"

    rules: list[tuple[tuple[str, ...], str, float, float]] = [
        (("黑", "墨", "耀", "黑晶", "黑发", "黑金", "鹰眼"), "#17181c", 0.1, 0.72),
        (("白", "奶", "阿塞", "贝母", "方解"), "#eef4f4", 0.18, 0.35),
        (("蓝", "海蓝", "天河", "青金", "堇青", "蓝纹", "蓝铜"), "#4d9fbd", 0.16, 0.5),
        (("紫", "舒俱来", "紫锂", "紫玉", "超七"), "#805bb4", 0.18, 0.55),
        (("黄", "金", "钛", "太阳", "虎眼", "桂花"), "#d9a340", 0.15, 0.58),
        (("粉", "草莓", "红纹", "摩根", "蔷薇", "樱花"), "#e69aa8", 0.2, 0.45),
        (("红", "南虹", "珊瑚", "石榴", "红铜"), "#b64a42", 0.18, 0.62),
        (("绿", "孔雀", "葡萄", "东陵", "幽灵"), "#5b9a6e", 0.18, 0.5),
        (("茶", "烟", "浅茶", "深茶"), "#7b5d48", 0.13, 0.55),
        (("月光", "萤石", "彩", "极光", "闪灵"), "#9aa8d6", 0.16, 0.48),
        (("玉", "岫玉", "和田"), "#d9e6d0", 0.28, 0.28),
    ]
    for keys, color, roughness, transmission in rules:
        if any(key in text for key in keys):
            return {"color": color, "roughness": roughness, "transmission": transmission}
    return {"color": "#b9ada0", "roughness": 0.18, "transmission": 0.42}


def tune_material(material: bpy.types.Material, transmission: float) -> None:
    node = material.node_tree.nodes.get("Principled BSDF")
    if not node:
        return
    if "Transmission Weight" in node.inputs:
        node.inputs["Transmission Weight"].default_value = transmission
    if "Alpha" in node.inputs:
        node.inputs["Alpha"].default_value = 0.92 if transmission < 0.55 else 0.86


def render_one(category: str, series: str, output: Path, size: int, samples: int) -> None:
    profile = profile_for(category, series)
    reset_scene()
    material = make_glass_material(
        series,
        hex_to_rgba(str(profile["color"])),
        ior=1.54,
        roughness=float(profile["roughness"]),
    )
    tune_material(material, float(profile["transmission"]))
    create_bead(material)
    add_lighting()
    add_camera()
    configure_render(output, size=size, samples=samples)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    args = parse_args()
    catalog = Path(args.catalog)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pairs = read_catalog(catalog)
    if args.limit:
        pairs = pairs[: args.limit]

    for index, (category, series) in enumerate(pairs, start=1):
        output = output_dir / f"{series}.png"
        print(f"[{index}/{len(pairs)}] render {category} / {series} -> {output}")
        render_one(category, series, output, size=args.size, samples=args.samples)

    print(f"rendered={len(pairs)} output={output_dir.resolve()}")


if __name__ == "__main__":
    main()
