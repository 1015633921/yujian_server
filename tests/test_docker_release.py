from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from app.runtime_health import readiness
from app.migrations.runner import MIGRATIONS
from app.migrations.runner import pending as pending_schema
from scripts.deploy import (
    DeployError,
    EnvironmentProfile,
    choose_candidate_slot,
    deployment_context_hash,
    is_local_test_image,
    pending_migrations,
    parse_upstream_port,
    prepare_candidate_slot,
    reconcile_active_routing,
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
    assert test.public_health_url == "https://operation-test.yustream.cn/health/ready"
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
    assert "proxy_set_header X-Forwarded-Prefix /test-api;" in converted
    assert "proxy_pass http://127.0.0.1:8006;" in converted
    converted = replace_location_proxy(converted, "/", "yujian_prod_active", False)
    assert "proxy_pass http://yujian_prod_active;" in converted
    assert "proxy_pass http://yujian_test_active/;" in converted


def test_nginx_upstream_and_slot_selection_fail_closed() -> None:
    assert "server 127.0.0.1:8011;" in render_upstream("yujian_test_active", 8011)
    assert (
        parse_upstream_port(
            "upstream yujian_test_active {\n    server 127.0.0.1:8033;\n}\n",
            "yujian_test_active",
        )
        == 8033
    )
    with pytest.raises(DeployError, match="invalid Nginx upstream"):
        render_upstream("bad-name;", 8011)
    with pytest.raises(DeployError, match="exactly one"):
        parse_upstream_port(
            "upstream yujian_test_active {\n"
            "    server 127.0.0.1:8011;\n"
            "    server 127.0.0.1:8012;\n"
            "}\n",
            "yujian_test_active",
        )
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
    assert "python3 scripts/deploy.py test" in workflow
    assert "python3 scripts/deploy.py prod" in workflow
    assert "compose.release.yaml" in workflow
    assert "docker/setup-buildx-action@" in workflow
    assert "BUILD_CACHE_FROM: type=gha,scope=yujian-api-linux-amd64" in workflow
    assert "BUILD_CACHE_TO: type=gha,mode=max,scope=yujian-api-linux-amd64" in workflow
    assert "Hash the minimal backend build context" in workflow
    assert "Package the minimal test build context" in workflow
    assert "build_remote_test_image.sh" in workflow
    assert "configure_operation_test_domain.sh" in workflow
    assert "deploy/nginx" in workflow
    assert "YUJIAN_LOCAL_TEST_IMAGE=1" in workflow
    assert "kubectl" not in workflow
    assert "k3s" not in workflow.lower()
    assert "--password-stdin" in workflow


def test_operation_test_domain_keeps_the_test_upstream_and_separates_api_routes() -> None:
    http_config = (ROOT / "deploy" / "nginx" / "yujian-operation-test-http.conf").read_text(
        encoding="utf-8",
    )
    https_config = (ROOT / "deploy" / "nginx" / "yujian-operation-test.conf").read_text(
        encoding="utf-8",
    )
    script = (ROOT / "scripts" / "configure_operation_test_domain.sh").read_text(
        encoding="utf-8",
    )

    assert "server_name operation-test.yustream.cn;" in http_config
    assert "location ^~ /.well-known/acme-challenge/" in http_config
    assert "proxy_pass http://yujian_test_active/admin-v2/;" in https_config
    assert "location ^~ /api/" in https_config
    assert "proxy_pass http://yujian_test_active;" in https_config
    assert "ssl_certificate /etc/letsencrypt/live/operation-test.yustream.cn/fullchain.pem;" in https_config
    assert "certbot certonly --webroot" in script
    assert "nginx -t" in script


def test_dockerfile_keeps_dynamic_labels_after_dependency_layer() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.index("RUN python -m pip install") < dockerfile.index(
        "org.opencontainers.image.source-hash"
    )
    build_script = (ROOT / "scripts" / "release" / "build_image.sh").read_text(
        encoding="utf-8"
    )
    assert '--cache-from "${BUILD_CACHE_FROM}"' in build_script
    assert '--cache-to "${BUILD_CACHE_TO}"' in build_script
    assert 'BUILD_CONTEXT_HASH="${BUILD_CONTEXT_HASH:?' in build_script

    remote_build_script = (
        ROOT / "scripts" / "release" / "build_remote_test_image.sh"
    ).read_text(encoding="utf-8")
    assert "docker image inspect" in remote_build_script
    assert 'IMAGE="yujian-test-local:ctx-' in remote_build_script
    assert "org.opencontainers.image.source-hash" in remote_build_script
    assert "https://mirrors.cloud.tencent.com/pypi/simple" in remote_build_script
    assert '--build-arg "PIP_INDEX_URL=${PIP_INDEX_URL}"' in remote_build_script


def test_local_cached_image_requires_test_environment_opt_in_and_matching_hash(
    monkeypatch,
) -> None:
    context_hash = "a" * 64
    image = f"yujian-test-local:ctx-{context_hash[:24]}"
    test_profile = EnvironmentProfile.load("test")
    prod_profile = EnvironmentProfile.load("prod")

    assert not is_local_test_image(test_profile, image)
    monkeypatch.setenv("YUJIAN_LOCAL_TEST_IMAGE", "1")
    monkeypatch.setenv("APP_CONTEXT_HASH", context_hash)
    assert is_local_test_image(test_profile, image)
    assert not is_local_test_image(prod_profile, image)
    assert deployment_context_hash(test_profile, image) == context_hash

    monkeypatch.setenv("APP_CONTEXT_HASH", "b" * 64)
    with pytest.raises(DeployError, match="does not match"):
        deployment_context_hash(test_profile, image)


def test_reconcile_active_routing_records_the_real_nginx_target(
    tmp_path: Path,
    monkeypatch,
) -> None:
    upstream = tmp_path / "upstream.conf"
    upstream.write_text(
        "upstream yujian_test_active {\n    server 127.0.0.1:8033;\n}\n",
        encoding="utf-8",
    )
    profile = replace(
        EnvironmentProfile.load("test"),
        nginx_upstream_file=upstream,
        release_state_dir=tmp_path / "state",
    )
    monkeypatch.setattr(
        "scripts.deploy.health_payload",
        lambda url: {"ready": True, "release_version": "v20260727-001-active"},
    )
    monkeypatch.setattr(
        "scripts.deploy.run_command",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout="active-image\n",
            stderr="",
        ),
    )

    reconciled = reconcile_active_routing(
        profile,
        {
            "release": "v20260721-001-stale",
            "slot": "blue",
            "port": 8011,
            "project": "yujian-test-blue",
            "image": "stale-image",
        },
    )

    assert reconciled["port"] == 8033
    assert reconciled["slot"] == "external"
    assert reconciled["image"] == "active-image"
    assert read_record(profile.release_state_dir / "current.json") == reconciled


