from __future__ import annotations

from typing import Any

from .models import (
    Address,
    CartItem,
    CrystalAssessment,
    DIYPlan,
    DailyEnergy,
    Favorite,
    Inspiration,
    Material,
    MiniUser,
    Order,
    Recommendation,
)
from .services import material_to_dict


def user_dict(user: MiniUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "openid": user.openid,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "phone": user.phone,
        "birth_date": user.birth_date.isoformat() if user.birth_date else None,
        "birth_time": user.birth_time.isoformat() if user.birth_time else None,
        "gender": user.gender,
        "city": user.city,
        "zodiac": user.zodiac,
        "element": user.element,
        "intention": user.intention,
    }


def assessment_dict(item: CrystalAssessment) -> dict[str, Any]:
    return {
        "id": item.id,
        "user_id": item.user_id,
        "profile": item.profile,
        "intention": item.intention,
        "energy_profile": item.energy_profile,
        "recommended_materials": item.recommended_materials,
        "bracelet_plan": item.bracelet_plan,
        "summary": item.summary,
        "created_at": item.created_at.isoformat(),
    }


def daily_energy_dict(item: DailyEnergy) -> dict[str, Any]:
    return {
        "id": item.id,
        "date": item.date.isoformat(),
        "score": item.score,
        "title": item.title,
        "summary": item.summary,
        "lucky_color": item.lucky_color,
        "lucky_crystal": item.lucky_crystal,
        "affirmation": item.affirmation,
        "actions": item.actions,
        "recommended_materials": item.recommended_materials,
        "source": item.source,
        "created_at": item.created_at.isoformat(),
    }


def recommendation_dict(item: Recommendation) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "subtitle": item.subtitle,
        "scene": item.scene,
        "image_url": item.image_url,
        "tags": item.tags,
        "materials": item.materials,
        "plan": item.plan,
        "popularity": item.popularity,
    }


def inspiration_dict(item: Inspiration) -> dict[str, Any]:
    return {
        "id": item.id,
        "user": user_dict(item.user) if item.user else None,
        "title": item.title,
        "content": item.content,
        "image_urls": item.image_urls,
        "tags": item.tags,
        "materials": item.materials,
        "likes_count": item.likes_count,
        "collects_count": item.collects_count,
        "is_featured": item.is_featured,
        "created_at": item.created_at.isoformat(),
    }


def diy_plan_dict(item: DIYPlan) -> dict[str, Any]:
    return {
        "id": item.id,
        "user_id": item.user_id,
        "name": item.name,
        "intention": item.intention,
        "wrist_size_cm": float(item.wrist_size_cm) if item.wrist_size_cm is not None else None,
        "beads": item.beads,
        "accessories": item.accessories,
        "layout": item.layout,
        "price_snapshot": float(item.price_snapshot),
        "cover_image_url": item.cover_image_url,
        "status": item.status,
        "remark": item.remark,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def order_dict(item: Order) -> dict[str, Any]:
    return {
        "id": item.id,
        "order_no": item.order_no,
        "status": item.status,
        "total_amount": float(item.total_amount),
        "items": item.items,
        "address": item.address,
        "logistics": item.logistics,
        "diy_plan": diy_plan_dict(item.diy_plan) if item.diy_plan else None,
        "paid_at": item.paid_at.isoformat() if item.paid_at else None,
        "created_at": item.created_at.isoformat(),
    }


def cart_item_dict(item: CartItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "material": material_to_dict(item.material),
        "quantity": item.quantity,
        "selected": item.selected,
    }


def favorite_dict(item: Favorite) -> dict[str, Any]:
    return {
        "id": item.id,
        "target_type": item.target_type,
        "target_id": item.target_id,
        "created_at": item.created_at.isoformat(),
    }


def address_dict(item: Address) -> dict[str, Any]:
    return {
        "id": item.id,
        "receiver": item.receiver,
        "phone": item.phone,
        "province": item.province,
        "city": item.city,
        "district": item.district,
        "detail": item.detail,
        "is_default": item.is_default,
    }


__all__ = [
    "address_dict",
    "assessment_dict",
    "cart_item_dict",
    "daily_energy_dict",
    "diy_plan_dict",
    "favorite_dict",
    "inspiration_dict",
    "material_to_dict",
    "order_dict",
    "recommendation_dict",
    "user_dict",
]
