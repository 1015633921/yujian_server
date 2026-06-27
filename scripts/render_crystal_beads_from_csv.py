from __future__ import annotations

"""
Blender 批量水晶珠渲染脚本

用法示例：

blender --background --python scripts/render_crystal_beads_from_csv.py -- ^
  --csv "C:\\Users\\10156\\Desktop\\test.csv" ^
  --output-dir "static\\materials\\photo_beads" ^
  --hdri "D:\\HDRI\\studio_small_09_2k.hdr" ^
  --size 1024 ^
  --samples 128

CSV 列要求：
SKU_Name,Template_ID,Category_Desc,Hex_Color,IOR,Notes

核心设计：
- T1_Transparent：高透水晶，使用 Principled BSDF 的 Transmission/IOR 做物理折射。
- T5_Opaque：玉石玛瑙，关闭 Transmission，开启 Subsurface Scattering 做油润透光。
- T2/T3：如果提供模板 blend，则 Append 模板对象；否则降级为基础透明珠并加一点程序纹理。
"""

import argparse
import csv
import hashlib
import math
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import bpy


REQUIRED_COLUMNS = {"SKU_Name", "Template_ID", "Category_Desc", "Hex_Color", "IOR", "Notes"}


@dataclass(frozen=True)
class CrystalRow:
    sku_name: str
    template_id: str
    category_desc: str
    hex_color: str
    ior: float
    notes: str
    render_template: str = ""


def get_script_args() -> list[str]:
    """Blender 会把自身参数和脚本参数混在一起，-- 后面才是我们的参数。"""
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1 :]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="根据 CSV 批量渲染照片级水晶/半宝石珠子 PNG。")
    parser.add_argument("--csv", required=True, help="CSV 文件路径")
    parser.add_argument("--output-dir", required=True, help="PNG 输出目录")
    parser.add_argument("--hdri", default="", help="HDRI 环境贴图路径，推荐 .hdr 或 .exr")
    parser.add_argument("--size", type=int, default=1024, help="输出 PNG 尺寸，默认 1024x1024")
    parser.add_argument("--samples", type=int, default=128, help="Cycles 采样率，默认 128")
    parser.add_argument("--t2-template", default="", help="T2 幽灵/异象水晶模板 .blend，可选")
    parser.add_argument("--t3-template", default="", help="T3 发晶模板 .blend，可选")
    parser.add_argument("--template-object", default="", help="模板 blend 里的对象名；不填则追加所有 mesh")
    parser.add_argument("--limit", type=int, default=0, help="只渲染前 N 行，用于测试")
    parser.add_argument("--only", default="", help="只渲染指定 SKU，多个名称用逗号分隔")
    parser.add_argument("--skip-existing", action="store_true", help="输出文件已存在时跳过")
    parser.add_argument("--with-thread-hole", action="store_true", help="渲染真实穿线孔；小程序盘面素材建议默认不启用")
    return parser.parse_args(get_script_args())


def read_csv_rows(path: Path) -> list[CrystalRow]:
    """稳健读取 CSV：优先 utf-8-sig，再兼容 gb18030。"""
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = path.read_text(encoding=encoding)
            reader = csv.DictReader(text.splitlines())
            if not reader.fieldnames:
                raise ValueError("CSV 没有表头")
            missing = REQUIRED_COLUMNS - set(reader.fieldnames)
            if missing:
                raise ValueError(f"CSV 缺少列：{', '.join(sorted(missing))}")

            rows: list[CrystalRow] = []
            for line_no, raw in enumerate(reader, start=2):
                sku_name = (raw.get("SKU_Name") or "").strip()
                if not sku_name:
                    print(f"[WARN] 第 {line_no} 行 SKU_Name 为空，已跳过")
                    continue
                rows.append(
                    CrystalRow(
                        sku_name=sku_name,
                        template_id=(raw.get("Template_ID") or "").strip(),
                        category_desc=(raw.get("Category_Desc") or "").strip(),
                        hex_color=(raw.get("Hex_Color") or "#ffffff").strip(),
                        ior=parse_float(raw.get("IOR"), default=1.54),
                        notes=(raw.get("Notes") or "").strip(),
                        render_template=(raw.get("Render_Template") or "").strip(),
                    )
                )
            return rows
        except Exception as exc:  # noqa: BLE001 - 这里需要保留最后一次失败原因
            last_error = exc
    raise RuntimeError(f"无法读取 CSV：{path}，最后错误：{last_error}") from last_error


