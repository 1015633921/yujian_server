from __future__ import annotations

import base64
import binascii
import json
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .auth_service import WechatAuthService
from .avatar_storage import AvatarStorage
from .daily_service import DailyEnergyService
from .admin_service import AdminService
from .materials import list_materials
from .order_service import OrderService
from .recommendation import RecommendationEngine
from .schemas import (
    AssessmentRequest,
    CartItemCreateRequest,
    CartItemUpdateRequest,
    CommunityFavoriteSaveRequest,
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

router = APIRouter(prefix="/api/v1", tags=["专属水晶测算"])
legacy_router = APIRouter(prefix="/api", tags=["兼容接口"])
service = AssessmentService()
daily_service = DailyEnergyService()
auth_service = WechatAuthService()
avatar_storage = AvatarStorage()
admin_content_service = AdminService()
order_service = OrderService()


def success(data, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


class AvatarBase64Payload(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    content_base64: str = Field(min_length=1)
    content_type: str | None = Field(default=None, max_length=80)
    filename: str | None = Field(default="avatar.jpg", max_length=120)


@router.get("/assessment/options", summary="获取测算表单选项")
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
):
    return success(list_materials(top=top, keyword=keyword, compact=compact, limit=limit))


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
def list_community_favorites(user_id: str = Query(min_length=1, max_length=100)):
    return success(order_service.list_community_favorites(user_id))


@router.post("/community-favorites", summary="收藏灵感")
def save_community_favorite(payload: CommunityFavoriteSaveRequest):
    try:
        return success(order_service.save_community_favorite(payload.model_dump(mode="json")), "灵感已收藏")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/community-favorites/{post_id}", summary="取消灵感收藏")
def delete_community_favorite(post_id: str, user_id: str = Query(min_length=1, max_length=100)):
    return success(order_service.delete_community_favorite(user_id, post_id), "已取消收藏")


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
    try:
        return success(auth_service.login(payload, request), "登录成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/auth/profile", summary="获取当前用户资料")
def auth_profile(user_id: str = Query(min_length=1, max_length=100)):
    user = auth_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return success(user)


@router.post("/auth/avatar", summary="上传用户头像到对象存储")
async def upload_auth_avatar(
    user_id: str = Form(min_length=1, max_length=100),
    file: UploadFile = File(...),
):
    try:
        content = await file.read()
        result = avatar_storage.upload(
            user_id=user_id,
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
def upload_auth_avatar_base64(payload: AvatarBase64Payload):
    content_type = payload.content_type
    content_base64 = payload.content_base64.strip()
    if content_base64.startswith("data:") and "," in content_base64:
        header, content_base64 = content_base64.split(",", 1)
        if not content_type:
            content_type = header.removeprefix("data:").split(";", 1)[0]
    try:
        content = base64.b64decode(content_base64, validate=True)
        result = avatar_storage.upload(
            user_id=payload.user_id,
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
def update_auth_profile(payload: UserProfileUpdateRequest):
    try:
        return success(auth_service.update_profile(payload), "资料已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auth/phone", summary="绑定微信手机号")
def bind_phone(payload: PhoneBindRequest):
    try:
        return success(auth_service.bind_phone(payload), "手机号已绑定")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/diy-designs", summary="保存或更新用户 DIY 方案")
def save_diy_design(payload: DIYDesignSaveRequest):
    try:
        return success(order_service.save_design(payload.model_dump(mode="json")), "DIY 方案已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/diy-designs/preview", summary="上传 DIY 方案预览图到对象存储")
async def upload_diy_design_preview(
    user_id: str = Form(min_length=1, max_length=100),
    file: UploadFile = File(...),
):
    try:
        content = await file.read()
        result = avatar_storage.upload_design_preview(
            user_id=user_id,
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
    user_id: str = Query(min_length=1, max_length=100),
    status: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=100),
):
    return success(order_service.list_designs(user_id=user_id, limit=limit, status=status))


@router.get("/diy-designs/{design_id}", summary="获取 DIY 方案")
def get_diy_design(design_id: str, user_id: str = Query(min_length=1, max_length=100)):
    try:
        design = order_service.get_design(design_id)
        if design["user_id"] != user_id:
            raise ValueError("无权查看该 DIY 方案")
        return success(design)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/diy-designs/{design_id}", summary="删除我的 DIY 方案")
def delete_diy_design(design_id: str, user_id: str = Query(min_length=1, max_length=100)):
    try:
        return success(order_service.delete_design(design_id, user_id), "DIY 方案已删除")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/cart", summary="获取我的购物车")
def get_cart(user_id: str = Query(min_length=1, max_length=100)):
    return success(order_service.list_cart_items(user_id))


@router.delete("/cart", summary="清空我的购物车")
def clear_cart(user_id: str = Query(min_length=1, max_length=100)):
    return success(order_service.clear_cart(user_id), "购物车已清空")


@router.post("/cart/items", summary="加入购物车")
def add_cart_item(payload: CartItemCreateRequest):
    try:
        return success(order_service.save_cart_item(payload.model_dump(mode="json")), "已加入购物车")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/cart/items/{cart_item_id}", summary="更新购物车条目")
def update_cart_item(cart_item_id: str, payload: CartItemUpdateRequest):
    try:
        return success(
            order_service.update_cart_item(cart_item_id, payload.user_id, payload.model_dump(mode="json", exclude_none=True)),
            "购物车已更新",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/cart/items/{cart_item_id}", summary="删除购物车条目")
def delete_cart_item(cart_item_id: str, user_id: str = Query(min_length=1, max_length=100)):
    try:
        return success(order_service.delete_cart_item(cart_item_id, user_id), "购物车条目已删除")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/user/addresses", summary="获取我的收货地址")
def list_user_addresses(user_id: str = Query(min_length=1, max_length=100)):
    return success(order_service.list_addresses(user_id))


@router.post("/user/addresses", summary="新增或更新收货地址")
def save_user_address(payload: UserAddressRequest):
    try:
        return success(order_service.save_address(payload.model_dump(mode="json")), "收货地址已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/user/addresses/{address_id}", summary="更新收货地址")
def update_user_address(address_id: str, payload: UserAddressRequest):
    try:
        data = payload.model_dump(mode="json")
        data["address_id"] = address_id
        return success(order_service.save_address(data), "收货地址已更新")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/user/addresses/{address_id}", summary="删除收货地址")
def delete_user_address(address_id: str, user_id: str = Query(min_length=1, max_length=100)):
    try:
        return success(order_service.delete_address(address_id, user_id), "收货地址已删除")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/user/addresses/{address_id}/default", summary="设置默认收货地址")
def set_default_user_address(address_id: str, payload: UserAddressActionRequest):
    try:
        return success(order_service.set_default_address(address_id, payload.user_id), "默认地址已设置")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/coupons/my", summary="获取我的优惠券")
def list_my_coupons(user_id: str = Query(min_length=1, max_length=100)):
    return success(order_service.list_coupons(user_id))


@router.get("/coupons/available", summary="获取当前订单可用优惠券")
def list_available_coupons(
    user_id: str = Query(min_length=1, max_length=100),
    amount: float = Query(default=0, ge=0),
):
    return success(order_service.available_coupons(user_id, amount))


@router.post("/orders", summary="创建订单并发起微信支付预下单")
def create_order(payload: OrderCreateRequest):
    try:
        return success(order_service.create_order(payload.model_dump(mode="json")), "订单已生成")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/orders", summary="获取我的订单")
def my_orders(
    user_id: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
):
    return success(order_service.list_user_orders(user_id, limit))


@router.get("/orders/{order_id}", summary="获取订单详情")
def get_order_detail(
    order_id: str,
    user_id: str = Query(min_length=1, max_length=100),
):
    try:
        order = order_service.get_order(order_id)
        order_service.ensure_order_owner(order, user_id)
        return success(order)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/orders/{order_id}/pay", summary="继续支付订单")
def pay_order(order_id: str, payload: OrderActionRequest):
    try:
        return success(order_service.request_payment(order_id, payload.user_id), "支付参数已生成")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/mock-pay", summary="本地调试：模拟支付成功")
def mock_pay_order(order_id: str, payload: OrderActionRequest):
    try:
        return success(order_service.mark_paid_for_dev(order_id, payload.user_id), "已模拟支付成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/mock-ship", summary="本地调试：模拟发货")
def mock_ship_order(order_id: str, payload: OrderShipRequest):
    try:
        return success(
            order_service.mark_shipped_for_dev(
                order_id,
                payload.user_id,
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
def confirm_order_receipt(order_id: str, payload: OrderActionRequest):
    try:
        return success(order_service.confirm_receipt(order_id, payload.user_id), "已确认收货")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/cancel", summary="取消待付款订单")
def cancel_order(order_id: str, payload: OrderActionRequest):
    try:
        return success(
            order_service.cancel_order(order_id, payload.user_id, payload.reason or ""),
            "订单已取消",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/orders/{order_id}/receiver", summary="修改未发货订单收货信息")
def update_order_receiver(order_id: str, payload: OrderReceiverUpdateRequest):
    try:
        return success(
            order_service.update_order_receiver(order_id, payload.user_id, payload.receiver),
            "收货信息已更新",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/after-sale", summary="申请退换货/售后")
def request_order_after_sale(order_id: str, payload: OrderActionRequest):
    try:
        return success(order_service.request_after_sale(order_id, payload.user_id, payload.reason or ""), "售后申请已提交")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/refund", summary="申请退款")
def request_order_refund(order_id: str, payload: OrderRefundRequest):
    try:
        return success(order_service.request_refund(order_id, payload.user_id, payload.reason or ""), "退款申请已提交")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/orders/{order_id}/logistics", summary="查询订单物流轨迹")
def get_order_logistics(order_id: str, user_id: str = Query(min_length=1, max_length=100)):
    try:
        return success(order_service.get_logistics(order_id, user_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/wechat-pay/notify", summary="微信支付结果回调")
async def wechat_pay_notify(request: Request):
    body_text = (await request.body()).decode("utf-8")
    headers = {key.lower(): value for key, value in request.headers.items()}
    try:
        order_service.handle_wechat_notify(headers, body_text)
    except (ValueError, json.JSONDecodeError) as exc:
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": str(exc)},
        )
    return {"code": "SUCCESS", "message": "成功"}


@router.post("/wechat-pay/refund-notify", summary="微信退款结果回调")
async def wechat_pay_refund_notify(request: Request):
    body_text = (await request.body()).decode("utf-8")
    headers = {key.lower(): value for key, value in request.headers.items()}
    try:
        order_service.handle_wechat_refund_notify(headers, body_text)
    except (ValueError, json.JSONDecodeError) as exc:
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": str(exc)},
        )
    return {"code": "SUCCESS", "message": "成功"}


@router.post("/assessment/calculate", summary="计算专属水晶与手串方案")
def calculate_assessment(payload: AssessmentRequest):
    result, cache_hit = service.calculate(payload)
    message = "读取已有测算结果" if cache_hit else "测算完成"
    return success({**result, "cache_hit": cache_hit}, message)


@router.post("/assessment/energy", summary="第一步：计算五行能量画像")
def calculate_energy(payload: AssessmentRequest):
    result, cache_hit = service.calculate_energy(payload)
    message = "读取已有能量画像" if cache_hit else "能量计算完成"
    return success({**result, "cache_hit": cache_hit}, message)


@router.post("/assessment/{assessment_id}/diy-recommendation", summary="第二步：填写腕围并生成 DIY 推荐")
def create_diy_recommendation(assessment_id: str, payload: DIYRecommendationRequest):
    result = service.create_diy_recommendation(assessment_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="测算结果不存在")
    return success(result, "专属手串已生成")


@legacy_router.post("/crystal/assessment/", summary="兼容旧小程序路径的专属水晶测算")
def legacy_calculate_assessment(payload: AssessmentRequest):
    result, cache_hit = service.calculate(payload)
    return success({**result, "cache_hit": cache_hit}, "测算完成")


@router.get("/assessment/history", summary="获取用户历史测算")
def assessment_history(
    user_id: str = Query(min_length=1, max_length=64),
    limit: int = Query(default=20, ge=1, le=100),
):
    return success(service.history(user_id, limit))


@router.get("/assessment/{assessment_id}", summary="获取测算详情")
def assessment_detail(assessment_id: str):
    result = service.get(assessment_id)
    if not result:
        raise HTTPException(status_code=404, detail="测算结果不存在")
    return success(result)


def parse_key_list(values: list[str] | None) -> list[str]:
    keys: list[str] = []
    for value in values or []:
        for chunk in str(value or "").replace("，", ",").split(","):
            key = chunk.strip()
            if key and key not in keys:
                keys.append(key)
    return keys


@router.get("/daily-energy/options", summary="获取今日能量可选标签、场景和目标")
def daily_energy_options():
    return success(daily_service.options())


@router.get("/daily-energy/today", summary="获取今日能量补给站内容")
def today_daily_energy(
    user_id: str = Query(min_length=1, max_length=100),
    initial_wish: str | None = Query(default=None, max_length=100),
    status_tags: list[str] | None = Query(default=None),
    scene_key: str | None = Query(default=None, max_length=80),
    goal_keys: list[str] | None = Query(default=None),
    force_recalculate: bool = Query(default=False),
):
    result, cache_hit = daily_service.get_or_calculate(
        user_id=user_id,
        target_date=date.today(),
        initial_wish=initial_wish,
        status_tags=parse_key_list(status_tags),
        scene_key=scene_key,
        goal_keys=parse_key_list(goal_keys),
        force_recalculate=force_recalculate,
    )
    return success({**result, "cache_hit": cache_hit}, "读取今日能量" if cache_hit else "今日能量已生成")


@router.post("/daily-energy/check-in", summary="提交每日心情、睡眠和压力签到")
def daily_energy_check_in(
    payload: DailyCheckInRequest,
    checkin_date: date | None = Query(default=None),
):
    return success(daily_service.check_in(payload, checkin_date or date.today()), "签到成功")


@router.get("/daily-energy/{energy_date}", summary="获取指定日期能量内容")
def dated_daily_energy(
    energy_date: date,
    user_id: str = Query(min_length=1, max_length=100),
    initial_wish: str | None = Query(default=None, max_length=100),
    status_tags: list[str] | None = Query(default=None),
    scene_key: str | None = Query(default=None, max_length=80),
    goal_keys: list[str] | None = Query(default=None),
    force_recalculate: bool = Query(default=False),
):
    result, cache_hit = daily_service.get_or_calculate(
        user_id=user_id,
        target_date=energy_date,
        initial_wish=initial_wish,
        status_tags=parse_key_list(status_tags),
        scene_key=scene_key,
        goal_keys=parse_key_list(goal_keys),
        force_recalculate=force_recalculate,
    )
    return success({**result, "cache_hit": cache_hit})
