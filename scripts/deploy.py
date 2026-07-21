from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.release_state import (  # noqa: E402
    atomic_write as write_state_record,
    promote,
    read_record,
    rollback as rollback_state,
)
from scripts.validate_image_ref import IMMUTABLE_IMAGE  # noqa: E402
from scripts.validate_release_env import RELEASE_PATTERN, parse_env, validate  # noqa: E402


ENVIRONMENTS = ("test", "prod")
SLOT_NAMES = ("blue", "green")
UPSTREAM_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
ENV_KEY = re.compile(r"^[A-Z][A-Z0-9_]*$")
DEPLOY_ONLY_KEYS = {"MYSQL_ROOT_PASSWORD"}
COMPOSE_FILE = ROOT / "compose.release.yaml"


class DeployError(RuntimeError):
    pass


@dataclass(frozen=True)
class EnvironmentProfile:
    environment: str
    public_health_url: str
    runtime_env_file: Path
    release_env_dir: Path
    certs_dir: Path
    image_repository: str
    backend_network: str
    release_state_dir: Path
    nginx_config_file: Path
    nginx_upstream_file: Path
    nginx_upstream_name: str
    nginx_location: str
    nginx_strip_prefix: bool
    bootstrap_active_port: int
    slot_ports: dict[str, int]
    backup_app_dir: Path
    mysql_container: str

    @classmethod
    def load(cls, environment: str) -> "EnvironmentProfile":
        path = ROOT / "deploy" / "environments" / f"{environment}.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DeployError(f"invalid environment profile: {path}") from exc
        if raw.get("environment") != environment:
            raise DeployError(f"environment profile mismatch: {path}")
        slots = raw.get("slots")
        if not isinstance(slots, dict) or set(slots) != set(SLOT_NAMES):
            raise DeployError("environment profile must define blue and green slots")
        slot_ports = {name: _valid_port(slots[name], f"slots.{name}") for name in SLOT_NAMES}
        if len(set(slot_ports.values())) != 2:
            raise DeployError("blue and green ports must be different")
        upstream_name = str(raw["nginxUpstreamName"])
        if not UPSTREAM_NAME.fullmatch(upstream_name):
            raise DeployError("invalid Nginx upstream name")
        runtime_override = os.getenv("YUJIAN_RUNTIME_ENV_FILE", "").strip()
        certs_override = os.getenv("YUJIAN_CERTS_DIR", "").strip()
        profile = cls(
            environment=environment,
            public_health_url=str(raw["publicHealthUrl"]),
            runtime_env_file=Path(runtime_override or raw["runtimeEnvFile"]),
            release_env_dir=Path(str(raw["releaseEnvDir"])),
            certs_dir=Path(certs_override or raw["certsDir"]),
            image_repository=str(raw["imageRepository"]),
            backend_network=str(raw["backendNetwork"]),
            release_state_dir=Path(str(raw["releaseStateDir"])),
            nginx_config_file=Path(str(raw["nginxConfigFile"])),
            nginx_upstream_file=Path(str(raw["nginxUpstreamFile"])),
            nginx_upstream_name=upstream_name,
            nginx_location=str(raw["nginxLocation"]),
            nginx_strip_prefix=bool(raw["nginxStripPrefix"]),
            bootstrap_active_port=_valid_port(raw["bootstrapActivePort"], "bootstrapActivePort"),
            slot_ports=slot_ports,
            backup_app_dir=Path(str(raw["backupAppDir"])),
            mysql_container=str(raw["mysqlContainer"]),
        )
        profile.validate_paths()
        return profile

    def validate_paths(self) -> None:
        for name, path in (
            ("runtimeEnvFile", self.runtime_env_file),
            ("releaseEnvDir", self.release_env_dir),
            ("certsDir", self.certs_dir),
            ("releaseStateDir", self.release_state_dir),
            ("nginxConfigFile", self.nginx_config_file),
            ("nginxUpstreamFile", self.nginx_upstream_file),
            ("backupAppDir", self.backup_app_dir),
        ):
            if not path.is_absolute():
                raise DeployError(f"{name} must be an absolute path")
        if self.nginx_location not in {"/", "/test-api/"}:
            raise DeployError("unsupported Nginx location")
        if not PROJECT_NAME.fullmatch(self.backend_network):
            raise DeployError("invalid Docker backend network name")
        if not PROJECT_NAME.fullmatch(self.mysql_container):
            raise DeployError("invalid MySQL container name")

    def project(self, slot: str) -> str:
        if slot not in SLOT_NAMES:
            raise DeployError("invalid deployment slot")
        return f"yujian-{self.environment}-{slot}"


