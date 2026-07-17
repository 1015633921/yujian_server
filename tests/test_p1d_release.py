from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest

from app.admin_service import AdminService
from app.database import runtime_schema_mutation_allowed
from app.feature_flags import mock_trade_enabled
from app.migrations.runner import MIGRATIONS, downgrade, upgrade
from app.order_service import OrderService
from app.repository import AssessmentRepository
from app.runtime_health import assert_startup_configuration, required_config_errors
from scripts.release_state import promote, read_record, rollback
from scripts.validate_release_env import parse_env, validate


ROOT = Path(__file__).resolve().parents[1]


def valid_environment(environment: str) -> dict[str, str]:
    app_env = "production" if environment == "prod" else "test"
    database = "yujian" if environment == "prod" else "yujian_test"
    values = {
        "APP_ENV": app_env,
        "RELEASE_VERSION": "v20260712-001",
        "DATABASE_BACKEND": "mysql",
        "MYSQL_HOST": "mysql.internal",
        "MYSQL_PORT": "3306",
        "MYSQL_DATABASE": database,
        "MYSQL_USER": "service-user",
        "MYSQL_PASSWORD": "not-a-real-secret",
        "LOG_HASH_SALT": "not-a-real-log-salt",
        "COMMERCE_CHECKOUT_ENABLED": "false",
        "WECHAT_PAYMENT_ENABLED": "false",
        "KUAIDI100_SUBSCRIBE_ENABLED": "false",
        "WECHAT_PAY_TEST_MODE": "false",
        "ALLOW_RUNTIME_SCHEMA_MUTATION": "false",
        "ALLOW_DEV_WECHAT_LOGIN": "false",
        "TRUST_CLOUDBASE_IDENTITY_HEADERS": "false",
    }
    if environment == "prod":
        values.update(
            {
                "WECHAT_APP_ID": "wx-release-test",
                "WECHAT_APP_SECRET": "not-a-real-wechat-secret",
                "TENCENT_COS_SECRET_ID": "not-a-real-cos-id",
                "TENCENT_COS_SECRET_KEY": "not-a-real-cos-secret",
                "TENCENT_COS_BUCKET": "release-test-bucket",
                "TENCENT_COS_REGION": "ap-guangzhou",
                "TENCENT_COS_CDN_BASE_URL": "https://cdn.invalid",
            }
        )
    return values


