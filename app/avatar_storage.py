from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

import httpx


IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_AVATAR_BYTES = 3 * 1024 * 1024
MAX_DESIGN_PREVIEW_BYTES = 5 * 1024 * 1024
MAX_ADMIN_MEDIA_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class AvatarUploadResult:
    key: str
    avatar_url: str


@dataclass(frozen=True)
class DesignPreviewUploadResult:
    key: str
    preview_url: str


@dataclass(frozen=True)
class MediaUploadResult:
    key: str
    url: str


class AvatarStorage:
    def __init__(self) -> None:
        self.bucket = os.getenv("TENCENT_COS_BUCKET", "")
        self.region = os.getenv("TENCENT_COS_REGION", "ap-guangzhou")
        self.secret_id = os.getenv("TENCENT_COS_SECRET_ID", "")
        self.secret_key = os.getenv("TENCENT_COS_SECRET_KEY", "")
        self.cdn_base_url = os.getenv("TENCENT_COS_CDN_BASE_URL", "").rstrip("/")
        self.prefix = os.getenv("TENCENT_COS_AVATAR_PREFIX", "users/avatars").strip("/")
        self.design_preview_prefix = os.getenv("TENCENT_COS_DESIGN_PREVIEW_PREFIX", "designs/previews").strip("/")

    @property
    def enabled(self) -> bool:
        return bool(self.bucket and self.region and self.secret_id and self.secret_key)

    def upload(
        self,
        user_id: str,
        content: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> AvatarUploadResult:
        if not self.enabled:
            raise RuntimeError("腾讯云 COS 未配置完整，无法上传头像")
        if not content:
            raise ValueError("头像文件不能为空")
        if len(content) > MAX_AVATAR_BYTES:
            raise ValueError("头像文件不能超过 3MB")

        normalized_content_type = (content_type or "").split(";")[0].strip().lower()
        if normalized_content_type not in IMAGE_EXTENSIONS:
            normalized_content_type = self._guess_content_type(filename)
        if normalized_content_type not in IMAGE_EXTENSIONS:
            raise ValueError("仅支持 jpg、png、webp、gif 格式头像")

        key = self._build_key(user_id, content, IMAGE_EXTENSIONS[normalized_content_type])
        client = self._client()
        client.put_object(
            Bucket=self.bucket,
            Body=content,
            Key=key,
            ContentType=normalized_content_type,
        )
        return AvatarUploadResult(key=key, avatar_url=self.public_url(key))

    def upload_design_preview(
        self,
        user_id: str,
        content: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> DesignPreviewUploadResult:
        if not self.enabled:
            raise RuntimeError("腾讯云 COS 未配置完整，无法上传方案预览图")
        if not content:
            raise ValueError("方案预览图不能为空")
        if len(content) > MAX_DESIGN_PREVIEW_BYTES:
            raise ValueError("方案预览图不能超过 5MB")

        normalized_content_type = (content_type or "").split(";")[0].strip().lower()
        if normalized_content_type not in IMAGE_EXTENSIONS:
            normalized_content_type = self._guess_content_type(filename)
        if normalized_content_type not in IMAGE_EXTENSIONS:
            raise ValueError("仅支持 jpg、png、webp、gif 格式方案预览图")

        key = self._build_key_for_prefix(
            self.design_preview_prefix,
            user_id,
            content,
            IMAGE_EXTENSIONS[normalized_content_type],
        )
        client = self._client()
        client.put_object(
            Bucket=self.bucket,
            Body=content,
            Key=key,
            ContentType=normalized_content_type,
        )
        return DesignPreviewUploadResult(key=key, preview_url=self.public_url(key))

    def upload_media(
        self,
        prefix: str,
        user_id: str,
        content: bytes,
        content_type: str | None = None,
        filename: str | None = None,
        max_bytes: int = MAX_ADMIN_MEDIA_BYTES,
        label: str = "图片",
    ) -> MediaUploadResult:
        if not self.enabled:
            raise RuntimeError("腾讯云 COS 未配置完整，无法上传图片")
        if not content:
            raise ValueError(f"{label}不能为空")
        if len(content) > max_bytes:
            max_mb = max(1, max_bytes // 1024 // 1024)
            raise ValueError(f"{label}不能超过 {max_mb}MB")

        normalized_content_type = (content_type or "").split(";")[0].strip().lower()
        if normalized_content_type not in IMAGE_EXTENSIONS:
            normalized_content_type = self._guess_content_type(filename)
        if normalized_content_type not in IMAGE_EXTENSIONS:
            raise ValueError(f"仅支持 jpg、png、webp、gif 格式{label}")

        key = self._build_key_for_prefix(
            prefix,
            user_id,
            content,
            IMAGE_EXTENSIONS[normalized_content_type],
        )
        client = self._client()
        client.put_object(
            Bucket=self.bucket,
            Body=content,
            Key=key,
            ContentType=normalized_content_type,
        )
        return MediaUploadResult(key=key, url=self.public_url(key))

    def upload_url(self, user_id: str, avatar_url: str) -> AvatarUploadResult:
        parsed = urlparse((avatar_url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("头像地址无效，请重新选择头像")
        try:
            with httpx.stream("GET", avatar_url, follow_redirects=True, timeout=10) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > MAX_AVATAR_BYTES:
                            raise ValueError("头像文件不能超过 3MB")
                    except ValueError as exc:
                        if str(exc) == "头像文件不能超过 3MB":
                            raise
                chunks = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_AVATAR_BYTES:
                        raise ValueError("头像文件不能超过 3MB")
                    chunks.append(chunk)
        except httpx.HTTPError as exc:
            raise ValueError("头像下载失败，请重新选择头像") from exc
        return self.upload(
            user_id=user_id,
            content=b"".join(chunks),
            content_type=content_type,
            filename=PurePosixPath(parsed.path).name,
        )

    def is_managed_url(self, avatar_url: str | None) -> bool:
        parsed = urlparse((avatar_url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        managed_hosts = {
            f"{self.bucket}.cos.{self.region}.myqcloud.com",
        }
        if self.cdn_base_url:
            cdn_host = urlparse(self.cdn_base_url).netloc
            if cdn_host:
                managed_hosts.add(cdn_host)
        extra_hosts = {
            item.strip()
            for item in os.getenv("TENCENT_COS_AVATAR_PUBLIC_HOSTS", "").split(",")
            if item.strip()
        }
        managed_hosts.update(extra_hosts)
        return parsed.netloc in managed_hosts and f"/{self.prefix}/" in f"/{parsed.path.lstrip('/')}"

    def public_url(self, key: str) -> str:
        quoted_key = quote(key, safe="/")
        if self.cdn_base_url:
            return f"{self.cdn_base_url}/{quoted_key}"
        return f"https://{self.bucket}.cos.{self.region}.myqcloud.com/{quoted_key}"

    def _build_key(self, user_id: str, content: bytes, extension: str) -> str:
        return self._build_key_for_prefix(self.prefix, user_id, content, extension)

    @staticmethod
    def _build_key_for_prefix(prefix: str, user_id: str, content: bytes, extension: str) -> str:
        safe_user = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in user_id)[:80] or "anonymous"
        digest = hashlib.sha256(content).hexdigest()[:18]
        unique = secrets.token_hex(6)
        path = PurePosixPath(prefix.strip("/") or "uploads") / safe_user / f"{digest}-{unique}{extension}"
        return str(path)

    def _client(self):
        from qcloud_cos import CosConfig, CosS3Client

        return CosS3Client(
            CosConfig(
                Region=self.region,
                SecretId=self.secret_id,
                SecretKey=self.secret_key,
                Token=None,
                Scheme="https",
            )
        )

    @staticmethod
    def _guess_content_type(filename: str | None) -> str:
        suffix = (PurePosixPath(filename or "").suffix or "").lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".png":
            return "image/png"
        if suffix == ".webp":
            return "image/webp"
        if suffix == ".gif":
            return "image/gif"
        return ""
