from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .admin_api import admin_service, require_admin, success
from .ai_material_tagging import (
    BailianMaterialTaggingError,
    MaterialTaggingRepository,
    MaterialTaggingResult,
    MaterialTaggingService,
)


ai_material_router = APIRouter(
    prefix="/api/v1/admin/material-ai-tags",
    tags=["后台管理"],
)
repository = MaterialTaggingRepository()


class MaterialTaggingRunPayload(BaseModel):
    top: str = Field(default="", max_length=40)
    material_codes: list[str] = Field(default_factory=list, max_length=20)
    series_keyword: str = Field(default="", max_length=80)
    limit: int = Field(default=1, ge=1, le=1)
    force: bool = False


class MaterialTaggingReviewPayload(BaseModel):
    action: Literal["approved", "rejected"]
    final_payload: dict[str, Any] | None = None
    notes: str = Field(default="", max_length=1000)


@ai_material_router.get("", summary="AI材料视觉标注列表")
def list_material_ai_tags(
    status: str = Query(default="", max_length=30),
    material_code: str = Query(default="", max_length=160),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    try:
        return success(
            repository.list_annotations(
                status=status,
                material_code=material_code,
                limit=limit,
            )
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@ai_material_router.get("/{annotation_id}", summary="AI材料视觉标注详情")
def material_ai_tag_detail(
    annotation_id: str,
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    try:
        return success(repository.get(annotation_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@ai_material_router.post("/analyze", summary="小批量执行AI材料视觉打标")
def analyze_materials(
    payload: MaterialTaggingRunPayload,
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    targets = repository.list_targets(
        limit=payload.limit,
        top=payload.top,
        material_codes=payload.material_codes,
        series_keyword=payload.series_keyword,
        require_gallery=True,
    )
    if not targets:
        raise HTTPException(status_code=400, detail="没有找到具备图库图片的目标品种")
    try:
        result = MaterialTaggingService(repository=repository).analyze_targets(
            targets,
            force=payload.force,
        )
    except BailianMaterialTaggingError as exc:
        status_code = 503 if exc.code == "BAILIAN_NOT_CONFIGURED" else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return success(result, "AI材料视觉打标已完成，请进行人工审核")


@ai_material_router.post("/{annotation_id}/review", summary="审核AI材料视觉标注")
def review_material_ai_tag(
    annotation_id: str,
    payload: MaterialTaggingReviewPayload,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    if payload.action == "approved" and payload.final_payload is not None:
        try:
            MaterialTaggingResult.model_validate(payload.final_payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="审核结果未通过材料打标Schema校验") from exc
    try:
        result = repository.review(
            annotation_id,
            action=payload.action,
            reviewer=actor,
            final_payload=payload.final_payload,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(result, "AI材料视觉标注审核已保存")


@ai_material_router.post("/{annotation_id}/apply", summary="将已审核AI标注应用到材料资料")
def apply_material_ai_tag(
    annotation_id: str,
    authorization: str | None = Header(default=None),
):
    actor = require_admin(authorization)
    try:
        result = repository.apply_to_material(
            annotation_id,
            operator=actor,
            audit_callback=admin_service.record_material_audit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return success(result, "AI标注已应用到材料资料")
