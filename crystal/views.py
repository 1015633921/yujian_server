from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable

from django.db import transaction
from django.db.models import F, Q
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import (
    Address,
    CartItem,
    CrystalAssessment,
    DIYPlan,
    Favorite,
    Inspiration,
    Material,
    MiniUser,
    Order,
    Recommendation,
)
from .serializers import (
    address_dict,
    assessment_dict,
    cart_item_dict,
    daily_energy_dict,
    diy_plan_dict,
    favorite_dict,
    inspiration_dict,
    material_to_dict,
    order_dict,
    recommendation_dict,
    user_dict,
)
from .services import calculate_assessment, calculate_daily_energy, estimate_plan_price


def ok(data: Any = None, message: str = "ok", status: int = 200) -> JsonResponse:
    return JsonResponse({"code": 0, "message": message, "data": data}, status=status, json_dumps_params={"ensure_ascii": False})


def fail(message: str, status: int = 400, code: int = 1) -> JsonResponse:
    return JsonResponse({"code": code, "message": message, "data": None}, status=status, json_dumps_params={"ensure_ascii": False})


def parse_body(request: HttpRequest) -> dict[str, Any]:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def get_user_id(request: HttpRequest, body: dict[str, Any] | None = None) -> int | None:
    body = body or {}
    raw = request.headers.get("X-User-Id") or request.GET.get("user_id") or body.get("user_id")
    try:
        return int(raw) if raw else None
    except (TypeError, ValueError):
        return None


def require_user(view: Callable[[HttpRequest, MiniUser, dict[str, Any]], JsonResponse]):
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        body = parse_body(request)
        user_id = get_user_id(request, body)
        if not user_id:
            return fail("missing user_id", status=401)
        user = MiniUser.objects.filter(id=user_id).first()
        if not user:
            return fail("user not found", status=404)
        return view(request, user, body, *args, **kwargs)

    return wrapper


def parse_limit(request: HttpRequest, default: int = 20, maximum: int = 100) -> int:
    try:
        limit = int(request.GET.get("limit", default))
    except ValueError:
        limit = default
    return max(1, min(limit, maximum))


def parse_date(value: str | None):
    if not value:
        return timezone.localdate()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return timezone.localdate()


@require_http_methods(["GET"])
def health(request: HttpRequest) -> JsonResponse:
    return ok({"service": "yujian crystal api", "time": timezone.now().isoformat()})


@csrf_exempt
@require_http_methods(["POST"])
def upsert_user(request: HttpRequest) -> JsonResponse:
    body = parse_body(request)
    openid = body.get("openid")
    user_id = get_user_id(request, body)
    if user_id:
        user, _ = MiniUser.objects.get_or_create(id=user_id)
    elif openid:
        user, _ = MiniUser.objects.get_or_create(openid=openid)
    else:
        user = MiniUser.objects.create()

    fields = [
        "openid",
        "nickname",
        "avatar_url",
        "phone",
        "gender",
        "city",
        "zodiac",
        "element",
        "intention",
    ]
    for field in fields:
        if field in body:
            setattr(user, field, body.get(field) or "")
    if body.get("birth_date"):
        user.birth_date = parse_date(body.get("birth_date"))
    if body.get("birth_time"):
        try:
            user.birth_time = datetime.strptime(body["birth_time"], "%H:%M").time()
        except ValueError:
            pass
    user.save()
    return ok(user_dict(user))


