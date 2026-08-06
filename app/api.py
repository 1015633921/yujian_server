from __future__ import annotations

import base64
import binascii
import json
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .auth_service import WechatAuthService
from . import order_service as order_service_module
from .avatar_storage import AvatarStorage
from .daily_service import DailyEnergyService
from .feature_flags import (
    checkout_enabled,
    mock_trade_enabled,
    payment_enabled,
    public_share_enabled,
    report_versioning_v2_enabled,
)
from .admin_service import AdminService
from .custom_design_service import CustomDesignService
from .materials import MaterialCatalogUnavailable, list_materials
from .order_service import (
    KUAIDI100_CALLBACK_MAX_BYTES,
    LogisticsCallbackSignatureError,
    OrderConflictError,
    OrderPriceChangedError,
    OrderPricingError,
    OrderService,
)
from .observability import Timer, current_request_id, log_event, metrics
from .recommendation import RecommendationEngine
from .report_repository import ReportConflictError, ReportVersionConflictError
from .schemas import (
    AfterSaleCancelRequest,
    AfterSaleCreateRequest,
    AfterSaleReturnShipmentRequest,
    AssessmentRequest,
    CartItemCreateRequest,
    CartItemUpdateRequest,
    CommunityFavoriteSaveRequest,
    CustomDesignRequestCreate,
    CustomDesignResponseRequest,
    DailyCheckInRequest,
    DIYDesignSaveRequest,
    DIYRecommendationRequest,
    OrderActionRequest,
    OrderCreateRequest,
    OrderReceiverUpdateRequest,
    OrderRefundRequest,
    OrderShipRequest,
    PhoneBindRequest,
    UserAddressActionRequest,
    UserAddressRequest,
    UserProfileUpdateRequest,
    WechatLoginRequest,
)
from .service import AssessmentService
from .user_sessions import (
    UserPrincipal,
    private_not_found,
    require_current_user,
    require_owner,
    session_service,
)

router = APIRouter(prefix="/api/v1", tags=["专属水晶分析"])
legacy_router = APIRouter(prefix="/api", tags=["兼容接口"])
service = AssessmentService()
daily_service = DailyEnergyService()
auth_service = WechatAuthService()
avatar_storage = AvatarStorage()
admin_content_service = AdminService()
order_service = OrderService()
custom_design_service = CustomDesignService(order_service=order_service)
BEIJING_TZ = ZoneInfo("Asia/Shanghai")
LOGGER = logging.getLogger("yujian.business")