def parse_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def sanitize_filename(name: str) -> str:
    """Windows/COS 都更稳的文件名清理，中文会保留。"""
    safe = re.sub(r'[\\/:*?"<>|]+', "_", name).strip()
    return safe or "unnamed"


def infer_render_template(row: CrystalRow) -> str:
    """把大量 SKU 收敛到少数渲染母版，避免每种水晶维护一套模型。"""
    if row.render_template:
        return row.render_template

    text = f"{row.sku_name}{row.category_desc}{row.notes}"
    if row.template_id.startswith("T3") or any(key in text for key in ("发晶", "发丝", "金发", "银发", "铜发", "兔毛")):
        return "T3_Rutilated"
    if row.template_id.startswith("T2") or any(key in text for key in ("幽灵", "满天星", "骨干", "水胆")):
        return "T2_Ghost"
    if any(key in text for key in ("虎眼", "鹰眼", "猫眼")):
        return "TigerEye"
    if row.template_id.startswith("T4") and any(key in text for key in ("月光", "拉长", "晕彩", "蓝色晕")):
        return "Moonstone"
    if any(key in text for key in ("月光", "拉长石", "闪灵", "贝母")):
        return "Moonstone"
    if any(key in text for key in ("萤石", "超七", "极光", "碧玺", "彩")):
        return "Fluorite"
    if any(key in text for key in ("玛瑙", "胶花", "南虹", "阿拉善", "盐源", "樱花")):
        return "BandedAgate"
    if row.template_id == "T5_Opaque" or any(key in text for key in ("玉", "孔雀石", "绿松", "舒俱来")):
        return "T5_Opaque"
    if any(key in text for key in ("茶", "烟", "墨晶", "黑茶", "黑晶", "黑曜", "黑耀")):
        return "T1_Smoky"
    return "T1_Clear"


def stable_rng(text: str) -> random.Random:
    seed = int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:12], 16)
    return random.Random(seed)


def hex_to_rgba(value: str) -> tuple[float, float, float, float]:
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        print(f"[WARN] 非法颜色 {value!r}，已回退为白色")
        text = "ffffff"
    return (
        int(text[0:2], 16) / 255.0,
        int(text[2:4], 16) / 255.0,
        int(text[4:6], 16) / 255.0,
        1.0,
    )


def set_cycles_gpu(samples: int) -> None:
    """启用 Cycles + GPU。若当前机器没有可用 GPU，则自动回退 CPU，不中断渲染。"""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 16
    scene.cycles.transparent_max_bounces = 16
    scene.cycles.transmission_bounces = 12
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 8
    scene.cycles.caustics_reflective = True
    scene.cycles.caustics_refractive = True

    preferences = bpy.context.preferences.addons["cycles"].preferences
    device_types = ["OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"]
    enabled = False
    for device_type in device_types:
        try:
            preferences.compute_device_type = device_type
            preferences.get_devices()
            for device in preferences.devices:
                device.use = device.type != "CPU"
                enabled = enabled or device.use
            if enabled:
                scene.cycles.device = "GPU"
                print(f"[INFO] Cycles GPU 已启用：{device_type}")
                return
        except Exception:
            continue

    scene.cycles.device = "CPU"
    print("[WARN] 未发现可用 GPU，已回退到 CPU 渲染")


