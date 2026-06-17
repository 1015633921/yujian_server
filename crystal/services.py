from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from .models import DailyEnergy, Material, MiniUser


INTENTION_TAGS = {
    "love": ["rose_quartz", "moonstone", "pink", "soft"],
    "career": ["citrine", "tiger_eye", "gold", "focus"],
    "wealth": ["citrine", "green_phantom", "gold", "growth"],
    "study": ["fluorite", "amethyst", "purple", "clarity"],
    "sleep": ["amethyst", "moonstone", "blue", "calm"],
    "health": ["clear_quartz", "green", "balance"],
    "protection": ["obsidian", "smoky_quartz", "black", "grounding"],
}

DEFAULT_ACTIONS = [
    "Wear the bracelet on your non-dominant hand for 2 hours.",
    "Keep one clear intention before starting work.",
    "Cleanse the crystal briefly with moonlight or a gentle cloth.",
]


def stable_score(user: MiniUser, target_date: date) -> int:
    raw = f"{user.pk}:{target_date.isoformat()}:{user.intention}:{user.zodiac}".encode()
    digest = hashlib.sha256(raw).hexdigest()
    return 60 + int(digest[:8], 16) % 36


def material_to_dict(material: Material) -> dict[str, Any]:
    return {
        "id": material.id,
        "type": material.material_type,
        "name": material.name,
        "code": material.code,
        "image_url": material.image_url,
        "price": float(material.price),
        "stock": material.stock,
        "diameter_mm": float(material.diameter_mm) if material.diameter_mm is not None else None,
        "color": material.color,
        "element": material.element,
        "energy_tags": material.energy_tags,
        "effects": material.effects,
        "description": material.description,
    }


def pick_materials(intention: str, limit: int = 6) -> list[Material]:
    tags = INTENTION_TAGS.get(intention, [])
    queryset: QuerySet[Material] = Material.objects.filter(is_active=True)
    scored = []
    for material in queryset:
        tag_score = len(set(tags) & set(material.energy_tags + material.effects + [material.color, material.element]))
        scored.append((tag_score, material.sort_order, material.id, material))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [item[3] for item in scored[:limit]]


def calculate_assessment(user: MiniUser, payload: dict[str, Any]) -> dict[str, Any]:
    intention = payload.get("intention") or user.intention or "career"
    profile = payload.get("profile") or {}
    materials = pick_materials(intention, 8)
    material_dicts = [material_to_dict(item) for item in materials]
    bead_count = int(payload.get("bead_count") or 18)
    wrist_size = payload.get("wrist_size_cm") or profile.get("wrist_size_cm")
    bracelet_items = [
        {
            "material_id": item["id"],
            "name": item["name"],
            "quantity": max(1, bead_count // max(1, len(material_dicts))),
            "role": "main" if index == 0 else "support",
        }
        for index, item in enumerate(material_dicts[:4])
    ]
    estimated_price = sum(Decimal(str(item["price"])) for item in material_dicts[:4])

    return {
        "profile": profile,
        "intention": intention,
        "energy_profile": {
            "main_intention": intention,
            "keywords": INTENTION_TAGS.get(intention, ["balance", "clarity"]),
            "wrist_size_cm": wrist_size,
        },
        "recommended_materials": material_dicts,
        "bracelet_plan": {
            "bead_count": bead_count,
            "wrist_size_cm": wrist_size,
            "items": bracelet_items,
            "estimated_price": float(estimated_price),
        },
        "summary": "This plan balances your main intention with daily wearability and color harmony.",
    }


def calculate_daily_energy(user: MiniUser, target_date: date | None = None) -> DailyEnergy:
    target_date = target_date or timezone.localdate()
    existing = DailyEnergy.objects.filter(user=user, date=target_date).first()
    if existing:
        return existing

    score = stable_score(user, target_date)
    intention = user.intention or "career"
    materials = [material_to_dict(item) for item in pick_materials(intention, 3)]
    lucky = materials[0]["name"] if materials else "Clear Quartz"
    lucky_color = materials[0]["color"] if materials and materials[0]["color"] else "white"
    title = "High Flow Day" if score >= 85 else "Steady Recharge Day" if score >= 72 else "Gentle Balance Day"
    summary = "Your energy is suitable for focused creation and calm decisions today."
    if score < 72:
        summary = "Keep the pace gentle today and use grounding crystals to protect your attention."

    return DailyEnergy.objects.create(
        user=user,
        date=target_date,
        score=score,
        title=title,
        summary=summary,
        lucky_color=lucky_color,
        lucky_crystal=lucky,
        affirmation="I choose what supports my energy today.",
        actions=DEFAULT_ACTIONS,
        recommended_materials=materials,
        source={"calculated_at": timezone.now().isoformat(), "intention": intention},
    )


def estimate_plan_price(beads: list[dict[str, Any]], accessories: list[dict[str, Any]]) -> Decimal:
    total = Decimal("0")
    all_items = beads + accessories
    material_ids = [item.get("material_id") for item in all_items if item.get("material_id")]
    materials = {item.id: item for item in Material.objects.filter(id__in=material_ids)}
    for item in all_items:
        material = materials.get(item.get("material_id"))
        quantity = Decimal(str(item.get("quantity") or 1))
        if material:
            total += material.price * quantity
        else:
            total += Decimal(str(item.get("price") or 0)) * quantity
    return total
