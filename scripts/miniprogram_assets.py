from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "miniprogram" / "config" / "asset-manifest.json"
DEFAULT_SOURCE = ROOT / "miniprogram" / "assets"
PREFIX = "miniprogram/assets"
SUPPORTED_SUFFIXES = {".avif", ".gif", ".jpg", ".jpeg", ".m4a", ".mp3", ".ogg", ".png", ".wav", ".webp"}
ENVIRONMENT_DEFAULTS = {
    "test": {
        "bucket": "yujian-test-1258267288",
        "region": "ap-guangzhou",
        "cdn_base_url": "https://cdn-test.yustream.cn",
        "env_file": ROOT / ".env.test",
    },
    "prod": {
        "bucket": "yujian-prod-1258267288",
        "region": "ap-guangzhou",
        "cdn_base_url": "https://cdn-prod.yustream.cn",
        "env_file": ROOT / ".env",
    },
}


class AssetError(RuntimeError):
    pass


@dataclass(frozen=True)
class AssetEntry:
    logical: str
    object_path: str
    sha256: str | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(value: str) -> str:
    path = PurePosixPath(str(value).replace("\\", "/").lstrip("/"))
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise AssetError(f"unsafe asset path: {value}")
    return path.as_posix()


def read_manifest(path: Path) -> dict[str, AssetEntry]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssetError(f"invalid asset manifest: {path}") from exc
    if payload.get("version") != 1 or not isinstance(payload.get("assets"), dict):
        raise AssetError("asset manifest must use version 1 and contain an assets object")
    entries: dict[str, AssetEntry] = {}
    for logical, raw in payload["assets"].items():
        logical_path = safe_relative_path(logical)
        object_path = safe_relative_path(str((raw or {}).get("object") or ""))
        checksum = (raw or {}).get("sha256")
        if checksum is not None and not (
            isinstance(checksum, str) and re.fullmatch(r"[0-9a-f]{64}", checksum)
        ):
            raise AssetError(f"invalid sha256 for asset: {logical_path}")
        entries[logical_path] = AssetEntry(logical_path, object_path, checksum)
    if not entries:
        raise AssetError("asset manifest is empty")
    return entries


def build_manifest(source: Path) -> dict[str, object]:
    if not source.is_dir():
        raise AssetError(f"asset source directory not found: {source}")
    assets: dict[str, dict[str, str]] = {}
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        logical = safe_relative_path(path.relative_to(source).as_posix())
        checksum = sha256_file(path)
        assets[logical] = {
            "object": f"releases/{checksum[:16]}/{logical}",
            "sha256": checksum,
        }
    if not assets:
        raise AssetError("asset source contains no supported image or audio files")
    return {"version": 1, "assets": assets}


def write_runtime_manifest(payload: dict[str, object], manifest: Path) -> Path:
    runtime_manifest = manifest.with_suffix(".js")
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    runtime_manifest.write_text(
        "'use strict';\n\n"
        "// Generated alongside asset-manifest.json for the WeChat Mini Program runtime.\n"
        f"module.exports = {serialized};\n",
        encoding="utf-8",
    )
    return runtime_manifest


def prepare(source: Path, manifest: Path) -> None:
    payload = build_manifest(source)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    runtime_manifest = write_runtime_manifest(payload, manifest)
    print(
        "asset manifest prepared: "
        f"assets={len(payload['assets'])} path={manifest} runtime={runtime_manifest}"
    )


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise AssetError(f"invalid environment line {number}: {path}")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def setting(environment: str, values: dict[str, str], name: str) -> str:
    scoped = f"TENCENT_COS_{environment.upper()}_{name.removeprefix('TENCENT_COS_')}"
    return os.getenv(scoped) or os.getenv(name) or values.get(scoped) or values.get(name) or ""