def test_prepare_candidate_slot_removes_only_the_named_inactive_slot(
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:3] == ["docker", "container", "inspect"]:
            return subprocess.CompletedProcess(command, 0, stdout="stale-id\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("scripts.deploy.run_command", fake_run)
    profile = EnvironmentProfile.load("test")
    prepare_candidate_slot(profile, {"slot": "external", "port": 8033}, "blue")

    assert ["docker", "rm", "--force", "yujian-test-blue-api-1"] in calls
    assert any(command[:3] == ["docker", "ps", "--filter"] for command in calls)


def test_prepare_candidate_slot_rejects_unrelated_port_owner(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        if command[:3] == ["docker", "container", "inspect"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
        if command[:3] == ["docker", "ps", "--filter"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="unrelated-service\n",
                stderr="",
            )
        raise AssertionError(command)

    monkeypatch.setattr("scripts.deploy.run_command", fake_run)
    profile = EnvironmentProfile.load("test")
    with pytest.raises(DeployError, match="unrelated container"):
        prepare_candidate_slot(profile, {"slot": "external", "port": 8033}, "blue")


def test_prepare_candidate_slot_removes_stale_test_namespace_port_owner(monkeypatch) -> None:
    calls: list[list[str]] = []
    port_checks = 0

    def fake_run(command, **kwargs):
        nonlocal port_checks
        calls.append(command)
        if command[:3] == ["docker", "container", "inspect"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
        if command[:3] == ["docker", "ps", "--filter"]:
            port_checks += 1
            owner = "yujian-test-search-api-1\n" if port_checks == 1 else ""
            return subprocess.CompletedProcess(command, 0, stdout=owner, stderr="")
        if command[:3] == ["docker", "rm", "--force"]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr("scripts.deploy.run_command", fake_run)
    profile = EnvironmentProfile.load("test")
    prepare_candidate_slot(profile, {"slot": "external", "port": 8033}, "blue")

    assert ["docker", "rm", "--force", "yujian-test-search-api-1"] in calls
    assert port_checks == 2


def test_pending_migration_preflight_parses_versions_and_noop(monkeypatch) -> None:
    profile = EnvironmentProfile.load("test")

    monkeypatch.setattr(
        "scripts.deploy.run_command",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout="pending: v20260727_16_custom_design_workbench\n",
            stderr="",
        ),
    )
    pending = pending_migrations(
        profile,
        "image",
        "v20260727-001-test",
        "blue",
        Path("/tmp/release.env"),
    )
    assert pending == ["v20260727_16_custom_design_workbench"]

    monkeypatch.setattr(
        "scripts.deploy.run_command",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout="pending: no changes\n",
            stderr="",
        ),
    )
    assert (
        pending_migrations(
            profile,
            "image",
            "v20260727-001-test",
            "blue",
            Path("/tmp/release.env"),
        )
        == []
    )


def test_pending_schema_query_tracks_applied_sqlite_migrations(tmp_path: Path) -> None:
    database = tmp_path / "pending.db"
    assert pending_schema("sqlite", database)
    with sqlite3.connect(database) as connection:
        connection.executemany(
            "INSERT INTO schema_migrations "
            "(version, applied_at, applied_by, release_version) "
            "VALUES (?, CURRENT_TIMESTAMP, 'test', 'test')",
            [(migration.VERSION,) for migration in MIGRATIONS],
        )
    assert pending_schema("sqlite", database) == []


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