def configure_color_and_output(output_path: Path, size: int) -> None:
    scene = bpy.context.scene
    scene.render.film_transparent = True
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "16"
    scene.render.image_settings.compression = 15
    scene.render.filepath = str(output_path.resolve())

    # Filmic/AgX 会让高光更自然。不同 Blender 版本名字可能不同，逐个尝试。
    for transform in ("AgX", "Filmic", "Standard"):
        try:
            scene.view_settings.view_transform = transform
            break
        except TypeError:
            continue
    for look in ("AgX - Medium High Contrast", "Medium High Contrast", "None"):
        try:
            scene.view_settings.look = look
            break
        except TypeError:
            continue
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def setup_world_hdri(hdri_path: Path | None) -> None:
    """使用 HDRI 提供真实反射/折射环境，同时 Film Transparent 保证背景不输出。"""
    world = bpy.context.scene.world or bpy.data.worlds.new("Crystal HDRI World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputWorld")
    background = nodes.new(type="ShaderNodeBackground")
    background.inputs["Strength"].default_value = 1.35
    links.new(background.outputs["Background"], output.inputs["Surface"])

    if hdri_path and hdri_path.exists():
        env = nodes.new(type="ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(str(hdri_path.resolve()))
        links.new(env.outputs["Color"], background.inputs["Color"])
        print(f"[INFO] 已加载 HDRI：{hdri_path}")
    else:
        # 没给 HDRI 时也要有明亮世界光，否则透明水晶会像黑玻璃。
        background.inputs["Color"].default_value = (0.86, 0.88, 0.9, 1.0)
        if hdri_path:
            print(f"[WARN] HDRI 不存在：{hdri_path}，已使用默认影棚世界光")


def add_studio_lights() -> None:
    """HDRI 之外补一盏柔光，保证缩略图层次稳定。"""
    for name, location, energy, size in [
        ("Large softbox", (-2.5, -3.0, 3.0), 350, 5.5),
        ("Small top glint", (-0.55, -1.1, 3.5), 60, 0.8),
    ]:
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.name = name
        light.data.energy = energy
        light.data.size = size


def add_reflection_cards() -> None:
    """
    产品摄影里水晶/玻璃必须有可控反射卡，否则透明背景上会显得很平。

    这些卡片对相机不可见，只参与 glossy/transmission 反射折射：
    - 左上白卡：给主高光
    - 右侧暗卡：压出边缘轮廓
    - 下方暖卡：让珠子底部有一点厚度
    """
    cards = [
        ("white softbox card", (-1.25, -0.74, 0.72), (0, math.radians(75), 0), (0.44, 0.62, 1), (0.95, 0.97, 1.0, 1)),
        ("dark edge card", (1.34, -0.58, 0.28), (0, math.radians(-77), 0), (0.34, 0.9, 1), (0.035, 0.04, 0.05, 1)),
        ("warm lower card", (0.0, -0.82, -0.92), (math.radians(82), 0, 0), (1.0, 0.24, 1), (0.78, 0.70, 0.58, 1)),
    ]
    for name, location, rotation, scale, color in cards:
        bpy.ops.mesh.primitive_plane_add(size=2.0, location=location, rotation=rotation)
        card = bpy.context.object
        card.name = name
        card.scale = scale
        material = bpy.data.materials.new(f"{name} material")
        material.diffuse_color = color
        material.use_nodes = True
        bsdf = find_principled_bsdf(material.node_tree.nodes)
        if bsdf:
            set_principled_input(bsdf, ("Base Color",), color)
            set_principled_input(bsdf, ("Roughness",), 0.2)
        card.data.materials.append(material)
        card.visible_camera = False
        card.visible_diffuse = False
        card.visible_glossy = True
        card.visible_transmission = True


def add_camera() -> None:
    bpy.ops.object.camera_add(location=(0, -4.6, 0.35), rotation=(math.radians(86), 0, 0))
    camera = bpy.context.object
    camera.name = "Orthographic Product Camera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.55
    bpy.context.scene.camera = camera


def create_uv_bead(with_thread_hole: bool = False) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1.0, location=(0, 0, 0))
    bead = bpy.context.object
    bead.name = "Crystal Bead"
    smooth_mesh_object(bead)
    if with_thread_hole:
        add_thread_hole(bead)
    return bead