@csrf_exempt
@require_http_methods(["POST"])
@require_user
def crystal_assessment(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    result = calculate_assessment(user, body)
    item = CrystalAssessment.objects.create(
        user=user,
        profile=result["profile"],
        intention=result["intention"],
        energy_profile=result["energy_profile"],
        recommended_materials=result["recommended_materials"],
        bracelet_plan=result["bracelet_plan"],
        summary=result["summary"],
    )
    if result["intention"] and user.intention != result["intention"]:
        user.intention = result["intention"]
        user.save(update_fields=["intention", "updated_at"])
    return ok(assessment_dict(item))


@require_http_methods(["GET"])
@require_user
def latest_assessment(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    item = CrystalAssessment.objects.filter(user=user).first()
    return ok(assessment_dict(item) if item else None)


@require_http_methods(["GET"])
@require_user
def daily_energy(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    target_date = parse_date(request.GET.get("date"))
    item = calculate_daily_energy(user, target_date)
    return ok(daily_energy_dict(item))


@require_http_methods(["GET"])
def recommendations(request: HttpRequest) -> JsonResponse:
    limit = parse_limit(request, 10)
    scene = request.GET.get("scene")
    queryset = Recommendation.objects.filter(is_active=True)
    if scene:
        queryset = queryset.filter(scene=scene)
    return ok([recommendation_dict(item) for item in queryset[:limit]])


@require_http_methods(["GET"])
def inspirations(request: HttpRequest) -> JsonResponse:
    limit = parse_limit(request, 20)
    tag = request.GET.get("tag")
    queryset = Inspiration.objects.filter(is_public=True)
    if tag:
        items = [item for item in queryset[:200] if tag in item.tags]
        return ok([inspiration_dict(item) for item in items[:limit]])
    return ok([inspiration_dict(item) for item in queryset[:limit]])


@csrf_exempt
@require_http_methods(["POST"])
@require_user
def create_inspiration(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    title = body.get("title")
    if not title:
        return fail("missing title")
    item = Inspiration.objects.create(
        user=user,
        title=title,
        content=body.get("content", ""),
        image_urls=body.get("image_urls", []),
        tags=body.get("tags", []),
        materials=body.get("materials", []),
        is_public=body.get("is_public", True),
    )
    return ok(inspiration_dict(item), status=201)


@csrf_exempt
@require_http_methods(["POST"])
@require_user
def like_inspiration(request: HttpRequest, user: MiniUser, body: dict[str, Any], inspiration_id: int) -> JsonResponse:
    updated = Inspiration.objects.filter(id=inspiration_id, is_public=True).update(likes_count=F("likes_count") + 1)
    if not updated:
        return fail("inspiration not found", status=404)
    return ok({"id": inspiration_id})


@require_http_methods(["GET"])
def material_list(request: HttpRequest) -> JsonResponse:
    material_type = request.GET.get("type")
    keyword = request.GET.get("keyword")
    queryset = Material.objects.filter(is_active=True)
    if material_type:
        queryset = queryset.filter(material_type=material_type)
    if keyword:
        queryset = queryset.filter(Q(name__icontains=keyword) | Q(code__icontains=keyword))
    return ok([material_to_dict(item) for item in queryset[: parse_limit(request, 50, 200)]])


@require_http_methods(["GET"])
def material_groups(request: HttpRequest) -> JsonResponse:
    data = {}
    for material_type, _label in Material.MATERIAL_CHOICES:
        data[material_type] = [
            material_to_dict(item)
            for item in Material.objects.filter(material_type=material_type, is_active=True)[:100]
        ]
    return ok(data)


@require_http_methods(["GET"])
def material_detail(request: HttpRequest, material_id: int) -> JsonResponse:
    item = Material.objects.filter(id=material_id, is_active=True).first()
    if not item:
        return fail("material not found", status=404)
    return ok(material_to_dict(item))


@csrf_exempt
@require_http_methods(["POST"])
@require_user
def save_diy_plan(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    beads = body.get("beads", [])
    accessories = body.get("accessories", [])
    price = estimate_plan_price(beads, accessories)
    plan_id = body.get("id")
    defaults = {
        "name": body.get("name") or "My Crystal Bracelet",
        "intention": body.get("intention", ""),
        "wrist_size_cm": body.get("wrist_size_cm"),
        "beads": beads,
        "accessories": accessories,
        "layout": body.get("layout", {}),
        "price_snapshot": price,
        "cover_image_url": body.get("cover_image_url", ""),
        "status": body.get("status", DIYPlan.STATUS_SAVED),
        "remark": body.get("remark", ""),
    }
    if plan_id:
        item, _ = DIYPlan.objects.update_or_create(id=plan_id, user=user, defaults=defaults)
    else:
        item = DIYPlan.objects.create(user=user, **defaults)
    return ok(diy_plan_dict(item), status=201)


@require_http_methods(["GET"])
@require_user
def diy_plans(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    status = request.GET.get("status")
    queryset = DIYPlan.objects.filter(user=user)
    if status:
        queryset = queryset.filter(status=status)
    return ok([diy_plan_dict(item) for item in queryset[: parse_limit(request, 20)]])


@require_http_methods(["GET"])
@require_user
def diy_plan_detail(request: HttpRequest, user: MiniUser, body: dict[str, Any], plan_id: int) -> JsonResponse:
    item = DIYPlan.objects.filter(id=plan_id, user=user).first()
    if not item:
        return fail("plan not found", status=404)
    return ok(diy_plan_dict(item))


@csrf_exempt
@require_http_methods(["POST"])
@require_user
def create_order(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    plan = None
    if body.get("diy_plan_id"):
        plan = DIYPlan.objects.filter(id=body["diy_plan_id"], user=user).first()
        if not plan:
            return fail("plan not found", status=404)
    total = Decimal(str(body.get("total_amount") or (plan.price_snapshot if plan else 0)))
    item = Order.objects.create(
        user=user,
        order_no=body.get("order_no") or f"YJ{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
        diy_plan=plan,
        total_amount=total,
        items=body.get("items", plan.beads + plan.accessories if plan else []),
        address=body.get("address", {}),
    )
    if plan:
        plan.status = DIYPlan.STATUS_ORDERED
        plan.save(update_fields=["status", "updated_at"])
    return ok(order_dict(item), status=201)


@require_http_methods(["GET"])
@require_user
def my_orders(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    status = request.GET.get("status")
    queryset = Order.objects.filter(user=user)
    if status:
        queryset = queryset.filter(status=status)
    return ok([order_dict(item) for item in queryset[: parse_limit(request, 20)]])


@require_http_methods(["GET"])
@require_user
def order_detail(request: HttpRequest, user: MiniUser, body: dict[str, Any], order_id: int) -> JsonResponse:
    item = Order.objects.filter(id=order_id, user=user).first()
    if not item:
        return fail("order not found", status=404)
    return ok(order_dict(item))


@csrf_exempt
@require_http_methods(["POST"])
@require_user
def favorite_toggle(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    target_type = body.get("target_type")
    target_id = body.get("target_id")
    if not target_type or not target_id:
        return fail("missing target_type or target_id")
    favorite, created = Favorite.objects.get_or_create(user=user, target_type=target_type, target_id=target_id)
    if not created and body.get("action") == "remove":
        favorite.delete()
        return ok({"favorited": False})
    return ok({"favorited": True, "favorite": favorite_dict(favorite)})


@require_http_methods(["GET"])
@require_user
def favorites(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    return ok([favorite_dict(item) for item in Favorite.objects.filter(user=user)[: parse_limit(request, 50)]])


@csrf_exempt
@require_http_methods(["POST"])
@require_user
def cart_add(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    material_id = body.get("material_id")
    quantity = int(body.get("quantity") or 1)
    material = Material.objects.filter(id=material_id, is_active=True).first()
    if not material:
        return fail("material not found", status=404)
    item, created = CartItem.objects.get_or_create(user=user, material=material, defaults={"quantity": quantity})
    if not created:
        item.quantity += quantity
        item.save(update_fields=["quantity", "updated_at"])
    return ok(cart_item_dict(item))


@require_http_methods(["GET"])
@require_user
def cart_list(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    return ok([cart_item_dict(item) for item in CartItem.objects.filter(user=user).select_related("material")])


@csrf_exempt
@require_http_methods(["POST"])
@require_user
def save_address(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    required = ["receiver", "phone", "province", "city", "detail"]
    if any(not body.get(field) for field in required):
        return fail("missing address field")
    with transaction.atomic():
        if body.get("is_default"):
            Address.objects.filter(user=user).update(is_default=False)
        address_id = body.get("id")
        defaults = {field: body.get(field, "") for field in ["receiver", "phone", "province", "city", "district", "detail"]}
        defaults["is_default"] = bool(body.get("is_default"))
        if address_id:
            item, _ = Address.objects.update_or_create(id=address_id, user=user, defaults=defaults)
        else:
            item = Address.objects.create(user=user, **defaults)
    return ok(address_dict(item), status=201)


@require_http_methods(["GET"])
@require_user
def addresses(request: HttpRequest, user: MiniUser, body: dict[str, Any]) -> JsonResponse:
    return ok([address_dict(item) for item in Address.objects.filter(user=user)])


@require_http_methods(["GET"])
def app_config(request: HttpRequest) -> JsonResponse:
    return ok(
        {
            "intentions": [
                {"key": "love", "label": "Love"},
                {"key": "career", "label": "Career"},
                {"key": "wealth", "label": "Wealth"},
                {"key": "study", "label": "Study"},
                {"key": "sleep", "label": "Sleep"},
                {"key": "health", "label": "Health"},
                {"key": "protection", "label": "Protection"},
            ],
            "material_types": [{"key": key, "label": label} for key, label in Material.MATERIAL_CHOICES],
            "order_statuses": [{"key": key, "label": label} for key, label in Order.STATUS_CHOICES],
        }
    )
