from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from .database import DEFAULT_SQLITE_PATH, MySQLConnection, use_mysql
from .feature_flags import checkout_enabled, payment_enabled, report_versioning_v2_enabled
from .observability import metrics


def required_config_errors() -> list[str]:
    errors: list[str] = []
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
    return errors


def assert_startup_configuration() -> None:
    if os.getenv("APP_ENV", "development").lower() not in {"test", "production"}:
        return
    errors = required_config_errors()
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
    return {"ok": not missing_tables, "missing_tables": missing_tables}


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
            return {"ok": False, "reason": "database_missing", "missing_tables": []}
        uri = f"file:{path.resolve()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        try:
            return _probe_connection(connection, "sqlite")
        finally:
            connection.close()
    except Exception as exc:
        metrics.increment("db_error_total", operation="readiness")
        return {"ok": False, "reason": "database_unavailable", "error_type": type(exc).__name__, "missing_tables": []}


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
    }