def _valid_port(value: object, label: str) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise DeployError(f"{label} must be a port") from exc
    if not 1024 <= port <= 65535:
        raise DeployError(f"{label} must be between 1024 and 65535")
    return port


@contextmanager
def deployment_lock(profile: EnvironmentProfile) -> Iterator[None]:
    path = Path(tempfile.gettempdir()) / f"yujian-docker-deploy-{profile.environment}.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DeployError(f"another {profile.environment} deployment is already running") from exc
        stream.write(f"pid={os.getpid()}\n")
        stream.flush()
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def run_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )
    if check and completed.returncode != 0:
        command_name = " ".join(command[:3])
        raise DeployError(f"command failed ({completed.returncode}): {command_name}")
    return completed


def ensure_deploy_inputs(profile: EnvironmentProfile, image: str, release: str) -> dict[str, str]:
    if not IMMUTABLE_IMAGE.fullmatch(image):
        raise DeployError("APP_IMAGE must use repository@sha256:<64 hex digest>")
    if not image.startswith(f"{profile.image_repository}@"):
        raise DeployError("APP_IMAGE repository does not match the selected environment profile")
    if not RELEASE_PATTERN.fullmatch(release):
        raise DeployError("RELEASE_VERSION must match vYYYYMMDD-NNN[-suffix]")
    if not profile.runtime_env_file.is_file():
        raise DeployError(f"runtime environment file not found: {profile.runtime_env_file}")
    values = parse_env(profile.runtime_env_file)
    values["RELEASE_VERSION"] = release
    errors = validate(values, profile.environment)
    if errors:
        raise DeployError("runtime environment rejected: " + ", ".join(errors))
    return values


def write_release_env(profile: EnvironmentProfile, values: dict[str, str], release: str) -> Path:
    runtime_values = {
        key: value
        for key, value in values.items()
        if key not in DEPLOY_ONLY_KEYS
    }
    for key, value in runtime_values.items():
        if not ENV_KEY.fullmatch(key):
            raise DeployError(f"invalid runtime environment key: {key}")
        if "\n" in value or "\r" in value:
            raise DeployError(f"multiline value must use a mounted file: {key}")
    profile.release_env_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    profile.release_env_dir.chmod(0o700)
    target = profile.release_env_dir / f"{release}.env"
    body = "".join(f"{key}={runtime_values[key]}\n" for key in sorted(runtime_values))
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", dir=profile.release_env_dir, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target


def compose_environment(
    profile: EnvironmentProfile,
    image: str,
    release: str,
    slot: str,
    env_file: Path,
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "APP_SLOT": slot,
            "APP_PORT": str(profile.slot_ports[slot]),
            "APP_IMAGE": image,
            "RELEASE_VERSION": release,
            "ENV_FILE": str(env_file),
            "CERTS_DIR": str(profile.certs_dir),
            "BACKEND_NETWORK": profile.backend_network,
        }
    )
    return environment


def compose_command(profile: EnvironmentProfile, slot: str, *arguments: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        profile.project(slot),
        "--file",
        str(COMPOSE_FILE),
        *arguments,
    ]


def ensure_runtime_dependencies(profile: EnvironmentProfile) -> None:
    for command in ("docker", "nginx", "curl"):
        if not shutil.which(command):
            raise DeployError(f"{command} is required on the deployment host")
    run_command(["docker", "compose", "version"], capture=True)
    run_command(["docker", "network", "inspect", profile.backend_network], capture=True)
    if not profile.certs_dir.is_dir():
        raise DeployError(f"certificate directory not found: {profile.certs_dir}")
    if stat.S_IMODE(profile.runtime_env_file.stat().st_mode) & 0o077:
        raise DeployError("runtime environment file must not be accessible by group or others")
    if not profile.nginx_config_file.is_file():
        raise DeployError(f"Nginx server configuration not found: {profile.nginx_config_file}")


