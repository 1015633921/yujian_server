from __future__ import annotations

import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai_material_tagging import (
    BailianMaterialTaggingClient,
    BailianMaterialTaggingError,
    MaterialAnalysisResponse,
    MaterialTaggingRepository,
    MaterialTaggingResult,
    deduplicate_image_urls,
    material_application_fields,
)
from app.material_knowledge import fetch_knowledge_map, upsert_material_knowledge
from app.main import app
from app.migrations.versions import v20260723_12_ai_material_annotations as migration


def result_payload(target_id: str, material_code: str) -> dict:
    return {
        "target_id": target_id,
        "material_code": material_code,
        "visual": {
            "dominant_colors": ["冷银色"],
            "brightness": 76,
            "saturation": 3,
            "temperature": -35,
            "transparency": 0,
            "texture_complexity": 24,
            "sparkle": 28,
            "visual_weight": 18,
        },
        "design": {
            "roles": ["节奏配饰", "过渡配饰"],
            "style_tags": ["清透", "极简", "通勤"],
            "shape_language": ["圆润", "细线条"],
            "recommended_metal_palettes": ["冷色低饱和", "蓝白透明"],
            "recommended_usage": {
                "count_min": 2,
                "count_max": 4,
                "symmetry": "prefer_paired",
                "focus_strength": "low",
            },
        },
        "confidence": 0.86,
        "uncertain_fields": [],
    }


def create_database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE managed_materials (
              id TEXT PRIMARY KEY, material_code TEXT NOT NULL, top TEXT NOT NULL,
              category TEXT NOT NULL, series TEXT NOT NULL, name TEXT NOT NULL,
              size REAL NOT NULL, image_url TEXT, image_urls_json TEXT,
              physical_specs_json TEXT, enabled INTEGER NOT NULL, sort_order INTEGER NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        gallery = json.dumps(
            [
                "https://cdn-test.yustream.cn/materials/gallery-a.webp",
                "https://cdn-test.yustream.cn/materials/gallery-b.webp",
            ]
        )
        for index, size in enumerate((8, 10), start=1):
            connection.execute(
                """
                INSERT INTO managed_materials
                (id, material_code, top, category, series, name, size, image_url,
                 image_urls_json, physical_specs_json, enabled, sort_order, updated_at)
                VALUES (?, 'silver_spacer', 'accessory', '隔珠', '银色圆柱隔珠',
                        '银色圆柱隔珠', ?, 'https://cdn-test.yustream.cn/main.webp',
                        ?, '{"installation":"threaded"}', 1, ?, '2026-07-23T00:00:00Z')
                """,
                (f"sku-{index}", size, gallery, index),
            )
        connection.execute(
            """
            CREATE TABLE material_knowledge (
              code TEXT PRIMARY KEY, name TEXT NOT NULL,
              primary_element TEXT NOT NULL DEFAULT '',
              secondary_elements_json TEXT NOT NULL, chakras_json TEXT NOT NULL,
              chakra_weights_json TEXT NOT NULL, effects_json TEXT NOT NULL,
              wish_pools_json TEXT NOT NULL, color_family TEXT NOT NULL DEFAULT '',
              mood_tags_json TEXT NOT NULL, visual_tags_json TEXT NOT NULL,
              story TEXT, allowed_roles_json TEXT NOT NULL,
              match_rules_json TEXT NOT NULL, care_tags_json TEXT NOT NULL,
              material_params_json TEXT NOT NULL, asset_json TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
            """
        )
        migration.upgrade(connection, "sqlite")


def test_schema_rejects_out_of_range_visual_score():
    payload = result_payload("spu_12345678", "silver_spacer")
    payload["visual"]["brightness"] = 101
    with pytest.raises(ValidationError):
        MaterialTaggingResult.model_validate(payload)


def test_image_deduplication_prefers_cdn_for_same_object_path():
    urls = [
        "https://bucket.cos.ap-guangzhou.myqcloud.com/materials/a.webp",
        "https://cdn-test.yustream.cn/materials/a.webp?v=2",
        "https://cdn-test.yustream.cn/materials/b.webp",
    ]

    assert deduplicate_image_urls(urls) == [
        "https://cdn-test.yustream.cn/materials/a.webp?v=2",
        "https://cdn-test.yustream.cn/materials/b.webp",
    ]


def test_repository_groups_sizes_and_uses_gallery_not_main_image(tmp_path):
    database = tmp_path / "tagging.db"
    create_database(database)
    repository = MaterialTaggingRepository(database)

    targets = repository.list_targets(limit=10)

    assert len(targets) == 1
    target = targets[0]
    assert target.known_facts["available_sizes_mm"] == [8.0, 10.0]
    assert target.image_urls == [
        "https://cdn-test.yustream.cn/materials/gallery-a.webp",
        "https://cdn-test.yustream.cn/materials/gallery-b.webp",
    ]
    assert "main.webp" not in target.image_urls


def test_client_validates_identity_and_disables_thinking(tmp_path):
    database = tmp_path / "tagging.db"
    create_database(database)
    target = MaterialTaggingRepository(database).list_targets(limit=1)[0]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "qwen3.7-plus-2026-05-26"
        assert body["enable_thinking"] is False
        assert body["response_format"] == {"type": "json_object"}
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            headers={"x-request-id": "request-1"},
            json={
                "id": "completion-1",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                result_payload(target.target_id, target.material_code),
                                ensure_ascii=False,
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 80},
            },
        )

    client = BailianMaterialTaggingClient(
        api_key="test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _seconds: None,
    )
    response = client.analyze(target)

    assert response.request_id == "request-1"
    assert response.result.target_id == target.target_id
    assert response.result.visual.brightness == 76
    assert response.result.design.roles == ["节奏配饰", "过渡配饰"]
    assert response.result.confidence == 0.85


