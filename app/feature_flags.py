from __future__ import annotations

import os


def enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def public_share_enabled() -> bool:
    return enabled("DIY_PUBLIC_SHARE_ENABLED", False)


def checkout_enabled() -> bool:
    return enabled("COMMERCE_CHECKOUT_ENABLED", False)


def payment_enabled() -> bool:
    return enabled("WECHAT_PAYMENT_ENABLED", False)


def mock_trade_enabled() -> bool:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    return app_env in {"local", "development", "dev", "test", "testing"} and enabled(
        "WECHAT_PAY_TEST_MODE", False
    )


def report_versioning_v2_enabled() -> bool:
    return enabled("REPORT_VERSIONING_V2_ENABLED", False)


def remote_avatar_fetch_enabled() -> bool:
    return enabled("REMOTE_AVATAR_FETCH_ENABLED", False)


def metrics_endpoint_enabled() -> bool:
    return enabled("METRICS_ENDPOINT_ENABLED", False)


def kuaidi100_subscribe_enabled() -> bool:
    return enabled("KUAIDI100_SUBSCRIBE_ENABLED", False)


def web_login_pairing_enabled() -> bool:
    return enabled("WEB_LOGIN_PAIRING_ENABLED", False)
