from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from app.runtime_health import readiness
from scripts.deploy import (
    DeployError,
    EnvironmentProfile,
    choose_candidate_slot,
    render_upstream,
    replace_location_proxy,
    restore_state,
    write_release_env,
)
from scripts.release_state import read_record
from scripts.miniprogram_assets import build_manifest, prepare, read_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_docker_profiles_share_one_contract_and_isolate_runtime() -> None:
    raw_profiles = []
    for environment in ("test", "prod"):
        path = ROOT / "deploy" / "environments" / f"{environment}.json"
        raw_profiles.append(json.loads(path.read_text(encoding="utf-8")))
    assert set(raw_profiles[0]) == set(raw_profiles[1])

    test = EnvironmentProfile.load("test")
    prod = EnvironmentProfile.load("prod")
    assert test.release_state_dir != prod.release_state_dir
    assert test.release_env_dir != prod.release_env_dir
    assert test.nginx_upstream_file != prod.nginx_upstream_file
    assert test.nginx_upstream_name != prod.nginx_upstream_name
    assert set(test.slot_ports.values()).isdisjoint(prod.slot_ports.values())
    assert "/test-api/" in test.public_health_url
    assert "/test-api/" not in prod.public_health_url
    assert test.image_repository == prod.image_repository
    assert test.backend_network == prod.backend_network


def test_release_compose_is_immutable_read_only_and_loopback_only() -> None:
    compose = (ROOT / "compose.release.yaml").read_text(encoding="utf-8")
    assert "build:" not in compose
    assert "${APP_IMAGE:?" in compose
    assert '127.0.0.1:${APP_PORT:?APP_PORT is required}:8000' in compose
    assert "read_only: true" in compose
    assert 'ALLOW_RUNTIME_SCHEMA_MUTATION: "false"' in compose
    assert "MYSQL_ROOT_PASSWORD" not in compose


def test_release_env_snapshot_excludes_deploy_only_credentials(tmp_path: Path) -> None:
    profile = replace(EnvironmentProfile.load("test"), release_env_dir=tmp_path / "runtime")
    values = {
        "APP_ENV": "test",
        "MYSQL_PASSWORD": "service-password",
        "MYSQL_ROOT_PASSWORD": "root-password",
        "LOG_HASH_SALT": "log-salt",
        "RELEASE_VERSION": "v20260714-001-test",
    }
    path = write_release_env(profile, values, "v20260714-001-test")
    content = path.read_text(encoding="utf-8")
    assert "MYSQL_PASSWORD=service-password" in content
    assert "MYSQL_ROOT_PASSWORD" not in content
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_nginx_location_conversion_is_scoped_and_preserves_prefix_semantics() -> None:
    source = """server {
    location /test-api/ {
        proxy_pass http://127.0.0.1:8001/;
        proxy_set_header Host $host;
    }
    location / {
        proxy_pass http://127.0.0.1:8006;
    }
}
"""
    converted = replace_location_proxy(source, "/test-api/", "yujian_test_active", True)
    assert "proxy_pass http://yujian_test_active/;" in converted
    assert "proxy_pass http://127.0.0.1:8006;" in converted
    converted = replace_location_proxy(converted, "/", "yujian_prod_active", False)
    assert "proxy_pass http://yujian_prod_active;" in converted
    assert "proxy_pass http://yujian_test_active/;" in converted


def test_nginx_upstream_and_slot_selection_fail_closed() -> None:
    assert "server 127.0.0.1:8011;" in render_upstream("yujian_test_active", 8011)
    with pytest.raises(DeployError, match="invalid Nginx upstream"):
        render_upstream("bad-name;", 8011)
    assert choose_candidate_slot({"slot": "legacy"}) == "blue"
    assert choose_candidate_slot({"slot": "blue"}) == "green"
    assert choose_candidate_slot({"slot": "green"}) == "blue"


def test_release_state_restore_recovers_exact_pre_switch_snapshot(tmp_path: Path) -> None:
    profile = replace(EnvironmentProfile.load("test"), release_state_dir=tmp_path / "state")
    current = {"release": "v20260714-001-test", "slot": "blue", "port": 8011}
    previous = {"release": "legacy-test", "slot": "legacy", "port": 8001}
    restore_state(profile, current, previous)
    assert read_record(profile.release_state_dir / "current.json") == current
    assert read_record(profile.release_state_dir / "previous.json") == previous

    restore_state(profile, current, {})
    assert not (profile.release_state_dir / "previous.json").exists()


