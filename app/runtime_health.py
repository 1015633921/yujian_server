from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .database import DEFAULT_SQLITE_PATH, MySQLConnection, use_mysql
from .feature_flags import (
    checkout_enabled,
    community_ugc_enabled,
    community_ugc_writes_enabled,
    kuaidi100_subscribe_enabled,
    payment_enabled,
    report_versioning_v2_enabled,
)
from .observability import metrics
from .migrations.versions.v20260717_09_community_ugc_core import (
    VERSION as COMMUNITY_UGC_MIGRATION_VERSION,
)


COMMUNITY_WRITE_SAFE_APP_ENVS = {"development", "dev", "local", "test", "testing"}


def required_config_errors() -> list[str]:
    errors: list[str] = []
    boolean_values = {"0", "1", "false", "true", "no", "yes", "off", "on"}
    backend = os.getenv("DATABASE_BACKEND", "sqlite").lower()
    if backend not in {"sqlite", "mysql"}:
        errors.append("DATABASE_BACKEND_INVALID")
    if backend == "mysql":
        for name in ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"):
            if not os.getenv(name):
                errors.append(f"{name}_MISSING")
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env in {"test", "production"}:
        if not os.getenv("LOG_HASH_SALT"):
            errors.append("LOG_HASH_SALT_MISSING")
        release_version = os.getenv("RELEASE_VERSION", "")
        if not release_version:
            errors.append("RELEASE_VERSION_MISSING")
        elif not re.fullmatch(r"v\d{8}-\d{3}(?:-[a-z0-9.-]+)?", release_version):
            errors.append("RELEASE_VERSION_INVALID")
        if os.getenv("ALLOW_RUNTIME_SCHEMA_MUTATION", "false").lower() in {"1", "true", "yes", "on"}:
            errors.append("RUNTIME_SCHEMA_MUTATION_FORBIDDEN")
    if app_env == "production":
        if os.getenv("WECHAT_PAY_TEST_MODE", "false").lower() in {"1", "true", "yes", "on"}:
            errors.append("WECHAT_PAY_TEST_MODE_FORBIDDEN")
        for name in (
            "WECHAT_APP_ID",
            "WECHAT_APP_SECRET",
            "TENCENT_COS_SECRET_ID",
            "TENCENT_COS_SECRET_KEY",
            "TENCENT_COS_BUCKET",
            "TENCENT_COS_REGION",
            "TENCENT_COS_CDN_BASE_URL",
        ):
            if not os.getenv(name):
                errors.append(f"{name}_MISSING")
    if str(os.getenv("METRICS_ENDPOINT_ENABLED", "false")).lower() in {"1", "true", "yes", "on"}:
        if not os.getenv("METRICS_ACCESS_TOKEN"):
            errors.append("METRICS_ACCESS_TOKEN_MISSING")
    subscribe_value = str(os.getenv("KUAIDI100_SUBSCRIBE_ENABLED", "false")).strip().lower()
    if subscribe_value not in {"0", "1", "false", "true", "no", "yes", "off", "on"}:
        errors.append("KUAIDI100_SUBSCRIBE_ENABLED_INVALID_BOOLEAN")
    callback_url = str(os.getenv("KUAIDI100_CALLBACK_URL") or "").strip()
    parsed_callback = urlparse(callback_url)
    if callback_url and (parsed_callback.scheme not in {"http", "https"} or not parsed_callback.netloc):
        errors.append("KUAIDI100_CALLBACK_URL_INVALID")
    if app_env == "production" and callback_url and parsed_callback.scheme != "https":
        errors.append("KUAIDI100_CALLBACK_URL_MUST_USE_HTTPS")
    if 0 < len(str(os.getenv("KUAIDI100_CALLBACK_SALT") or "")) < 16:
        errors.append("KUAIDI100_CALLBACK_SALT_TOO_SHORT")
    if kuaidi100_subscribe_enabled():
        for name in (
            "KUAIDI100_CUSTOMER",
            "KUAIDI100_KEY",
            "KUAIDI100_CALLBACK_URL",
            "KUAIDI100_CALLBACK_SALT",
        ):
            if not os.getenv(name):
                errors.append(f"{name}_MISSING")
    if payment_enabled():
        alternatives = {
            "WECHAT_PAY_APP_ID": ("WECHAT_PAY_APP_ID", "WECHAT_APP_ID", "WX_APPID"),
            "WECHAT_PAY_MCH_ID": ("WECHAT_PAY_MCH_ID", "WX_MCH_ID"),
            "WECHAT_PAY_SERIAL_NO": ("WECHAT_PAY_SERIAL_NO", "WX_PAY_SERIAL_NO"),
            "WECHAT_PAY_PRIVATE_KEY": (
                "WECHAT_PAY_PRIVATE_KEY_PATH", "WECHAT_PAY_PRIVATE_KEY",
                "WX_PAY_PRIVATE_KEY_PATH", "WX_PAY_PRIVATE_KEY",
            ),
            "WECHAT_PAY_API_V3_KEY": ("WECHAT_PAY_API_V3_KEY", "WX_PAY_API_V3_KEY"),
            "WECHAT_PAY_NOTIFY_URL": ("WECHAT_PAY_NOTIFY_URL", "WX_PAY_NOTIFY_URL"),
        }
        for label, names in alternatives.items():
            if not any(os.getenv(name) for name in names):
                errors.append(f"{label}_MISSING")
    if community_ugc_writes_enabled() and not community_ugc_enabled():
        errors.append("COMMUNITY_UGC_WRITES_REQUIRES_COMMUNITY_UGC_ENABLED")
    for name, default in (
        ("COMMUNITY_UGC_ENABLED", "false"),
        ("COMMUNITY_UGC_WRITES_ENABLED", "false"),
        ("COMMUNITY_MODERATION_REQUIRED", "true"),
    ):
        if str(os.getenv(name, default)).strip().lower() not in boolean_values:
            errors.append(f"{name}_INVALID_BOOLEAN")
    if app_env not in COMMUNITY_WRITE_SAFE_APP_ENVS:
        if community_ugc_writes_enabled():
            errors.append("COMMUNITY_UGC_WRITES_FORBIDDEN_IN_PRODUCTION")
        moderation = str(os.getenv("COMMUNITY_MODERATION_REQUIRED", "true")).strip().lower()
        if moderation not in {"1", "true", "yes", "on"}:
            errors.append("COMMUNITY_MODERATION_REQUIRED_IN_PRODUCTION")
    return errors