def test_client_rejects_changed_target_id(tmp_path):
    database = tmp_path / "tagging.db"
    create_database(database)
    target = MaterialTaggingRepository(database).list_targets(limit=1)[0]
    invalid = result_payload("spu_wrong_target", target.material_code)

    client = BailianMaterialTaggingClient(
        api_key="test-key",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    json={
                        "choices": [
                            {"message": {"content": json.dumps(invalid, ensure_ascii=False)}}
                        ]
                    },
                )
            )
        ),
        sleep=lambda _seconds: None,
    )

    with pytest.raises(BailianMaterialTaggingError) as exc:
        client.analyze(target)
    assert exc.value.code == "BAILIAN_ID_MISMATCH"


def test_client_retries_transient_multimodal_download_failure(tmp_path):
    database = tmp_path / "tagging.db"
    create_database(database)
    target = MaterialTaggingRepository(database).list_targets(limit=1)[0]
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "code": "invalid_parameter_error",
                        "message": "Failed to download multimodal content",
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                result_payload(target.target_id, target.material_code),
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    client = BailianMaterialTaggingClient(
        api_key="test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _seconds: None,
    )

    assert client.analyze(target).result.material_code == target.material_code
    assert calls == 2


def test_client_removes_cross_type_roles_and_caps_single_image_confidence(tmp_path):
    database = tmp_path / "tagging.db"
    create_database(database)
    target = MaterialTaggingRepository(database).list_targets(limit=1)[0]
    target = target.__class__(
        **{**target.__dict__, "image_urls": target.image_urls[:1]}
    )
    payload = result_payload(target.target_id, target.material_code)
    payload["design"]["roles"] = ["主题珠材", "焦点配饰"]
    payload["uncertain_fields"] = ["具体合金成分", "侧面反光无法确认"]
    client = BailianMaterialTaggingClient(
        api_key="test-key",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(payload, ensure_ascii=False)
                                }
                            }
                        ]
                    },
                )
            )
        ),
        sleep=lambda _seconds: None,
    )

    result = client.analyze(target).result

    assert result.design.roles == ["焦点配饰"]
    assert result.confidence == 0.75
    assert "具体合金成分" not in result.uncertain_fields
    assert "侧面反光无法确认" in result.uncertain_fields
    assert any("仅有1张图库图" in item for item in result.uncertain_fields)


def test_annotation_can_be_saved_and_approved(tmp_path):
    database = tmp_path / "tagging.db"
    create_database(database)
    repository = MaterialTaggingRepository(database)
    target = repository.list_targets(limit=1)[0]
    parsed = MaterialTaggingResult.model_validate(
        result_payload(target.target_id, target.material_code)
    )

    saved = repository.save_result(
        target,
        "qwen3.7-plus-2026-05-26",
        MaterialAnalysisResponse(
            result=parsed,
            raw_response=json.dumps(parsed.model_dump(), ensure_ascii=False),
            request_id="request-1",
            usage={"total_tokens": 180},
        ),
    )
    approved = repository.review(
        saved["annotation_id"],
        action="approved",
        reviewer={"admin_id": "admin-1", "display_name": "设计师"},
        notes="图片表现一致",
    )

    assert saved["status"] == "pending_review"
    assert approved["status"] == "approved"
    assert approved["reviewer_name"] == "设计师"
    assert approved["reviewer_final"]["visual"]["brightness"] == 76
    assert repository.find_reusable(target, "qwen3.7-plus-2026-05-26")["status"] == "approved"


