from __future__ import annotations

import argparse
import math
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a transparent crystal bead PNG in Blender.")
    parser.add_argument("--output", default="generated/blender_beads/white_crystal.png")
    parser.add_argument("--blend-output", default="generated/blender_beads/crystal_bead_scene.blend")
    parser.add_argument("--name", default="white_crystal")
    parser.add_argument("--color", default="#ffffff")
    parser.add_argument("--ior", type=float, default=1.54)
    parser.add_argument("--roughness", type=float, default=0.015)
    parser.add_argument("--size", type=int, default=1024)
    parser.add_argument("--samples", type=int, default=128)
    return parser.parse_args(get_script_args())


def get_script_args() -> list[str]:
    import sys

    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1 :]


def hex_to_rgba(value: str) -> tuple[float, float, float, float]:
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ValueError(f"Invalid hex color: {value}")
    return (
        int(text[0:2], 16) / 255,
        int(text[2:4], 16) / 255,
        int(text[4:6], 16) / 255,
        1.0,
    )


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def make_glass_material(name: str, color: tuple[float, float, float, float], ior: float, roughness: float) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.blend_method = "BLEND"
    material.use_screen_refraction = True

    nodes = material.node_tree.nodes
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = (260, 0)
    shader = nodes.new(type="ShaderNodeBsdfPrincipled")
    shader.location = (0, 0)

    set_input(shader, "Base Color", color)
    set_input(shader, "Alpha", 0.9)
    set_input(shader, "Roughness", roughness)
    set_input(shader, "IOR", ior)
    set_input(shader, "Metallic", 0.0)
    set_input(shader, "Specular IOR Level", 0.62)
    set_input(shader, "Transmission Weight", 0.32)
    set_input(shader, "Coat Weight", 0.18)
    set_input(shader, "Coat Roughness", 0.16)

    material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def set_input(node: bpy.types.Node, name: str, value: object) -> None:
    if name in node.inputs:
        node.inputs[name].default_value = value


def create_bead(material: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=1.0, location=(0, 0, 0))
    bead = bpy.context.object
    bead.name = "Crystal Bead"
    bead.data.materials.append(material)
    bpy.ops.object.shade_smooth()

    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.18, depth=2.4, location=(0, 0, 0.08), rotation=(math.pi / 2, 0, 0))
    cutter = bpy.context.object
    cutter.name = "Bead Hole Cutter"

    modifier = bead.modifiers.new("Thread hole", "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.object = cutter
    bpy.context.view_layer.objects.active = bead
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)

    return bead


def add_lighting() -> None:
    bpy.context.scene.world = bpy.data.worlds.new("Soft Studio World")
    bpy.context.scene.world.color = (0.94, 0.95, 0.96)

    lights = [
        ("Key softbox", (-2.8, -3.2, 3.4), 420, 6.5),
        ("Top glint", (-0.55, -1.05, 3.8), 95, 0.78),
    ]
    for name, location, energy, size in lights:
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.name = name
        light.data.energy = energy
        light.data.size = size

    # A single soft reflection card keeps the bead readable without making it look like black glass.
    for name, location, rotation, scale, color in [
        ("Soft white reflection", (-1.15, -0.62, 0.62), (0, math.radians(78), math.radians(0)), (0.34, 0.48, 1.0), (0.76, 0.82, 0.88, 1)),
    ]:
        bpy.ops.mesh.primitive_plane_add(size=1.8, location=location, rotation=rotation)
        card = bpy.context.object
        card.name = name
        card.scale = scale
        mat = bpy.data.materials.new(f"{name} material")
        mat.diffuse_color = color
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = color
            bsdf.inputs["Roughness"].default_value = 0.28
        card.data.materials.append(mat)
        card.visible_camera = False
        card.visible_diffuse = False
        card.visible_transmission = True
        card.visible_glossy = True


def add_camera() -> None:
    bpy.ops.object.camera_add(location=(0, -4.6, 0.35), rotation=(math.radians(86), 0, 0))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.55
    bpy.context.scene.camera = camera


def configure_render(output: Path, size: int, samples: int) -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.compression = 15
    scene.render.filepath = str(output.resolve())


def main() -> None:
    args = parse_args()
    output = Path(args.output)
    blend_output = Path(args.blend_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    blend_output.parent.mkdir(parents=True, exist_ok=True)

    reset_scene()
    material = make_glass_material(args.name, hex_to_rgba(args.color), args.ior, args.roughness)
    create_bead(material)
    add_lighting()
    add_camera()
    configure_render(output, args.size, args.samples)

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_output.resolve()))
    bpy.ops.render.render(write_still=True)
    print(f"rendered={output.resolve()}")
    print(f"blend={blend_output.resolve()}")


if __name__ == "__main__":
    main()
