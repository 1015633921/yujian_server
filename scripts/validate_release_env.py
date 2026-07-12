from __future__ import annotations

import argparse
import re
from pathlib import Path


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
    for name in ("COMMERCE_CHECKOUT_ENABLED", "WECHAT_PAYMENT_ENABLED"):
        value = require(name).lower()
        if value and value not in FALSE_VALUES:
            errors.append(f"{name}_MUST_REMAIN_FALSE")
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