def test_approved_annotation_applies_visual_fields_and_preserves_energy_data(tmp_path):
    database = tmp_path / "tagging.db"
    create_database(database)
    repository = MaterialTaggingRepository(database)
    target = repository.list_targets(limit=1)[0]
    parsed = MaterialTaggingResult.model_validate(
        result_payload(target.target_id, target.material_code)
    )
    fields = material_application_fields(parsed)

    assert fields["allowed_roles"] == ["spacer"]
    assert fields["match_rules"] == ["spacer_only", "pair_symmetry", "avoid_dense"]
    assert fields["visual_tags"] == ["soft_color"]
    assert fields["color_family"] == "white"
    assert fields["material_params"]["transparency_level"] == "opaque"

    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        upsert_material_knowledge(
            {
                "material_code": target.material_code,
                "name": target.name,
                "primary_element": "metal",
                "effects": ["protection"],
                "wish_pools": ["career"],
                "care_tags": ["avoid_water"],
                "allowed_roles": ["primary", "support", "accent"],
                "match_rules": ["no_limit"],
            },
            {
                "material_code": target.material_code,
                "name": target.name,
                "top": target.top,
            },
            connection=connection,
            force_update=True,
        )

    saved = repository.save_result(
        target,
        "qwen3.7-plus-2026-05-26",
        MaterialAnalysisResponse(
            result=parsed,
            raw_response=json.dumps(parsed.model_dump(), ensure_ascii=False),
            request_id="request-apply",
            usage={},
        ),
    )
    approved = repository.review(
        saved["annotation_id"],
        action="approved",
        reviewer={"admin_id": "admin-1", "display_name": "设计师"},
    )
    applied = repository.apply_to_material(
        approved["annotation_id"],
        operator={"admin_id": "admin-2", "display_name": "运营"},
    )
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        knowledge = fetch_knowledge_map([target.material_code], connection)[target.material_code]

    assert applied["status"] == "applied"
    assert applied["application"]["applied"] is True
    assert knowledge["primary_element"] == "metal"
    assert knowledge["effects"] == ["protection"]
    assert knowledge["wish_pools"] == ["career"]
    assert knowledge["care_tags"] == ["avoid_water"]
    assert knowledge["allowed_roles"] == ["spacer"]
    assert knowledge["match_rules"] == ["spacer_only", "pair_symmetry", "avoid_dense"]
    assert knowledge["visual_tags"] == ["soft_color"]
    assert knowledge["color_family"] == "white"
    assert knowledge["material_params"]["transparency_level"] == "opaque"
    assert knowledge["asset"]["ai_visual_profile"]["annotation_id"] == approved["annotation_id"]
    assert repository.apply_to_material(
        approved["annotation_id"],
        operator={"admin_id": "admin-2"},
    )["status"] == "applied"
    assert repository.find_reusable(target, "qwen3.7-plus-2026-05-26")["status"] == "applied"


def test_pending_annotation_cannot_be_applied(tmp_path):
    database = tmp_path / "tagging.db"
    create_database(database)
    repository = MaterialTaggingRepository(database)
    target = repository.list_targets(limit=1)[0]
    parsed = MaterialTaggingResult.model_validate(
        result_payload(target.target_id, target.material_code)
    )
    saved = repository.save_result(
        target,
        "qwen3.7-plus-2026-05-26",
        MaterialAnalysisResponse(
            result=parsed,
            raw_response="{}",
            request_id="request-pending",
            usage={},
        ),
    )

    with pytest.raises(ValueError, match="审核通过"):
        repository.apply_to_material(saved["annotation_id"], operator={"admin_id": "admin-1"})


def test_admin_apply_endpoint_writes_material_audit(tmp_path, monkeypatch):
    import app.ai_material_api as api_module

    database = tmp_path / "tagging.db"
    create_database(database)
    repository = MaterialTaggingRepository(database)
    target = repository.list_targets(limit=1)[0]
    parsed = MaterialTaggingResult.model_validate(
        result_payload(target.target_id, target.material_code)
    )
    saved = repository.save_result(
        target,
        "qwen3.7-plus-2026-05-26",
        MaterialAnalysisResponse(
            result=parsed,
            raw_response="{}",
            request_id="request-api-apply",
            usage={},
        ),
    )
    approved = repository.review(
        saved["annotation_id"],
        action="approved",
        reviewer={"admin_id": "admin-1", "display_name": "设计师"},
    )
    monkeypatch.setattr(api_module, "repository", repository)
    monkeypatch.setattr(
        api_module,
        "require_admin",
        lambda _authorization: {
            "admin_id": "admin-2",
            "username": "operator",
            "display_name": "运营",
        },
    )

    response = TestClient(app).post(
        f"/api/v1/admin/material-ai-tags/{approved['annotation_id']}/apply",
        headers={"authorization": "Bearer test"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "applied"
    with sqlite3.connect(database) as connection:
        audit = connection.execute(
            "SELECT action, material_code, actor_name FROM material_audit_logs"
        ).fetchone()
    assert audit == ("ai_tag_apply", target.material_code, "operator")


def test_migration_has_rollback(tmp_path):
    database = tmp_path / "migration.db"
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    migration.upgrade(connection, "sqlite")
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_material_annotations'"
    ).fetchone()
    migration.downgrade(connection, "sqlite")
    assert not connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_material_annotations'"
    ).fetchone()
    connection.close()