def success(data, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


def beijing_today() -> date:
    return datetime.now(BEIJING_TZ).date()


def owned_payload(payload: BaseModel, principal: UserPrincipal):
    require_owner(principal, getattr(payload, "user_id", None))
    return payload.model_copy(update={"user_id": principal.user_id})


def require_feature(enabled: bool, message: str) -> None:
    if not enabled:
        raise HTTPException(status_code=503, detail=message)


def require_mock_trade_tools() -> None:
    if not mock_trade_enabled():
        raise HTTPException(status_code=404, detail="Not Found")


def require_assessment_owner(assessment_id: str, principal: UserPrincipal) -> dict:
    result = service.get(assessment_id)
    owner_id = str(((result or {}).get("input_summary") or {}).get("user_id") or "")
    if not result or owner_id != principal.user_id:
        raise private_not_found()
    return result


def report_version_conflict(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": "report_version_conflict", "message": str(exc)},
    )


def require_report_owner(
    report_id: str,
    principal: UserPrincipal,
    expected_version: int | None = None,
) -> dict:
    try:
        snapshot = service.report_repository.owned(report_id, principal.user_id, expected_version)
    except ReportVersionConflictError as exc:
        raise report_version_conflict(exc) from exc
    if not snapshot:
        raise private_not_found()
    return snapshot


def require_order_owner(order_id: str, principal: UserPrincipal) -> dict:
    try:
        order = order_service.get_order(order_id)
        order_service.ensure_order_owner(order, principal.user_id)
        return order
    except ValueError as exc:
        raise private_not_found() from exc


class AvatarBase64Payload(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    content_base64: str = Field(min_length=1)
    content_type: str | None = Field(default=None, max_length=80)
    filename: str | None = Field(default="avatar.jpg", max_length=120)


@router.get("/assessment/options", summary="获取分析表单选项")
def assessment_options():
    return success(service.options())


@router.get("/crystals/catalog", summary="获取推荐水晶图鉴")
def crystal_catalog():
    catalog = RecommendationEngine.catalog()
    return success(
        [
            {"code": code, **item}
            for code, item in catalog.items()
        ]
    )


@router.get("/materials", summary="获取 DIY 材料列表")
def material_catalog(
    top: str | None = Query(default=None, description="材料大类：bead/accessory/incense/pendant"),
    keyword: str | None = Query(default=None, max_length=40, description="搜索关键词"),
    compact: bool = Query(default=False, description="仅返回材料结果，适用于搜索页"),
    limit: int | None = Query(default=None, ge=1, le=100, description="最多返回数量"),
    category: str | None = Query(default=None, max_length=80),
    series: str | None = Query(default=None, max_length=120),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=60),
    slim: bool = Query(default=False),
    ids: str | None = Query(default=None, max_length=2000),
):
    try:
        return success(
            list_materials(
                top=top,
                keyword=keyword,
                compact=compact,
                limit=limit,
                category=category,
                series=series,
                page=page,
                page_size=page_size,
                slim=slim,
                ids=ids,
            )
        )
    except MaterialCatalogUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/content-blocks", summary="content blocks")
def content_blocks(section: str | None = Query(default=None, max_length=40)):
    blocks = admin_content_service.list_blocks(section=section or "")
    return success([item for item in blocks if item.get("status") == "published"])


@router.get("/home-banners", summary="home banners")
def public_home_banners(limit: int = Query(default=10, ge=1, le=50)):
    return success(admin_content_service.list_home_banners(status="published", limit=limit))


@router.get("/community-posts", summary="community posts")
def public_community_posts(
    home_hot: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    return success(admin_content_service.list_community_posts(status="published", is_home_hot=home_hot, limit=limit))


@router.get("/community-posts/{post_id}", summary="获取社区灵感详情")
def public_community_post(post_id: str):
    try:
        post = admin_content_service.get_community_post(post_id)
        if post.get("status") != "published":
            raise ValueError("社区灵感未发布")
        return success(post)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/community-favorites", summary="获取我的灵感收藏")
def list_community_favorites(
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    return success(order_service.list_community_favorites(principal.user_id))


@router.post("/community-favorites", summary="收藏灵感")
def save_community_favorite(
    payload: CommunityFavoriteSaveRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        safe_payload = owned_payload(payload, principal)
        return success(order_service.save_community_favorite(safe_payload.model_dump(mode="json")), "灵感已收藏")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/community-favorites/{post_id}", summary="取消灵感收藏")
def delete_community_favorite(
    post_id: str,
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    return success(order_service.delete_community_favorite(principal.user_id, post_id), "已取消收藏")


@router.get("/recommendation-plans", summary="获取已发布热门推荐方案")
def public_recommendation_plans(
    home_hot: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    community_posts = admin_content_service.list_community_posts(
        status="published",
        is_home_hot=home_hot,
        limit=limit,
    )
    if community_posts:
        return success([
            admin_content_service.public_recommendation_from_community_post(post)
            for post in community_posts
        ])
    return success(
        admin_content_service.list_recommendation_plans(
            status="published",
            is_home_hot=home_hot,
            limit=limit,
        )
    )


@router.get("/recommendation-plans/{plan_id}", summary="获取热门推荐方案详情")
def public_recommendation_plan(plan_id: str):
    try:
        post = admin_content_service.get_community_post(plan_id)
        if post.get("status") == "published":
            return success(admin_content_service.public_recommendation_from_community_post(post))
    except ValueError:
        pass
    try:
        plan = admin_content_service.get_recommendation_plan(plan_id)
        if plan.get("status") != "published":
            raise ValueError("推荐方案未发布")
        return success(plan)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/auth/wechat-login", summary="微信快捷登录")
def wechat_login(payload: WechatLoginRequest, request: Request):
    timer = Timer()
    try:
        user = auth_service.login(payload, request)
        session = session_service.create(user["user_id"])
        metrics.increment("login_success_total")
        log_event(LOGGER, "auth.login.succeeded", user_id=user["user_id"], duration_ms=timer.elapsed_ms, result="success")
        return success(
            {
                "access_token": session["access_token"],
                "token_type": session["token_type"],
                "expires_at": session["expires_at"],
                "user": user,
            },
            "登录成功",
        )
    except ValueError as exc:
        metrics.increment("login_failed_total", error_type=type(exc).__name__)
        log_event(LOGGER, "auth.login.failed", level=logging.WARNING, error_type=type(exc).__name__, result="failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        metrics.increment("login_failed_total", error_type=type(exc).__name__)
        log_event(LOGGER, "auth.login.failed", level=logging.ERROR, error_type=type(exc).__name__, result="failed")
        raise


@router.post("/auth/logout", summary="退出当前用户会话")
def auth_logout(principal: UserPrincipal = Depends(require_current_user)):
    session_service.revoke(principal.session_id)
    return success({"revoked": True}, "已退出登录")


@router.get("/auth/profile", summary="获取当前用户资料")
def auth_profile(
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    user = auth_service.get_user(principal.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return success(user)


@router.post("/auth/avatar", summary="上传用户头像到对象存储")
async def upload_auth_avatar(
    user_id: str = Form(min_length=1, max_length=100),
    file: UploadFile = File(...),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    try:
        content = await file.read()
        result = avatar_storage.upload(
            user_id=principal.user_id,
            content=content,
            content_type=file.content_type,
            filename=file.filename,
        )
        return success({"avatar_url": result.avatar_url, "key": result.key}, "头像已上传")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/auth/avatar-base64", summary="上传 base64 用户头像到对象存储")
def upload_auth_avatar_base64(
    payload: AvatarBase64Payload,
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, payload.user_id)
    content_type = payload.content_type
    content_base64 = payload.content_base64.strip()
    if content_base64.startswith("data:") and "," in content_base64:
        header, content_base64 = content_base64.split(",", 1)
        if not content_type:
            content_type = header.removeprefix("data:").split(";", 1)[0]
    try:
        content = base64.b64decode(content_base64, validate=True)
        result = avatar_storage.upload(
            user_id=principal.user_id,
            content=content,
            content_type=content_type,
            filename=payload.filename,
        )
        return success({"avatar_url": result.avatar_url, "key": result.key}, "头像已上传")
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc) if isinstance(exc, ValueError) else "头像文件无效") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/auth/profile", summary="保存微信授权资料")
def update_auth_profile(
    payload: UserProfileUpdateRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(auth_service.update_profile(owned_payload(payload, principal)), "资料已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auth/phone", summary="绑定微信手机号")
def bind_phone(payload: PhoneBindRequest, principal: UserPrincipal = Depends(require_current_user)):
    try:
        return success(auth_service.bind_phone(owned_payload(payload, principal)), "手机号已绑定")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/diy-designs", summary="保存或更新用户 DIY 方案")
def save_diy_design(payload: DIYDesignSaveRequest, principal: UserPrincipal = Depends(require_current_user)):
    try:
        safe_payload = owned_payload(payload, principal)
        return success(order_service.save_design(safe_payload.model_dump(mode="json")), "DIY 方案已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/custom-design-requests", summary="申请人工水晶搭配服务")
def create_custom_design_request(
    payload: CustomDesignRequestCreate,
    principal: UserPrincipal = Depends(require_current_user),
):
    safe_payload = owned_payload(payload, principal)
    # Only a source reference is retained; assessment inputs are never copied into this service.
    if safe_payload.assessment_id:
        require_assessment_owner(safe_payload.assessment_id, principal)
    else:
        require_report_owner(safe_payload.report_id, principal, safe_payload.report_version)
    try:
        return success(custom_design_service.create(principal.user_id, safe_payload.model_dump(mode="json")), "申请已提交")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/custom-design-requests", summary="获取我的人工搭配申请")
def list_custom_design_requests(principal: UserPrincipal = Depends(require_current_user)):
    return success(custom_design_service.list_for_user(principal.user_id))


@router.post("/custom-design-requests/{request_id}/deposit/pay", summary="发起人工搭配设计保证金支付")
def pay_custom_design_deposit(
    request_id: str,
    payload: CustomDesignResponseRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    require_feature(payment_enabled(), "微信支付当前未开放")
    safe_payload = owned_payload(payload, principal)
    try:
        return success(
            custom_design_service.request_deposit_payment(request_id, principal.user_id),
            "设计保证金支付参数已生成",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/custom-design-requests/{request_id}/deposit/mock-pay", summary="本地调试：模拟设计保证金支付成功")
def mock_pay_custom_design_deposit(
    request_id: str,
    payload: CustomDesignResponseRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    require_mock_trade_tools()
    owned_payload(payload, principal)
    try:
        return success(custom_design_service.mark_deposit_paid_for_dev(request_id, principal.user_id), "设计保证金已模拟支付成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/custom-design-requests/{request_id}", summary="获取人工搭配申请详情")
def get_custom_design_request(request_id: str, principal: UserPrincipal = Depends(require_current_user)):
    try:
        return success(custom_design_service.get_for_user(request_id, principal.user_id))
    except ValueError as exc:
        raise private_not_found() from exc


@router.post("/custom-design-requests/{request_id}/confirm", summary="确认人工搭配方案")
def confirm_custom_design_request(
    request_id: str,
    payload: CustomDesignResponseRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    safe_payload = owned_payload(payload, principal)
    try:
        return success(custom_design_service.user_response(request_id, principal.user_id, "confirm", safe_payload.note), "设计已确认，商品订单已生成，请补充收货地址后支付")
    except (OrderPriceChangedError, OrderConflictError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OrderPricingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/custom-design-requests/{request_id}/order", summary="根据已确认人工搭配方案生成商品订单")
def create_order_from_custom_design_request(
    request_id: str,
    payload: CustomDesignResponseRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    safe_payload = owned_payload(payload, principal)
    try:
        return success(custom_design_service.create_order_from_proposal(request_id, principal.user_id), "待支付商品订单已生成")
    except (OrderPriceChangedError, OrderConflictError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OrderPricingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/custom-design-requests/{request_id}/revision", summary="申请调整人工搭配方案")
def revise_custom_design_request(
    request_id: str,
    payload: CustomDesignResponseRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    safe_payload = owned_payload(payload, principal)
    try:
        return success(custom_design_service.user_response(request_id, principal.user_id, "revision", safe_payload.note), "已提交调整说明")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/diy-designs/preview", summary="上传 DIY 方案预览图到对象存储")
async def upload_diy_design_preview(
    user_id: str = Form(min_length=1, max_length=100),
    file: UploadFile = File(...),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    try:
        content = await file.read()
        result = avatar_storage.upload_design_preview(
            user_id=principal.user_id,
            content=content,
            content_type=file.content_type,
            filename=file.filename,
        )
        return success({"preview_url": result.preview_url, "url": result.preview_url, "key": result.key}, "方案预览图已上传")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/diy-designs", summary="获取我的 DIY 方案列表")
def list_diy_designs(
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    status: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    return success(order_service.list_designs(user_id=principal.user_id, limit=limit, status=status))


@router.get("/diy-designs/shared/{share_token}", summary="通过安全令牌获取已发布 DIY 方案")
def get_shared_diy_design(share_token: str):
    require_feature(public_share_enabled(), "公共 DIY 分享当前未开放")
    try:
        return success(order_service.get_shared_design(share_token))
    except ValueError as exc:
        raise private_not_found() from exc


@router.post("/diy-designs/{design_id}/share", summary="发布 DIY 分享")
def publish_diy_design(design_id: str, principal: UserPrincipal = Depends(require_current_user)):
    require_feature(public_share_enabled(), "公共 DIY 分享当前未开放")
    try:
        return success(order_service.publish_design(design_id, principal.user_id), "分享已发布")
    except ValueError as exc:
        raise private_not_found() from exc


@router.delete("/diy-designs/{design_id}/share", summary="撤销 DIY 分享")
def revoke_diy_design_share(design_id: str, principal: UserPrincipal = Depends(require_current_user)):
    require_feature(public_share_enabled(), "公共 DIY 分享当前未开放")
    try:
        return success(order_service.revoke_design_share(design_id, principal.user_id), "分享已撤销")
    except ValueError as exc:
        raise private_not_found() from exc


@router.get("/diy-designs/{design_id}", summary="获取 DIY 方案")
def get_diy_design(
    design_id: str,
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    try:
        design = order_service.get_design(design_id)
        if design["user_id"] != principal.user_id:
            raise private_not_found()
        return success(design)
    except HTTPException:
        raise
    except ValueError as exc:
        raise private_not_found() from exc


@router.delete("/diy-designs/{design_id}", summary="删除我的 DIY 方案")
def delete_diy_design(
    design_id: str,
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    try:
        return success(order_service.delete_design(design_id, principal.user_id), "DIY 方案已删除")
    except ValueError as exc:
        raise private_not_found() from exc


@router.get("/cart", summary="获取我的购物车")
def get_cart(
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    return success(order_service.list_cart_items(principal.user_id))


@router.delete("/cart", summary="清空我的购物车")
def clear_cart(
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    return success(order_service.clear_cart(principal.user_id), "购物车已清空")


@router.post("/cart/items", summary="加入购物车")
def add_cart_item(payload: CartItemCreateRequest, principal: UserPrincipal = Depends(require_current_user)):
    try:
        safe_payload = owned_payload(payload, principal)
        return success(order_service.save_cart_item(safe_payload.model_dump(mode="json")), "已加入购物车")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/cart/items/{cart_item_id}", summary="更新购物车条目")
def update_cart_item(
    cart_item_id: str,
    payload: CartItemUpdateRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        safe_payload = owned_payload(payload, principal)
        return success(
            order_service.update_cart_item(
                cart_item_id,
                principal.user_id,
                safe_payload.model_dump(mode="json", exclude_none=True),
            ),
            "购物车已更新",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/cart/items/{cart_item_id}", summary="删除购物车条目")
def delete_cart_item(
    cart_item_id: str,
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    try:
        return success(order_service.delete_cart_item(cart_item_id, principal.user_id), "购物车条目已删除")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/user/addresses", summary="获取我的收货地址")
def list_user_addresses(
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    return success(order_service.list_addresses(principal.user_id))


@router.post("/user/addresses", summary="新增或更新收货地址")
def save_user_address(payload: UserAddressRequest, principal: UserPrincipal = Depends(require_current_user)):
    try:
        safe_payload = owned_payload(payload, principal)
        return success(order_service.save_address(safe_payload.model_dump(mode="json")), "收货地址已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/user/addresses/{address_id}", summary="更新收货地址")
def update_user_address(
    address_id: str,
    payload: UserAddressRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        data = owned_payload(payload, principal).model_dump(mode="json")
        data["address_id"] = address_id
        return success(order_service.save_address(data), "收货地址已更新")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/user/addresses/{address_id}", summary="删除收货地址")
def delete_user_address(
    address_id: str,
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    try:
        return success(order_service.delete_address(address_id, principal.user_id), "收货地址已删除")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/user/addresses/{address_id}/default", summary="设置默认收货地址")
def set_default_user_address(
    address_id: str,
    payload: UserAddressActionRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        owned_payload(payload, principal)
        return success(order_service.set_default_address(address_id, principal.user_id), "默认地址已设置")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/coupons/my", summary="获取我的优惠券")
def list_my_coupons(
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    return success(order_service.list_coupons(principal.user_id))


@router.get("/coupons/available", summary="获取当前订单可用优惠券")
def list_available_coupons(
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    amount: float = Query(default=0, ge=0),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    return success(order_service.available_coupons(principal.user_id, amount))


@router.post("/orders", summary="创建订单并发起微信支付预下单")
def create_order(
    payload: OrderCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_feature(checkout_enabled(), "结算功能当前未开放")
    timer = Timer()
    try:
        safe_payload = owned_payload(payload, principal)
        data = safe_payload.model_dump(mode="json")
        data["idempotency_key"] = idempotency_key
        result = order_service.create_order(data)
        metrics.increment("order_create_total", result="success")
        log_event(LOGGER, "order.create.succeeded", user_id=principal.user_id, duration_ms=timer.elapsed_ms, result="success")
        return success(result, "订单已生成")
    except (OrderPriceChangedError, OrderConflictError) as exc:
        metrics.increment("order_create_failed_total", error_type=type(exc).__name__)
        log_event(LOGGER, "order.create.failed", level=logging.WARNING, error_type=type(exc).__name__, result="failed")
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OrderPricingError as exc:
        metrics.increment("order_create_failed_total", error_type=type(exc).__name__)
        log_event(LOGGER, "order.create.failed", level=logging.WARNING, error_type=type(exc).__name__, result="failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        metrics.increment("order_create_failed_total", error_type=type(exc).__name__)
        log_event(LOGGER, "order.create.failed", level=logging.WARNING, error_type=type(exc).__name__, result="failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        metrics.increment("order_create_failed_total", error_type=type(exc).__name__)
        log_event(LOGGER, "order.create.failed", level=logging.ERROR, error_type=type(exc).__name__, result="failed")
        raise


@router.get("/orders", summary="获取我的订单")
def my_orders(
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    return success(order_service.list_user_orders(principal.user_id, limit))


@router.get("/orders/{order_id}", summary="获取订单详情")
def get_order_detail(
    order_id: str,
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    try:
        order = order_service.get_order(order_id)
        order_service.ensure_order_owner(order, principal.user_id)
        return success(order)
    except ValueError as exc:
        raise private_not_found() from exc


@router.post("/orders/{order_id}/pay", summary="继续支付订单")
def pay_order(
    order_id: str,
    payload: OrderActionRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    require_feature(checkout_enabled(), "支付功能当前未开放")
    require_feature(payment_enabled(), "微信支付当前未开放")
    require_order_owner(order_id, principal)
    try:
        owned_payload(payload, principal)
        return success(order_service.request_payment(order_id, principal.user_id), "支付参数已生成")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/orders/{order_id}/payment-status", summary="确认订单支付状态")
def get_order_payment_status(
    order_id: str,
    principal: UserPrincipal = Depends(require_current_user),
):
    require_order_owner(order_id, principal)
    return success(order_service.payment_confirmation(order_id, principal.user_id))


@router.post("/orders/{order_id}/mock-pay", summary="本地调试：模拟支付成功")
def mock_pay_order(order_id: str, payload: OrderActionRequest, principal: UserPrincipal = Depends(require_current_user)):
    require_mock_trade_tools()
    require_order_owner(order_id, principal)
    try:
        owned_payload(payload, principal)
        return success(order_service.mark_paid_for_dev(order_id, principal.user_id), "已模拟支付成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/mock-ship", summary="本地调试：模拟发货")
def mock_ship_order(order_id: str, payload: OrderShipRequest, principal: UserPrincipal = Depends(require_current_user)):
    require_mock_trade_tools()
    require_order_owner(order_id, principal)
    try:
        owned_payload(payload, principal)
        return success(
            order_service.mark_shipped_for_dev(
                order_id,
                principal.user_id,
                payload.carrier or "顺丰速运",
                payload.tracking_no,
                payload.carrier_code or "shunfeng",
                payload.phone_tail,
            ),
            "已发货",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/confirm-receipt", summary="确认收货")
def confirm_order_receipt(order_id: str, payload: OrderActionRequest, principal: UserPrincipal = Depends(require_current_user)):
    require_order_owner(order_id, principal)
    try:
        owned_payload(payload, principal)
        return success(order_service.confirm_receipt(order_id, principal.user_id), "已确认收货")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/cancel", summary="取消待付款订单")
def cancel_order(order_id: str, payload: OrderActionRequest, principal: UserPrincipal = Depends(require_current_user)):
    require_order_owner(order_id, principal)
    try:
        owned_payload(payload, principal)
        return success(
            order_service.cancel_order(order_id, principal.user_id, payload.reason or ""),
            "订单已取消",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/orders/{order_id}/receiver", summary="修改未发货订单收货信息")
def update_order_receiver(
    order_id: str,
    payload: OrderReceiverUpdateRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    require_order_owner(order_id, principal)
    try:
        owned_payload(payload, principal)
        return success(
            order_service.update_order_receiver(order_id, principal.user_id, payload.receiver),
            "收货信息已更新",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/orders/{order_id}/after-sales", summary="查询订单售后工单")
def list_order_after_sales(
    order_id: str,
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    require_order_owner(order_id, principal)
    return success(order_service.list_after_sale_cases(order_id, principal.user_id))


@router.post("/orders/{order_id}/after-sales", summary="创建结构化售后工单")
def create_order_after_sale(
    order_id: str,
    payload: AfterSaleCreateRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    require_order_owner(order_id, principal)
    try:
        safe_payload = owned_payload(payload, principal)
        result = order_service.create_after_sale_case(
            order_id=order_id,
            user_id=principal.user_id,
            case_type=safe_payload.type,
            reason_code=safe_payload.reason_code,
            reason=safe_payload.reason,
            evidence_urls=safe_payload.evidence_urls,
            idempotency_key=safe_payload.idempotency_key,
        )
        metrics.increment("after_sale_create_total", case_type=safe_payload.type, result="success")
        log_event(
            LOGGER,
            "after_sale.create.succeeded",
            user_id=principal.user_id,
            case_type=safe_payload.type,
            result="success",
        )
        return success(result, "售后申请已提交")
    except OrderConflictError as exc:
        metrics.increment("after_sale_create_total", case_type=payload.type, result="conflict")
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        metrics.increment("after_sale_create_total", case_type=payload.type, result="failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/orders/{order_id}/after-sales/{case_id}/return-shipment",
    summary="提交售后退回物流",
)
def submit_after_sale_return_shipment(
    order_id: str,
    case_id: str,
    payload: AfterSaleReturnShipmentRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    require_order_owner(order_id, principal)
    try:
        safe_payload = owned_payload(payload, principal)
        return success(
            order_service.submit_after_sale_return_shipment(
                order_id,
                case_id,
                principal.user_id,
                safe_payload.carrier,
                safe_payload.tracking_no,
            ),
            "退回物流已提交",
        )
    except OrderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/after-sales/{case_id}/cancel", summary="取消售后工单")
def cancel_after_sale_case(
    order_id: str,
    case_id: str,
    payload: AfterSaleCancelRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    require_order_owner(order_id, principal)
    try:
        safe_payload = owned_payload(payload, principal)
        return success(
            order_service.cancel_after_sale_case(
                order_id,
                case_id,
                principal.user_id,
                safe_payload.reason,
            ),
            "售后申请已取消",
        )
    except OrderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/refund", summary="申请退款")
def request_order_refund(
    order_id: str,
    payload: OrderRefundRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    require_order_owner(order_id, principal)
    try:
        owned_payload(payload, principal)
        return success(order_service.request_refund(order_id, principal.user_id, payload.reason or ""), "退款申请已提交")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/orders/{order_id}/logistics", summary="查询订单物流轨迹")
def get_order_logistics(
    order_id: str,
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    try:
        return success(order_service.get_logistics(order_id, principal.user_id))
    except ValueError as exc:
        raise private_not_found() from exc


@router.post("/logistics/kuaidi100/callback", summary="快递100主动订阅回调")
async def kuaidi100_logistics_callback(
    request: Request,
    order_id: str = Query(min_length=1, max_length=80),
):
    body = await request.body()
    if len(body) > KUAIDI100_CALLBACK_MAX_BYTES:
        return JSONResponse(
            status_code=413,
            content={"result": False, "returnCode": "500", "message": "回调数据过大"},
        )
    try:
        body_text = body.decode("utf-8")
        param_text, sign = order_service.parse_kuaidi100_callback_form(body_text)
        order_service.handle_kuaidi100_callback(order_id, param_text, sign)
    except LogisticsCallbackSignatureError as exc:
        metrics.increment("logistics_callback_total", service="kuaidi100", result="invalid_signature")
        log_event(
            LOGGER,
            "logistics.callback.failed",
            level=logging.WARNING,
            service="kuaidi100",
            error_type=type(exc).__name__,
            result="invalid_signature",
        )
        return JSONResponse(
            status_code=401,
            content={"result": False, "returnCode": "500", "message": "验签失败"},
        )
    except RuntimeError as exc:
        metrics.increment("logistics_callback_total", service="kuaidi100", result="configuration_unavailable")
        log_event(
            LOGGER,
            "logistics.callback.failed",
            level=logging.ERROR,
            service="kuaidi100",
            error_type=type(exc).__name__,
            result="configuration_unavailable",
        )
        return JSONResponse(
            status_code=503,
            content={"result": False, "returnCode": "500", "message": "回调服务未就绪"},
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        metrics.increment("logistics_callback_total", service="kuaidi100", result="invalid_payload")
        log_event(
            LOGGER,
            "logistics.callback.failed",
            level=logging.WARNING,
            service="kuaidi100",
            error_type=type(exc).__name__,
            result="invalid_payload",
        )
        return JSONResponse(
            status_code=400,
            content={"result": False, "returnCode": "500", "message": "回调处理失败"},
        )
    return {"result": True, "returnCode": "200", "message": "成功"}


@router.post("/wechat-pay/notify", summary="微信支付结果回调")
async def wechat_pay_notify(request: Request):
    body_text = (await request.body()).decode("utf-8")
    headers = {key.lower(): value for key, value in request.headers.items()}
    try:
        config = order_service_module.WechatPayConfig()
        payload = order_service.decode_verified_webhook(headers, body_text, config, "微信支付回调")
        transaction = order_service.decrypt_wechat_resource(payload.get("resource") or {}, config.api_v3_key)
        if not isinstance(transaction, dict):
            raise ValueError("微信支付回调资源格式错误")
        if custom_design_service.is_deposit_trade(str(transaction.get("out_trade_no") or "")):
            custom_design_service.handle_wechat_payment_transaction(transaction, config)
        else:
            order_service.handle_wechat_notify(headers, body_text)
    except (ValueError, json.JSONDecodeError) as exc:
        metrics.increment("payment_callback_total", callback_type="payment", result="failed")
        metrics.increment("payment_callback_failed_total", callback_type="payment", error_type=type(exc).__name__)
        log_event(LOGGER, "payment.callback.failed", level=logging.WARNING, callback_type="payment", error_type=type(exc).__name__, result="failed")
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "支付回调处理失败", "request_id": current_request_id()},
        )
    metrics.increment("payment_callback_total", callback_type="payment", result="success")
    log_event(LOGGER, "payment.callback.succeeded", callback_type="payment", result="success")
    return {"code": "SUCCESS", "message": "成功"}


@router.post("/wechat-pay/refund-notify", summary="微信退款结果回调")
async def wechat_pay_refund_notify(request: Request):
    body_text = (await request.body()).decode("utf-8")
    headers = {key.lower(): value for key, value in request.headers.items()}
    try:
        config = order_service_module.WechatPayConfig()
        payload = order_service.decode_verified_webhook(headers, body_text, config, "微信退款回调")
        refund_result = order_service.decrypt_wechat_resource(payload.get("resource") or {}, config.api_v3_key)
        if not isinstance(refund_result, dict):
            raise ValueError("微信退款回调资源格式错误")
        if custom_design_service.is_deposit_trade(str(refund_result.get("out_trade_no") or "")):
            custom_design_service.handle_wechat_refund_result(refund_result, config)
        else:
            order_service.handle_wechat_refund_notify(headers, body_text)
    except (ValueError, json.JSONDecodeError) as exc:
        metrics.increment("payment_callback_total", callback_type="refund", result="failed")
        metrics.increment("payment_callback_failed_total", callback_type="refund", error_type=type(exc).__name__)
        log_event(LOGGER, "payment.callback.failed", level=logging.WARNING, callback_type="refund", error_type=type(exc).__name__, result="failed")
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "退款回调处理失败", "request_id": current_request_id()},
        )
    metrics.increment("payment_callback_total", callback_type="refund", result="success")
    log_event(LOGGER, "payment.callback.succeeded", callback_type="refund", result="success")
    return {"code": "SUCCESS", "message": "成功"}


@router.post("/assessment/calculate", summary="计算专属水晶与手串方案")
def calculate_assessment(payload: AssessmentRequest, principal: UserPrincipal = Depends(require_current_user)):
    safe_payload = owned_payload(payload, principal)
    result, cache_hit = service.calculate(safe_payload)
    message = "读取已有分析结果" if cache_hit else "分析完成"
    return success({**result, "cache_hit": cache_hit}, message)


@router.post("/assessment/energy", summary="第一步：生成五行元素画像")
def calculate_energy(
    payload: AssessmentRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: UserPrincipal = Depends(require_current_user),
):
    safe_payload = owned_payload(payload, principal)
    timer = Timer()
    if report_versioning_v2_enabled():
        try:
            result, replay = service.calculate_energy_v2(safe_payload, idempotency_key or "")
        except ReportConflictError as exc:
            metrics.increment("report_generate_failed_total", error_type=type(exc).__name__)
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc
        except ValueError as exc:
            metrics.increment("report_generate_failed_total", error_type=type(exc).__name__)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            metrics.increment("report_generate_failed_total", error_type=type(exc).__name__)
            log_event(LOGGER, "report.generate.failed", level=logging.ERROR, error_type=type(exc).__name__, result="failed")
            raise
        metrics.increment("report_generate_total", result="replay" if replay else "created")
        metrics.observe("report_generate_duration", timer.elapsed_ms, version="v2")
        log_event(LOGGER, "report.generate.succeeded", user_id=principal.user_id, duration_ms=timer.elapsed_ms, result="replay" if replay else "created")
        return success(
            {**result, "idempotent_replay": replay},
            "读取已有报告" if replay else "元素分析完成",
        )
    try:
        result, cache_hit = service.calculate_energy(safe_payload)
    except Exception as exc:
        metrics.increment("report_generate_failed_total", error_type=type(exc).__name__)
        log_event(LOGGER, "report.generate.failed", level=logging.ERROR, error_type=type(exc).__name__, result="failed")
        raise
    background_tasks.add_task(
        service.pre_generate_diy_recommendation,
        result["assessment_id"],
        safe_payload.wrist_size_cm,
        safe_payload.bead_size_mm,
    )
    message = "读取已有元素画像" if cache_hit else "元素分析完成"
    metrics.increment("report_generate_total", result="cache" if cache_hit else "created", version="legacy")
    metrics.observe("report_generate_duration", timer.elapsed_ms, version="legacy")
    log_event(LOGGER, "report.generate.succeeded", user_id=principal.user_id, duration_ms=timer.elapsed_ms, result="cache" if cache_hit else "created")
    return success({**result, "cache_hit": cache_hit}, message)


@router.get("/reports/{report_id}", summary="按明确版本获取不可变搭配报告")
def report_detail(
    report_id: str,
    report_version: int = Query(ge=1),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_feature(report_versioning_v2_enabled(), "报告版本功能当前未开放")
    snapshot = require_report_owner(report_id, principal, report_version)
    log_event(LOGGER, "report.read.succeeded", user_id=principal.user_id, result="success", report_version=report_version)
    return success(service.report_repository.detail_dto(snapshot))


@router.get("/reports/{report_id}/basis", summary="获取指定版本的私有测算依据")
def report_basis(
    report_id: str,
    report_version: int = Query(ge=1),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_feature(report_versioning_v2_enabled(), "报告版本功能当前未开放")
    snapshot = require_report_owner(report_id, principal, report_version)
    log_event(LOGGER, "report.basis.read.succeeded", user_id=principal.user_id, result="success", report_version=report_version)
    return success(service.report_repository.basis_dto(snapshot))


@router.get("/reports/{report_id}/poster", summary="获取指定版本的脱敏海报数据")
def report_poster(
    report_id: str,
    report_version: int = Query(ge=1),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_feature(report_versioning_v2_enabled(), "报告版本功能当前未开放")
    try:
        snapshot = require_report_owner(report_id, principal, report_version)
        result = service.report_repository.poster_dto(snapshot)
        metrics.increment("poster_generate_total", result="success")
        log_event(LOGGER, "poster.payload.succeeded", user_id=principal.user_id, result="success", report_version=report_version)
        return success(result)
    except Exception as exc:
        metrics.increment("poster_failed_total", error_type=type(exc).__name__)
        log_event(LOGGER, "poster.payload.failed", level=logging.WARNING, error_type=type(exc).__name__, result="failed")
        raise


@router.post("/reports/{report_id}/diy-recommendation", summary="基于指定报告版本生成 DIY 推荐")
def report_diy_recommendation(
    report_id: str,
    payload: DIYRecommendationRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    require_feature(report_versioning_v2_enabled(), "报告版本功能当前未开放")
    if payload.report_id and payload.report_id != report_id:
        raise report_version_conflict(ReportVersionConflictError("请求中的 report_id 不一致"))
    try:
        result = service.create_diy_recommendation_v2(report_id, principal.user_id, payload)
    except ReportVersionConflictError as exc:
        raise report_version_conflict(exc) from exc
    if not result:
        raise private_not_found()
    message = "读取已有手串方案" if result.get("recommendation_cache_hit") else "专属手串已生成"
    return success(result, message)


@router.post("/assessment/{assessment_id}/diy-recommendation", summary="第二步：填写腕围并生成 DIY 推荐")
def create_diy_recommendation(
    assessment_id: str,
    payload: DIYRecommendationRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    require_assessment_owner(assessment_id, principal)
    try:
        result = service.create_diy_recommendation(assessment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=404, detail="分析结果不存在")
    message = "读取预生成手串" if result.get("recommendation_cache_hit") else "专属手串已生成"
    return success(result, message)


@legacy_router.post("/crystal/assessment/", summary="兼容旧小程序路径的专属水晶分析")
def legacy_calculate_assessment(
    payload: AssessmentRequest,
    principal: UserPrincipal = Depends(require_current_user),
):
    result, cache_hit = service.calculate(owned_payload(payload, principal))
    return success({**result, "cache_hit": cache_hit}, "分析完成")


@router.get("/assessment/history", summary="获取用户历史分析")
def assessment_history(
    user_id: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=20, ge=1, le=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    return success(service.history(principal.user_id, limit))


@router.get("/privacy/data-summary", summary="查看我的测算与画像数据摘要")
def privacy_data_summary(
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    return success(service.privacy_data_summary(principal.user_id))


@router.delete("/privacy/personalization-data", summary="删除我的测算、画像与每日状态数据")
def delete_personalization_data(
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    return success(service.delete_personalization_data(principal.user_id), "测算与画像数据已删除")


@router.get("/assessment/{assessment_id}", summary="获取分析详情")
def assessment_detail(assessment_id: str, principal: UserPrincipal = Depends(require_current_user)):
    return success(require_assessment_owner(assessment_id, principal))


def parse_key_list(values: list[str] | None) -> list[str]:
    keys: list[str] = []
    for value in values or []:
        for chunk in str(value or "").replace("，", ",").split(","):
            key = chunk.strip()
            if key and key not in keys:
                keys.append(key)
    return keys


@router.get("/daily-energy/options", summary="获取今日搭配可选标签、场景和目标")
def daily_energy_options():
    return success(daily_service.options())


@router.get("/daily-energy/today", summary="获取今日搭配建议内容")
def today_daily_energy(
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    initial_wish: str | None = Query(default=None, max_length=100),
    status_tags: list[str] | None = Query(default=None),
    scene_key: str | None = Query(default=None, max_length=80),
    goal_keys: list[str] | None = Query(default=None),
    force_recalculate: bool = Query(default=False),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    result, cache_hit = daily_service.get_or_calculate(
        user_id=principal.user_id,
        target_date=beijing_today(),
        initial_wish=initial_wish,
        status_tags=parse_key_list(status_tags),
        scene_key=scene_key,
        goal_keys=parse_key_list(goal_keys),
        force_recalculate=force_recalculate,
    )
    return success({**result, "cache_hit": cache_hit}, "读取今日搭配" if cache_hit else "今日搭配已生成")


@router.post("/daily-energy/check-in", summary="提交每日心情、睡眠和压力签到")
def daily_energy_check_in(
    payload: DailyCheckInRequest,
    checkin_date: date | None = Query(default=None),
    principal: UserPrincipal = Depends(require_current_user),
):
    return success(
        daily_service.check_in(owned_payload(payload, principal), checkin_date or beijing_today()),
        "签到成功",
    )


@router.get("/daily-energy/{energy_date}", summary="获取指定日期搭配建议")
def dated_daily_energy(
    energy_date: date,
    user_id: str | None = Query(default=None, min_length=1, max_length=100),
    initial_wish: str | None = Query(default=None, max_length=100),
    status_tags: list[str] | None = Query(default=None),
    scene_key: str | None = Query(default=None, max_length=80),
    goal_keys: list[str] | None = Query(default=None),
    force_recalculate: bool = Query(default=False),
    principal: UserPrincipal = Depends(require_current_user),
):
    require_owner(principal, user_id)
    result, cache_hit = daily_service.get_or_calculate(
        user_id=principal.user_id,
        target_date=energy_date,
        initial_wish=initial_wish,
        status_tags=parse_key_list(status_tags),
        scene_key=scene_key,
        goal_keys=parse_key_list(goal_keys),
        force_recalculate=force_recalculate,
    )
    return success({**result, "cache_hit": cache_hit})