def environment_settings(environment: str, env_file: Path | None = None) -> dict[str, str]:
    defaults = ENVIRONMENT_DEFAULTS[environment]
    values = parse_env_file(env_file or Path(defaults["env_file"]))
    return {
        "bucket": setting(environment, values, "TENCENT_COS_BUCKET") or str(defaults["bucket"]),
        "region": setting(environment, values, "TENCENT_COS_REGION") or str(defaults["region"]),
        "cdn_base_url": setting(environment, values, "TENCENT_COS_CDN_BASE_URL") or str(defaults["cdn_base_url"]),
        "secret_id": setting(environment, values, "TENCENT_COS_SECRET_ID"),
        "secret_key": setting(environment, values, "TENCENT_COS_SECRET_KEY"),
    }


def content_type(path: Path) -> str:
    explicit = {".m4a": "audio/mp4", ".ogg": "audio/ogg", ".wav": "audio/wav", ".webp": "image/webp"}
    return explicit.get(path.suffix.lower()) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def public_url(cdn_base_url: str, object_path: str) -> str:
    encoded = "/".join(quote(part) for part in f"{PREFIX}/{object_path}".split("/"))
    return f"{cdn_base_url.rstrip('/')}/{encoded}"


def validate_sources(source: Path, entries: dict[str, AssetEntry]) -> list[tuple[Path, AssetEntry]]:
    rows: list[tuple[Path, AssetEntry]] = []
    for entry in entries.values():
        path = source / entry.logical
        if not path.is_file():
            raise AssetError(f"asset source file missing: {entry.logical}")
        checksum = sha256_file(path)
        if not entry.sha256 or checksum != entry.sha256:
            raise AssetError(f"asset checksum mismatch; run prepare first: {entry.logical}")
        rows.append((path, entry))
    return rows


def publish(
    environment: str,
    source: Path,
    manifest: Path,
    env_file: Path | None,
    dry_run: bool,
) -> None:
    entries = read_manifest(manifest)
    rows = validate_sources(source, entries)
    settings = environment_settings(environment, env_file)
    print(f"environment={environment} assets={len(rows)} prefix={PREFIX}")
    if dry_run:
        print("dry_run=true")
        return
    if not settings["secret_id"] or not settings["secret_key"]:
        raise AssetError("selected environment is missing Tencent COS credentials")
    from qcloud_cos import CosConfig, CosS3Client

    client = CosS3Client(
        CosConfig(
            Region=settings["region"],
            SecretId=settings["secret_id"],
            SecretKey=settings["secret_key"],
            Scheme="https",
        )
    )
    for path, entry in rows:
        key = f"{PREFIX}/{entry.object_path}"
        client.upload_file(
            Bucket=settings["bucket"],
            LocalFilePath=str(path),
            Key=key,
            PartSize=10,
            MAXThread=4,
            EnableMD5=True,
            ContentType=content_type(path),
            CacheControl="public, max-age=31536000, immutable",
        )
        print(f"uploaded={entry.logical}")
    verify(environment, manifest, env_file)


def verify(environment: str, manifest: Path, env_file: Path | None = None) -> None:
    entries = read_manifest(manifest)
    settings = environment_settings(environment, env_file)
    failures: list[str] = []
    for entry in entries.values():
        url = public_url(settings["cdn_base_url"], entry.object_path)
        try:
            request = Request(url, method="HEAD", headers={"User-Agent": "yujian-asset-verifier/1"})
            with urlopen(request, timeout=12) as response:
                if response.status != 200:
                    failures.append(entry.logical)
        except Exception:
            failures.append(entry.logical)
    if failures:
        raise AssetError("CDN verification failed for: " + ", ".join(failures))
    print(f"CDN verification passed: environment={environment} assets={len(entries)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare, publish and verify immutable miniprogram CDN assets.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    prepare_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)

    for command in ("publish", "verify"):
        child = subparsers.add_parser(command)
        child.add_argument("environment", choices=("test", "prod"))
        child.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
        child.add_argument("--env-file", type=Path, default=None)
        if command == "publish":
            child.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
            child.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "prepare":
            prepare(args.source, args.manifest)
        elif args.command == "publish":
            publish(args.environment, args.source, args.manifest, args.env_file, args.dry_run)
        else:
            verify(args.environment, args.manifest, args.env_file)
        return 0
    except (AssetError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"asset operation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
