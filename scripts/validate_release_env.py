from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse


FALSE_VALUES = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}
PLACEHOLDER_MARKERS = ("change-me", "replace-me", "example", "填写", "<", "${")
RELEASE_PATTERN = re.compile(r"^v\d{8}-\d{3}(?:-[a-z0-9.-]+)?$")


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"line {number} is not KEY=VALUE")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate(values: dict[str, str], environment: str, allow_placeholders: bool = False) -> list[str]:
    errors: list[str] = []

    def require(name: str) -> str:
        value = values.get(name, "").strip()
        if not value:
            errors.append(f"{name}_MISSING")
        elif not allow_placeholders and any(marker in value.lower() for marker in PLACEHOLDER_MARKERS):
            errors.append(f"{name}_PLACEHOLDER")
        return value

    def require_any(label: str, names: tuple[str, ...]) -> str:
        for name in names:
            value = values.get(name, "").strip()
            if value:
                if not allow_placeholders and any(marker in value.lower() for marker in PLACEHOLDER_MARKERS):
                    errors.append(f"{label}_PLACEHOLDER")
                return value
        errors.append(f"{label}_MISSING")
        return ""

    expected_app_env = "production" if environment == "prod" else environment
    if values.get("APP_ENV", "").lower() != expected_app_env:
        errors.append("APP_ENV_MISMATCH")
    if values.get("DATABASE_BACKEND", "").lower() != "mysql":
        errors.append("DATABASE_BACKEND_MUST_BE_MYSQL")
    for name in ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"):
        require(name)

    database = values.get("MYSQL_DATABASE", "").lower()
    if environment == "test" and ("test" not in database or database == "yujian"):
        errors.append("TEST_DATABASE_NAME_UNSAFE")
    if environment == "prod" and (not database or any(marker in database for marker in ("test", "local", "dev"))):
        errors.append("PROD_DATABASE_NAME_UNSAFE")

    release_version = require("RELEASE_VERSION")
    if release_version and not allow_placeholders and not RELEASE_PATTERN.fullmatch(release_version):
        errors.append("RELEASE_VERSION_INVALID")
    require("LOG_HASH_SALT")
    checkout_value = require("COMMERCE_CHECKOUT_ENABLED").lower()
    if checkout_value and checkout_value not in FALSE_VALUES | TRUE_VALUES:
        errors.append("COMMERCE_CHECKOUT_ENABLED_INVALID_BOOLEAN")

    payment_value = require("WECHAT_PAYMENT_ENABLED").lower()
    if payment_value and payment_value not in FALSE_VALUES | TRUE_VALUES:
        errors.append("WECHAT_PAYMENT_ENABLED_INVALID_BOOLEAN")
    if payment_value in TRUE_VALUES:
        require_any("WECHAT_PAY_APP_ID", ("WECHAT_PAY_APP_ID", "WECHAT_APP_ID", "WX_APPID"))
        require_any("WECHAT_PAY_MCH_ID", ("WECHAT_PAY_MCH_ID", "WX_MCH_ID"))
        require_any("WECHAT_PAY_SERIAL_NO", ("WECHAT_PAY_SERIAL_NO", "WX_PAY_SERIAL_NO"))
        require_any(
            "WECHAT_PAY_PRIVATE_KEY",
            ("WECHAT_PAY_PRIVATE_KEY_PATH", "WECHAT_PAY_PRIVATE_KEY", "WX_PAY_PRIVATE_KEY_PATH", "WX_PAY_PRIVATE_KEY"),
        )
        api_v3_key = require_any("WECHAT_PAY_API_V3_KEY", ("WECHAT_PAY_API_V3_KEY", "WX_PAY_API_V3_KEY"))
        notify_url = require_any("WECHAT_PAY_NOTIFY_URL", ("WECHAT_PAY_NOTIFY_URL", "WX_PAY_NOTIFY_URL"))
        public_key = require_any(
            "WECHAT_PAY_VERIFICATION_KEY",
            (
                "WECHAT_PAY_PUBLIC_KEY_PATH", "WECHAT_PAY_PUBLIC_KEY",
                "WECHAT_PAY_PLATFORM_CERT_PATH", "WECHAT_PAY_PLATFORM_CERT",
            ),
        )
        if api_v3_key and not allow_placeholders and len(api_v3_key) != 32:
            errors.append("WECHAT_PAY_API_V3_KEY_INVALID")
        if notify_url and environment == "prod" and urlparse(notify_url).scheme.lower() != "https":
            errors.append("WECHAT_PAY_NOTIFY_URL_MUST_USE_HTTPS")
        if public_key and (values.get("WECHAT_PAY_PUBLIC_KEY_PATH") or values.get("WECHAT_PAY_PUBLIC_KEY")):
            require("WECHAT_PAY_PUBLIC_KEY_ID")

    community_enabled = values.get("COMMUNITY_UGC_ENABLED", "false").strip().lower()
    community_writes_enabled = values.get("COMMUNITY_UGC_WRITES_ENABLED", "false").strip().lower()
    moderation_required = values.get("COMMUNITY_MODERATION_REQUIRED", "true").strip().lower()
    for name, value in (
        ("COMMUNITY_UGC_ENABLED", community_enabled),
        ("COMMUNITY_UGC_WRITES_ENABLED", community_writes_enabled),
        ("COMMUNITY_MODERATION_REQUIRED", moderation_required),
    ):
        if value not in FALSE_VALUES | TRUE_VALUES:
            errors.append(f"{name}_INVALID_BOOLEAN")
    if community_writes_enabled in TRUE_VALUES and community_enabled not in TRUE_VALUES:
        errors.append("COMMUNITY_UGC_WRITES_REQUIRES_COMMUNITY_UGC_ENABLED")
    if environment == "prod":
        if community_writes_enabled not in FALSE_VALUES:
            errors.append("COMMUNITY_UGC_WRITES_FORBIDDEN_IN_PRODUCTION")
        if moderation_required not in TRUE_VALUES:
            errors.append("COMMUNITY_MODERATION_REQUIRED_IN_PRODUCTION")

    kuaidi100_subscribe_value = values.get("KUAIDI100_SUBSCRIBE_ENABLED", "false").strip().lower()
    if kuaidi100_subscribe_value not in FALSE_VALUES | TRUE_VALUES:
        errors.append("KUAIDI100_SUBSCRIBE_ENABLED_INVALID_BOOLEAN")
    configured_callback_url = values.get("KUAIDI100_CALLBACK_URL", "").strip()
    configured_callback_salt = values.get("KUAIDI100_CALLBACK_SALT", "").strip()
    parsed_callback = urlparse(configured_callback_url)
    if configured_callback_url and (
        parsed_callback.scheme not in {"http", "https"} or not parsed_callback.netloc
    ):
        errors.append("KUAIDI100_CALLBACK_URL_INVALID")
    if configured_callback_url and environment == "prod" and parsed_callback.scheme != "https":
        errors.append("KUAIDI100_CALLBACK_URL_MUST_USE_HTTPS")
    if configured_callback_salt and not allow_placeholders and len(configured_callback_salt) < 16:
        errors.append("KUAIDI100_CALLBACK_SALT_TOO_SHORT")
    if kuaidi100_subscribe_value in TRUE_VALUES:
        require("KUAIDI100_CUSTOMER")
        require("KUAIDI100_KEY")
        require("KUAIDI100_CALLBACK_URL")
        require("KUAIDI100_CALLBACK_SALT")
    if environment == "prod":
        mock_trade_mode = require("WECHAT_PAY_TEST_MODE").lower()
        if mock_trade_mode and mock_trade_mode not in FALSE_VALUES:
            errors.append("WECHAT_PAY_TEST_MODE_FORBIDDEN")
    if values.get("ALLOW_RUNTIME_SCHEMA_MUTATION", "false").lower() not in FALSE_VALUES:
        errors.append("RUNTIME_SCHEMA_MUTATION_FORBIDDEN")
    if values.get("ALLOW_DEV_WECHAT_LOGIN", "false").lower() not in FALSE_VALUES:
        errors.append("DEV_WECHAT_LOGIN_FORBIDDEN")
    if values.get("TRUST_CLOUDBASE_IDENTITY_HEADERS", "false").lower() not in FALSE_VALUES:
        errors.append("CLOUDBASE_IDENTITY_HEADERS_FORBIDDEN")

    for group in (
        ("WECHAT_APP_ID", "WECHAT_APP_SECRET"),
        (
            "TENCENT_COS_SECRET_ID",
            "TENCENT_COS_SECRET_KEY",
            "TENCENT_COS_BUCKET",
            "TENCENT_COS_REGION",
            "TENCENT_COS_CDN_BASE_URL",
        ),
    ):
        present = [bool(values.get(name, "").strip()) for name in group]
        if any(present) and not all(present):
            errors.append(f"{group[0]}_GROUP_INCOMPLETE")
        if environment == "prod" and not all(present):
            errors.append(f"{group[0]}_GROUP_REQUIRED")
        if environment == "prod":
            for name in group:
                require(name)

    metrics_enabled = values.get("METRICS_ENDPOINT_ENABLED", "false").lower() in TRUE_VALUES
    if metrics_enabled:
        require("METRICS_ACCESS_TOKEN")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a release environment without printing secrets")
    parser.add_argument("--environment", choices=("test", "prod"), required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()
    try:
        errors = validate(parse_env(args.env_file), args.environment, args.allow_placeholders)
    except (OSError, ValueError) as exc:
        print(f"environment validation failed: {type(exc).__name__}")
        return 1
    if errors:
        print("environment validation failed: " + ", ".join(errors))
        return 1
    print(f"{args.environment} environment validation passed; values were not displayed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
