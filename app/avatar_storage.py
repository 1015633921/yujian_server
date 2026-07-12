from __future__ import annotations

import hashlib
import http.client
import ipaddress
import logging
import os
import secrets
import socket
import ssl
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

from .feature_flags import remote_avatar_fetch_enabled
from .observability import current_request_id, log_event, metrics


LOGGER = logging.getLogger("yujian.external")


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


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, pinned_ip: str, timeout: float = 6) -> None:
        super().__init__(host, port=443, timeout=timeout, context=ssl.create_default_context())
        self.pinned_ip = pinned_ip

    def connect(self) -> None:
        raw_socket = socket.create_connection((self.pinned_ip, 443), timeout=self.timeout)
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


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
        self._put_object(content, key, normalized_content_type)
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
        self._put_object(content, key, normalized_content_type)
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
        self._put_object(content, key, normalized_content_type)
        return MediaUploadResult(key=key, url=self.public_url(key))

    def upload_url(self, user_id: str, avatar_url: str) -> AvatarUploadResult:
        if not remote_avatar_fetch_enabled():
            raise ValueError("远程头像抓取已关闭，请重新选择并上传头像")
        parsed, addresses = self.validate_remote_avatar_url(avatar_url)
        content, content_type = self.download_pinned_avatar(parsed, addresses)
        detected_content_type = self.detect_image_content_type(content)
        declared_content_type = content_type.split(";", 1)[0].strip().lower()
        if not detected_content_type or declared_content_type not in IMAGE_EXTENSIONS:
            raise ValueError("远程头像不是受支持的图片")
        if IMAGE_EXTENSIONS[declared_content_type] != IMAGE_EXTENSIONS[detected_content_type]:
            raise ValueError("远程头像格式与响应类型不一致")
        return self.upload(
            user_id=user_id,
            content=content,
            content_type=detected_content_type,
            filename=PurePosixPath(parsed.path).name,
        )

    @staticmethod
    def pinned_https_connection(host: str, pinned_ip: str) -> PinnedHTTPSConnection:
        return PinnedHTTPSConnection(host, pinned_ip)

    @classmethod
    def download_pinned_avatar(cls, parsed, addresses: frozenset[str]) -> tuple[bytes, str]:
        target = parsed.path or "/"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        last_error: Exception | None = None
        for pinned_ip in sorted(addresses):
            connection = cls.pinned_https_connection(parsed.hostname or "", pinned_ip)
            try:
                connection.request(
                    "GET",
                    target,
                    headers={
                        "Accept": "image/*",
                        "User-Agent": "YujianAvatarFetcher/1.0",
                        "X-Request-ID": current_request_id(),
                    },
                )
                response = connection.getresponse()
                if 300 <= response.status < 400:
                    raise ValueError("头像地址不能跳转，请重新选择头像")
                if response.status < 200 or response.status >= 300:
                    raise ValueError("头像下载失败，请重新选择头像")
                content_type = response.getheader("Content-Type", "")
                content_length = response.getheader("Content-Length")
                if content_length:
                    try:
                        if int(content_length) > MAX_AVATAR_BYTES:
                            raise ValueError("头像文件不能超过 3MB")
                    except (TypeError, ValueError) as exc:
                        if isinstance(exc, ValueError) and str(exc) == "头像文件不能超过 3MB":
                            raise
                chunks = []
                total = 0
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_AVATAR_BYTES:
                        raise ValueError("头像文件不能超过 3MB")
                    chunks.append(chunk)
                return b"".join(chunks), content_type
            except ValueError:
                raise
            except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
                last_error = exc
            finally:
                connection.close()
        metrics.increment("external_service_failed_total", service="remote_avatar", error_type=type(last_error).__name__ if last_error else "unknown")
        log_event(
            LOGGER,
            "external.remote_avatar.failed",
            level=logging.WARNING,
            service="remote_avatar",
            error_type=type(last_error).__name__ if last_error else "unknown",
            result="failed",
        )
        raise ValueError("头像下载失败，请重新选择头像") from last_error

    @staticmethod
    def remote_avatar_allowed_hosts() -> set[str]:
        return {
            host.strip().lower().rstrip(".")
            for host in os.getenv("REMOTE_AVATAR_ALLOWED_HOSTS", "thirdwx.qlogo.cn").split(",")
            if host.strip()
        }

    @classmethod
    def validate_remote_avatar_url(cls, avatar_url: str):
        parsed = urlparse((avatar_url or "").strip())
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not host:
            raise ValueError("远程头像仅支持 HTTPS 地址")
        if parsed.username or parsed.password or parsed.port not in (None, 443):
            raise ValueError("远程头像地址包含不允许的认证信息或端口")
        if host not in cls.remote_avatar_allowed_hosts():
            raise ValueError("远程头像域名不在允许列表中")
        addresses = cls.resolve_host_addresses(host)
        cls.reject_unsafe_addresses(addresses)
        return parsed, addresses

    @staticmethod
    def resolve_host_addresses(host: str) -> frozenset[str]:
        try:
            records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError("远程头像域名无法解析") from exc
        addresses = frozenset(record[4][0].split("%", 1)[0] for record in records)
        if not addresses:
            raise ValueError("远程头像域名没有可用地址")
        return addresses

    @staticmethod
    def reject_unsafe_addresses(addresses: frozenset[str]) -> None:
        for value in addresses:
            try:
                address = ipaddress.ip_address(value)
            except ValueError as exc:
                raise ValueError("远程头像域名解析结果无效") from exc
            if (
                address.is_loopback
                or address.is_private
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
                or address.is_unspecified
            ):
                raise ValueError("远程头像地址指向不允许的网络")

    @staticmethod
    def detect_image_content_type(content: bytes) -> str:
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return "image/webp"
        return ""

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
                Timeout=max(3, min(int(os.getenv("COS_REQUEST_TIMEOUT_SECONDS", "15")), 60)),
            )
        )

    def _put_object(self, content: bytes, key: str, content_type: str) -> None:
        try:
            self._client().put_object(
                Bucket=self.bucket,
                Body=content,
                Key=key,
                ContentType=content_type,
            )
        except Exception as exc:
            metrics.increment("external_service_failed_total", service="tencent_cos", error_type=type(exc).__name__)
            log_event(
                LOGGER,
                "external.tencent_cos.failed",
                level=logging.WARNING,
                service="tencent_cos",
                error_type=type(exc).__name__,
                result="failed",
            )
            raise RuntimeError("对象存储服务暂时不可用") from exc

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
