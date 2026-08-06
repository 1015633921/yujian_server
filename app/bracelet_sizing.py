"""Shared, unit-safe bracelet fitting primitives for server-side decisions."""

from __future__ import annotations

import math
from typing import Any


BRACELET_FIT_MODEL_VERSION = "bracelet-fit-v3"
DEFAULT_ALLOWANCE_MM = 8.0
DEFAULT_TOLERANCE_MM = 5.0


def _positive_number(*values: Any) -> float:
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number > 0:
            return number
    return 0.0


def _merged_params(item: dict[str, Any]) -> dict[str, Any]:
    visual = item.get("visual") if isinstance(item.get("visual"), dict) else {}
    return {
        **(visual.get("material_params") if isinstance(visual.get("material_params"), dict) else {}),
        **(item.get("material_params") if isinstance(item.get("material_params"), dict) else {}),
        **(item.get("physical_specs") if isinstance(item.get("physical_specs"), dict) else {}),
    }


def _axis_degrees(value: Any) -> float:
    try:
        angle = float(value)
    except (TypeError, ValueError):
        angle = 90.0
    return angle % 180.0 if math.isfinite(angle) else 90.0


def _radial_depth_mm(params: dict[str, Any], fallback_mm: float) -> float:
    explicit = _positive_number(params.get("radial_depth_mm"), params.get("inward_depth_mm"))
    if explicit:
        return explicit
    width = _positive_number(params.get("body_width_mm"), fallback_mm)
    height = _positive_number(params.get("body_height_mm"), fallback_mm)
    if not width or not height:
        return fallback_mm
    axis = math.radians(_axis_degrees(params.get("image_string_axis_deg")))
    return abs(width * math.sin(axis)) + abs(height * math.cos(axis))


