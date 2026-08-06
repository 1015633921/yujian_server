from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .database import connect_database
from .material_knowledge import fetch_knowledge_map, upsert_material_knowledge
from .materials import invalidate_material_cache


DEFAULT_MODEL = "qwen3.7-plus-2026-05-26"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
PROMPT_VERSION = "yujian-material-visual-v2"
SCHEMA_VERSION = "material-visual-v2"
MAX_IMAGES = 5

BEAD_ROLE_VALUES = (
    "主题珠材",
    "调和珠材",
    "点睛珠材",
    "焦点珠",
)
ACCESSORY_ROLE_VALUES = (
    "节奏配饰",
    "过渡配饰",
    "焦点配饰",
)
ROLE_VALUES = (*BEAD_ROLE_VALUES, *ACCESSORY_ROLE_VALUES)
NON_VISUAL_UNCERTAINTY_TERMS = (
    "真假",
    "产地",
    "成分",
    "重量",
    "库存",
    "价格",
    "电镀工艺",
    "孔道",
    "穿孔",
    "尺寸",
)
APPLICATION_ROLE_MAP = {
    "主题珠材": "primary",
    "焦点珠": "primary",
    "调和珠材": "support",
    "点睛珠材": "accent",
    "焦点配饰": "accent",
    "节奏配饰": "spacer",
    "过渡配饰": "spacer",
}
APPLICATION_MOOD_KEYWORDS = (
    ("calming", ("舒缓", "静谧", "平静", "沉静", "疗愈")),
    ("confidence", ("自信", "力量")),
    ("clarity", ("清晰", "清透", "澄澈")),
    ("focus", ("专注", "理性")),
    ("vitality", ("活力", "明快", "元气")),
    ("softness", ("柔和", "温柔", "轻盈")),
    ("boundary", ("边界", "克制", "冷峻")),
    ("companionship", ("陪伴", "亲和")),
)
APPLICATION_COLOR_KEYWORDS = (
    ("pink", ("粉", "桃")),
    ("purple", ("紫",)),
    ("blue", ("蓝", "青")),
    ("green", ("绿", "苔藓")),
    ("gold", ("金", "黄", "香槟")),
    ("red", ("红", "朱", "橙")),
    ("brown", ("棕", "褐", "咖")),
    ("black", ("黑", "墨")),
    ("white", ("白", "银", "灰", "透明", "无色")),
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def json_value(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return default
    return parsed


def unique_texts(values: Any, *, limit: int, max_length: int = 80) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if not text or len(text) > max_length or text in result:
            continue
        result.append(text)
        if len(result) >= limit:
            break
    return result


def deduplicate_image_urls(values: Any, *, limit: int = MAX_IMAGES) -> list[str]:
    candidates = unique_texts(values, limit=50, max_length=2000)
    preferred = sorted(
        candidates,
        key=lambda value: (
            0 if "yustream.cn" in (urlparse(value).hostname or "").lower() else 1,
            candidates.index(value),
        ),
    )
    result: list[str] = []
    seen_objects: set[str] = set()
    for value in preferred:
        parsed = urlparse(value)
        object_key = parsed.path.rstrip("/") or value
        if object_key in seen_objects:
            continue
        seen_objects.add(object_key)
        result.append(value)
        if len(result) >= limit:
            break
    return result


class MaterialVisualScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dominant_colors: list[str] = Field(min_length=1, max_length=5)
    brightness: int = Field(ge=0, le=100)
    saturation: int = Field(ge=0, le=100)
    temperature: int = Field(ge=-100, le=100)
    transparency: int = Field(ge=0, le=100)
    texture_complexity: int = Field(ge=0, le=100)
    sparkle: int = Field(ge=0, le=100)
    visual_weight: int = Field(ge=0, le=100)

    @field_validator("dominant_colors")
    @classmethod
    def validate_colors(cls, value: list[str]) -> list[str]:
        cleaned = unique_texts(value, limit=5, max_length=30)
        if not cleaned:
            raise ValueError("dominant_colors 不能为空")
        return cleaned


class RecommendedUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count_min: int = Field(ge=1, le=40)
    count_max: int = Field(ge=1, le=40)
    symmetry: Literal["none", "prefer_paired", "required_paired"]
    focus_strength: Literal["low", "medium", "high"]

    @model_validator(mode="after")
    def validate_count_range(self) -> "RecommendedUsage":
        if self.count_max < self.count_min:
            raise ValueError("count_max 不能小于 count_min")
        return self


class MaterialDesignTags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: list[
        Literal[
            "主题珠材",
            "调和珠材",
            "点睛珠材",
            "焦点珠",
            "节奏配饰",
            "过渡配饰",
            "焦点配饰",
        ]
    ] = Field(min_length=1, max_length=4)
    style_tags: list[str] = Field(min_length=1, max_length=8)
    shape_language: list[str] = Field(min_length=1, max_length=6)
    recommended_metal_palettes: list[str] = Field(default_factory=list, max_length=5)
    recommended_usage: RecommendedUsage

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator("style_tags")
    @classmethod
    def validate_style_tags(cls, value: list[str]) -> list[str]:
        cleaned = unique_texts(value, limit=8, max_length=30)
        if not cleaned:
            raise ValueError("style_tags 不能为空")
        return cleaned

    @field_validator("shape_language")
    @classmethod
    def validate_shape_language(cls, value: list[str]) -> list[str]:
        cleaned = unique_texts(value, limit=6, max_length=30)
        if not cleaned:
            raise ValueError("shape_language 不能为空")
        return cleaned

    @field_validator("recommended_metal_palettes")
    @classmethod
    def validate_palettes(cls, value: list[str]) -> list[str]:
        return unique_texts(value, limit=5, max_length=40)


class MaterialTaggingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str = Field(min_length=8, max_length=80)
    material_code: str = Field(min_length=1, max_length=160)
    visual: MaterialVisualScores
    design: MaterialDesignTags
    confidence: float = Field(ge=0, le=1)
    uncertain_fields: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("uncertain_fields")
    @classmethod
    def validate_uncertain_fields(cls, value: list[str]) -> list[str]:
        return unique_texts(value, limit=10, max_length=160)


def material_application_fields(result: MaterialTaggingResult) -> dict[str, Any]:
    visual = result.visual
    design = result.design
    roles = list(
        dict.fromkeys(
            APPLICATION_ROLE_MAP[role]
            for role in design.roles
            if role in APPLICATION_ROLE_MAP
        )
    )
    rules: list[str] = []
    if "primary" in roles:
        rules.append("best_as_primary")
    if "support" in roles:
        rules.append("best_as_support")
    if "accent" in roles:
        rules.append("accent_only")
    if "spacer" in roles:
        rules.append("spacer_only")
    if design.recommended_usage.symmetry != "none":
        rules.append("pair_symmetry")
    if design.recommended_usage.count_max <= 4:
        rules.append("avoid_dense")
    if not rules:
        rules.append("no_limit")

    visual_tags: list[str] = []
    if visual.transparency >= 65:
        visual_tags.append("transparent")
    if visual.transparency >= 82 and visual.brightness >= 58:
        visual_tags.append("icy")
    if visual.sparkle >= 55:
        visual_tags.append("sparkling")
    if visual.saturation <= 40:
        visual_tags.append("soft_color")
    if visual.texture_complexity >= 55:
        visual_tags.append("texture")
    if visual.brightness <= 35 or visual.visual_weight >= 78:
        visual_tags.append("dark")
    if visual.temperature >= 30:
        visual_tags.append("warm")

    style_text = " ".join(design.style_tags)
    mood_tags = [
        key
        for key, keywords in APPLICATION_MOOD_KEYWORDS
        if any(keyword in style_text for keyword in keywords)
    ]
    color_text = " ".join(visual.dominant_colors)
    color_family = next(
        (
            key
            for key, keywords in APPLICATION_COLOR_KEYWORDS
            if any(keyword in color_text for keyword in keywords)
        ),
        "",
    )
    transparency_level = (
        "transparent"
        if visual.transparency >= 75
        else "semi_transparent"
        if visual.transparency >= 45
        else "translucent"
        if visual.transparency >= 20
        else "opaque"
    )
    texture_text = " ".join(
        [
            *visual.dominant_colors,
            *design.style_tags,
            *design.shape_language,
        ]
    )
    texture_keywords = (
        ("rutile", ("发丝", "发晶", "针状")),
        ("phantom", ("幽灵", "千层", "聚宝盆")),
        ("cat_eye", ("猫眼",)),
        ("color_band", ("色带", "条带")),
        ("cloud", ("棉絮", "云雾")),
        ("crack", ("冰裂", "裂纹")),
        ("mineral_inclusion", ("矿物", "包裹体", "内含")),
    )
    texture_features = [
        key
        for key, keywords in texture_keywords
        if any(keyword in texture_text for keyword in keywords)
    ]
    return {
        "visual_tags": visual_tags,
        "mood_tags": mood_tags,
        "allowed_roles": roles,
        "match_rules": list(dict.fromkeys(rules)),
        "color_family": color_family,
        "material_params": {
            "transparency_level": transparency_level,
            "texture_features": texture_features,
        },
        "ai_visual_profile": {
            "dominant_colors": visual.dominant_colors,
            "brightness": visual.brightness,
            "saturation": visual.saturation,
            "temperature": visual.temperature,
            "transparency": visual.transparency,
            "texture_complexity": visual.texture_complexity,
            "sparkle": visual.sparkle,
            "visual_weight": visual.visual_weight,
            "style_tags": design.style_tags,
            "shape_language": design.shape_language,
            "recommended_metal_palettes": design.recommended_metal_palettes,
            "recommended_usage": design.recommended_usage.model_dump(),
            "confidence": result.confidence,
        },
    }


@dataclass(frozen=True)
class MaterialTaggingTarget:
    target_id: str
    material_code: str
    top: str
    category: str
    series: str
    name: str
    known_facts: dict[str, Any]
    image_urls: list[str]
    source_updated_at: str


@dataclass(frozen=True)
class MaterialAnalysisResponse:
    result: MaterialTaggingResult
    raw_response: str
    request_id: str
    usage: dict[str, Any]


class BailianMaterialTaggingError(RuntimeError):
    def __init__(self, message: str, *, code: str = "BAILIAN_ERROR", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def _allowed_image_hosts() -> tuple[str, ...]:
    value = os.getenv("DASHSCOPE_IMAGE_ALLOWED_HOSTS", "")
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())


def validate_image_url(url: str) -> str:
    text = str(url or "").strip()
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("材料图片必须使用不含账号信息的 HTTPS 公网地址")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("材料图片不能使用本机地址")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved):
        raise ValueError("材料图片不能使用内网地址")
    allowed = _allowed_image_hosts()
    if allowed and not any(host == item or (item.startswith("*.") and host.endswith(item[1:])) for item in allowed):
        raise ValueError(f"材料图片域名未在白名单中：{host}")
    return text


def _compact_schema(allowed_roles: tuple[str, ...]) -> dict[str, Any]:
    return {
        "target_id": "string，必须与输入完全一致",
        "material_code": "string，必须与输入完全一致",
        "visual": {
            "dominant_colors": ["1至5个中文颜色描述"],
            "brightness": "integer 0-100",
            "saturation": "integer 0-100",
            "temperature": "integer -100冷到100暖",
            "transparency": "integer 0-100",
            "texture_complexity": "integer 0-100",
            "sparkle": "integer 0-100",
            "visual_weight": "integer 0-100",
        },
        "design": {
            "roles": list(allowed_roles),
            "style_tags": ["1至8个简短中文标签"],
            "shape_language": ["1至6个简短中文标签"],
            "recommended_metal_palettes": ["0至5个简短中文配色建议"],
            "recommended_usage": {
                "count_min": "integer 1-40",
                "count_max": "integer 1-40且不小于count_min",
                "symmetry": "none/prefer_paired/required_paired",
                "focus_strength": "low/medium/high",
            },
        },
        "confidence": "number 0-1",
        "uncertain_fields": ["看不清或图片不足以确认的字段，最多10项"],
    }


def build_material_messages(target: MaterialTaggingTarget) -> list[dict[str, Any]]:
    allowed_roles = ACCESSORY_ROLE_VALUES if target.top in {"accessory", "pendant"} else BEAD_ROLE_VALUES
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "请只以一个合法 JSON 对象分析这个宇涧材料品种的视觉与设计属性。\n"
                "不得判断真假、产地、品质等级或功效；不得修改名称、编码、尺寸、库存、价格或安装方式；"
                "不得生成不存在的材料；图片不足时降低 confidence 并写入 uncertain_fields。\n"
                "uncertain_fields 只记录图片无法确认的视觉属性，不要记录成分、产地、重量、孔道、尺寸、价格或库存。\n"
                f"允许的设计角色只有：{'、'.join(allowed_roles)}；不能输出其他类型的角色。\n"
                "评分锚点：0表示几乎没有该属性，25偏低，50中等，75偏高，100极强；"
                "temperature 使用 -100极冷、0中性、100极暖。只根据图片评分，不把拍摄背景算作材料颜色。\n"
                f"目标ID：{target.target_id}\n"
                f"材料编码：{target.material_code}\n"
                f"已确认事实：{json_text(target.known_facts)}\n"
                f"图片数量：{len(target.image_urls)}\n"
                f"输出JSON结构：{json_text(_compact_schema(allowed_roles))}"
            ),
        }
    ]
    content.extend(
        {"type": "image_url", "image_url": {"url": validate_image_url(url)}}
        for url in target.image_urls[:MAX_IMAGES]
    )
    return [
        {
            "role": "system",
            "content": (
                "你是宇涧水晶设计团队的材料视觉标注助理。你的任务是稳定、克制、可复核地打标，"
                "不是自由创作。所有主观判断必须来自给定商品图库。"
            ),
        },
        {"role": "user", "content": content},
    ]


class BailianMaterialTaggingClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int = 2,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.api_key = str(api_key or os.getenv("DASHSCOPE_API_KEY") or "").strip()
        if not self.api_key:
            raise BailianMaterialTaggingError(
                "未配置 DASHSCOPE_API_KEY",
                code="BAILIAN_NOT_CONFIGURED",
            )
        self.model = str(model or os.getenv("QWEN_MATERIAL_TAG_MODEL") or DEFAULT_MODEL).strip()
        self.base_url = str(base_url or os.getenv("DASHSCOPE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout_seconds = float(
            timeout_seconds or os.getenv("QWEN_MATERIAL_TAG_TIMEOUT_SECONDS") or 60
        )
        self.max_retries = max(0, min(int(max_retries), 4))
        self.client = client or httpx.Client(timeout=self.timeout_seconds)
        self.sleep = sleep

    def analyze(self, target: MaterialTaggingTarget) -> MaterialAnalysisResponse:
        if not target.image_urls:
            raise ValueError("该品种没有图库图片，不能进行视觉打标")
        payload = {
            "model": self.model,
            "messages": build_material_messages(target),
            "response_format": {"type": "json_object"},
            "enable_thinking": False,
            "temperature": 0.1,
        }
        response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise BailianMaterialTaggingError(
                        "千问视觉打标请求超时或网络不可用",
                        code="BAILIAN_NETWORK_ERROR",
                        retryable=True,
                    ) from exc
                self.sleep(0.5 * (2**attempt))
                continue
            if response.status_code < 400:
                break
            try:
                error = response.json().get("error") or {}
                error_code = str(error.get("code") or f"HTTP_{response.status_code}")
                error_message = str(error.get("message") or "千问视觉打标请求失败")
            except (ValueError, AttributeError):
                error_code = f"HTTP_{response.status_code}"
                error_message = "千问视觉打标请求失败"
            download_failed = "failed to download multimodal content" in error_message.lower()
            retryable = (
                response.status_code in {408, 409, 429}
                or response.status_code >= 500
                or download_failed
            )
            if retryable and attempt < self.max_retries:
                self.sleep(0.5 * (2**attempt))
                continue
            raise BailianMaterialTaggingError(
                error_message[:300],
                code=error_code[:80],
                retryable=retryable,
            )
        if response is None:
            raise BailianMaterialTaggingError("千问视觉打标没有返回响应")
        try:
            body = response.json()
            raw = body["choices"][0]["message"]["content"]
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("empty content")
            parsed = json.loads(raw)
            result = MaterialTaggingResult.model_validate(parsed)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BailianMaterialTaggingError(
                "千问返回内容未通过材料打标 Schema 校验",
                code="BAILIAN_SCHEMA_ERROR",
            ) from exc
        if result.target_id != target.target_id or result.material_code != target.material_code:
            raise BailianMaterialTaggingError(
                "千问返回的材料标识与输入不一致",
                code="BAILIAN_ID_MISMATCH",
            )
        result = normalize_result_for_target(result, target)
        return MaterialAnalysisResponse(
            result=result,
            raw_response=raw,
            request_id=str(response.headers.get("x-request-id") or body.get("id") or ""),
            usage=body.get("usage") if isinstance(body.get("usage"), dict) else {},
        )


def normalize_result_for_target(
    result: MaterialTaggingResult,
    target: MaterialTaggingTarget,
) -> MaterialTaggingResult:
    allowed_roles = (
        ACCESSORY_ROLE_VALUES if target.top in {"accessory", "pendant"} else BEAD_ROLE_VALUES
    )
    roles = [role for role in result.design.roles if role in allowed_roles]
    if not roles:
        roles = ["过渡配饰"] if target.top in {"accessory", "pendant"} else ["调和珠材"]
    uncertainties = [
        item
        for item in result.uncertain_fields
        if not any(term in item for term in NON_VISUAL_UNCERTAINTY_TERMS)
    ]
    confidence_cap = 0.75 if len(target.image_urls) == 1 else 0.85 if len(target.image_urls) == 2 else 0.95
    if len(target.image_urls) == 1:
        uncertainties.append("仅有1张图库图，侧面、背面及不同光线表现待确认")
    normalized_design = result.design.model_copy(update={"roles": list(dict.fromkeys(roles))})
    return result.model_copy(
        update={
            "design": normalized_design,
            "confidence": min(result.confidence, confidence_cap),
            "uncertain_fields": unique_texts(uncertainties, limit=10, max_length=160),
        }
    )


class MaterialTaggingRepository:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path is not None else None

    def connect(self):
        return connect_database(self.db_path)

    @staticmethod
    def target_id(top: str, category: str, series: str, material_code: str) -> str:
        identity = "\x1f".join((top, category, series, material_code))
        return f"spu_{hashlib.sha256(identity.encode()).hexdigest()[:32]}"

    @staticmethod
    def _row_images(row: dict[str, Any]) -> list[str]:
        values = json_value(row.get("image_urls_json"), [])
        return unique_texts(values if isinstance(values, list) else [], limit=MAX_IMAGES, max_length=2000)

    @staticmethod
    def _material_facts(rows: list[dict[str, Any]], target_id: str) -> dict[str, Any]:
        first = rows[0]
        sizes: list[float] = []
        physical_specs: list[dict[str, Any]] = []
        names: list[str] = []
        for row in rows:
            try:
                size = float(row.get("size") or 0)
            except (TypeError, ValueError):
                size = 0
            if size > 0 and size not in sizes:
                sizes.append(size)
            spec = json_value(row.get("physical_specs_json"), {})
            if isinstance(spec, dict) and spec and spec not in physical_specs:
                physical_specs.append(spec)
            name = str(row.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
        return {
            "target_id": target_id,
            "material_code": str(first.get("material_code") or ""),
            "type": str(first.get("top") or ""),
            "category": str(first.get("category") or ""),
            "series": str(first.get("series") or first.get("name") or ""),
            "catalog_names": names[:10],
            "available_sizes_mm": sorted(sizes),
            "confirmed_physical_specs": physical_specs[:10],
        }

    def list_targets(
        self,
        *,
        limit: int = 50,
        top: str = "",
        material_codes: list[str] | None = None,
        series_keyword: str = "",
        require_gallery: bool = True,
    ) -> list[MaterialTaggingTarget]:
        clauses = ["enabled = 1", "COALESCE(material_code, '') <> ''"]
        params: list[Any] = []
        if top:
            clauses.append("top = ?")
            params.append(top)
        codes = unique_texts(material_codes, limit=100, max_length=160)
        if codes:
            clauses.append(f"material_code IN ({','.join('?' for _ in codes)})")
            params.extend(codes)
        if series_keyword:
            clauses.append("(series LIKE ? OR name LIKE ?)")
            params.extend([f"%{series_keyword}%", f"%{series_keyword}%"])
        with self.connect() as connection:
            rows = [
                dict(row)
                for row in connection.execute(
                    f"""
                    SELECT * FROM managed_materials
                    WHERE {' AND '.join(clauses)}
                    ORDER BY sort_order ASC, updated_at DESC, id ASC
                    """,
                    params,
                ).fetchall()
            ]
            taxonomy_assets: dict[tuple[str, str, str, str], list[str]] = {}
            try:
                taxonomy_rows = connection.execute(
                    """
                    SELECT s.top AS top, COALESCE(c.name, '') AS category, s.name AS series,
                           COALESCE(s.material_code, '') AS material_code, s.image_urls_json
                    FROM material_taxonomy s
                    LEFT JOIN material_taxonomy c ON c.item_id=s.parent_id
                    WHERE s.kind='series' AND s.enabled=1
                    """
                ).fetchall()
                for row in taxonomy_rows:
                    item = dict(row)
                    key = (
                        str(item.get("top") or ""),
                        str(item.get("category") or ""),
                        str(item.get("series") or ""),
                        str(item.get("material_code") or ""),
                    )
                    taxonomy_assets[key] = self._row_images(item)
            except Exception:
                taxonomy_assets = {}
        grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
        for row in rows:
            key = (
                str(row.get("top") or ""),
                str(row.get("category") or ""),
                str(row.get("series") or row.get("name") or ""),
                str(row.get("material_code") or ""),
            )
            grouped.setdefault(key, []).append(row)
        targets: list[MaterialTaggingTarget] = []
        for key, group_rows in grouped.items():
            target_id = self.target_id(*key)
            images: list[str] = []
            for row in group_rows:
                images.extend(self._row_images(row))
            images.extend(taxonomy_assets.get(key, []))
            images = deduplicate_image_urls(images, limit=MAX_IMAGES)
            if require_gallery and not images:
                continue
            facts = self._material_facts(group_rows, target_id)
            updated_at = max(str(row.get("updated_at") or "") for row in group_rows)
            targets.append(
                MaterialTaggingTarget(
                    target_id=target_id,
                    material_code=key[3],
                    top=key[0],
                    category=key[1],
                    series=key[2],
                    name=key[2],
                    known_facts=facts,
                    image_urls=images,
                    source_updated_at=updated_at,
                )
            )
            if len(targets) >= max(1, min(int(limit), 100)):
                break
        return targets

    @staticmethod
    def fingerprint(target: MaterialTaggingTarget, model_id: str) -> str:
        source = {
            "target_id": target.target_id,
            "known_facts": target.known_facts,
            "image_urls": target.image_urls,
            "source_updated_at": target.source_updated_at,
            "model_id": model_id,
            "prompt_version": PROMPT_VERSION,
            "schema_version": SCHEMA_VERSION,
        }
        return hashlib.sha256(json_text(source).encode()).hexdigest()

    def find_reusable(self, target: MaterialTaggingTarget, model_id: str) -> dict[str, Any] | None:
        fingerprint = self.fingerprint(target, model_id)
        with self.connect() as connection:
            try:
                row = connection.execute(
                    """
                    SELECT * FROM ai_material_annotations
                    WHERE input_fingerprint=? AND status IN ('pending_review', 'approved', 'applied')
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (fingerprint,),
                ).fetchone()
            except Exception as exc:
                raise RuntimeError("AI材料标注表尚未迁移，请先执行数据库升级") from exc
        return self.public_annotation(dict(row)) if row else None

    def save_result(
        self,
        target: MaterialTaggingTarget,
        model_id: str,
        response: MaterialAnalysisResponse,
    ) -> dict[str, Any]:
        timestamp = now_iso()
        annotation_id = f"mat_ai_{uuid.uuid4().hex}"
        values = {
            "annotation_id": annotation_id,
            "target_id": target.target_id,
            "material_code": target.material_code,
            "top": target.top,
            "category": target.category,
            "series": target.series,
            "model_id": model_id,
            "prompt_version": PROMPT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "input_fingerprint": self.fingerprint(target, model_id),
            "image_urls_json": json_text(target.image_urls),
            "known_facts_json": json_text(target.known_facts),
            "raw_response_json": response.raw_response,
            "parsed_response_json": json_text(response.result.model_dump()),
            "reviewer_final_json": "",
            "status": "pending_review",
            "request_id": response.request_id,
            "usage_json": json_text(response.usage),
            "error_code": "",
            "error_message": "",
            "review_notes": "",
            "reviewer_id": "",
            "reviewer_name": "",
            "reviewed_at": None,
            "source_updated_at": target.source_updated_at,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO ai_material_annotations
                (annotation_id, target_id, material_code, top, category, series, model_id,
                 prompt_version, schema_version, input_fingerprint, image_urls_json,
                 known_facts_json, raw_response_json, parsed_response_json, reviewer_final_json,
                 status, request_id, usage_json, error_code, error_message, review_notes,
                 reviewer_id, reviewer_name, reviewed_at, source_updated_at, created_at, updated_at)
                VALUES
                (:annotation_id, :target_id, :material_code, :top, :category, :series, :model_id,
                 :prompt_version, :schema_version, :input_fingerprint, :image_urls_json,
                 :known_facts_json, :raw_response_json, :parsed_response_json, :reviewer_final_json,
                 :status, :request_id, :usage_json, :error_code, :error_message, :review_notes,
                 :reviewer_id, :reviewer_name, :reviewed_at, :source_updated_at, :created_at, :updated_at)
                """,
                values,
            )
        return self.get(annotation_id)

    def save_failure(
        self,
        target: MaterialTaggingTarget,
        model_id: str,
        error: Exception,
    ) -> dict[str, Any]:
        timestamp = now_iso()
        annotation_id = f"mat_ai_{uuid.uuid4().hex}"
        error_code = getattr(error, "code", type(error).__name__)
        error_message = str(error or "打标失败")[:500]
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO ai_material_annotations
                (annotation_id, target_id, material_code, top, category, series, model_id,
                 prompt_version, schema_version, input_fingerprint, image_urls_json,
                 known_facts_json, raw_response_json, parsed_response_json, reviewer_final_json,
                 status, request_id, usage_json, error_code, error_message, review_notes,
                 reviewer_id, reviewer_name, reviewed_at, source_updated_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', '', 'failed', '', '{}', ?, ?,
                        '', '', '', NULL, ?, ?, ?)
                """,
                (
                    annotation_id,
                    target.target_id,
                    target.material_code,
                    target.top,
                    target.category,
                    target.series,
                    model_id,
                    PROMPT_VERSION,
                    SCHEMA_VERSION,
                    self.fingerprint(target, model_id),
                    json_text(target.image_urls),
                    json_text(target.known_facts),
                    str(error_code)[:80],
                    error_message,
                    target.source_updated_at,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get(annotation_id)

    def get(self, annotation_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM ai_material_annotations WHERE annotation_id=?",
                (annotation_id,),
            ).fetchone()
        if not row:
            raise ValueError("AI材料标注记录不存在")
        return self.public_annotation(dict(row))

    def list_annotations(
        self,
        *,
        status: str = "",
        material_code: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if material_code:
            clauses.append("material_code=?")
            params.append(material_code)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(int(limit), 500)))
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM ai_material_annotations {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self.public_annotation(dict(row)) for row in rows]

    def review(
        self,
        annotation_id: str,
        *,
        action: Literal["approved", "rejected"],
        reviewer: dict[str, Any],
        final_payload: dict[str, Any] | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        current = self.get(annotation_id)
        if current["status"] not in {"pending_review", "approved", "rejected"}:
            raise ValueError("只有待审核或已审核记录可以重新审核")
        if action == "approved":
            payload = final_payload or current["parsed_response"]
            validated = MaterialTaggingResult.model_validate(payload).model_dump()
            if validated["target_id"] != current["target_id"]:
                raise ValueError("审核结果的目标ID不一致")
            if validated["material_code"] != current["material_code"]:
                raise ValueError("审核结果的材料编码不一致")
            final_json = json_text(validated)
        else:
            final_json = ""
        timestamp = now_iso()
        reviewer_id = str(reviewer.get("admin_id") or reviewer.get("id") or "")[:80]
        reviewer_name = str(
            reviewer.get("display_name") or reviewer.get("username") or reviewer_id
        )[:120]
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE ai_material_annotations
                SET status=?, reviewer_final_json=?, review_notes=?, reviewer_id=?,
                    reviewer_name=?, reviewed_at=?, updated_at=?
                WHERE annotation_id=?
                """,
                (
                    action,
                    final_json,
                    str(notes or "")[:1000],
                    reviewer_id,
                    reviewer_name,
                    timestamp,
                    timestamp,
                    annotation_id,
                ),
            )
        return self.get(annotation_id)

    def apply_to_material(
        self,
        annotation_id: str,
        *,
        operator: dict[str, Any],
        audit_callback: Callable[..., None] | None = None,
    ) -> dict[str, Any]:
        current = self.get(annotation_id)
        if current["status"] == "applied":
            return current
        if current["status"] != "approved":
            raise ValueError("只有审核通过的AI标注才能应用到材料资料")
        payload = current.get("reviewer_final") or current.get("parsed_response") or {}
        validated = MaterialTaggingResult.model_validate(payload)
        if validated.target_id != current["target_id"]:
            raise ValueError("审核结果的目标ID不一致，不能应用")
        if validated.material_code != current["material_code"]:
            raise ValueError("审核结果的材料编码不一致，不能应用")
        application = material_application_fields(validated)
        timestamp = now_iso()
        material_code = current["material_code"]
        with self.connect() as connection:
            claimed = connection.execute(
                """
                UPDATE ai_material_annotations
                SET status='applying', updated_at=?
                WHERE annotation_id=? AND status='approved'
                """,
                (timestamp, annotation_id),
            )
            if int(claimed.rowcount or 0) != 1:
                row = connection.execute(
                    "SELECT * FROM ai_material_annotations WHERE annotation_id=?",
                    (annotation_id,),
                ).fetchone()
                if row and row["status"] == "applied":
                    return self.public_annotation(dict(row))
                raise ValueError("该标注正在应用或状态已经变化，请刷新后重试")

            material_row = connection.execute(
                """
                SELECT top, category, COALESCE(NULLIF(series, ''), name, '') AS series
                FROM managed_materials
                WHERE material_code=?
                ORDER BY enabled DESC, sort_order ASC, id ASC
                LIMIT 1
                """,
                (material_code,),
            ).fetchone()
            if not material_row:
                raise ValueError("目标材料已不存在，无法应用AI标注")
            material = {
                **dict(material_row),
                "material_code": material_code,
                "name": current.get("series") or material_row["series"] or material_code,
            }
            before = fetch_knowledge_map([material_code], connection).get(material_code) or {}
            merged_visual_tags = list(
                dict.fromkeys(
                    [
                        *(before.get("visual_tags") or []),
                        *application["visual_tags"],
                    ]
                )
            )
            merged_mood_tags = list(
                dict.fromkeys(
                    [
                        *(before.get("mood_tags") or []),
                        *application["mood_tags"],
                    ]
                )
            )
            previous_params = dict(before.get("material_params") or {})
            ai_params = dict(application["material_params"])
            merged_texture_features = list(
                dict.fromkeys(
                    [
                        *(previous_params.get("texture_features") or []),
                        *(ai_params.get("texture_features") or []),
                    ]
                )
            )
            material_params = {
                **previous_params,
                **ai_params,
                "texture_features": merged_texture_features,
            }
            ai_profile = {
                **application["ai_visual_profile"],
                "annotation_id": annotation_id,
                "model_id": current.get("model_id") or "",
                "schema_version": current.get("schema_version") or "",
                "applied_at": timestamp,
            }
            write_payload = {
                **before,
                "code": material_code,
                "material_code": material_code,
                "name": before.get("name") or material["name"],
                "visual_tags": merged_visual_tags,
                "mood_tags": merged_mood_tags,
                "allowed_roles": application["allowed_roles"] or before.get("allowed_roles") or [],
                "match_rules": application["match_rules"] or before.get("match_rules") or [],
                "color_family": application["color_family"] or before.get("color_family") or "",
                "material_params": material_params,
                "asset": {
                    **(before.get("asset") or {}),
                    "ai_visual_profile": ai_profile,
                },
                "enabled": before.get("enabled", True),
            }
            after = upsert_material_knowledge(
                write_payload,
                material,
                connection=connection,
                force_update=True,
            )
            if audit_callback:
                audit_callback(
                    connection,
                    action="ai_tag_apply",
                    target_type="material_knowledge",
                    target_id=material_code,
                    before=before,
                    after={**after, "material_code": material_code},
                    actor=operator,
                    summary=f"应用AI视觉标注：{material['name']}",
                )
            connection.execute(
                """
                UPDATE ai_material_annotations
                SET status='applied', updated_at=?
                WHERE annotation_id=? AND status='applying'
                """,
                (timestamp, annotation_id),
            )
        invalidate_material_cache()
        return self.get(annotation_id)

    @staticmethod
    def public_annotation(row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        image_urls = json_value(data.pop("image_urls_json", ""), [])
        known_facts = json_value(data.pop("known_facts_json", ""), {})
        raw_response = str(data.pop("raw_response_json", "") or "")
        parsed_response = json_value(data.pop("parsed_response_json", ""), {})
        reviewer_final = json_value(data.pop("reviewer_final_json", ""), {})
        usage = json_value(data.pop("usage_json", ""), {})
        payload = reviewer_final or parsed_response
        application_fields: dict[str, Any] = {}
        if payload:
            try:
                application_fields = material_application_fields(
                    MaterialTaggingResult.model_validate(payload)
                )
            except ValueError:
                application_fields = {}
        return {
            **data,
            "image_urls": image_urls,
            "known_facts": known_facts,
            "raw_response": raw_response,
            "parsed_response": parsed_response,
            "reviewer_final": reviewer_final,
            "usage": usage,
            "application": {
                "can_apply": data.get("status") == "approved",
                "applied": data.get("status") == "applied",
                "fields": application_fields,
            },
        }


class MaterialTaggingService:
    def __init__(
        self,
        repository: MaterialTaggingRepository | None = None,
        client: BailianMaterialTaggingClient | None = None,
    ):
        self.repository = repository or MaterialTaggingRepository()
        self.client = client

    def analyze_targets(
        self,
        targets: list[MaterialTaggingTarget],
        *,
        force: bool = False,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        client = self.client or BailianMaterialTaggingClient(api_key=api_key)
        results: list[dict[str, Any]] = []
        for target in targets:
            if not force:
                reusable = self.repository.find_reusable(target, client.model)
                if reusable:
                    results.append(
                        {
                            "target_id": target.target_id,
                            "material_code": target.material_code,
                            "series": target.series,
                            "status": "skipped",
                            "annotation_id": reusable["annotation_id"],
                        }
                    )
                    continue
            try:
                response = client.analyze(target)
                saved = self.repository.save_result(target, client.model, response)
                results.append(
                    {
                        "target_id": target.target_id,
                        "material_code": target.material_code,
                        "series": target.series,
                        "status": saved["status"],
                        "annotation_id": saved["annotation_id"],
                        "confidence": saved["parsed_response"].get("confidence"),
                    }
                )
            except Exception as exc:
                saved = self.repository.save_failure(target, client.model, exc)
                results.append(
                    {
                        "target_id": target.target_id,
                        "material_code": target.material_code,
                        "series": target.series,
                        "status": "failed",
                        "annotation_id": saved["annotation_id"],
                        "error_code": saved["error_code"],
                        "error_message": saved["error_message"],
                    }
                )
        return {
            "model_id": client.model,
            "prompt_version": PROMPT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "total": len(results),
            "pending_review": sum(item["status"] == "pending_review" for item in results),
            "skipped": sum(item["status"] == "skipped" for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
            "items": results,
        }
