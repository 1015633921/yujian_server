from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath


MATERIAL_ASSET_SIZE = 512
MAX_MATERIAL_ASSET_BYTES = 800_000
MAX_MATERIAL_ASSET_COUNT = 24
MATERIAL_ASSET_PREFIX = "materials/processed"


@dataclass(frozen=True)
class MaterialAssetInspection:
    width: int
    height: int
    has_alpha: bool
    animated: bool
    bytes: int
    codec: str

    def as_dict(self) -> dict[str, int | bool | str]:
        return asdict(self)


def _uint24(data: bytes) -> int:
    return int.from_bytes(data, "little")


def inspect_webp(content: bytes) -> MaterialAssetInspection:
    if len(content) < 20 or content[:4] != b"RIFF" or content[8:12] != b"WEBP":
        raise ValueError("处理结果必须是 WebP 图片")
    declared_size = int.from_bytes(content[4:8], "little") + 8
    if declared_size != len(content):
        raise ValueError("WebP 文件长度异常或数据不完整")

    width = height = 0
    has_alpha = False
    animated = False
    codec = ""
    position = 12
    limit = min(declared_size, len(content))
    while position + 8 <= limit:
        chunk_type = content[position : position + 4]
        chunk_size = int.from_bytes(content[position + 4 : position + 8], "little")
        chunk_start = position + 8
        chunk_end = chunk_start + chunk_size
        if chunk_end > limit:
            raise ValueError("WebP 数据块不完整")
        payload = content[chunk_start:chunk_end]

        if chunk_type == b"VP8X" and len(payload) >= 10:
            flags = payload[0]
            width = _uint24(payload[4:7]) + 1
            height = _uint24(payload[7:10]) + 1
            has_alpha = has_alpha or bool(flags & 0x10)
            animated = animated or bool(flags & 0x02)
            codec = "VP8X"
        elif chunk_type == b"ALPH":
            has_alpha = True
        elif chunk_type in {b"ANIM", b"ANMF"}:
            animated = True
        elif chunk_type == b"VP8L" and len(payload) >= 5 and payload[0] == 0x2F:
            bits = int.from_bytes(payload[1:5], "little")
            if not width:
                width = (bits & 0x3FFF) + 1
                height = ((bits >> 14) & 0x3FFF) + 1
            has_alpha = has_alpha or bool((bits >> 28) & 1)
            codec = codec or "VP8L"
        elif chunk_type == b"VP8 " and len(payload) >= 10 and payload[3:6] == b"\x9d\x01\x2a":
            if not width:
                width = int.from_bytes(payload[6:8], "little") & 0x3FFF
                height = int.from_bytes(payload[8:10], "little") & 0x3FFF
            codec = codec or "VP8"

        position = chunk_end + (chunk_size & 1)

    if width <= 0 or height <= 0:
        raise ValueError("无法读取 WebP 图片尺寸")
    return MaterialAssetInspection(
        width=width,
        height=height,
        has_alpha=has_alpha,
        animated=animated,
        bytes=len(content),
        codec=codec or "WEBP",
    )


def validate_material_ready_webp(content: bytes) -> MaterialAssetInspection:
    if not content:
        raise ValueError("处理后的材料图片不能为空")
    if len(content) > MAX_MATERIAL_ASSET_BYTES:
        raise ValueError("处理后的材料图片不能超过 800KB")
    inspection = inspect_webp(content)
    if inspection.animated:
        raise ValueError("材料图片不支持动画 WebP")
    if (inspection.width, inspection.height) != (MATERIAL_ASSET_SIZE, MATERIAL_ASSET_SIZE):
        raise ValueError(f"材料图片必须为 {MATERIAL_ASSET_SIZE}×{MATERIAL_ASSET_SIZE}")
    if not inspection.has_alpha:
        raise ValueError("材料图片必须保留透明背景")
    return inspection


def validate_material_asset_key(value: str) -> str:
    key = str(value or "").strip()
    if not key or len(key) > 500 or "\\" in key or key.startswith("/"):
        raise ValueError("材料图片对象标识无效")
    path = PurePosixPath(key)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("材料图片对象标识无效")
    prefix_parts = PurePosixPath(MATERIAL_ASSET_PREFIX).parts
    if path.parts[: len(prefix_parts)] != prefix_parts or path.suffix.lower() != ".webp":
        raise ValueError("只能绑定素材处理页上传的 WebP 图片")
    return str(path)