def add_thread_hole(bead: bpy.types.Object) -> None:
    """用布尔差集挖穿线孔。若你想做无孔珠子，可以删除这段调用。"""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=96,
        radius=0.18,
        depth=2.5,
        location=(0, 0, 0.08),
        # 默认圆柱沿 Z 轴；绕 Y 轴旋转 90 度后孔沿 X 轴横穿，
        # 相机从 -Y 方向看时不会变成正对孔洞的“甜甜圈”。
        rotation=(0, math.pi / 2, 0),
    )
    cutter = bpy.context.object
    cutter.name = "Thread Hole Cutter"
    modifier = bead.modifiers.new("Thread hole", "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.object = cutter
    bpy.context.view_layer.objects.active = bead
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    smooth_mesh_object(bead)


def smooth_mesh_object(obj: bpy.types.Object) -> None:
    """无头模式下不依赖 bpy.ops，直接给 Mesh 多边形开启平滑。"""
    if obj.type != "MESH":
        return
    for polygon in obj.data.polygons:
        polygon.use_smooth = True


def assign_single_material(obj: bpy.types.Object, material: bpy.types.Material) -> None:
    """Boolean cutters can leave an empty material slot at index 0; force a clean slot."""
    if obj.type != "MESH":
        return
    obj.data.materials.clear()
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.material_index = 0


def make_principled_material(row: CrystalRow) -> bpy.types.Material:
    material = bpy.data.materials.new(row.sku_name)
    material.use_nodes = True
    material.blend_method = "BLEND"
    material.use_screen_refraction = True
    material.diffuse_color = hex_to_rgba(row.hex_color)

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = (320, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    template = infer_render_template(row)
    color = display_color_for(row, template)
    set_principled_input(bsdf, ("Base Color",), color)
    set_principled_input(bsdf, ("Metallic",), 0.0)
    set_principled_input(bsdf, ("Alpha",), 1.0)
    set_principled_input(bsdf, ("IOR",), row.ior)

    if template in {"T1_Clear", "T1_Transparent"}:
        # 高透水晶：低粗糙度 + 高透射 + 正确 IOR，依赖 HDRI 产生真实折射和边缘暗部。
        set_principled_input(bsdf, ("Roughness",), 0.0)
        set_principled_input(bsdf, ("Transmission Weight", "Transmission"), 1.0)
        # 注意：珠子的透明感由 Transmission/IOR 负责；Alpha 必须保持 1，
        # 否则 PNG 中珠子本体也会变半透明，叠到小程序盘面会发灰。
        set_principled_input(bsdf, ("Alpha",), 1.0)
        set_principled_input(bsdf, ("Specular IOR Level", "Specular"), 1.0)
        set_principled_input(bsdf, ("Coat Weight", "Clearcoat"), 0.18)
        set_principled_input(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.02)
    elif template == "T1_Smoky":
        set_principled_input(bsdf, ("Roughness",), 0.015)
        set_principled_input(bsdf, ("Transmission Weight", "Transmission"), 0.72)
        set_principled_input(bsdf, ("Specular IOR Level", "Specular"), 0.88)
        set_principled_input(bsdf, ("Coat Weight", "Clearcoat"), 0.2)
        set_principled_input(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.04)
        add_subtle_noise_to_material(material, color)
    elif template == "T5_Opaque":
        # 玉石/玛瑙：不要像玻璃一样透明，靠 SSS 做“油润、内透”的感觉。
        set_principled_input(bsdf, ("Roughness",), 0.38)
        set_principled_input(bsdf, ("Transmission Weight", "Transmission"), 0.0)
        set_principled_input(bsdf, ("Subsurface Weight", "Subsurface"), 1.0)
        set_principled_input(bsdf, ("Subsurface Radius",), (0.85, 0.62, 0.42))
        set_principled_input(bsdf, ("Subsurface Scale",), 0.1)
        set_principled_input(bsdf, ("Specular IOR Level", "Specular"), 0.45)
        set_principled_input(bsdf, ("Coat Weight", "Clearcoat"), 0.08)
        set_principled_input(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.22)
    elif template in {"T2_Ghost", "T3_Rutilated", "Fluorite"}:
        # T2/T3 如果没有模板，就先用半透明基础壳兜底，并加一点程序噪波，避免纯色塑料感。
        set_principled_input(bsdf, ("Roughness",), 0.035 if template == "T3_Rutilated" else 0.09)
        set_principled_input(bsdf, ("Transmission Weight", "Transmission"), 0.72 if template == "T3_Rutilated" else 0.58)
        set_principled_input(bsdf, ("Specular IOR Level", "Specular"), 0.92)
        set_principled_input(bsdf, ("Coat Weight", "Clearcoat"), 0.16)
        set_principled_input(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.035)
        set_principled_input(bsdf, ("Alpha",), 1.0)
        add_subtle_noise_to_material(material, color)
    elif template == "TigerEye":
        set_principled_input(bsdf, ("Roughness",), 0.2)
        set_principled_input(bsdf, ("Transmission Weight", "Transmission"), 0.0)
        set_principled_input(bsdf, ("Subsurface Weight", "Subsurface"), 0.36)
        set_principled_input(bsdf, ("Subsurface Scale",), 0.08)
        add_wave_bands_to_material(material, color, warm=True)
    elif template == "Moonstone":
        set_principled_input(bsdf, ("Roughness",), 0.24)
        set_principled_input(bsdf, ("Transmission Weight", "Transmission"), 0.35)
        set_principled_input(bsdf, ("Subsurface Weight", "Subsurface"), 0.38)
        set_principled_input(bsdf, ("Subsurface Scale",), 0.08)
        add_moonstone_sheen_to_material(material, color)
    elif template == "BandedAgate":
        set_principled_input(bsdf, ("Roughness",), 0.32)
        set_principled_input(bsdf, ("Transmission Weight", "Transmission"), 0.08)
        set_principled_input(bsdf, ("Subsurface Weight", "Subsurface"), 0.55)
        set_principled_input(bsdf, ("Subsurface Scale",), 0.08)
        add_wave_bands_to_material(material, color, warm=False)
    else:
        set_principled_input(bsdf, ("Roughness",), 0.16)
        set_principled_input(bsdf, ("Transmission Weight", "Transmission"), 0.42)
        add_subtle_noise_to_material(material, color)

    return material


def display_color_for(row: CrystalRow, template: str) -> tuple[float, float, float, float]:
    """CSV 颜色偏通用时，根据 SKU/母版给渲染色做合理兜底。"""
    color = hex_to_rgba(row.hex_color)
    text = f"{row.sku_name}{row.category_desc}{row.notes}"
    if template == "T3_Rutilated" and row.hex_color.upper() in {"#FFFFFF", "#FDFDFD", "#FAFAFA"}:
        return (0.96, 0.9, 0.68, 1) if "金" in text else (0.86, 0.9, 0.92, 1)
    if template == "T2_Ghost" and row.hex_color.upper() in {"#FFFFFF", "#FDFDFD", "#FAFAFA"}:
        if "红" in text:
            return (0.98, 0.72, 0.7, 1)
        if "黄" in text:
            return (0.96, 0.86, 0.48, 1)
        if "紫" in text:
            return (0.72, 0.58, 0.9, 1)
        return (0.62, 0.86, 0.66, 1)
    if template == "TigerEye":
        return (0.92, 0.58, 0.12, 1)
    if template == "Moonstone":
        return (0.78, 0.9, 1.0, 1)
    return color


def set_principled_input(node: bpy.types.Node, names: tuple[str, ...], value: Any) -> None:
    """Principled BSDF 在 Blender 3/4/5 中输入名会变化，所以这里做多名称兼容。"""
    for name in names:
        if name in node.inputs:
            node.inputs[name].default_value = value
            return
    print(f"[WARN] 当前 Blender 版本找不到节点输入：{names}")


def find_principled_bsdf(nodes: bpy.types.Nodes) -> bpy.types.Node | None:
    """Find the Principled BSDF node by type instead of localized display name."""
    return next((node for node in nodes if node.type == "BSDF_PRINCIPLED"), None)


def add_subtle_noise_to_material(material: bpy.types.Material, base_color: tuple[float, float, float, float]) -> None:
    """给 T2/T3 兜底材质加轻微云雾感。复杂幽灵/发晶建议使用模板 blend。"""
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = find_principled_bsdf(nodes)
    if not bsdf:
        return

    noise = nodes.new(type="ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 18
    noise.inputs["Detail"].default_value = 9
    noise.inputs["Roughness"].default_value = 0.55

    color_ramp = nodes.new(type="ShaderNodeValToRGB")
    color_ramp.color_ramp.elements[0].position = 0.28
    color_ramp.color_ramp.elements[0].color = (
        base_color[0] * 0.55,
        base_color[1] * 0.55,
        base_color[2] * 0.55,
        1,
    )
    color_ramp.color_ramp.elements[1].position = 1.0
    color_ramp.color_ramp.elements[1].color = (
        min(base_color[0] * 1.35 + 0.08, 1),
        min(base_color[1] * 1.35 + 0.08, 1),
        min(base_color[2] * 1.35 + 0.08, 1),
        1,
    )
    links.new(noise.outputs["Fac"], color_ramp.inputs["Fac"])
    links.new(color_ramp.outputs["Color"], bsdf.inputs["Base Color"])


def add_wave_bands_to_material(
    material: bpy.types.Material,
    base_color: tuple[float, float, float, float],
    warm: bool,
) -> None:
    """虎眼/玛瑙类复用的条带母版。虎眼更细更亮，玛瑙更宽更柔。"""
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = find_principled_bsdf(nodes)
    if not bsdf:
        return

    wave = nodes.new(type="ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 9 if warm else 7
    wave.inputs["Distortion"].default_value = 5 if warm else 11
    if hasattr(wave, "wave_type"):
        wave.wave_type = "RINGS" if not warm else "BANDS"

    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.36
    ramp.color_ramp.elements[1].position = 0.72
    if warm:
        ramp.color_ramp.elements[0].color = (base_color[0] * 0.45, base_color[1] * 0.38, base_color[2] * 0.25, 1)
        ramp.color_ramp.elements[1].color = (min(base_color[0] * 1.55 + 0.18, 1), min(base_color[1] * 1.42 + 0.12, 1), min(base_color[2] * 0.95 + 0.05, 1), 1)
    else:
        ramp.color_ramp.elements[0].color = (base_color[0] * 0.62, base_color[1] * 0.62, base_color[2] * 0.62, 1)
        ramp.color_ramp.elements[1].color = (min(base_color[0] * 1.25 + 0.08, 1), min(base_color[1] * 1.25 + 0.08, 1), min(base_color[2] * 1.25 + 0.08, 1), 1)

    wave_factor = wave.outputs["Fac"] if "Fac" in wave.outputs else wave.outputs["Color"]
    links.new(wave_factor, ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])


def add_moonstone_sheen_to_material(material: bpy.types.Material, base_color: tuple[float, float, float, float]) -> None:
    """月光石/拉长石母版：底色偏乳白，叠加蓝色晕光噪波。"""
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = find_principled_bsdf(nodes)
    if not bsdf:
        return

    noise = nodes.new(type="ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 7
    noise.inputs["Detail"].default_value = 12
    noise.inputs["Roughness"].default_value = 0.48

    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.32
    ramp.color_ramp.elements[0].color = (
        min(base_color[0] * 1.1 + 0.08, 1),
        min(base_color[1] * 1.1 + 0.08, 1),
        min(base_color[2] * 1.1 + 0.08, 1),
        1,
    )
    ramp.color_ramp.elements[1].position = 0.94
    ramp.color_ramp.elements[1].color = (0.62, 0.82, 1.0, 1)

    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])


def gently_tint_template_materials(objects: list[bpy.types.Object], row: CrystalRow) -> None:
    """
    T2/T3 模板材质保护逻辑。

    绝不清空模板材质槽，也不替换复杂节点树；只寻找已有 Principled BSDF，
    对基础底色、IOR、粗糙度做很轻的调整。这样绿幽灵内部山丘、发晶金丝、
    云雾噪波、体积材质等母版细节都会保留下来。
    """
    target_color = hex_to_rgba(row.hex_color)
    for obj in objects:
        if obj.type != "MESH":
            continue
        smooth_mesh_object(obj)
        for material in obj.data.materials:
            if not material or not material.use_nodes:
                continue
            for node in material.node_tree.nodes:
                if node.type != "BSDF_PRINCIPLED":
                    continue
                if "Base Color" in node.inputs:
                    current = node.inputs["Base Color"].default_value
                    node.inputs["Base Color"].default_value = (
                        current[0] * 0.65 + target_color[0] * 0.35,
                        current[1] * 0.65 + target_color[1] * 0.35,
                        current[2] * 0.65 + target_color[2] * 0.35,
                        current[3],
                    )
                set_principled_input(node, ("IOR",), row.ior)
                if row.template_id.startswith("T2"):
                    set_principled_input(node, ("Roughness",), 0.08)
                    set_principled_input(node, ("Transmission Weight", "Transmission"), 0.72)
                elif row.template_id.startswith("T3"):
                    set_principled_input(node, ("Roughness",), 0.04)
                    set_principled_input(node, ("Transmission Weight", "Transmission"), 0.62)


def make_simple_material(name: str, color: tuple[float, float, float, float], roughness: float = 0.35) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    bsdf = find_principled_bsdf(material.node_tree.nodes)
    if bsdf:
        set_principled_input(bsdf, ("Base Color",), color)
        set_principled_input(bsdf, ("Roughness",), roughness)
        set_principled_input(bsdf, ("Metallic",), 0.0)
    return material


def add_rutilated_inclusions(row: CrystalRow) -> None:
    """发晶/兔毛母版：在透明壳内部生成一组细长发丝。"""
    rng = stable_rng(row.sku_name)
    base = hex_to_rgba(row.hex_color)
    text = row.sku_name
    if "黑" in text:
        hair_color = (0.02, 0.018, 0.014, 1)
    elif "银" in text or "白" in text:
        hair_color = (0.88, 0.86, 0.78, 1)
    elif "绿" in text:
        hair_color = (0.2, 0.62, 0.34, 1)
    elif "红" in text or "铜" in text:
        hair_color = (0.8, 0.28, 0.16, 1)
    else:
        hair_color = (1.0, 0.72, 0.18, 1)
    material = make_simple_material(f"{row.sku_name} inclusion hair", hair_color, roughness=0.18)
    bsdf = find_principled_bsdf(material.node_tree.nodes)
    if bsdf:
        set_principled_input(bsdf, ("Metallic",), 0.35)
        set_principled_input(bsdf, ("Roughness",), 0.12)
        set_principled_input(bsdf, ("Specular IOR Level", "Specular"), 1.0)
        set_principled_input(bsdf, ("Emission Color", "Emission"), hair_color)
        set_principled_input(bsdf, ("Emission Strength",), 0.08)

    for index in range(42):
        curve = bpy.data.curves.new(f"rutile_{index:02d}", type="CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 2
        curve.bevel_depth = rng.uniform(0.009, 0.018)
        curve.bevel_resolution = 2
        spline = curve.splines.new(type="POLY")
        spline.points.add(1)
        y = rng.uniform(-0.72, -0.32)
        x0 = rng.uniform(-0.62, 0.18)
        x1 = rng.uniform(-0.12, 0.64)
        z0 = rng.uniform(-0.5, 0.44)
        z1 = z0 + rng.uniform(-0.24, 0.24)
        tilt = rng.uniform(-0.22, 0.22)
        spline.points[0].co = (x0 - tilt, y, z0, 1)
        spline.points[1].co = (x1 + tilt, y + rng.uniform(-0.06, 0.06), z1, 1)
        obj = bpy.data.objects.new(curve.name, curve)
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(material)


def add_ghost_inclusions(row: CrystalRow) -> None:
    """幽灵/水胆母版：内部增加半透明云雾矿层。"""
    rng = stable_rng(row.sku_name)
    base = display_color_for(row, "T2_Ghost")
    ghost_color = (
        min(base[0] * 0.72 + 0.04, 1),
        min(base[1] * 0.88 + 0.04, 1),
        min(base[2] * 0.72 + 0.04, 1),
        0.86,
    )
    material = make_simple_material(f"{row.sku_name} ghost cloud", ghost_color, roughness=0.62)
    material.blend_method = "BLEND"
    bsdf = find_principled_bsdf(material.node_tree.nodes)
    if bsdf:
        set_principled_input(bsdf, ("Alpha",), 0.82)
        set_principled_input(bsdf, ("Transmission Weight", "Transmission"), 0.04)
        set_principled_input(bsdf, ("Subsurface Weight", "Subsurface"), 0.5)
        set_principled_input(bsdf, ("Subsurface Scale",), 0.12)
        set_principled_input(bsdf, ("Emission Color", "Emission"), ghost_color)
        set_principled_input(bsdf, ("Emission Strength",), 0.035)

    for index in range(7):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=32,
            ring_count=16,
            radius=rng.uniform(0.16, 0.28),
            location=(rng.uniform(-0.18, 0.18), rng.uniform(-0.62, -0.36), rng.uniform(-0.36, 0.06)),
        )
        cloud = bpy.context.object
        cloud.name = f"ghost inclusion {index}"
        cloud.scale = (rng.uniform(1.15, 1.85), rng.uniform(0.16, 0.28), rng.uniform(0.34, 0.68))
        cloud.data.materials.append(material)
        smooth_mesh_object(cloud)


def append_template_objects(template_path: Path, object_name: str = "") -> list[bpy.types.Object]:
    """
    从模板 .blend 追加对象。

    建议模板文件里把复杂内部结构和外壳做成一个 Collection 或几个 Mesh。
    如果 object_name 为空，则追加全部 Object；否则只追加指定对象。
    """
    if not template_path.exists():
        raise FileNotFoundError(template_path)

    with bpy.data.libraries.load(str(template_path.resolve()), link=False) as (data_from, data_to):
        if object_name:
            if object_name not in data_from.objects:
                raise ValueError(f"模板中找不到对象：{object_name}")
            data_to.objects = [object_name]
        else:
            data_to.objects = list(data_from.objects)

    objects = [obj for obj in data_to.objects if obj is not None]
    for obj in objects:
        bpy.context.collection.objects.link(obj)
        obj.location = (0, 0, 0)
    return objects


def render_row(row: CrystalRow, args: argparse.Namespace, output_path: Path) -> None:
    reset_scene()
    setup_world_hdri(Path(args.hdri) if args.hdri else None)
    add_studio_lights()
    add_reflection_cards()
    add_camera()
    configure_color_and_output(output_path, size=args.size)

    render_template = infer_render_template(row)
    template_path = ""
    if render_template == "T2_Ghost":
        template_path = args.t2_template
    elif render_template == "T3_Rutilated":
        template_path = args.t3_template

    material = make_principled_material(row)
    objects: list[bpy.types.Object]
    if template_path:
        objects = append_template_objects(Path(template_path), args.template_object)
        gently_tint_template_materials(objects, row)
    else:
        bead = create_uv_bead(with_thread_hole=args.with_thread_hole)
        assign_single_material(bead, material)
        if render_template == "T3_Rutilated":
            add_rutilated_inclusions(row)
        elif render_template == "T2_Ghost":
            add_ghost_inclusions(row)

    bpy.ops.render.render(write_still=True)


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = read_csv_rows(csv_path)
    if args.only:
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        rows = [row for row in rows if row.sku_name in wanted]
    if args.limit:
        rows = rows[: args.limit]

    set_cycles_gpu(args.samples)
    print(f"[INFO] 待渲染：{len(rows)} 条")

    for index, row in enumerate(rows, start=1):
        output_path = output_dir / f"{sanitize_filename(row.sku_name)}.png"
        if args.skip_existing and output_path.exists():
            print(f"[{index}/{len(rows)}] skip {row.sku_name}")
            continue
        print(f"[{index}/{len(rows)}] render {row.sku_name} ({infer_render_template(row)}) -> {output_path}")
        render_row(row, args, output_path)

    print(f"[DONE] 输出目录：{output_dir.resolve()}")


if __name__ == "__main__":
    main()
