from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import sys
import threading
import time
import traceback
from pathlib import Path
from collections import defaultdict
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any


SERVICE_NAME = os.getenv("SERVICE_NAME", "yujian-api")
REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
SENSITIVE_KEYS = {
    "authorization", "token", "access_token", "refresh_token", "secret", "secret_id",
    "secret_key", "password", "openid", "unionid", "phone", "phone_number",
    "address", "receiver", "birth_place", "birthday", "birth_time", "payload", "body",
}

_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_user_id_hash: ContextVar[str] = ContextVar("user_id_hash", default="-")


def new_request_id() -> str:
    return f"req_{secrets.token_hex(16)}"


def normalize_request_id(value: str | None) -> str:
    candidate = str(value or "").strip()
    return candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else new_request_id()


def current_request_id() -> str:
    return _request_id.get()


def bind_request_id(value: str) -> Token:
    return _request_id.set(normalize_request_id(value))


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


def hash_user_id(user_id: str | None) -> str:
    value = str(user_id or "").strip()
    if not value:
        return "-"
    salt = os.getenv("LOG_HASH_SALT", "yujian-log-hash-v1")
    return hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()[:16]


def bind_user_id(user_id: str | None) -> Token:
    return _user_id_hash.set(hash_user_id(user_id))


def reset_user_id(token: Token) -> None:
    _user_id_hash.reset(token)


def redact_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text)
    text = re.sub(r"(?i)(access_token|secret|password)=([^&\s]+)", r"\1=[REDACTED]", text)
    text = re.sub(r"(?i)(secret|password|token)\s+[^\s\n]+", r"\1 [REDACTED]", text)
    text = re.sub(r"(?<!\d)1\d{10}(?!\d)", "[REDACTED_PHONE]", text)
    text = re.sub(r"\bo[A-Za-z0-9_-]{20,}\b", "[REDACTED_OPENID]", text)
    return text[:2000]


def sanitize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in fields.items():
        normalized_key = str(key).lower()
        if normalized_key == "user_id":
            sanitized["user_id_hash"] = hash_user_id(str(value))
        elif normalized_key in SENSITIVE_KEYS or any(part in normalized_key for part in ("token", "secret", "password")):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = redact_text(value) if isinstance(value, str) else value
        elif isinstance(value, (list, tuple, set)):
            sanitized[key] = [redact_text(item) for item in list(value)[:20]]
        else:
            sanitized[key] = redact_text(type(value).__name__)
    return sanitized


def safe_exception_frames(exc: BaseException) -> list[str]:
    frames = traceback.extract_tb(exc.__traceback__)[-12:]
    return [f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}" for frame in frames]


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "service": SERVICE_NAME,
            "request_id": current_request_id(),
            "user_id_hash": _user_id_hash.get(),
            "logger": record.name,
            "event": getattr(record, "event", "log"),
            "message": redact_text(record.getMessage()),
        }
        payload.update(sanitize_fields(getattr(record, "structured_fields", {}) or {}))
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    root = logging.getLogger()
    if any(getattr(handler, "_yujian_json_handler", False) for handler in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler._yujian_json_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)
    configured_level = str(os.getenv("LOG_LEVEL", "INFO")).upper()
    root.setLevel(getattr(logging, configured_level, logging.INFO))


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    message: str = "",
    exc_info: bool = False,
    **fields: Any,
) -> None:
    logger.log(
        level,
        message or event,
        extra={"event": event, "structured_fields": sanitize_fields(fields)},
        exc_info=exc_info,
    )


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)
        self._durations: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, float]] = {}

    @staticmethod
    def _key(name: str, labels: dict[str, Any]) -> tuple[str, tuple[tuple[str, str], ...]]:
        normalized = tuple(sorted((str(key), str(value)) for key, value in labels.items()))
        return name, normalized

    def increment(self, name: str, amount: int = 1, **labels: Any) -> None:
        with self._lock:
            self._counters[self._key(name, labels)] += int(amount)

    def observe(self, name: str, value: float, **labels: Any) -> None:
        key = self._key(name, labels)
        with self._lock:
            item = self._durations.setdefault(key, {"count": 0, "sum": 0.0, "max": 0.0})
            item["count"] += 1
            item["sum"] += float(value)
            item["max"] = max(item["max"], float(value))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = [
                {"name": name, "labels": dict(labels), "value": value}
                for (name, labels), value in sorted(self._counters.items())
            ]
            durations = [
                {"name": name, "labels": dict(labels), **values}
                for (name, labels), values in sorted(self._durations.items())
            ]
            request_total = sum(value for (name, _labels), value in self._counters.items() if name == "api_request_total")
            error_total = sum(value for (name, _labels), value in self._counters.items() if name == "api_error_total")
        error_rate = round(error_total / request_total, 6) if request_total else 0.0
        return {
            "counters": counters,
            "durations": durations,
            "gauges": [{"name": "api_error_rate", "labels": {}, "value": error_rate}],
        }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._durations.clear()


metrics = MetricsRegistry()

CORE_COUNTERS = (
    "login_success_total", "login_failed_total", "report_generate_total",
    "report_generate_failed_total", "poster_generate_total", "poster_failed_total",
    "order_create_total", "order_create_failed_total", "payment_callback_total",
    "payment_callback_failed_total", "logistics_sync_total", "logistics_sync_failed_total",
    "api_request_total", "api_error_total", "db_error_total", "external_service_failed_total",
)
for _counter in CORE_COUNTERS:
    metrics.increment(_counter, 0)


class Timer:
    def __init__(self) -> None:
        self.started = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self.started) * 1000, 3)