def assert_startup_configuration() -> None:
    app_env = os.getenv("APP_ENV", "development").lower()
    errors = required_config_errors()
    if app_env not in {"test", "production"}:
        errors = [error for error in errors if error.startswith("COMMUNITY_")]
    if errors:
        raise RuntimeError("startup configuration rejected: " + ", ".join(sorted(errors)))


def _required_tables() -> tuple[str, ...]:
    required = ["schema_migrations"]
    if checkout_enabled():
        required.extend(("order_requests", "inventory_reservations"))
    if payment_enabled():
        required.append("payment_webhook_events")
    if report_versioning_v2_enabled():
        required.extend(("report_snapshots", "report_generation_requests"))
    if community_ugc_enabled():
        required.extend(
            (
                "community_ugc_posts",
                "community_ugc_likes",
                "community_ugc_saves",
                "community_ugc_comments",
                "community_ugc_follows",
                "community_ugc_reports",
            )
        )
    return tuple(required)


def _probe_connection(connection, backend: str, database: str = "") -> dict[str, Any]:
    connection.execute("SELECT 1").fetchone()
    missing_tables: list[str] = []
    for table in _required_tables():
        if backend == "mysql":
            exists = connection.execute(
                "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? LIMIT 1",
                (database, table),
            ).fetchone()
        else:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
                (table,),
            ).fetchone()
        if not exists:
            missing_tables.append(table)
    missing_migrations: list[str] = []
    if community_ugc_enabled() and "schema_migrations" not in missing_tables:
        migration = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ? LIMIT 1",
            (COMMUNITY_UGC_MIGRATION_VERSION,),
        ).fetchone()
        if not migration:
            missing_migrations.append(COMMUNITY_UGC_MIGRATION_VERSION)
    return {
        "ok": not missing_tables and not missing_migrations,
        "missing_tables": missing_tables,
        "missing_migrations": missing_migrations,
    }


def database_readiness(sqlite_path: Path | None = None) -> dict[str, Any]:
    try:
        if use_mysql() and sqlite_path is None:
            connection = MySQLConnection()
            try:
                return _probe_connection(connection, "mysql", os.getenv("MYSQL_DATABASE", ""))
            finally:
                connection.raw.close()
        path = Path(sqlite_path or DEFAULT_SQLITE_PATH)
        if not path.exists():
            return {
                "ok": False,
                "reason": "database_missing",
                "missing_tables": [],
                "missing_migrations": [],
            }
        uri = f"file:{path.resolve()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        try:
            return _probe_connection(connection, "sqlite")
        finally:
            connection.close()
    except Exception as exc:
        metrics.increment("db_error_total", operation="readiness")
        return {
            "ok": False,
            "reason": "database_unavailable",
            "error_type": type(exc).__name__,
            "missing_tables": [],
            "missing_migrations": [],
        }


def readiness(sqlite_path: Path | None = None) -> dict[str, Any]:
    config_errors = required_config_errors()
    database = database_readiness(sqlite_path)
    ready = not config_errors and bool(database.get("ok"))
    return {
        "ready": ready,
        "checks": {
            "database": "ok" if database.get("ok") else "failed",
            "configuration": "ok" if not config_errors else "failed",
        },
        "missing_config": config_errors,
        "missing_tables": database.get("missing_tables") or [],
        "missing_migrations": database.get("missing_migrations") or [],
    }