def health_payload(url: str) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": "yujian-docker-deployer/1"})
    with urlopen(request, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = payload.get("data") or payload
    if payload.get("code") != 0 or not data.get("ready", True):
        raise DeployError("readiness response was not ready")
    return data


def verify_health(url: str, expected_release: str | None = None, attempts: int = 20) -> None:
    last_error = "unavailable"
    for _ in range(attempts):
        try:
            data = health_payload(url)
            if expected_release and data.get("release_version") != expected_release:
                last_error = "different release"
            else:
                print(f"readiness passed: {url}")
                return
        except Exception as exc:  # Retry while Docker and Nginx converge.
            last_error = type(exc).__name__
        time.sleep(2)
    raise DeployError(f"readiness failed ({last_error}): {url}")


def render_upstream(name: str, port: int) -> str:
    if not UPSTREAM_NAME.fullmatch(name):
        raise DeployError("invalid Nginx upstream name")
    _valid_port(port, "upstream port")
    return (
        f"upstream {name} {{\n"
        f"    server 127.0.0.1:{port};\n"
        "    keepalive 32;\n"
        "}\n"
    )


def replace_location_proxy(
    content: str,
    location: str,
    upstream_name: str,
    strip_prefix: bool,
) -> str:
    lines = content.splitlines(keepends=True)
    location_pattern = re.compile(rf"^\s*location\s+{re.escape(location)}\s*\{{\s*$")
    start = next((index for index, line in enumerate(lines) if location_pattern.match(line)), None)
    if start is None:
        raise DeployError(f"Nginx location not found: {location}")
    depth = 0
    proxy_indexes: list[int] = []
    for index in range(start, len(lines)):
        line = lines[index]
        depth += line.count("{") - line.count("}")
        if index > start and depth > 0 and re.match(r"^\s*proxy_pass\s+", line):
            proxy_indexes.append(index)
        if index > start and depth == 0:
            break
    if len(proxy_indexes) != 1:
        raise DeployError(f"Nginx location must contain exactly one proxy_pass: {location}")
    index = proxy_indexes[0]
    indentation = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
    suffix = "/" if strip_prefix else ""
    lines[index] = f"{indentation}proxy_pass http://{upstream_name}{suffix};\n"
    return "".join(lines)


def atomic_write(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def reload_nginx() -> None:
    run_command(["nginx", "-t"])
    run_command(["nginx", "-s", "reload"])


def ensure_nginx_routing(profile: EnvironmentProfile) -> None:
    config_before = profile.nginx_config_file.read_text(encoding="utf-8")
    upstream_existed = profile.nginx_upstream_file.exists()
    upstream_before = (
        profile.nginx_upstream_file.read_text(encoding="utf-8") if upstream_existed else ""
    )
    reference = f"proxy_pass http://{profile.nginx_upstream_name}"
    config_after = config_before
    if reference not in config_before:
        config_after = replace_location_proxy(
            config_before,
            profile.nginx_location,
            profile.nginx_upstream_name,
            profile.nginx_strip_prefix,
        )
    if not upstream_existed:
        atomic_write(
            profile.nginx_upstream_file,
            render_upstream(profile.nginx_upstream_name, profile.bootstrap_active_port),
        )
    if config_after != config_before:
        atomic_write(profile.nginx_config_file, config_after)
    if upstream_existed and config_after == config_before:
        return
    try:
        reload_nginx()
    except DeployError:
        atomic_write(profile.nginx_config_file, config_before)
        if upstream_existed:
            atomic_write(profile.nginx_upstream_file, upstream_before)
        else:
            profile.nginx_upstream_file.unlink(missing_ok=True)
        reload_nginx()
        raise


def switch_upstream(profile: EnvironmentProfile, port: int) -> None:
    previous = profile.nginx_upstream_file.read_text(encoding="utf-8")
    atomic_write(
        profile.nginx_upstream_file,
        render_upstream(profile.nginx_upstream_name, port),
    )
    try:
        reload_nginx()
    except DeployError:
        atomic_write(profile.nginx_upstream_file, previous)
        reload_nginx()
        raise


def bootstrap_state(profile: EnvironmentProfile) -> dict[str, object]:
    current = read_record(profile.release_state_dir / "current.json")
    if current:
        return current
    url = f"http://127.0.0.1:{profile.bootstrap_active_port}/health/ready"
    verify_health(url, attempts=1)
    record: dict[str, object] = {
        "release": f"legacy-{profile.environment}",
        "slot": "legacy",
        "port": profile.bootstrap_active_port,
        "project": f"legacy-{profile.environment}",
        "image": "legacy-local-image",
    }
    promote(profile.release_state_dir, record)
    return record


def choose_candidate_slot(current: dict[str, object]) -> str:
    return "green" if current.get("slot") == "blue" else "blue"


def restore_state(
    profile: EnvironmentProfile,
    current: dict[str, object],
    previous: dict[str, object],
) -> None:
    write_state_record(profile.release_state_dir / "current.json", current)
    previous_path = profile.release_state_dir / "previous.json"
    if previous:
        write_state_record(previous_path, previous)
    else:
        previous_path.unlink(missing_ok=True)


def run_backup(profile: EnvironmentProfile, values: dict[str, str], release: str) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "APP_DIR": str(profile.backup_app_dir),
            "BACKUP_DATABASE": values["MYSQL_DATABASE"],
            "MYSQL_CONTAINER": profile.mysql_container,
            "RELEASE_VERSION": release,
            "MIGRATION_OPERATOR": f"docker-{profile.environment}",
        }
    )
    run_command(["bash", str(ROOT / "scripts" / "backup_mysql.sh")], env=environment)