def normalize_bracelet_specs(items_or_sizes: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for raw in items_or_sizes or []:
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            size = _positive_number(raw)
            specs.append({
                "tangent_width_mm": size,
                "radial_depth_mm": size,
                "participates": bool(size),
                "spec_complete": bool(size),
            })
            continue
        if not isinstance(raw, dict):
            continue
        params = _merged_params(raw)
        tangent_width_mm = _positive_number(
            params.get("string_axis_width_mm"),
            raw.get("string_axis_width_mm"),
            raw.get("actual_material_size_mm"),
            raw.get("bead_size_mm"),
            raw.get("size"),
            raw.get("size_mm"),
            raw.get("diameter"),
        )
        placement_mode = str(raw.get("placement_mode") or params.get("placement_mode") or "threaded").strip().lower()
        attachment = raw.get("attachment") if isinstance(raw.get("attachment"), dict) else {}
        attachment_mode = str(raw.get("attachment_mode") or attachment.get("mode") or "").strip().lower()
        attached_side = placement_mode == "attached_side" or attachment_mode == "bead_cap"
        explicit_shape = params.get("bead_shape") or raw.get("shape")
        shape = str(explicit_shape or ("round" if raw.get("top", "bead") == "bead" else "special")).strip().lower()
        round_shape = shape in {"round", "faceted_round"}
        body_complete = all(_positive_number(params.get(key)) > 0 for key in (
            "string_axis_width_mm", "body_width_mm", "body_height_mm"
        ))
        specs.append({
            "tangent_width_mm": tangent_width_mm,
            "radial_depth_mm": 0.0 if placement_mode == "hanging" else _radial_depth_mm(params, tangent_width_mm),
            "participates": not attached_side and tangent_width_mm > 0,
            # Old order/recommendation records have no shape metadata at all;
            # retain their established round-SKU behavior.  Explicitly non-round
            # materials must carry all measured dimensions.
            "spec_complete": attached_side or round_shape or body_complete or not explicit_shape,
        })
    return specs


def solve_closed_ring(specs: list[dict[str, Any]]) -> dict[str, Any] | None:
    items = [item for item in specs if item.get("participates") and item.get("tangent_width_mm", 0) > 0]
    if len(items) < 3:
        return None
    tangent_radii = [float(item["tangent_width_mm"]) / 2 for item in items]
    radial_radii = [max(0.0, float(item.get("radial_depth_mm") or 0)) / 2 for item in items]
    contacts = [
        tangent_radii[index] + tangent_radii[(index + 1) % len(tangent_radii)]
        for index in range(len(tangent_radii))
    ]

    def central_angles(center_radius: float) -> list[float]:
        return [2 * math.asin(min(1.0, contact / (2 * center_radius))) for contact in contacts]

    lower = max(max(tangent_radii), max(radial_radii), max(contacts) / 2) * (1 + 1e-9)
    if sum(central_angles(lower)) < math.tau:
        return None
    upper = max(lower * 2, sum(contacts))
    while sum(central_angles(upper)) > math.tau:
        upper *= 2
    for _ in range(72):
        midpoint = (lower + upper) / 2
        if sum(central_angles(midpoint)) > math.tau:
            lower = midpoint
        else:
            upper = midpoint
    center_radius_mm = (lower + upper) / 2
    angles = central_angles(center_radius_mm)
    inner_circumference_mm = sum(
        max(0.0, center_radius_mm - radius) * (angles[index - 1] + angles[index]) / 2
        for index, radius in enumerate(radial_radii)
    )
    return {
        "center_radius_mm": center_radius_mm,
        "angles": angles,
        "inner_circumference_mm": inner_circumference_mm,
    }


def estimate_inner_circumference_mm(items_or_sizes: list[Any] | tuple[Any, ...]) -> float:
    geometry = solve_closed_ring(normalize_bracelet_specs(items_or_sizes))
    return float(geometry["inner_circumference_mm"]) if geometry else 0.0


def resize_sequence_to_count(sequence: list[Any], target_count: int) -> list[Any]:
    source = [item for item in sequence if item]
    count = max(0, int(target_count or 0))
    if not source or not count:
        return []
    if count == len(source):
        return list(source)
    return [source[min(len(source) - 1, int((index + 0.5) * len(source) / count))] for index in range(count)]


def recommend_bead_count(
    items_or_sizes: list[Any] | tuple[Any, ...],
    wrist_size_cm: float,
    *,
    allowance_mm: float = DEFAULT_ALLOWANCE_MM,
    min_count: int = 12,
    max_count: int = 40,
    default_bead_size_mm: float = 8,
) -> int:
    source = [item for item in items_or_sizes if item] or [default_bead_size_mm]
    minimum = max(3, int(min_count))
    maximum = max(minimum, int(max_count))
    target_mm = max(0.0, float(wrist_size_cm or 0) * 10 + max(0.0, float(allowance_mm or 0)))
    best: tuple[tuple[float, bool, int], int] | None = None
    for count in range(minimum, maximum + 1):
        actual_mm = estimate_inner_circumference_mm(resize_sequence_to_count(source, count))
        if actual_mm <= 0:
            continue
        error_mm = actual_mm - target_mm
        rank = (abs(error_mm), error_mm < 0, count)
        if best is None or rank < best[0]:
            best = (rank, count)
    return best[1] if best else maximum


def calculate_bracelet_fit(
    items_or_sizes: list[Any] | tuple[Any, ...],
    wrist_size_cm: float,
    *,
    allowance_mm: float = DEFAULT_ALLOWANCE_MM,
    tolerance_mm: float = DEFAULT_TOLERANCE_MM,
    min_count: int = 12,
    max_count: int = 40,
) -> dict[str, Any]:
    allowance = max(0.0, float(allowance_mm or 0))
    tolerance = max(0.0, float(tolerance_mm or 0))
    wrist_mm = max(0.0, float(wrist_size_cm or 0) * 10)
    specs = normalize_bracelet_specs(items_or_sizes)
    active = [item for item in specs if item.get("participates")]
    geometry = solve_closed_ring(specs)
    actual_mm = float(geometry["inner_circumference_mm"]) if geometry else 0.0
    target_mm = wrist_mm + allowance
    error_mm = actual_mm - target_mm
    measurable = bool(active) and len(active) >= 3 and geometry is not None and all(item.get("spec_complete") for item in active)
    if not active:
        status = "empty"
    elif not measurable:
        status = "unverifiable"
    elif error_mm > tolerance:
        status = "long"
    elif error_mm < -tolerance:
        status = "short"
    else:
        status = "fit"
    return {
        "model_version": BRACELET_FIT_MODEL_VERSION,
        "wrist_mm": wrist_mm,
        "allowance_mm": allowance,
        "tolerance_mm": tolerance,
        "target_inner_mm": target_mm,
        "actual_inner_mm": actual_mm,
        "error_mm": error_mm,
        "status": status,
        "measurable": measurable,
        "recommended_count": recommend_bead_count(
            items_or_sizes,
            wrist_size_cm,
            allowance_mm=allowance,
            min_count=min_count,
            max_count=max_count,
        ),
    }
