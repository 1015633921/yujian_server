from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field, field_validator

from .admin_service import AdminService
from .avatar_storage import AvatarStorage
from .design_candidates import build_design_candidates
from .custom_design_service import CustomDesignService
from .material_asset_upload import (
    MATERIAL_ASSET_PREFIX,
    MAX_MATERIAL_ASSET_BYTES,
    MAX_MATERIAL_ASSET_COUNT,
    validate_material_asset_key,
    validate_material_ready_webp,
)
from .order_service import OrderConflictError, OrderService

admin_router = APIRouter(prefix="/api/v1/admin", tags=["后台管理"])
admin_service = AdminService()
order_service = OrderService()
custom_design_service = CustomDesignService()
media_storage = AvatarStorage()


class AdminAuthPayload(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6, max_length=80)


class AdminAccountPayload(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=80)
    display_name: str | None = Field(default="", max_length=120)
    role: str = Field(default="operator", max_length=40)
    status: str = Field(default="active", max_length=20)


class CustomDesignWorkbenchPayload(BaseModel):
    wrist_size_cm: float = Field(ge=10, le=25)
    bead_size_mm: float = Field(ge=6, le=16)
    layout: list[dict[str, Any]] = Field(min_length=1, max_length=40)
    notes: str = Field(default="", max_length=1000)

    @field_validator("layout")
    @classmethod
    def validate_layout(cls, values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        for index, value in enumerate(values):
            if not isinstance(value, dict):
                raise ValueError(f"第 {index + 1} 个材料格式无效")
            material_id = str(
                value.get("material_id")
                or value.get("sku_id")
                or value.get("id")
                or ""
            ).strip()
            if not material_id or len(material_id) > 120:
                raise ValueError(f"第 {index + 1} 个材料缺少有效 ID")
            image_url = str(
                value.get("selected_image_url")
                or value.get("image_url")
                or ""
            ).strip()
            if image_url and (
                not image_url.startswith(("https://", "http://"))
                or len(image_url) > 2000
            ):
                raise ValueError(f"第 {index + 1} 个材料图片地址无效")
            cleaned.append(
                {
                    **value,
                    "id": material_id,
                    "material_id": material_id,
                    "quantity": 1,
                    "selected_image_url": image_url,
                }
            )
        return cleaned


class CustomDesignDraftPayload(CustomDesignWorkbenchPayload):
    pass


class CustomDesignProposalPayload(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    image_urls: list[str] = Field(default_factory=list, max_length=6)
    workbench: CustomDesignWorkbenchPayload

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            url = str(value or "").strip()
            if not url.startswith(("https://", "http://")) or len(url) > 2000:
                raise ValueError("方案图片必须是有效的图片地址")
            if url not in cleaned:
                cleaned.append(url)
        return cleaned


class CustomDesignCandidatePayload(BaseModel):
    """Current workbench materials, used only to surface compatibility cautions."""

    selected_material_ids: list[str] = Field(default_factory=list, max_length=40)
    wrist_size_cm: float | None = Field(default=None, ge=10, le=25)
    bead_size_mm: float | None = Field(default=None, ge=6, le=16)

    @field_validator("selected_material_ids")
    @classmethod
    def validate_selected_material_ids(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            material_id = str(value or "").strip()
            if not material_id or len(material_id) > 120:
                raise ValueError("材料 ID 无效")
            if material_id not in cleaned:
                cleaned.append(material_id)
        return cleaned


def validated_custom_design_workbench(
    payload: CustomDesignWorkbenchPayload,
) -> dict[str, Any]:
    raw = payload.model_dump(mode="json")
    requested_layout = raw["layout"]
    snapshots = order_service.validate_and_refresh_material_prices(requested_layout)
    layout: list[dict[str, Any]] = []
    for requested, snapshot in zip(requested_layout, snapshots, strict=True):
        selected_image_url = str(requested.get("selected_image_url") or "").strip()
        gallery_images = [
            str(url).strip()
            for url in snapshot.get("gallery_image_urls") or []
            if str(url).strip()
        ]
        allowed_images = set(gallery_images)
        if selected_image_url and selected_image_url not in allowed_images:
            raise ValueError(f"{snapshot.get('name') or '材料'}的图库图片已更新，请重新选择")
        if not allowed_images:
            raise ValueError(f"{snapshot.get('name') or '材料'}暂无图库图片，不能用于实物搭配")
        exact_image_url = selected_image_url or gallery_images[0]
        layout.append(
            {
                **snapshot,
                "id": snapshot["id"],
                "material_id": snapshot["id"],
                "quantity": 1,
                "selected_image_url": exact_image_url,
                "image_url": exact_image_url,
            }
        )
    total_fee = sum(int(item.get("subtotal_cents") or 0) for item in layout)
    return {
        "schema_version": 1,
        "wrist_size_cm": raw["wrist_size_cm"],
        "bead_size_mm": raw["bead_size_mm"],
        "layout": layout,
        "selected": [item["id"] for item in layout],
        "notes": raw.get("notes") or "",
        "summary": {
            "count": len(layout),
            "total_fee": total_fee,
            "price": order_service.cents_text(total_fee),
        },
    }


class CustomDesignSettingsPayload(BaseModel):
    daily_capacity: int = Field(ge=0, le=200)
    sla_hours: int = Field(ge=1, le=168)
    deposit_amount_fee: int = Field(ge=100, le=100000)


class AdminAccountUpdatePayload(BaseModel):
    display_name: str | None = Field(default="", max_length=120)
    role: str | None = Field(default=None, max_length=40)
    status: str | None = Field(default=None, max_length=20)
    password: str | None = Field(default="", max_length=80)


class MaterialPayload(BaseModel):
    id: str | None = None
    skuId: str | None = ""
    material_code: str | None = ""
    top: str
    category: str
    series: str | None = ""
    grade: str | None = ""
    name: str
    effect: str = ""
    element: str = ""
    primary_element: str | None = ""
    secondary_elements: list[str] = Field(default_factory=list)
    chakras: list[str] = Field(default_factory=list)
    chakra_weights: dict = Field(default_factory=dict)
    effects: list[str] = Field(default_factory=list)
    wish_pools: list[str] = Field(default_factory=list)
    color_family: str | None = ""
    mood_tags: list[str] = Field(default_factory=list)
    visual_tags: list[str] = Field(default_factory=list)
    story: str | None = ""
    allowed_roles: list[str] = Field(default_factory=list)
    conflict_codes: list[str] = Field(default_factory=list)
    match_rules: list[str] = Field(default_factory=list)
    care_tags: list[str] = Field(default_factory=list)
    material_params: dict = Field(default_factory=dict)
    physical_specs: dict = Field(default_factory=dict)
    bead_shape: str | None = ""
    surface_finish: str | None = ""
    transparency_level: str | None = ""
    texture_features: list[str] = Field(default_factory=list)
    batch_variation: str | None = ""
    hole_diameter_mm: float | None = None
    size_tolerance_mm: float | None = None
    asset: dict = Field(default_factory=dict)
    thumbnail_url: str | None = ""
    diffuse_map_url: str | None = ""
    normal_map_url: str | None = ""
    glb_model_url: str | None = ""
    preview_render_url: str | None = ""
    price: float = 0
    size: float = 8
    weight: float = 1
    cost_price: float = 0
    safety_stock: int = 0
    supplier_name: str | None = ""
    purchase_note: str | None = ""
    color: str = "#dfe3e5"
    shine: str = "#ffffff"
    image_path: str | None = ""
    image_url: str | None = ""
    image_urls: list[str] = Field(default_factory=list)
    stock: int = 0
    enabled: bool = True
    sort_order: int = 0


class MaterialBatchPayload(BaseModel):
    ids: list[str]
    action: str
    value: float | int | str | None = None


class MaterialAssetBindPayload(BaseModel):
    series_id: str = Field(min_length=1, max_length=120)
    asset_keys: list[str] = Field(min_length=1, max_length=MAX_MATERIAL_ASSET_COUNT)
    mode: Literal["replace", "append"] = "replace"
    # Kept for older admin clients; series assets are now always authoritative.
    sync_sku_images: bool = True


class MaterialTypePayload(BaseModel):
    id: str | None = None
    code: str | None = Field(default="", max_length=40)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default="", max_length=500)
    sort_order: int = 0
    enabled: bool = True


class MaterialCategoryPayload(BaseModel):
    id: str | None = None
    top: str = "bead"
    name: str
    sort_order: int = 0
    enabled: bool = True


class MaterialCategoryBatchDeletePayload(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)


class MaterialDirectoryBatchDeletePayload(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)


class MaterialSeriesPayload(BaseModel):
    id: str | None = None
    category_id: str
    name: str
    material_code: str | None = ""
    color: str | None = "#dfe3e5"
    shine: str | None = "#ffffff"
    image_path: str | None = ""
    image_url: str | None = ""
    image_urls: list[str] = Field(default_factory=list)
    sync_sku_images: bool = False
    primary_element: str | None = ""
    secondary_elements: list[str] = Field(default_factory=list)
    chakras: list[str] = Field(default_factory=list)
    chakra_weights: dict = Field(default_factory=dict)
    effects: list[str] = Field(default_factory=list)
    wish_pools: list[str] = Field(default_factory=list)
    color_family: str | None = ""
    mood_tags: list[str] = Field(default_factory=list)
    visual_tags: list[str] = Field(default_factory=list)
    story: str | None = ""
    allowed_roles: list[str] = Field(default_factory=list)
    conflict_codes: list[str] = Field(default_factory=list)
    match_rules: list[str] = Field(default_factory=list)
    care_tags: list[str] = Field(default_factory=list)
    material_params: dict = Field(default_factory=dict)
    asset: dict = Field(default_factory=dict)
    sort_order: int = 0
    enabled: bool = True


class MaterialOptionPayload(BaseModel):
    id: str | None = None
    option_type: str
    key: str | None = ""
    label: str
    sort_order: int = 0
    enabled: bool = True


class ContentBlockPayload(BaseModel):
    block_id: str | None = None
    section: str = "home"
    title: str
    subtitle: str | None = ""
    body: str | None = ""
    image_url: str | None = ""
    action_text: str | None = ""
    action_url: str | None = ""
    status: str = "draft"
    sort_order: int = 0


class HomeBannerPayload(BaseModel):
    id: str | None = None
    banner_id: str | None = None
    title: str
    subtitle: str | None = ""
    eyebrow: str | None = ""
    image_url: str | None = ""
    actionText: str | None = ""
    action_text: str | None = ""
    actionUrl: str | None = ""
    action_url: str | None = ""
    theme: str = "dark"
    status: str = "draft"
    sort_order: int = 0


class CommunityPostPayload(BaseModel):
    id: str | None = None
    post_id: str | None = None
    title: str
    author: str = "宇涧主理人"
    desc: str | None = ""
    description: str | None = ""
    story: str | None = ""
    scene: str | None = ""
    authorNote: str | None = ""
    author_note: str | None = ""
    likes: int = 0
    tone: str = "clear"
    recipe: list[str] = []
    materials: list[str] = []
    tags: list[str] = []
    image_url: str | None = ""
    is_home_hot: bool = False
    status: str = "draft"
    sort_order: int = 0


class RecommendationPlanPayload(BaseModel):
    id: str | None = None
    plan_id: str | None = None
    name: str
    subtitle: str | None = ""
    desc: str | None = ""
    description: str | None = ""
    price: float = 0
    tone: str = "clear"
    recipe: list[str] = []
    materials: list[dict | str] = []
    designStory: str | None = ""
    design_story: str | None = ""
    designReason: str | None = ""
    design_reason: str | None = ""
    scenes: list[str] = []
    tags: list[str] = []
    image_url: str | None = ""
    is_home_hot: bool = True
    status: str = "draft"
    sort_order: int = 0


class OrderShipPayload(BaseModel):
    carrier: str = Field(default="顺丰速运", max_length=50)
    carrier_code: str = Field(default="shunfeng", min_length=1, max_length=40)
    tracking_no: str = Field(min_length=6, max_length=32)
    phone_tail: str = Field(default="", max_length=8)


class OrderRefundReviewPayload(BaseModel):
    note: str = Field(default="", max_length=300)


class AfterSaleReviewPayload(BaseModel):
    action: Literal[
        "reject",
        "approve_service",
        "request_return",
        "prepare_direct_refund",
        "confirm_return",
        "complete",
    ]
    note: str = Field(default="", max_length=500)


class AfterSaleRefundPayload(BaseModel):
    note: str = Field(default="", max_length=500)


class PaymentCompensationResolvePayload(BaseModel):
    action: Literal["refund_verified", "manual_settlement_verified"]
    note: str = Field(min_length=5, max_length=300)


class WechatOrderPathPayload(BaseModel):
    path: str = "/pages/order-detail/order-detail?id=${商品订单号}"


class DailyEnergyRulesPayload(BaseModel):
    rules: dict[str, Any] = Field(default_factory=dict)
    reset_to_default: bool = False


class WarehouseItemPayload(BaseModel):
    item_id: str | None = ""
    item_code: str | None = ""
    item_type: str = "bead"
    category: str | None = ""
    material_name: str
    size_mm: float = 0
    grade: str | None = ""
    color_label: str | None = ""
    quality_label: str | None = ""
    origin_place: str | None = ""
    unit: str = "颗"
    image_urls: list[str] = Field(default_factory=list)
    image_urls_text: str | None = ""
    remark: str | None = ""
    enabled: bool = True


class WarehouseInboundPayload(BaseModel):
    item_id: str
    supplier_id: str | None = ""
    location_id: str | None = ""
    quantity: int = Field(gt=0)
    unit_cost: float = 0
    purchase_date: str | None = ""
    inbound_at: str | None = ""
    quality_note: str | None = ""
    image_urls: list[str] = Field(default_factory=list)
    image_urls_text: str | None = ""
    certificate_urls: list[str] = Field(default_factory=list)
    certificate_urls_text: str | None = ""
    remark: str | None = ""


class WarehouseOutboundPayload(BaseModel):
    item_id: str
    batch_id: str | None = ""
    movement_type: str = "sale_out"
    channel_id: str | None = ""
    quantity: int = Field(gt=0)
    external_order_no: str | None = ""
    external_platform: str | None = ""
    reason: str | None = ""
    remark: str | None = ""
    occurred_at: str | None = ""


class WarehouseSupplierPayload(BaseModel):
    supplier_id: str | None = ""
    supplier_code: str | None = ""
    name: str
    contact_name: str | None = ""
    phone: str | None = ""
    address: str | None = ""
    remark: str | None = ""
    enabled: bool = True


class WarehouseLocationPayload(BaseModel):
    location_id: str | None = ""
    location_code: str | None = ""
    name: str
    area: str | None = ""
    shelf: str | None = ""
    box_no: str | None = ""
    remark: str | None = ""
    enabled: bool = True


class WarehouseChannelPayload(BaseModel):
    channel_id: str | None = ""
    channel_code: str | None = ""
    name: str
    channel_type: str = "manual"
    remark: str | None = ""
    enabled: bool = True


def success(data, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


def token_from_header(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization.strip()


def require_admin(authorization: str | None) -> dict:
    try:
        return admin_service.require_admin(token_from_header(authorization))
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_design_operator(authorization: str | None) -> dict:
    actor = require_admin(authorization)
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="只读账号不能处理人工搭配工单")
    return actor


def request_context(request: Request) -> dict[str, str]:
    return {
        "ip": request.client.host if request.client else "",
        "x_forwarded_for": request.headers.get("x-forwarded-for", ""),
        "user_agent": request.headers.get("user-agent", ""),
    }


@admin_router.post("/register", summary="注册后台管理员")
def register_admin():
    raise HTTPException(status_code=403, detail="后台公开注册已关闭，请由管理员在后台手动创建子账号")


@admin_router.post("/login", summary="后台登录")
def login_admin(payload: AdminAuthPayload, request: Request):
    try:
        return success(admin_service.login(payload.username, payload.password, request_context(request)), "登录成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/logout", summary="后台退出登录")
def logout_admin(authorization: str | None = Header(default=None)):
    admin_service.logout(token_from_header(authorization))
    return success({"ok": True}, "已退出")


@admin_router.get("/me", summary="当前后台用户")
def admin_me(authorization: str | None = Header(default=None)):
    return success(require_admin(authorization))


@admin_router.get("/admins", summary="管理员账号列表")
def list_admins(authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.list_admins(actor))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@admin_router.post("/admins", summary="新增管理员子账号")
def create_admin(payload: AdminAccountPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.create_admin_user(payload.model_dump(), actor), "管理员账号已创建")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.put("/admins/{admin_id}", summary="更新管理员子账号")
def update_admin(admin_id: str, payload: AdminAccountUpdatePayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.update_admin_user(admin_id, payload.model_dump(), actor), "管理员账号已更新")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/admins/{admin_id}", summary="停用管理员子账号")
def disable_admin(admin_id: str, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.disable_admin_user(admin_id, actor), "管理员账号已停用")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/login-logs", summary="后台登录留痕")
def login_logs(
    limit: int = Query(default=120, ge=1, le=300),
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    try:
        return success(admin_service.list_login_logs(actor, limit=limit))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@admin_router.get("/dashboard", summary="后台仪表盘")
def dashboard(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    return success(admin_service.dashboard())


@admin_router.get("/system-status", summary="后台系统配置状态")
def system_status(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    return success(admin_service.system_status())


@admin_router.post("/media/upload", summary="后台运营素材上传")
async def upload_admin_media(
    category: str = Form(default="content"),
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    safe_category = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in category)[:40] or "content"
    try:
        content = await file.read()
        result = media_storage.upload_media(
            prefix=f"admin/{safe_category}",
            user_id="assets",
            content=content,
            content_type=file.content_type,
            filename=file.filename,
            label="运营图片",
        )
        return success({"image_url": result.url, "url": result.url, "key": result.key}, "图片已上传")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@admin_router.post("/material-assets/upload", summary="上传已标准化的材料透明图")
async def upload_material_asset(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="只读账号不能上传材料素材")
    try:
        content = await file.read(MAX_MATERIAL_ASSET_BYTES + 1)
        inspection = validate_material_ready_webp(content)
        result = media_storage.upload_media(
            prefix=MATERIAL_ASSET_PREFIX,
            user_id=actor.get("admin_id") or actor.get("username") or "operator",
            content=content,
            content_type="image/webp",
            filename=file.filename or "material.webp",
            max_bytes=MAX_MATERIAL_ASSET_BYTES,
            label="材料透明图",
        )
        return success(
            {
                "image_url": result.url,
                "url": result.url,
                "key": result.key,
                "inspection": inspection.as_dict(),
            },
            "材料图片已上传",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@admin_router.post("/material-assets/bind", summary="绑定处理后的图片到材料品种")
def bind_material_assets(
    payload: MaterialAssetBindPayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="只读账号不能修改材料素材")
    try:
        keys = list(dict.fromkeys(validate_material_asset_key(value) for value in payload.asset_keys))
        urls = [media_storage.public_url(key) for key in keys]
        return success(
            admin_service.bind_material_series_images(
                payload.series_id,
                urls,
                mode=payload.mode,
                sync_sku_images=True,
                actor=actor,
            ),
            "材料图片已绑定",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/users", summary="小程序用户列表")
def users(
    keyword: str = Query(default="", max_length=80),
    profile_status: str = Query(default="", max_length=20),
    energy_tag: str = Query(default="", max_length=20),
    spend_level: str = Query(default="", max_length=20),
    start_date: str = Query(default="", max_length=20),
    end_date: str = Query(default="", max_length=20),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(
        admin_service.list_users(
            keyword=keyword,
            profile_status=profile_status,
            energy_tag=energy_tag,
            spend_level=spend_level,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    )


@admin_router.post("/users/avatar-sync", summary="同步用户头像到腾讯云对象存储")
def sync_user_avatars(
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    try:
        return success(admin_service.sync_user_avatars_to_cos(limit=limit), "用户头像已同步")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/users/{user_id}", summary="用户详情")
def user_detail(user_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.get_user_detail(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.get("/assessments", summary="分析记录列表")
def assessments(
    keyword: str = Query(default="", max_length=80),
    core_wish: str = Query(default="", max_length=80),
    hide_tests: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_assessments(keyword=keyword, core_wish=core_wish, hide_tests=hide_tests, limit=limit))


@admin_router.get("/daily-energies", summary="每日搭配记录列表")
def daily_energies(
    keyword: str = Query(default="", max_length=80),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_daily_energies(keyword=keyword, limit=limit))


@admin_router.get("/daily-energy-rules", summary="每日搭配规则配置")
def daily_energy_rules(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    return success(admin_service.daily_energy_rules())


@admin_router.put("/daily-energy-rules", summary="保存每日搭配规则配置")
def save_daily_energy_rules(
    payload: DailyEnergyRulesPayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    try:
        return success(admin_service.save_daily_energy_rules(payload.model_dump(), actor), "每日搭配规则已保存")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/checkins", summary="每日签到记录")
def checkins(
    keyword: str = Query(default="", max_length=80),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_checkins(keyword=keyword, limit=limit))


@admin_router.get("/custom-design-requests", summary="人工搭配工单列表")
def custom_design_requests(
    status: str = Query(default="", max_length=40),
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0, le=100000),
    include_meta: bool = Query(default=False),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(
        custom_design_service.list_for_admin(
            status=status,
            limit=limit,
            offset=offset,
            include_meta=include_meta,
        )
    )


@admin_router.get("/custom-design-requests/settings", summary="人工搭配服务设置")
def custom_design_settings(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    return success(custom_design_service.get_settings())


@admin_router.put("/custom-design-requests/settings", summary="更新人工搭配服务设置")
def update_custom_design_settings(
    payload: CustomDesignSettingsPayload,
    authorization: str | None = Header(default=None),
):
    require_design_operator(authorization)
    return success(custom_design_service.save_settings(payload.model_dump()), "人工搭配服务设置已保存")


@admin_router.get("/custom-design-requests/{request_id}", summary="人工搭配工单详情")
def custom_design_request_detail(request_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(custom_design_service.get_for_admin(request_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.get("/custom-design-requests/{request_id}/overview", summary="人工搭配工单首屏摘要")
def custom_design_request_overview(request_id: str, authorization: str | None = Header(default=None)):
    """Small V2 detail payload; the report evidence and proposal workbench load separately."""
    require_admin(authorization)
    try:
        return success(custom_design_service.get_admin_overview(request_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.get("/custom-design-requests/{request_id}/workbench", summary="人工搭配设计师工作台")
def custom_design_workbench(request_id: str, authorization: str | None = Header(default=None)):
    require_design_operator(authorization)
    try:
        return success(custom_design_service.get_admin_workbench(request_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.get("/custom-design-requests/{request_id}/assessment-evidence", summary="人工搭配测算依据")
def custom_design_assessment_evidence(request_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(custom_design_service.get_admin_assessment_evidence(request_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.get("/custom-design-requests/{request_id}/proposals", summary="人工搭配方案记录")
def custom_design_proposals(request_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(custom_design_service.list_admin_proposals(request_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.get(
    "/custom-design-requests/{request_id}/proposals/{proposal_id}/composition",
    summary="人工搭配方案材料组成",
)
def custom_design_proposal_composition(
    request_id: str,
    proposal_id: str,
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    try:
        return success(custom_design_service.get_admin_proposal_composition(request_id, proposal_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.get("/custom-design-requests/{request_id}/events", summary="人工搭配服务记录")
def custom_design_events(request_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(custom_design_service.list_admin_events(request_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.post("/custom-design-requests/{request_id}/material-candidates", summary="人工搭配材料候选")
def custom_design_material_candidates(
    request_id: str,
    payload: CustomDesignCandidatePayload,
    authorization: str | None = Header(default=None),
):
    """Return advisory candidates only; this endpoint never mutates a service order."""
    require_design_operator(authorization)
    try:
        design_request = custom_design_service.get_admin_overview(request_id)
        materials = admin_service.list_materials(
            status="enabled",
            sort_by="sort_order",
            sort_order="asc",
        )
        return success(
            build_design_candidates(
                design_request.get("design_brief"),
                materials,
                selected_material_ids=payload.selected_material_ids,
                wrist_size_cm=payload.wrist_size_cm,
                bead_size_mm=payload.bead_size_mm,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.put("/custom-design-requests/{request_id}/draft", summary="保存设计师结构化草稿")
def save_custom_design_draft(
    request_id: str,
    payload: CustomDesignDraftPayload,
    authorization: str | None = Header(default=None),
):
    actor = require_design_operator(authorization)
    try:
        workbench = validated_custom_design_workbench(payload)
        return success(
            custom_design_service.save_draft(
                request_id,
                str(actor.get("admin_id") or actor.get("username") or "operator"),
                workbench,
            ),
            "设计草稿已保存",
        )
    except (OrderConflictError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/custom-design-requests/{request_id}/proposal", summary="发布结构化人工搭配方案")
def publish_custom_design_proposal(
    request_id: str,
    payload: CustomDesignProposalPayload,
    authorization: str | None = Header(default=None),
):
    actor = require_design_operator(authorization)
    try:
        proposal_payload = payload.model_dump(mode="json")
        proposal_payload["workbench"] = validated_custom_design_workbench(payload.workbench)
        return success(
            custom_design_service.publish_proposal(
                request_id,
                str(actor.get("admin_id") or actor.get("username") or "operator"),
                proposal_payload,
            ),
            "方案已提交给用户",
        )
    except (OrderConflictError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/orders", summary="后台订单列表")
def orders(
    keyword: str = Query(default="", max_length=80),
    status: str = Query(default="", max_length=40),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    include_meta: bool = Query(default=False),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(
        admin_service.list_orders(
            keyword=keyword,
            status=status,
            limit=limit,
            offset=offset,
            include_meta=include_meta,
        )
    )


@admin_router.get("/after-sales", summary="后台售后工单列表")
def after_sale_cases(
    keyword: str = Query(default="", max_length=100),
    status: str = Query(default="", max_length=40),
    case_type: str = Query(default="", max_length=40),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    include_meta: bool = Query(default=False),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    try:
        return success(
            order_service.admin_list_after_sale_cases(
                keyword=keyword,
                status=status,
                case_type=case_type,
                limit=limit,
                offset=offset,
                include_meta=include_meta,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/after-sales/{case_id}", summary="后台售后工单详情")
def after_sale_case_detail(case_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(order_service.admin_get_after_sale_case(case_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.post("/after-sales/{case_id}/review", summary="后台审核售后工单")
def review_after_sale_case(
    case_id: str,
    payload: AfterSaleReviewPayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    operator = actor.get("username") or actor.get("display_name") or actor.get("admin_id") or "admin"
    try:
        result = order_service.review_after_sale_case(
            case_id,
            payload.action,
            operator=operator,
            note=payload.note,
        )
        return success(result, "售后工单已更新")
    except OrderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/after-sales/{case_id}/refund", summary="售后工单确认微信原路退款")
def refund_after_sale_case(
    case_id: str,
    payload: AfterSaleRefundPayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    operator = actor.get("username") or actor.get("display_name") or actor.get("admin_id") or "admin"
    try:
        return success(
            order_service.submit_after_sale_refund(case_id, operator=operator, note=payload.note),
            "已提交微信原路退款",
        )
    except OrderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/after-sales/{case_id}/refund/sync", summary="同步售后工单微信退款状态")
def sync_after_sale_case_refund(
    case_id: str,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    operator = actor.get("username") or actor.get("display_name") or actor.get("admin_id") or "admin"
    try:
        return success(
            order_service.sync_after_sale_refund(case_id, operator=operator),
            "微信退款状态已同步",
        )
    except OrderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/after-sales/{case_id}/refund/retry", summary="核对并恢复售后工单微信退款")
def retry_after_sale_case_refund(
    case_id: str,
    payload: AfterSaleRefundPayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    operator = actor.get("username") or actor.get("display_name") or actor.get("admin_id") or "admin"
    try:
        return success(
            order_service.retry_after_sale_refund(
                case_id,
                operator=operator,
                note=payload.note,
            ),
            "退款状态已核对并恢复",
        )
    except OrderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/orders/{order_id}", summary="后台订单详情")
def order_detail(order_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.get_order(order_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.get("/payments/compensations", summary="支付补偿待办列表")
def payment_compensations(
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(order_service.list_payment_compensations(limit=limit))


@admin_router.post("/payments/compensations/{event_id}/resolve", summary="确认支付补偿已处理")
def resolve_payment_compensation(
    event_id: str,
    payload: PaymentCompensationResolvePayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    operator = actor.get("username") or actor.get("display_name") or actor.get("admin_id") or "admin"
    try:
        return success(
            order_service.resolve_payment_compensation(
                event_id,
                action=payload.action,
                operator=operator,
                note=payload.note,
            ),
            "支付补偿记录已确认",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/orders/{order_id}/ship", summary="后台订单发货")
def ship_order(
    order_id: str,
    payload: OrderShipPayload,
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    try:
        result = admin_service.ship_order(
            order_id,
            payload.carrier,
            payload.tracking_no,
            payload.carrier_code,
            payload.phone_tail,
        )
        subscription = order_service.subscribe_order_logistics(order_id)
        result["logistics"] = order_service.get_order(order_id).get("logistics") or result.get("logistics") or {}
        result["logistics_subscription"] = subscription
        message = "订单已发货" if subscription.get("status") != "failed" else "订单已发货，物流订阅待重试"
        return success(result, message)
    except OrderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/orders/{order_id}/logistics/subscribe", summary="重试订单物流主动订阅")
def subscribe_order_logistics(order_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        result = order_service.subscribe_order_logistics(order_id)
        return success(result, "物流订阅已处理")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/wechat-trade/status", summary="查询微信发货与订单管理状态")
def wechat_trade_status(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.wechat_trade_status())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/wechat-trade/order-detail-path", summary="配置微信购物订单跳转路径")
def configure_wechat_order_path(
    payload: WechatOrderPathPayload,
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    try:
        return success(admin_service.configure_wechat_order_path(payload.path), "微信订单跳转路径已配置")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/orders/{order_id}/sync-wechat-shipping", summary="重新同步微信发货信息")
def sync_wechat_shipping(
    order_id: str,
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    try:
        return success(admin_service.sync_order_shipping_to_wechat(order_id), "微信发货信息已同步")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/orders/{order_id}/refund/approve", summary="后台同意退款并原路退回微信支付")
def approve_order_refund(
    order_id: str,
    payload: OrderRefundReviewPayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    operator = actor.get("username") or actor.get("display_name") or actor.get("admin_id") or ""
    try:
        order_service.approve_refund(order_id, operator=operator, note=payload.note)
        return success(admin_service.get_order(order_id), "已提交微信原路退款")
    except OrderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/orders/{order_id}/refund/reject", summary="后台拒绝退款申请")
def reject_order_refund(
    order_id: str,
    payload: OrderRefundReviewPayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    operator = actor.get("username") or actor.get("display_name") or actor.get("admin_id") or ""
    try:
        order_service.reject_refund(order_id, operator=operator, note=payload.note)
        return success(admin_service.get_order(order_id), "已拒绝退款申请")
    except OrderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/orders/{order_id}/refund/sync", summary="后台同步微信退款状态")
def sync_order_refund(
    order_id: str,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    operator = actor.get("username") or actor.get("display_name") or actor.get("admin_id") or ""
    try:
        order_service.sync_wechat_refund(order_id, operator=operator)
        return success(admin_service.get_order(order_id), "微信退款状态已同步")
    except OrderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/orders/{order_id}/refund/retry", summary="核对并恢复微信退款提交")
def retry_order_refund(
    order_id: str,
    payload: OrderRefundReviewPayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    operator = actor.get("username") or actor.get("display_name") or actor.get("admin_id") or ""
    try:
        order_service.retry_refund_submission(order_id, operator=operator, note=payload.note)
        return success(admin_service.get_order(order_id), "退款状态已核对并恢复")
    except OrderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/orders/{order_id}/logistics/refresh", summary="后台主动刷新订单物流")
def refresh_order_logistics(order_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(order_service.refresh_order_logistics(order_id, force=True), "物流状态已刷新")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/orders/logistics/refresh-all", summary="批量同步运输中订单物流")
def refresh_all_order_logistics(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    return success(order_service.refresh_active_shipments(), "运输中订单物流已同步")


@admin_router.post(
    "/maintenance/inventory-reservations/release-expired",
    summary="幂等释放过期库存预占",
)
def release_expired_inventory_reservations(
    limit: int = Query(default=100, ge=1, le=1000),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(order_service.release_expired_reservations(limit=limit), "过期库存预占处理完成")


@admin_router.get("/warehouse/overview", summary="仓库库存概览")
def warehouse_overview(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    return success(admin_service.warehouse_overview())


@admin_router.get("/warehouse/options", summary="仓库基础选项")
def warehouse_options(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    return success(admin_service.warehouse_options())


@admin_router.get("/warehouse/items", summary="仓库库存品列表")
def warehouse_items(
    keyword: str = Query(default="", max_length=120),
    category: str = Query(default="", max_length=120),
    item_type: str = Query(default="", max_length=40),
    enabled: str = Query(default="", max_length=10),
    limit: int = Query(default=300, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(
        admin_service.list_warehouse_items(
            keyword=keyword,
            category=category,
            item_type=item_type,
            enabled=enabled,
            limit=limit,
        )
    )


@admin_router.post("/warehouse/items", summary="新增仓库库存品")
def create_warehouse_item(payload: WarehouseItemPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.save_warehouse_item(payload.model_dump(), actor=actor), "库存品已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.put("/warehouse/items/{item_id}", summary="更新仓库库存品")
def update_warehouse_item(item_id: str, payload: WarehouseItemPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.save_warehouse_item(payload.model_dump(), item_id=item_id, actor=actor), "库存品已更新")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/warehouse/items/{item_id}", summary="停用仓库库存品")
def delete_warehouse_item(item_id: str, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.delete_warehouse_item(item_id, actor=actor), "库存品已停用")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/warehouse/batches", summary="仓库批次列表")
def warehouse_batches(
    keyword: str = Query(default="", max_length=120),
    item_id: str = Query(default="", max_length=80),
    status: str = Query(default="", max_length=40),
    limit: int = Query(default=300, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_warehouse_batches(keyword=keyword, item_id=item_id, status=status, limit=limit))


@admin_router.post("/warehouse/inbound", summary="仓库入库")
def create_warehouse_inbound(payload: WarehouseInboundPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.create_warehouse_inbound(payload.model_dump(), actor=actor), "入库已记录")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/warehouse/outbound", summary="仓库出库")
def create_warehouse_outbound(payload: WarehouseOutboundPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.create_warehouse_outbound(payload.model_dump(), actor=actor), "出库已记录")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/warehouse/movements", summary="仓库库存流水")
def warehouse_movements(
    keyword: str = Query(default="", max_length=120),
    item_id: str = Query(default="", max_length=80),
    movement_type: str = Query(default="", max_length=40),
    channel_id: str = Query(default="", max_length=80),
    start_date: str = Query(default="", max_length=20),
    end_date: str = Query(default="", max_length=20),
    limit: int = Query(default=300, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(
        admin_service.list_warehouse_movements(
            keyword=keyword,
            item_id=item_id,
            movement_type=movement_type,
            channel_id=channel_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    )


@admin_router.post("/warehouse/suppliers", summary="新增或更新仓库供应商")
def save_warehouse_supplier(payload: WarehouseSupplierPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.save_warehouse_supplier(payload.model_dump(), actor=actor), "供应商已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/warehouse/locations", summary="新增或更新仓位")
def save_warehouse_location(payload: WarehouseLocationPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.save_warehouse_location(payload.model_dump(), actor=actor), "仓位已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/warehouse/channels", summary="新增或更新出库渠道")
def save_warehouse_channel(payload: WarehouseChannelPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.save_warehouse_channel(payload.model_dump(), actor=actor), "渠道已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/materials", summary="后台材料列表")
def materials(
    keyword: str = Query(default="", max_length=80),
    top: str = Query(default="", max_length=40),
    category: str = Query(default="", max_length=100),
    element: str = Query(default="", max_length=20),
    status: str = Query(default="", max_length=20),
    quality: str = Query(default="", max_length=30),
    stock_state: str = Query(default="", max_length=20),
    margin: str = Query(default="", max_length=20),
    spec_state: str = Query(default="", max_length=20),
    sort_by: str = Query(default="sort_order", max_length=40),
    sort_order: str = Query(default="asc", max_length=10),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    if page is None and page_size is None:
        return success(
            admin_service.list_materials(
                keyword=keyword,
                top=top,
                category=category,
                element=element,
                status=status,
                quality=quality,
                stock_state=stock_state,
                margin=margin,
                spec_state=spec_state,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        )
    return success(
        admin_service.list_materials_paginated(
            keyword=keyword,
            top=top,
            category=category,
            element=element,
            status=status,
            quality=quality,
            stock_state=stock_state,
            margin=margin,
            spec_state=spec_state,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page or 1,
            page_size=page_size or 50,
        )
    )


@admin_router.get("/material-spus", summary="后台材料 SPU/SKU 列表")
def material_spus(
    keyword: str = Query(default="", max_length=80),
    top: str = Query(default="", max_length=40),
    category: str = Query(default="", max_length=100),
    element: str = Query(default="", max_length=20),
    status: str = Query(default="", max_length=20),
    quality: str = Query(default="", max_length=30),
    stock_state: str = Query(default="", max_length=20),
    margin: str = Query(default="", max_length=20),
    spec_state: str = Query(default="", max_length=20),
    sort_by: str = Query(default="sort_order", max_length=40),
    sort_order: str = Query(default="asc", max_length=10),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(
        admin_service.list_material_spus(
            keyword=keyword,
            top=top,
            category=category,
            element=element,
            status=status,
            quality=quality,
            stock_state=stock_state,
            margin=margin,
            spec_state=spec_state,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    )


@admin_router.get("/material-options", summary="后台材料规范选项")
def material_options(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    return success(admin_service.material_options_payload())


@admin_router.get("/material-types", summary="后台材料类型")
def material_types(
    include_disabled: bool = Query(default=True),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_material_types(include_disabled=include_disabled))


@admin_router.post("/material-types", summary="新增或更新材料类型")
def save_material_type(payload: MaterialTypePayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.save_material_type(payload.model_dump(exclude_unset=True), actor=actor), "材料类型已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/material-types/{type_code}", summary="停用材料类型")
def disable_material_type(type_code: str, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.disable_material_type(type_code, actor=actor), "材料类型已停用")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/material-refs", summary="后台材料轻量引用列表")
def material_refs(
    keyword: str = Query(default="", max_length=80),
    limit: int = Query(default=1000, ge=1, le=3000),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_material_refs(keyword=keyword, limit=limit))


@admin_router.get("/material-taxonomy", summary="后台材料分类与品种")
def material_taxonomy(
    top: str = Query(default="", max_length=40),
    include_disabled: bool = Query(default=True),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_material_taxonomy(top=top, include_disabled=include_disabled))


@admin_router.post("/material-taxonomy/categories", summary="新增或更新材料分类")
def save_material_category(payload: MaterialCategoryPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.save_material_category(payload.model_dump(), actor=actor), "分类已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/material-taxonomy/categories/batch-delete", summary="批量删除空材料分类")
def delete_empty_material_categories(
    payload: MaterialCategoryBatchDeletePayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    try:
        return success(
            admin_service.delete_empty_material_categories(payload.ids, actor=actor),
            "空材料分类已删除",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/material-types/batch-delete", summary="批量删除空材料类型")
def delete_empty_material_types(
    payload: MaterialDirectoryBatchDeletePayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    try:
        return success(admin_service.delete_empty_material_types(payload.ids, actor=actor), "空材料类型已删除")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/material-taxonomy/series", summary="新增或更新材料品种")
def save_material_series(payload: MaterialSeriesPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.save_material_series(payload.model_dump(exclude_unset=True), actor=actor), "品种已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/material-taxonomy/series/batch-delete", summary="批量删除空材料品种")
def delete_empty_material_series(
    payload: MaterialDirectoryBatchDeletePayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    try:
        return success(admin_service.delete_empty_material_series(payload.ids, actor=actor), "空材料品种已删除")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/material-taxonomy/{item_id}", summary="停用材料分类或品种")
def disable_material_taxonomy(item_id: str, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.disable_material_taxonomy_item(item_id, actor=actor), "分类或品种已停用")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/material-taxonomy/repair-enabled-state", summary="修复材料层级停用脏数据")
def repair_material_taxonomy_enabled_state(authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    return success(admin_service.repair_material_hierarchy_enabled_state(actor=actor), "材料层级停用状态已修复")


@admin_router.get("/material-option-items", summary="后台材料字段字典")
def material_option_items(
    option_type: str = Query(default="", max_length=40),
    include_disabled: bool = Query(default=True),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_material_option_items(option_type=option_type, include_disabled=include_disabled))


@admin_router.post("/material-option-items", summary="新增或更新材料字段字典")
def save_material_option_item(payload: MaterialOptionPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.save_material_option_item(payload.model_dump(), actor=actor), "字段选项已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/material-option-items/{item_id}", summary="停用材料字段字典")
def disable_material_option_item(item_id: str, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.disable_material_option_item(item_id, actor=actor), "字段选项已停用")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/materials", summary="新增材料")
def create_material(payload: MaterialPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.save_material(payload.model_dump(), actor=actor), "材料已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/materials/{material_id}", summary="后台材料详情")
def material_detail(material_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.get_material(material_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.put("/materials/{material_id}", summary="更新材料")
def update_material(material_id: str, payload: MaterialPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.save_material(payload.model_dump(), material_id=material_id, actor=actor), "材料已更新")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/materials/{material_id}", summary="删除材料")
def delete_material(material_id: str, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    admin_service.delete_material(material_id, actor=actor)
    return success({"deleted": material_id}, "材料已删除")


@admin_router.post("/materials/batch", summary="批量操作珠材")
def batch_materials(payload: MaterialBatchPayload, authorization: str | None = Header(default=None)):
    actor = require_admin(authorization)
    try:
        return success(admin_service.batch_update_materials(payload.ids, payload.action, payload.value, actor=actor), "批量操作已完成")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/materials/audit-logs", summary="材料资料变更记录")
def material_audit_logs(
    material_id: str = Query(default="", max_length=120),
    target_type: str = Query(default="", max_length=40),
    limit: int = Query(default=100, ge=1, le=300),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_material_audit_logs(material_id=material_id, target_type=target_type, limit=limit))


@admin_router.get("/home-banners", summary="home banners")
def home_banners(
    keyword: str = Query(default="", max_length=80),
    status: str = Query(default="", max_length=40),
    limit: int = Query(default=100, ge=1, le=200),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_home_banners(keyword=keyword, status=status, limit=limit))


@admin_router.post("/home-banners", summary="create home banner")
def create_home_banner(payload: HomeBannerPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_home_banner(payload.model_dump()), "Banner ???")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.put("/home-banners/{banner_id}", summary="update home banner")
def update_home_banner(banner_id: str, payload: HomeBannerPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_home_banner(payload.model_dump(), banner_id=banner_id), "Banner ???")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/home-banners/{banner_id}", summary="delete home banner")
def delete_home_banner(banner_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    admin_service.delete_home_banner(banner_id)
    return success({"deleted": banner_id}, "Banner ???")


@admin_router.get("/blocks", summary="板块内容列表")
def blocks(
    section: str = Query(default="", max_length=40),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_blocks(section=section))


@admin_router.post("/blocks", summary="新增板块内容")
def create_block(payload: ContentBlockPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_block(payload.model_dump()), "板块已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.put("/blocks/{block_id}", summary="更新板块内容")
def update_block(block_id: str, payload: ContentBlockPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_block(payload.model_dump(), block_id=block_id), "板块已更新")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/blocks/{block_id}", summary="删除板块内容")
def delete_block(block_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    admin_service.delete_block(block_id)
    return success({"deleted": block_id}, "板块已删除")


@admin_router.get("/community-posts", summary="社区灵感列表")
def community_posts(
    keyword: str = Query(default="", max_length=80),
    status: str = Query(default="", max_length=40),
    home_hot: bool | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_community_posts(keyword=keyword, status=status, is_home_hot=home_hot, limit=limit))


@admin_router.post("/community-posts", summary="新增社区灵感")
def create_community_post(payload: CommunityPostPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_community_post(payload.model_dump()), "社区灵感已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.put("/community-posts/{post_id}", summary="更新社区灵感")
def update_community_post(post_id: str, payload: CommunityPostPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_community_post(payload.model_dump(), post_id=post_id), "社区灵感已更新")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/community-posts/{post_id}", summary="删除社区灵感")
def delete_community_post(post_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    admin_service.delete_community_post(post_id)
    return success({"deleted": post_id}, "社区灵感已删除")


@admin_router.get("/recommendation-plans", summary="热门推荐方案列表")
def recommendation_plans(
    keyword: str = Query(default="", max_length=80),
    status: str = Query(default="", max_length=40),
    home_hot: bool | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_recommendation_plans(keyword=keyword, status=status, is_home_hot=home_hot, limit=limit))


@admin_router.post("/recommendation-plans", summary="新增热门推荐方案")
def create_recommendation_plan(payload: RecommendationPlanPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_recommendation_plan(payload.model_dump()), "推荐方案已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.put("/recommendation-plans/{plan_id}", summary="更新热门推荐方案")
def update_recommendation_plan(plan_id: str, payload: RecommendationPlanPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_recommendation_plan(payload.model_dump(), plan_id=plan_id), "推荐方案已更新")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/recommendation-plans/{plan_id}", summary="删除热门推荐方案")
def delete_recommendation_plan(plan_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    admin_service.delete_recommendation_plan(plan_id)
    return success({"deleted": plan_id}, "推荐方案已删除")