def run_migrations(
    profile: EnvironmentProfile,
    image: str,
    release: str,
    slot: str,
    env_file: Path,
) -> None:
    environment = compose_environment(profile, image, release, slot, env_file)
    run_command(
        compose_command(
            profile,
            slot,
            "run",
            "--rm",
            "--no-deps",
            "-e",
            f"MIGRATION_OPERATOR=docker-{profile.environment}",
            "api",
            "python",
            "-m",
            "app.migrations.runner",
            "upgrade",
            "--backend",
            "mysql",
        ),
        env=environment,
    )


def pull_and_validate_image(
    profile: EnvironmentProfile,
    image: str,
    release: str,
    slot: str,
    env_file: Path,
) -> None:
    environment = compose_environment(profile, image, release, slot, env_file)
    run_command(compose_command(profile, slot, "pull", "api"), env=environment)
    inspected = run_command(
        [
            "docker",
            "image",
            "inspect",
            image,
            "--format",
            '{{ index .Config.Labels "org.opencontainers.image.version" }}',
        ],
        capture=True,
    )
    if inspected.stdout.strip() != release:
        raise DeployError("image release label does not match RELEASE_VERSION")


def deploy_candidate(
    profile: EnvironmentProfile,
    image: str,
    release: str,
    slot: str,
    env_file: Path,
) -> None:
    environment = compose_environment(profile, image, release, slot, env_file)
    run_command(
        compose_command(profile, slot, "up", "--detach", "--no-build", "api"),
        env=environment,
    )
    verify_health(
        f"http://127.0.0.1:{profile.slot_ports[slot]}/health/ready",
        release,
        attempts=30,
    )