def test_environment_validator_fails_closed_and_keeps_databases_isolated():
    assert validate(valid_environment("test"), "test") == []
    assert validate(valid_environment("prod"), "prod") == []
    missing = valid_environment("prod")
    missing.pop("MYSQL_PASSWORD")
    assert "MYSQL_PASSWORD_MISSING" in validate(missing, "prod")
    crossed = valid_environment("prod")
    crossed["MYSQL_DATABASE"] = "yujian_test"
    assert "PROD_DATABASE_NAME_UNSAFE" in validate(crossed, "prod")
    incomplete_payment = valid_environment("prod")
    incomplete_payment["WECHAT_PAYMENT_ENABLED"] = "true"
    assert "WECHAT_PAY_MCH_ID_MISSING" in validate(incomplete_payment, "prod")
    enabled_payment = valid_environment("prod")
    enabled_payment.update(
        {
            "WECHAT_PAYMENT_ENABLED": "true",
            "WECHAT_PAY_MCH_ID": "1900000109",
            "WECHAT_PAY_SERIAL_NO": "ABCDEF1234",
            "WECHAT_PAY_PRIVATE_KEY_PATH": "/run/secrets/apiclient_key.pem",
            "WECHAT_PAY_API_V3_KEY": "0" * 32,
            "WECHAT_PAY_NOTIFY_URL": "https://api.invalid/api/v1/wechat-pay/notify",
            "WECHAT_PAY_PUBLIC_KEY_PATH": "/run/secrets/wechatpay_pub_key.pem",
            "WECHAT_PAY_PUBLIC_KEY_ID": "PUB_KEY_ID_01111111111111111111111111111111",
        }
    )
    assert validate(enabled_payment, "prod") == []
    invalid_payment = valid_environment("prod")
    invalid_payment["WECHAT_PAYMENT_ENABLED"] = "sometimes"
    assert "WECHAT_PAYMENT_ENABLED_INVALID_BOOLEAN" in validate(invalid_payment, "prod")
    checkout_enabled = valid_environment("prod")
    checkout_enabled["COMMERCE_CHECKOUT_ENABLED"] = "true"
    assert validate(checkout_enabled, "prod") == []
    invalid_checkout = valid_environment("prod")
    invalid_checkout["COMMERCE_CHECKOUT_ENABLED"] = "sometimes"
    assert "COMMERCE_CHECKOUT_ENABLED_INVALID_BOOLEAN" in validate(invalid_checkout, "prod")
    mock_trade = valid_environment("prod")
    mock_trade["WECHAT_PAY_TEST_MODE"] = "true"
    assert "WECHAT_PAY_TEST_MODE_FORBIDDEN" in validate(mock_trade, "prod")
    missing_mock_guard = valid_environment("prod")
    missing_mock_guard.pop("WECHAT_PAY_TEST_MODE")
    assert "WECHAT_PAY_TEST_MODE_MISSING" in validate(missing_mock_guard, "prod")
    invalid_subscription = valid_environment("prod")
    invalid_subscription["KUAIDI100_SUBSCRIBE_ENABLED"] = "sometimes"
    assert "KUAIDI100_SUBSCRIBE_ENABLED_INVALID_BOOLEAN" in validate(invalid_subscription, "prod")
    incomplete_subscription = valid_environment("prod")
    incomplete_subscription["KUAIDI100_SUBSCRIBE_ENABLED"] = "true"
    assert "KUAIDI100_CALLBACK_SALT_MISSING" in validate(incomplete_subscription, "prod")
    enabled_subscription = valid_environment("prod")
    enabled_subscription.update(
        {
            "KUAIDI100_SUBSCRIBE_ENABLED": "true",
            "KUAIDI100_CUSTOMER": "test-customer",
            "KUAIDI100_KEY": "test-key",
            "KUAIDI100_CALLBACK_URL": "https://api.invalid/api/v1/logistics/kuaidi100/callback",
            "KUAIDI100_CALLBACK_SALT": "not-a-real-callback-salt-32-bytes",
        }
    )
    assert validate(enabled_subscription, "prod") == []
    insecure_subscription = dict(enabled_subscription)
    insecure_subscription["KUAIDI100_CALLBACK_URL"] = "http://api.invalid/callback"
    assert "KUAIDI100_CALLBACK_URL_MUST_USE_HTTPS" in validate(insecure_subscription, "prod")
    invalid_community = valid_environment("prod")
    invalid_community["COMMUNITY_UGC_ENABLED"] = "sometimes"
    assert "COMMUNITY_UGC_ENABLED_INVALID_BOOLEAN" in validate(invalid_community, "prod")
    writes_without_reads = valid_environment("prod")
    writes_without_reads["COMMUNITY_UGC_WRITES_ENABLED"] = "true"
    assert "COMMUNITY_UGC_WRITES_REQUIRES_COMMUNITY_UGC_ENABLED" in validate(
        writes_without_reads, "prod"
    )
    production_writes = valid_environment("prod")
    production_writes.update(
        {"COMMUNITY_UGC_ENABLED": "true", "COMMUNITY_UGC_WRITES_ENABLED": "true"}
    )
    assert "COMMUNITY_UGC_WRITES_FORBIDDEN_IN_PRODUCTION" in validate(
        production_writes, "prod"
    )
    production_without_moderation = valid_environment("prod")
    production_without_moderation["COMMUNITY_MODERATION_REQUIRED"] = "false"
    assert "COMMUNITY_MODERATION_REQUIRED_IN_PRODUCTION" in validate(
        production_without_moderation, "prod"
    )
    test_writes = valid_environment("test")
    test_writes.update(
        {
            "COMMUNITY_UGC_ENABLED": "true",
            "COMMUNITY_UGC_WRITES_ENABLED": "true",
            "COMMUNITY_MODERATION_REQUIRED": "false",
        }
    )
    assert validate(test_writes, "test") == []


def test_example_environment_files_have_expected_shape():
    for environment in ("test", "prod"):
        path = ROOT / "config" / "examples" / f".env.{environment}.example"
        assert validate(parse_env(path), environment, allow_placeholders=True) == []


