from __future__ import annotations

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from .admin_service import AdminService
from .avatar_storage import AvatarStorage
from .order_service import OrderService

admin_router = APIRouter(prefix="/api/v1/admin", tags=["后台管理"])
admin_service = AdminService()
order_service = OrderService()
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


class AdminAccountUpdatePayload(BaseModel):
    display_name: str | None = Field(default="", max_length=120)
    role: str | None = Field(default=None, max_length=40)
    status: str | None = Field(default=None, max_length=20)
    password: str | None = Field(default="", max_length=80)


class MaterialPayload(BaseModel):
    id: str | None = None
    skuId: str | None = ""
    top: str
    category: str
    series: str | None = ""
    grade: str | None = ""
    name: str
    effect: str
    element: str
    price: float = 0
    size: float = 8
    weight: float = 1
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
    carrier: str = "顺丰速运"
    carrier_code: str = "shunfeng"
    tracking_no: str
    phone_tail: str = ""


class OrderStatusPayload(BaseModel):
    status: str
    note: str = ""


class OrderRefundReviewPayload(BaseModel):
    note: str = Field(default="", max_length=300)


class WechatOrderPathPayload(BaseModel):
    path: str = "/pages/order-detail/order-detail?id=${商品订单号}"


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


@admin_router.get("/assessments", summary="测算记录列表")
def assessments(
    keyword: str = Query(default="", max_length=80),
    core_wish: str = Query(default="", max_length=80),
    hide_tests: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_assessments(keyword=keyword, core_wish=core_wish, hide_tests=hide_tests, limit=limit))


@admin_router.get("/daily-energies", summary="每日能量记录列表")
def daily_energies(
    keyword: str = Query(default="", max_length=80),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_daily_energies(keyword=keyword, limit=limit))


@admin_router.get("/checkins", summary="每日签到记录")
def checkins(
    keyword: str = Query(default="", max_length=80),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_checkins(keyword=keyword, limit=limit))


@admin_router.get("/orders", summary="后台订单列表")
def orders(
    keyword: str = Query(default="", max_length=80),
    status: str = Query(default="", max_length=40),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_orders(keyword=keyword, status=status, limit=limit))


@admin_router.get("/orders/{order_id}", summary="后台订单详情")
def order_detail(order_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.get_order(order_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.post("/orders/{order_id}/ship", summary="后台订单发货")
def ship_order(
    order_id: str,
    payload: OrderShipPayload,
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    try:
        return success(
            admin_service.ship_order(
                order_id,
                payload.carrier,
                payload.tracking_no,
                payload.carrier_code,
                payload.phone_tail,
            ),
            "订单已发货",
        )
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


@admin_router.post("/orders/{order_id}/status", summary="后台调整订单状态")
def update_order_status(
    order_id: str,
    payload: OrderStatusPayload,
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    try:
        return success(admin_service.update_order_status(order_id, payload.status, payload.note), "订单状态已更新")
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


@admin_router.get("/materials", summary="后台材料列表")
def materials(
    keyword: str = Query(default="", max_length=80),
    top: str = Query(default="", max_length=40),
    element: str = Query(default="", max_length=20),
    status: str = Query(default="", max_length=20),
    sort_by: str = Query(default="sort_order", max_length=40),
    sort_order: str = Query(default="asc", max_length=10),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(
        admin_service.list_materials(
            keyword=keyword,
            top=top,
            element=element,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    )


@admin_router.post("/materials", summary="新增材料")
def create_material(payload: MaterialPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_material(payload.model_dump()), "材料已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.put("/materials/{material_id}", summary="更新材料")
def update_material(material_id: str, payload: MaterialPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_material(payload.model_dump(), material_id=material_id), "材料已更新")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/materials/{material_id}", summary="删除材料")
def delete_material(material_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    admin_service.delete_material(material_id)
    return success({"deleted": material_id}, "材料已删除")


@admin_router.post("/materials/batch", summary="批量操作珠材")
def batch_materials(payload: MaterialBatchPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.batch_update_materials(payload.ids, payload.action, payload.value), "批量操作已完成")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
