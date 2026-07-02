from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import connect_database, use_mysql


DEFAULT_SOURCE_ROOT = ROOT / "static" / "materials" / "rendered_beads"
DEFAULT_COS_PREFIX = "materials/beads/wps-circle-v2"
DEFAULT_BUCKET = "yujian-test-1258267288"
DEFAULT_REGION = "ap-guangzhou"
DEFAULT_CDN_BASE_URL = "https://cdn-test.yustream.cn"
DEFAULT_NAME_REGEX = r"幽灵|满天星|phantom|ghost|youling|starry|mantianxing"
TARGET_NAME_ALIASES = {
    "满天星": ("绿幽灵满天星", "高品绿幽灵满天星"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload rotated phantom bead circle PNGs to COS and rebind matching material rows."
    )
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--name-regex", default=DEFAULT_NAME_REGEX)
    parser.add_argument("--cos-prefix", default=DEFAULT_COS_PREFIX)
    parser.add_argument("--bucket", default=os.getenv("TENCENT_TEST_COS_BUCKET") or DEFAULT_BUCKET)
    parser.add_argument("--region", default=os.getenv("TENCENT_COS_REGION") or DEFAULT_REGION)
    parser.add_argument("--cdn-base-url", default=os.getenv("TENCENT_TEST_COS_CDN_BASE_URL") or DEFAULT_CDN_BASE_URL)
    parser.add_argument("--secret-id", default=os.getenv("TENCENT_COS_SECRET_ID"))
    parser.add_argument("--secret-key", default=os.getenv("TENCENT_COS_SECRET_KEY"))
    parser.add_argument("--app-env", default="test")
    parser.add_argument("--mysql-database", default="yujian_test")
    parser.add_argument(
        "--url-version",
        default=datetime.now().strftime("%Y%m%d%H%M%S"),
        help="Cache-busting query appended to image_url/image_urls_json.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    return parser.parse_args()


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip("\"'")
        if name and value:
            os.environ.setdefault(name, value)


def configure_environment(args: argparse.Namespace) -> None:
    load_local_env(ROOT / ".env")
    load_local_env(ROOT / ".env.local")
    args.region = args.region or os.getenv("TENCENT_COS_REGION") or DEFAULT_REGION
    args.secret_id = args.secret_id or os.getenv("TENCENT_COS_SECRET_ID")
    args.secret_key = args.secret_key or os.getenv("TENCENT_COS_SECRET_KEY")
    os.environ["DATABASE_BACKEND"] = "mysql"
    os.environ["APP_ENV"] = args.app_env
    os.environ["MYSQL_DATABASE"] = args.mysql_database
    app_env = os.getenv("APP_ENV", "").lower()
    if app_env not in {"test", "testing", "staging"}:
        raise SystemExit(f"Refusing to bind outside test/staging environment: APP_ENV={app_env or '<empty>'}")


def validate_cos_args(args: argparse.Namespace) -> None:
    if args.skip_upload:
        return
    missing = [
        name
        for name in ("bucket", "region", "secret_id", "secret_key")
        if not getattr(args, name.replace("-", "_"), None)
    ]
    if missing:
        raise SystemExit(
            "Missing COS config: "
            + ", ".join(missing)
            + ". Set TENCENT_COS_SECRET_ID and TENCENT_COS_SECRET_KEY."
        )


def selected_files(source_root: Path, name_regex: str) -> list[Path]:
    source_root = source_root.resolve()
    if not source_root.exists():
        raise SystemExit(f"Source root not found: {source_root}")
    if ROOT.resolve() not in source_root.parents:
        raise SystemExit(f"Refusing source root outside workspace: {source_root}")
    pattern = re.compile(name_regex, re.I)
    return sorted(path for path in source_root.glob("*.png") if pattern.search(path.name))


def public_url(args: argparse.Namespace, key: str, version: bool = True) -> str:
    base = args.cdn_base_url.rstrip("/") if args.cdn_base_url else f"https://{args.bucket}.cos.{args.region}.myqcloud.com"
    url = f"{base}/{quote(key, safe='/%')}"
    if version and args.url_version:
        return f"{url}?v={quote(args.url_version)}"
    return url


def target_names_for(asset_name: str) -> list[str]:
    names = [asset_name, f"高品{asset_name}"]
    names.extend(TARGET_NAME_ALIASES.get(asset_name, ()))
    result: list[str] = []
    for name in names:
        if name and name not in result:
            result.append(name)
    return result


def placeholders(values: list[str]) -> str:
    return ", ".join("?" for _ in values)


def preview_matches(files: list[Path]) -> tuple[dict[str, int], dict[str, list[str]], list[str]]:
    counts: dict[str, int] = {}
    targets: dict[str, list[str]] = {}
    with connect_database() as connection:
        for path in files:
            names = target_names_for(path.stem)
            targets[path.stem] = names
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS row_count
                FROM managed_materials
                WHERE top = ?
                  AND (series IN ({placeholders(names)}) OR name IN ({placeholders(names)}))
                """,
                ("bead", *names, *names),
            ).fetchone()
            counts[path.stem] = int(row["row_count"] if hasattr(row, "keys") else row[0])
    unmatched = [name for name, count in counts.items() if count == 0]
    return counts, targets, unmatched


def upload_files(args: argparse.Namespace, files: list[Path]) -> list[tuple[str, str, str]]:
    prefix = args.cos_prefix.strip("/")
    payload = [
        (path.stem, f"{prefix}/{path.name}" if prefix else path.name, path)
        for path in files
    ]
    if args.skip_upload:
        return [(name, key, public_url(args, key)) for name, key, _ in payload]

    from qcloud_cos import CosConfig, CosS3Client

    client = CosS3Client(
        CosConfig(
            Region=args.region,
            SecretId=args.secret_id,
            SecretKey=args.secret_key,
            Scheme="https",
        )
    )
    uploaded: list[tuple[str, str, str]] = []
    for name, key, path in payload:
        client.upload_file(
            Bucket=args.bucket,
            LocalFilePath=str(path),
            Key=key,
            PartSize=10,
            MAXThread=4,
            EnableMD5=False,
        )
        uploaded.append((name, key, public_url(args, key)))
    return uploaded


def rebind_materials(uploaded: list[tuple[str, str, str]], targets: dict[str, list[str]]) -> int:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    updated = 0
    with connect_database() as connection:
        for name, key, image_url in uploaded:
            names = targets.get(name) or target_names_for(name)
            cursor = connection.execute(
                f"""
                UPDATE managed_materials
                SET image_path = ?, image_url = ?, image_urls_json = ?, updated_at = ?
                WHERE top = ?
                  AND (series IN ({placeholders(names)}) OR name IN ({placeholders(names)}))
                """,
                (key, image_url, json.dumps([image_url], ensure_ascii=False), now, "bead", *names, *names),
            )
            updated += int(cursor.rowcount or 0)
    return updated


def main() -> None:
    args = parse_args()
    configure_environment(args)
    validate_cos_args(args)
    files = selected_files(args.source_root, args.name_regex)
    counts, targets, unmatched = preview_matches(files)
    matched = [path for path in files if counts.get(path.stem, 0) > 0]

    print(
        f"source_files={len(files)} matched_files={len(matched)} "
        f"unmatched_files={len(unmatched)} database={args.mysql_database}"
    )
    for path in files:
        count = counts.get(path.stem, 0)
        status = "MATCH" if count else "SKIP"
        key = f"{args.cos_prefix.strip('/')}/{path.name}" if args.cos_prefix.strip("/") else path.name
        print(f"[{status}] {path.name} -> rows={count} targets={','.join(targets.get(path.stem, []))} key={key}")
    if args.dry_run:
        print("dry_run=true")
        return

    uploaded = upload_files(args, files)
    updated = rebind_materials(uploaded, targets)
    backup = "mysql-no-local-file-backup" if use_mysql() else "sqlite"
    print(
        f"uploaded={len(uploaded)} updated_material_rows={updated} "
        f"bucket={args.bucket} prefix={args.cos_prefix.strip('/')} backup={backup}"
    )


if __name__ == "__main__":
    main()
