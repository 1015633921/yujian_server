from __future__ import annotations

import argparse
import mimetypes
import os
import sys
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_REGION = "ap-guangzhou"
DEFAULT_PREFIX = "miniprogram/assets"
ENV_DEFAULTS = {
    "test": {
        "bucket": "yujian-test-1258267288",
        "cdn_base_url": "https://cdn-test.yustream.cn",
    },
    "prod": {
        "bucket": "yujian-prod-1258267288",
        "cdn_base_url": "https://cdn-prod.yustream.cn",
    },
}
SUPPORTED_SUFFIXES = {".avif", ".gif", ".jpg", ".jpeg", ".m4a", ".mp3", ".ogg", ".png", ".wav", ".webp"}


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def iter_assets(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        raise SystemExit(f"Asset directory not found: {source_dir}")
    return [
        path
        for path in sorted(source_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]


def guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    explicit = {
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
        ".webp": "image/webp",
    }
    if suffix in explicit:
        return explicit[suffix]
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def build_key(prefix: str, source_dir: Path, path: Path) -> str:
    relative = path.relative_to(source_dir).as_posix()
    clean_prefix = prefix.strip("/")
    return f"{clean_prefix}/{relative}" if clean_prefix else relative


def public_url(cdn_base_url: str, key: str) -> str:
    base = cdn_base_url.rstrip("/")
    return f"{base}/{'/'.join(quote(part) for part in key.split('/'))}"


def main() -> None:
    load_env_file(ROOT / ".env")
    load_env_file(ROOT / ".env.local")

    parser = argparse.ArgumentParser(description="Upload miniprogram image/audio assets to Tencent COS.")
    parser.add_argument("--env", choices=["test", "prod"], default=os.getenv("MINIPROGRAM_ENV", "test"))
    parser.add_argument("--source", type=Path, default=ROOT / "miniprogram" / "assets")
    parser.add_argument("--bucket", default=None)
    parser.add_argument("--region", default=os.getenv("TENCENT_COS_REGION", DEFAULT_REGION))
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--cdn-base-url", default=None)
    parser.add_argument("--secret-id", default=os.getenv("TENCENT_COS_SECRET_ID"))
    parser.add_argument("--secret-key", default=os.getenv("TENCENT_COS_SECRET_KEY"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env_defaults = ENV_DEFAULTS[args.env]
    args.bucket = (
        args.bucket
        or os.getenv(f"TENCENT_COS_{args.env.upper()}_BUCKET")
        or os.getenv(f"COS_{args.env.upper()}_BUCKET")
        or env_defaults["bucket"]
    )
    args.cdn_base_url = (
        args.cdn_base_url
        or os.getenv(f"TENCENT_COS_{args.env.upper()}_CDN_BASE_URL")
        or os.getenv(f"COS_{args.env.upper()}_CDN_BASE_URL")
        or env_defaults["cdn_base_url"]
    )

    source_dir = args.source.resolve()
    assets = iter_assets(source_dir)
    print(f"source={source_dir}")
    print(f"env={args.env}")
    print(f"bucket={args.bucket} region={args.region} prefix={args.prefix.strip('/')}")
    print(f"asset_count={len(assets)}")

    rows = []
    for path in assets:
      key = build_key(args.prefix, source_dir, path)
      size = path.stat().st_size
      rows.append((path, key, size, guess_content_type(path), public_url(args.cdn_base_url, key)))
      over_limit = " over_200k" if size > 200 * 1024 else ""
      print(f"{path.relative_to(source_dir).as_posix()}\t{size} bytes{over_limit}\t{public_url(args.cdn_base_url, key)}")

    if args.dry_run:
        print("dry_run=true")
        return
    if not args.secret_id or not args.secret_key:
        raise SystemExit("Missing TENCENT_COS_SECRET_ID / TENCENT_COS_SECRET_KEY.")

    from qcloud_cos import CosConfig, CosS3Client

    client = CosS3Client(CosConfig(
        Region=args.region,
        SecretId=args.secret_id,
        SecretKey=args.secret_key,
        Scheme="https",
    ))

    uploaded = 0
    for path, key, _size, content_type, url in rows:
        client.upload_file(
            Bucket=args.bucket,
            LocalFilePath=str(path),
            Key=key,
            PartSize=10,
            MAXThread=4,
            EnableMD5=False,
            ContentType=content_type,
            CacheControl="public, max-age=31536000",
        )
        uploaded += 1
        print(f"[UPLOADED] {key} -> {url}")
    print(f"uploaded={uploaded}")


if __name__ == "__main__":
    main()