def prune_release_env_files(profile: EnvironmentProfile, keep: int = 8) -> None:
    files = sorted(
        profile.release_env_dir.glob("v*.env"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in files[keep:]:
        path.unlink()


def deploy(profile: EnvironmentProfile, image: str, release: str, dry_run: bool) -> None:
    values = ensure_deploy_inputs(profile, image, release)
    if dry_run:
        print(f"environment={profile.environment}")
        print(f"release={release}")
        print(f"image={image}")
        print(f"blue_port={profile.slot_ports['blue']} green_port={profile.slot_ports['green']}")
        print("dry-run passed; Docker, Nginx and external services were not changed")
        return
    ensure_runtime_dependencies(profile)
    ensure_nginx_routing(profile)
    current = bootstrap_state(profile)
    current_port = _valid_port(current.get("port"), "current port")
    previous_before = read_record(profile.release_state_dir / "previous.json")
    slot = choose_candidate_slot(current)
    port = profile.slot_ports[slot]
    if port == current_port:
        raise DeployError("candidate port is already active")
    release_env = write_release_env(profile, values, release)
    pull_and_validate_image(profile, image, release, slot, release_env)
    run_backup(profile, values, release)
    run_migrations(profile, image, release, slot, release_env)
    deploy_candidate(profile, image, release, slot, release_env)
    record = {
        "release": release,
        "slot": slot,
        "port": port,
        "project": profile.project(slot),
        "image": image,
    }
    switched = False
    try:
        switch_upstream(profile, port)
        switched = True
        promote(profile.release_state_dir, record)
        verify_health(profile.public_health_url, release)
    except (DeployError, OSError, ValueError) as exc:
        if switched:
            try:
                switch_upstream(profile, current_port)
                restore_state(profile, current, previous_before)
            except (DeployError, OSError, ValueError) as rollback_exc:
                raise DeployError(
                    "deployment failed and automatic traffic rollback also failed"
                ) from rollback_exc
        raise DeployError(
            "deployment verification failed; traffic and release state were automatically rolled back"
        ) from exc
    prune_release_env_files(profile)
    print(
        f"deployment complete: environment={profile.environment} "
        f"release={release} slot={slot} port={port}"
    )


def show_plan(profile: EnvironmentProfile) -> None:
    print(f"environment={profile.environment}")
    print("driver=docker-blue-green")
    print(f"runtime_env={profile.runtime_env_file} present={profile.runtime_env_file.is_file()}")
    print(f"certs_dir={profile.certs_dir} present={profile.certs_dir.is_dir()}")
    print(f"backend_network={profile.backend_network}")
    print(f"blue_port={profile.slot_ports['blue']} green_port={profile.slot_ports['green']}")
    print(f"public_health={profile.public_health_url}")
    print(f"docker_present={bool(shutil.which('docker'))}")
    print(f"nginx_present={bool(shutil.which('nginx'))}")


def show_status(profile: EnvironmentProfile) -> None:
    current = read_record(profile.release_state_dir / "current.json")
    previous = read_record(profile.release_state_dir / "previous.json")
    print(f"environment={profile.environment}")
    print("current=" + (json.dumps(current, sort_keys=True) if current else "uninitialized"))
    print("previous=" + (json.dumps(previous, sort_keys=True) if previous else "unavailable"))
    if shutil.which("docker"):
        run_command(
            [
                "docker",
                "ps",
                "--filter",
                f"name=yujian-{profile.environment}-",
                "--format",
                "{{.Names}} {{.Status}} {{.Ports}}",
            ]
        )


def rollback(profile: EnvironmentProfile) -> None:
    ensure_runtime_dependencies(profile)
    current = read_record(profile.release_state_dir / "current.json")
    previous = read_record(profile.release_state_dir / "previous.json")
    if not current or not previous:
        raise DeployError("both current and previous releases are required for rollback")
    current_port = _valid_port(current.get("port"), "current port")
    previous_port = _valid_port(previous.get("port"), "previous port")
    expected = str(previous.get("release", ""))
    verify_health(
        f"http://127.0.0.1:{previous_port}/health/ready",
        expected if RELEASE_PATTERN.fullmatch(expected) else None,
        attempts=1,
    )
    switch_upstream(profile, previous_port)
    try:
        verify_health(
            profile.public_health_url,
            expected if RELEASE_PATTERN.fullmatch(expected) else None,
        )
    except DeployError:
        switch_upstream(profile, current_port)
        raise DeployError("rollback verification failed; original traffic was restored")
    try:
        rollback_state(profile.release_state_dir)
    except (OSError, ValueError, RuntimeError) as exc:
        switch_upstream(profile, current_port)
        restore_state(profile, current, previous)
        raise DeployError("rollback state update failed; original traffic was restored") from exc
    print(f"traffic rolled back to {expected}; database was not downgraded")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deploy Yujian through one Docker blue-green release path.",
    )
    parser.add_argument("environment", choices=ENVIRONMENTS, help="the only required deployment choice")
    parser.add_argument(
        "action",
        nargs="?",
        choices=("deploy", "plan", "status", "rollback"),
        default="deploy",
    )
    parser.add_argument("--image", default=os.getenv("APP_IMAGE", ""), help=argparse.SUPPRESS)
    parser.add_argument("--release", default=os.getenv("RELEASE_VERSION", ""), help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        profile = EnvironmentProfile.load(args.environment)
        if args.action == "plan":
            show_plan(profile)
        elif args.action == "status":
            show_status(profile)
        elif args.action == "rollback":
            with deployment_lock(profile):
                rollback(profile)
        else:
            if args.dry_run:
                deploy(profile, args.image, args.release, True)
            else:
                with deployment_lock(profile):
                    deploy(profile, args.image, args.release, False)
        return 0
    except (DeployError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"deployment failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
