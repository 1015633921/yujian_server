from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def validate_media_urls(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    if values:
        raise ValueError("社区媒体上传尚未开放，不能提交客户端外链")
    return []


def normalize_tags(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    normalized: list[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if not value or len(value) > 30:
            raise ValueError("每个标签长度必须为 1-30 个字符")
        if value not in normalized:
            normalized.append(value)
    return normalized


class CommunityPayload(BaseModel):
    """Strict base model for user-controlled community writes."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CommunityPostCreate(CommunityPayload):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=5000)
    image_urls: list[str] = Field(default_factory=list, max_length=9)
    tags: list[str] = Field(default_factory=list, max_length=10)
    design_id: str | None = Field(default=None, min_length=1, max_length=80)
    source_post_id: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, values: list[str]) -> list[str]:
        return validate_media_urls(values) or []

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        return normalize_tags(values) or []


class CommunityPostUpdate(CommunityPayload):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    image_urls: list[str] | None = Field(default=None, max_length=9)
    tags: list[str] | None = Field(default=None, max_length=10)
    design_id: str | None = Field(default=None, min_length=1, max_length=80)
    source_post_id: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, values: list[str] | None) -> list[str] | None:
        return validate_media_urls(values)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str] | None) -> list[str] | None:
        return normalize_tags(values)

    @model_validator(mode="after")
    def require_valid_change(self):
        if not self.model_fields_set:
            raise ValueError("至少需要提供一个待更新字段")
        nullable_references = {"design_id", "source_post_id"}
        if any(
            getattr(self, field) is None
            for field in self.model_fields_set
            if field not in nullable_references
        ):
            raise ValueError("标题、正文、图片和标签不能更新为 null")
        return self


class CommunityCommentCreate(CommunityPayload):
    content: str = Field(min_length=1, max_length=500)


class CommunityReportCreate(CommunityPayload):
    target_type: Literal["post", "comment"]
    target_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=40)
    detail: str | None = Field(default=None, max_length=500)
