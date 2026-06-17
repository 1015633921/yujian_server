from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request

from .auth_service import WechatAuthService
from .daily_service import DailyEnergyService
from .admin_service import AdminService
from .materials import list_materials
from .order_service import OrderService
from .recommendation import CRYSTAL_CATALOG
from .schemas import (
    AssessmentRequest,
    DailyCheckInRequest,
    DIYRecommendationRequest,
    OrderActionRequest,
    OrderCreateRequest,
    OrderRefundRequest,
    OrderShipRequest,
    PhoneBindRequest,
    UserProfileUpdateRequest,
    WechatLoginRequest,
)
from .service import AssessmentService

router = APIRouter(prefix="/api/v1", tags=["专属水晶测算"])
legacy_router = APIRouter(prefix="/api", tags=["兼容接口"])
service = AssessmentService()
daily_service = DailyEnergyService()
auth_service = WechatAuthService()
admin_content_service = AdminService()
order_service = OrderService()


def success(data, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/assessment/options", summary="获取测算表单选项")
def assessment_options():
    return success(service.options())


@router.get("/crystals/catalog", summary="获取推荐水晶图鉴")
def crystal_catalog():
    return success(
        [
            {"code": code, **item}
            for code, item in CRYSTAL_CATALOG.items()
        ]
    )


@router.get("/materials", summary="获取 DIY 材料列表")
def material_catalog(
    top: str | None = Query(default=None, description="材料大类：bead/accessory/incense/pendant"),
    keyword: str | None = Query(default=None, max_length=40, description="搜索关键词"),
):
    return success(list_materials(top=top, keyword=keyword))


@router.get("/content-blocks", summary="获取已发布板块信息")
def content_blocks(section: str | None = Query(default=None, max_length=40)):
    blocks = admin_content_service.list_blocks(section=section or "")
    return success([item for item in blocks if item.get("status") == "published"])


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


@router.post("/auth/profile", summary="保存微信授权资料")
def update_auth_profile(payload: UserProfileUpdateRequest):
    return success(auth_service.update_profile(payload), "资料已保存")


@router.post("/auth/phone", summary="绑定微信手机号")
def bind_phone(payload: PhoneBindRequest):
    try:
        return success(auth_service.bind_phone(payload), "手机号已绑定")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.post("/wechat-pay/notify", summary="微信支付回调占位")
async def wechat_pay_notify(request: Request):
    # 生产环境应在这里校验 Wechatpay-Signature 并解密 resource 后再更新订单状态。
    # 当前先返回 SUCCESS，避免商户平台联调时因地址未实现而失败。
    await request.body()
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


@router.get("/daily-energy/today", summary="获取今日能量补给站内容")
def today_daily_energy(
    user_id: str = Query(min_length=1, max_length=100),
    initial_wish: str | None = Query(default=None, max_length=100),
    force_recalculate: bool = Query(default=False),
):
    result, cache_hit = daily_service.get_or_calculate(
        user_id=user_id,
        target_date=date.today(),
        initial_wish=initial_wish,
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
    force_recalculate: bool = Query(default=False),
):
    result, cache_hit = daily_service.get_or_calculate(
        user_id=user_id,
        target_date=energy_date,
        force_recalculate=force_recalculate,
    )
    return success({**result, "cache_hit": cache_hit})