def test_strict_startup_rejects_missing_configuration(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_BACKEND", "mysql")
    for name in ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD", "LOG_HASH_SALT", "RELEASE_VERSION"):
        monkeypatch.delenv(name, raising=False)
    errors = required_config_errors()
    assert "MYSQL_PASSWORD_MISSING" in errors
    assert "RELEASE_VERSION_MISSING" in errors
    with pytest.raises(RuntimeError, match="startup configuration rejected"):
        assert_startup_configuration()


def test_production_startup_rejects_community_writes_and_disabled_moderation(monkeypatch):
    for name, value in valid_environment("prod").items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("COMMUNITY_UGC_ENABLED", "true")
    monkeypatch.setenv("COMMUNITY_UGC_WRITES_ENABLED", "true")
    monkeypatch.setenv("COMMUNITY_MODERATION_REQUIRED", "false")

    errors = required_config_errors()

    assert "COMMUNITY_UGC_WRITES_FORBIDDEN_IN_PRODUCTION" in errors
    assert "COMMUNITY_MODERATION_REQUIRED_IN_PRODUCTION" in errors
    with pytest.raises(RuntimeError, match="COMMUNITY_UGC_WRITES_FORBIDDEN_IN_PRODUCTION"):
        assert_startup_configuration()


@pytest.mark.parametrize("app_env", ["prod", "staging", "preview", "unknown"])
def test_non_safe_environment_names_cannot_bypass_community_write_gate(
    monkeypatch, app_env
):
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    monkeypatch.setenv("COMMUNITY_UGC_ENABLED", "true")
    monkeypatch.setenv("COMMUNITY_UGC_WRITES_ENABLED", "true")
    monkeypatch.setenv("COMMUNITY_MODERATION_REQUIRED", "false")

    errors = required_config_errors()

    assert "COMMUNITY_UGC_WRITES_FORBIDDEN_IN_PRODUCTION" in errors
    assert "COMMUNITY_MODERATION_REQUIRED_IN_PRODUCTION" in errors
    with pytest.raises(RuntimeError, match="COMMUNITY_UGC_WRITES_FORBIDDEN_IN_PRODUCTION"):
        assert_startup_configuration()


def test_runtime_configuration_requires_signed_kuaidi100_callback(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    monkeypatch.setenv("KUAIDI100_SUBSCRIBE_ENABLED", "true")
    for name in (
        "KUAIDI100_CUSTOMER",
        "KUAIDI100_KEY",
        "KUAIDI100_CALLBACK_URL",
        "KUAIDI100_CALLBACK_SALT",
    ):
        monkeypatch.delenv(name, raising=False)
    errors = required_config_errors()
    assert "KUAIDI100_KEY_MISSING" in errors
    assert "KUAIDI100_CALLBACK_SALT_MISSING" in errors

    monkeypatch.setenv("KUAIDI100_CUSTOMER", "test-customer")
    monkeypatch.setenv("KUAIDI100_KEY", "test-key")
    monkeypatch.setenv("KUAIDI100_CALLBACK_URL", "http://127.0.0.1:8000/callback")
    monkeypatch.setenv("KUAIDI100_CALLBACK_SALT", "not-a-real-callback-salt-32-bytes")
    assert not [error for error in required_config_errors() if error.startswith("KUAIDI100_")]


def test_production_startup_and_feature_flag_reject_mock_trade_mode(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")

    assert mock_trade_enabled() is False
    assert "WECHAT_PAY_TEST_MODE_FORBIDDEN" in required_config_errors()
    with pytest.raises(RuntimeError, match="WECHAT_PAY_TEST_MODE_FORBIDDEN"):
        assert_startup_configuration()


@pytest.mark.parametrize("app_env", ["prod", "production", "staging"])
def test_mock_trade_mode_is_fail_closed_outside_local_test_environments(monkeypatch, app_env):
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")
    assert mock_trade_enabled() is False


@pytest.mark.parametrize("app_env", ["local", "development", "dev", "test", "testing"])
def test_mock_trade_mode_requires_explicit_non_production_environment(monkeypatch, app_env):
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")
    assert mock_trade_enabled() is True


def test_production_import_rejects_config_before_database_initialization():
    environment = os.environ.copy()
    environment.update({"APP_ENV": "production", "DATABASE_BACKEND": "mysql", "PYTHONPATH": str(ROOT)})
    for name in (
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_DATABASE",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "LOG_HASH_SALT",
        "RELEASE_VERSION",
    ):
        environment.pop(name, None)
    result = subprocess.run(
        [os.sys.executable, "-c", "import app.main"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "startup configuration rejected" in result.stderr
    assert "KeyError" not in result.stderr


def test_runtime_schema_mutation_is_disabled_in_deployed_environments(monkeypatch):
    monkeypatch.delenv("ALLOW_RUNTIME_SCHEMA_MUTATION", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    assert runtime_schema_mutation_allowed() is False
    monkeypatch.setenv("APP_ENV", "test")
    assert runtime_schema_mutation_allowed() is False
    monkeypatch.setenv("APP_ENV", "development")
    assert runtime_schema_mutation_allowed() is True


def test_migration_audit_records_operator_release_and_rollback(tmp_path, monkeypatch):
    database = tmp_path / "migration-audit.db"
    AssessmentRepository(database)
    OrderService(database)
    AdminService(database)
    monkeypatch.setenv("MIGRATION_OPERATOR", "release-test")
    monkeypatch.setenv("RELEASE_VERSION", "v20260712-001")
    expected = [migration.VERSION for migration in MIGRATIONS]
    assert upgrade("sqlite", database) == expected
    assert downgrade("sqlite", database, steps=1) == [expected[-1]]
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT action, operator_name, release_version FROM schema_migration_history ORDER BY recorded_at, rowid"
        ).fetchall()
    assert rows[-1] == ("downgrade", "release-test", "v20260712-001")
    assert all(row[1:] == ("release-test", "v20260712-001") for row in rows)


def test_release_state_can_promote_and_rollback_atomically(tmp_path):
    first = {"release": "v20260712-001", "slot": "blue", "port": 18001, "project": "blue-1", "image": "repo@sha256:" + "1" * 64}
    second = {"release": "v20260712-002", "slot": "green", "port": 18002, "project": "green-2", "image": "repo@sha256:" + "2" * 64}
    promote(tmp_path, first)
    promote(tmp_path, second)
    assert read_record(tmp_path / "current.json") == second
    assert read_record(tmp_path / "previous.json") == first
    rollback(tmp_path)
    assert read_record(tmp_path / "current.json") == first
    assert read_record(tmp_path / "previous.json") == second


def test_release_assets_enforce_immutable_images_and_no_runtime_build():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.release.yaml").read_text(encoding="utf-8")
    assert "@sha256:" in dockerfile
    assert "--require-hashes" in dockerfile
    assert "build:" not in compose
    assert "${APP_IMAGE:?" in compose
    assert "read_only: true" in compose
    assert "ALLOW_RUNTIME_SCHEMA_MUTATION: \"false\"" in compose
    accepted = subprocess.run(
        [os.sys.executable, "scripts/validate_image_ref.py", "registry.example/api@sha256:" + "a" * 64],
        cwd=ROOT,
        check=False,
    )
    rejected = subprocess.run(
        [os.sys.executable, "scripts/validate_image_ref.py", "registry.example/api:latest"],
        cwd=ROOT,
        check=False,
    )
    assert accepted.returncode == 0
    assert rejected.returncode == 1


def test_legacy_deploy_and_backup_are_fail_closed_by_default():
    legacy = (ROOT / "scripts" / "deploy_env.ps1").read_text(encoding="utf-8")
    backup = (ROOT / "scripts" / "backup_mysql.sh").read_text(encoding="utf-8")
    assert "ALLOW_LEGACY_INPLACE_DEPLOY" in legacy
    assert "[string]$Server = \"\"" in legacy
    assert "BACKUP_DATABASE:?" in backup


def test_ci_actions_are_commit_pinned():
    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        content = workflow.read_text(encoding="utf-8")
        for line in content.splitlines():
            if "uses:" in line:
                reference = line.split("uses:", 1)[1].split("#", 1)[0].strip()
                assert reference.rsplit("@", 1)[-1].isalnum()
                assert len(reference.rsplit("@", 1)[-1]) == 40
