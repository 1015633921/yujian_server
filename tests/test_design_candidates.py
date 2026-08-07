from __future__ import annotations

from app import admin_api
from app.admin_api import CustomDesignCandidatePayload
from app.design_candidates import build_design_candidates, parse_budget


def brief() -> dict:
    return {
        "lineage": {"input_fingerprint": "brief-safe-fingerprint"},
        "intervention": {"level": "moderate"},
        "hard_constraints": [
            {"key": "wrist_size_cm", "value": "16 cm"},
            {"key": "bead_size_mm", "value": "8 mm"},
            {"key": "budget", "value": "100–200 元"},
        ],
        "palette": {
            "base": [{"key": "blue"}, {"key": "white"}],
            "support": [{"key": "clear"}],
            "accent": [{"key": "gray"}],
            "avoid": [{"key": "black"}],
        },
        "optics": {"tags": ["冰透", "低饱和"]},
        "preferences": {"accessory": "少量银饰"},
        "material_roles": [
            {"key": "primary", "element": "水"},
            {"key": "support", "element": "金"},
            {"key": "accent", "element": ""},
        ],
    }


def material(material_id: str, **overrides) -> dict:
    item = {
        "id": material_id,
        "material_code": material_id,
        "enabled": True,
        "top": "bead",
        "price": 8.0,
        "size": 8,
        "stock": 20,
        "reserved_stock": 0,
        "sku": {
            "id": material_id,
            "name": material_id,
            "top": "bead",
            "enabled": True,
            "price_per_bead": 8.0,
            "size_mm": 8,
            "stock": 20,
            "reserved_stock": 0,
        },
        "energy": {
            "primary_element": "water",
            "secondary_elements": [],
            "color_family": "blue",
            "visual_tags": ["icy", "soft_color"],
        },
        "visual": {"image_urls": [f"https://cdn.example.com/{material_id}-gallery.webp"]},
        "rules": {
            "allowed_roles": ["primary"],
            "match_rules": ["best_as_primary"],
        },
        "material_params": {"bead_shape": "round", "placement_mode": "threaded"},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(item.get(key), dict):
            item[key] = {**item[key], **value}
        else:
            item[key] = value
    return item


def group(result: dict, role: str) -> list[dict]:
    return next(item["items"] for item in result["candidate_groups"] if item["role"] == role)


def test_candidates_rank_live_gallery_materials_against_brief_without_auto_layout():
    result = build_design_candidates(
        brief(),
        [
            material("water-primary"),
            material(
                "metal-support",
                energy={"primary_element": "metal", "color_family": "clear", "visual_tags": ["icy"]},
                rules={"allowed_roles": ["support"], "match_rules": ["best_as_support"]},
            ),
            material(
                "silver-accent",
                top="accessory",
                sku={"id": "silver-accent", "name": "银色隔珠", "top": "accessory", "enabled": True, "price_per_bead": 4.0, "size_mm": 0, "stock": 20},
                price=4,
                size=0,
                energy={"primary_element": "metal", "color_family": "gray", "visual_tags": []},
                rules={"allowed_roles": ["accent"], "match_rules": ["accent_only"]},
            ),
        ],
    )

    primary = group(result, "primary")[0]
    support = group(result, "support")[0]
    accent = group(result, "accent")[0]
    assert result["status"] == "ready"
    assert result["estimated_bead_count"] > 0
    assert result["active_constraints"] == {"wrist_size_cm": 16.0, "bead_size_mm": 8.0}
    assert primary["material_id"] == "water-primary"
    assert primary["image_url"].endswith("water-primary-gallery.webp")
    assert primary["single_material_string_estimate"] > 0
    assert any("水" in reason for reason in primary["reasons"])
    assert support["material_id"] == "metal-support"
    assert accent["material_id"] == "silver-accent"
    assert accent["single_material_string_estimate"] is None
    assert "layout" not in result
    assert "birthday" not in str(result)


def test_candidates_exclude_incompatible_or_unsupported_materials_without_conflict_rules():
    selected = material("selected", rules={"allowed_roles": ["primary"], "match_rules": []})
    materials = [
        selected,
        material("out-stock", stock=0, sku={"stock": 0}),
        material("missing-gallery", visual={"image_urls": []}),
        material("wrong-size", size=10, sku={"size_mm": 10}),
        material("black-avoid", energy={"primary_element": "water", "color_family": "black", "visual_tags": []}),
        material("cap", top="accessory", sku={"top": "accessory", "size_mm": 0}, size=0, material_params={"bead_shape": "bead_cap", "placement_mode": "attached_side"}),
        material("hanging", top="accessory", sku={"top": "accessory", "size_mm": 0}, size=0, material_params={"bead_shape": "charm", "placement_mode": "hanging"}),
        material("conflict", material_code="conflicting"),
    ]

    result = build_design_candidates(brief(), materials, selected_material_ids=["selected"])
    ids = {item["material_id"] for candidate_group in result["candidate_groups"] for item in candidate_group["items"]}

    assert "selected" in ids  # Re-using a material is a designer decision.
    assert {"out-stock", "missing-gallery", "wrong-size", "black-avoid", "cap", "hanging"}.isdisjoint(ids)
    assert "conflict" in ids


def test_candidates_use_stable_tie_breaking_and_budget_is_advisory_not_a_filter():
    expensive_a = material("a-expensive", price=50, sku={"price_per_bead": 50})
    expensive_b = material("b-expensive", price=50, sku={"price_per_bead": 50})
    first = build_design_candidates(brief(), [expensive_b, expensive_a])
    second = build_design_candidates(brief(), [expensive_a, expensive_b])

    assert [item["material_id"] for item in group(first, "primary")] == ["a-expensive", "b-expensive"]
    assert [item["material_id"] for item in group(second, "primary")] == ["a-expensive", "b-expensive"]
    assert group(first, "primary")[0]["budget_status"] == "over"
    assert "高于用户预算" in group(first, "primary")[0]["budget_message"]


def test_candidates_recalculate_physical_filter_for_current_designer_size_without_changing_brief():
    result = build_design_candidates(
        brief(),
        [material("eight-mm"), material("ten-mm", size=10, sku={"size_mm": 10})],
        wrist_size_cm=17,
        bead_size_mm=10,
    )

    assert result["active_constraints"] == {"wrist_size_cm": 17.0, "bead_size_mm": 10.0}
    assert [item["material_id"] for item in group(result, "primary")] == ["ten-mm"]


def test_budget_parser_handles_ranges_and_open_ended_display_text():
    assert parse_budget("100-200 元") == {"raw": "100-200 元", "minimum": 100.0, "maximum": 200.0, "recognized": True}
    assert parse_budget("800 元以上")["minimum"] == 800.0
    assert parse_budget("500 元以内")["maximum"] == 500.0


def test_admin_candidate_endpoint_is_operator_only_read_model(monkeypatch):
    class FakeAdminService:
        def require_admin(self, token):
            assert token == "operator-token"
            return {"admin_id": "operator-1", "role": "operator"}

        def list_materials(self, **kwargs):
            assert kwargs == {"status": "enabled", "sort_by": "sort_order", "sort_order": "asc"}
            return [material("endpoint-primary")]

    class FakeCustomDesignService:
        @staticmethod
        def get_admin_overview(request_id):
            assert request_id == "CD-CANDIDATE-1"
            return {"design_brief": brief()}

    monkeypatch.setattr(admin_api, "admin_service", FakeAdminService())
    monkeypatch.setattr(admin_api, "custom_design_service", FakeCustomDesignService())

    result = admin_api.custom_design_material_candidates(
        "CD-CANDIDATE-1",
        CustomDesignCandidatePayload(selected_material_ids=[]),
        "Bearer operator-token",
    )

    assert result["code"] == 0
    assert result["data"]["status"] == "ready"
    assert result["data"]["candidate_groups"][0]["items"][0]["material_id"] == "endpoint-primary"