def test_deploy_dry_run_requires_only_environment_from_operator(tmp_path: Path) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text(
        "\n".join(
            (
                "APP_ENV=test",
                "DATABASE_BACKEND=mysql",
                "MYSQL_HOST=mysql.internal",
                "MYSQL_PORT=3306",
                "MYSQL_DATABASE=yujian_test",
                "MYSQL_USER=service-user",
                "MYSQL_PASSWORD=not-a-real-password",
                "LOG_HASH_SALT=not-a-real-log-salt",
                "COMMERCE_CHECKOUT_ENABLED=false",
                "WECHAT_PAYMENT_ENABLED=false",
                "KUAIDI100_SUBSCRIBE_ENABLED=false",
                "WECHAT_PAY_TEST_MODE=false",
                "ALLOW_RUNTIME_SCHEMA_MUTATION=false",
                "ALLOW_DEV_WECHAT_LOGIN=false",
                "TRUST_CLOUDBASE_IDENTITY_HEADERS=false",
                "",
            )
        ),
        encoding="utf-8",
    )
    env_file.chmod(0o600)
    profile = EnvironmentProfile.load("test")
    environment = os.environ.copy()
    environment["YUJIAN_RUNTIME_ENV_FILE"] = str(env_file)
    environment["APP_IMAGE"] = profile.image_repository + "@sha256:" + "d" * 64
    environment["RELEASE_VERSION"] = "v20260714-001-test"
    result = subprocess.run(
        [sys.executable, "scripts/deploy.py", "test", "--dry-run"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "driver" not in result.stderr
    assert "dry-run passed" in result.stdout
    assert "not-a-real-password" not in result.stdout + result.stderr
    assert "not-a-real-log-salt" not in result.stdout + result.stderr


def test_deployment_workflow_has_one_environment_choice_and_no_kubernetes() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-docker.yml").read_text(encoding="utf-8")
    assert "deploy-docker-blue-green" in workflow
    assert "branches: [master]" in workflow
    assert "github.event_name == 'push' && 'test' || inputs.environment" in workflow
    assert "python3 scripts/deploy.py '${TARGET_ENVIRONMENT}'" in workflow
    assert "compose.release.yaml" in workflow
    assert "kubectl" not in workflow
    assert "k3s" not in workflow.lower()
    assert "--password-stdin" in workflow


def test_miniprogram_environment_switch_writes_only_an_ignored_generated_file() -> None:
    selector = (ROOT / "scripts/select_miniprogram_env.js").read_text(encoding="utf-8")
    entrypoint = (ROOT / "miniprogram/config/env.js").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "env.current.js" in selector
    assert "env.current.js" in entrypoint
    assert "miniprogram/config/env.current.js" in gitignore
    assert "fs.writeFileSync(envFile" not in entrypoint


def test_readiness_exposes_release_for_post_switch_verification(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RELEASE_VERSION", "v20260714-001-test")
    result = readiness(tmp_path / "missing.db")
    assert result["release_version"] == "v20260714-001-test"


def test_asset_manifest_covers_all_literal_miniprogram_cdn_references() -> None:
    manifest = read_manifest(ROOT / "miniprogram/config/asset-manifest.json")
    referenced: set[str] = set()
    pattern = re.compile(r"assetUrl\('([^']+)'\)")
    for path in (ROOT / "miniprogram").rglob("*.js"):
        referenced.update(pattern.findall(path.read_text(encoding="utf-8")))
    assert referenced
    assert referenced <= set(manifest)
    assert all(not entry.object_path.startswith(("http://", "https://")) for entry in manifest.values())


def test_asset_prepare_uses_content_addressed_objects(tmp_path: Path) -> None:
    source = tmp_path / "assets"
    asset = source / "home" / "sample.webp"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"not-a-real-image-but-stable-for-the-manifest")
    payload = build_manifest(source)
    entry = payload["assets"]["home/sample.webp"]
    assert entry["object"].startswith("releases/")
    assert entry["object"].endswith("/home/sample.webp")
    assert len(entry["sha256"]) == 64


def test_asset_prepare_writes_a_miniprogram_runtime_module(tmp_path: Path) -> None:
    source = tmp_path / "assets"
    asset = source / "home" / "sample.webp"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"stable-asset")
    manifest = tmp_path / "asset-manifest.json"

    prepare(source, manifest)

    runtime_manifest = manifest.with_suffix(".js").read_text(encoding="utf-8")
    assert runtime_manifest.startswith("'use strict';")
    assert "module.exports =" in runtime_manifest
    assert '"home/sample.webp"' in runtime_manifest
