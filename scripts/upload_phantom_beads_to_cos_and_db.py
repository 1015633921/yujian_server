from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import connect_database, use_mysql
from app.repository import DB_PATH


SIZES = tuple(range(8, 16))


@dataclass(frozen=True)
class PhantomSeries:
    slug: str
    series: str
    category: str
    effect: str
    element: str
    color: str
    shine: str
    sort_order: int
    base_price: int


SERIES = (
    PhantomSeries(
        slug="green-phantom",
        series="绿幽灵",
        category="幽灵水晶",
        effect="生长与复原",
        element="木",
        color="#5f9a72",
        shine="#e1f2e7",
        sort_order=650,
        base_price=12,
    ),
    PhantomSeries(
        slug="red-phantom",
        series="红幽灵",
        category="幽灵水晶",
        effect="生长与复原",
        element="木",
        color="#8f4f48",
        shine="#ffe0dc",
        sort_order=530,
        base_price=12,
    ),
    PhantomSeries(
        slug="colorful-phantom",
        series="彩幽灵",
        category="幽灵水晶",
        effect="生长与复原",
        element="木",
        color="#7c8f72",
        shine="#f2ead8",
        sort_order=140,
        base_price=12,
    ),
)


def main() -> None:
    load_local_env(ROOT / ".env")
    load_local_env(ROOT / ".env.local")
    parser = argparse.ArgumentParser(description="Upload phantom bead image pools to COS and upsert materials.")
    parser.add_argument("--assets-root", type=Path, default=ROOT / "static" / "materials" / "beads" / "real")
    parser.add_argument("--cos-prefix", default="materials/beads/real")
    parser.add_argument("--bucket", default=os.getenv("TENCENT_COS_BUCKET"))
    parser.add_argument("--region", default=os.getenv("TENCENT_COS_REGION"))
    parser.add_argument("--secret-id", default=os.getenv("TENCENT_COS_SECRET_ID"))
    parser.add_argument("--secret-key", default=os.getenv("TENCENT_COS_SECRET_KEY"))
    parser.add_argument("--cdn-base-url", default=os.getenv("TENCENT_COS_CDN_BASE_URL", ""))
    parser.add_argument(
        "--url-version",
        default=datetime.now().strftime("%Y%m%d%H%M%S"),
        help="Append a cache-busting version query to material image URLs.",
    )
    parser.add_argument("--app-env", default=None, help="Override APP_ENV after loading local env files.")
    parser.add_argument("--mysql-database", default=None, help="Override MYSQL_DATABASE after loading local env files.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    args = parser.parse_args()

    if args.app_env:
        os.environ["APP_ENV"] = args.app_env
    if args.mysql_database:
        os.environ["MYSQL_DATABASE"] = args.mysql_database
    app_env = os.getenv("APP_ENV", "").lower()
    if app_env not in {"test", "testing", "staging"}:
        raise SystemExit(
            f"Refusing to upload outside test environment: APP_ENV={app_env or '<empty>'}. "
            "Set APP_ENV=test/testing/staging for this script."
        )
    validate_assets(args.assets_root)
    payload = build_payload(args)
    print_preview(payload)
    if args.dry_run:
        print("dry_run=true")
        return
    validate_cos_args(args)

    if not args.skip_upload:
        upload_payload(args, payload)
    backup = backup_database()
    upsert_materials(payload)
    print(f"database_backup={backup}")
    print("done=true")


def validate_assets(root: Path) -> None:
    for item in SERIES:
        directory = root / item.slug
        if not directory.exists():
            raise SystemExit(f"Missing asset directory: {directory}")
        files = sorted(directory.glob("*.webp"))
        if not files:
            raise SystemExit(f"No webp assets found: {directory}")


def build_payload(args: argparse.Namespace) -> dict[str, dict[str, object]]:
    payload: dict[str, dict[str, object]] = {}
    prefix = args.cos_prefix.strip("/")
    for item in SERIES:
        files = sorted((args.assets_root / item.slug).glob("*.webp"))
        keys = [f"{prefix}/{item.slug}/{path.name}" for path in files]
        urls = [public_url(args, key) for key in keys]
        payload[item.slug] = {
            "series": item,
            "files": files,
            "keys": keys,
            "urls": urls,
        }
    return payload


def print_preview(payload: dict[str, dict[str, object]]) -> None:
    with connect_database() as connection:
        for slug, info in payload.items():
            item: PhantomSeries = info["series"]  # type: ignore[assignment]
            rows = connection.execute(
                """
                SELECT size FROM managed_materials
                WHERE top = ? AND series = ?
                ORDER BY size
                """,
                ("bead", item.series),
            ).fetchall()
            existing_sizes = [float(row["size"]) if hasattr(row, "keys") else float(row[0]) for row in rows]
            print(
                f"{item.series}: assets={len(info['files'])} "
                f"existing_sizes={existing_sizes or 'none'} target_sizes={list(SIZES)}"
            )


def validate_cos_args(args: argparse.Namespace) -> None:
    missing = [
        name
        for name in ("bucket", "region", "secret_id", "secret_key")
        if not getattr(args, name.replace("-", "_"), None)
    ]
    if missing:
        raise SystemExit(
            "Missing COS config: "
            + ", ".join(missing)
            + ". Set TENCENT_COS_BUCKET, TENCENT_COS_REGION, "
            "TENCENT_COS_SECRET_ID, TENCENT_COS_SECRET_KEY."
        )


def upload_payload(args: argparse.Namespace, payload: dict[str, dict[str, object]]) -> None:
    from qcloud_cos import CosConfig, CosS3Client

    client = CosS3Client(
        CosConfig(
            Region=args.region,
            SecretId=args.secret_id,
            SecretKey=args.secret_key,
            Scheme="https",
        )
    )
    uploaded = 0
    for info in payload.values():
        files: list[Path] = info["files"]  # type: ignore[assignment]
        keys: list[str] = info["keys"]  # type: ignore[assignment]
        for path, key in zip(files, keys, strict=True):
            client.upload_file(
                Bucket=args.bucket,
                LocalFilePath=str(path),
                Key=key,
                PartSize=10,
                MAXThread=4,
                EnableMD5=False,
            )
            uploaded += 1
    print(f"uploaded={uploaded}")


def backup_database() -> str:
    if use_mysql():
        return "mysql-no-local-file-backup"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB_PATH.with_name(f"{DB_PATH.stem}.before_phantom_upload_{timestamp}{DB_PATH.suffix}")
    shutil.copy2(DB_PATH, backup)
    return str(backup)


def upsert_materials(payload: dict[str, dict[str, object]]) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with connect_database() as connection:
        for info in payload.values():
            item: PhantomSeries = info["series"]  # type: ignore[assignment]
            keys: list[str] = info["keys"]  # type: ignore[assignment]
            urls: list[str] = info["urls"]  # type: ignore[assignment]
            primary_key = keys[0]
            image_path = material_image_path(primary_key)
            primary_url = urls[0]
            image_urls_json = json.dumps(urls, ensure_ascii=False)
            for offset, size in enumerate(SIZES):
                material_id = f"bead_{item.slug.replace('-', '_')}_{size}mm"
                sku_id = f"bead_{item.slug.replace('-', '_')}"
                existing = connection.execute(
                    """
                    SELECT id, created_at FROM managed_materials
                    WHERE top = ? AND series = ? AND size = ?
                    """,
                    ("bead", item.series, size),
                ).fetchone()
                row = (
                    sku_id,
                    "bead",
                    item.category,
                    item.series,
                    "",
                    item.series,
                    item.effect,
                    item.element,
                    estimate_price(item.base_price, size),
                    float(size),
                    round((size / 8) ** 3 * 1.2, 2),
                    item.color,
                    item.shine,
                    image_path,
                    primary_url,
                    image_urls_json,
                    999,
                    1,
                    item.sort_order + offset,
                    now,
                )
                if existing:
                    existing_id = existing["id"] if hasattr(existing, "keys") else existing[0]
                    connection.execute(
                        """
                        UPDATE managed_materials
                        SET skuId=?, top=?, category=?, series=?, grade=?, name=?, effect=?, element=?,
                            price=?, size=?, weight=?, color=?, shine=?, image_path=?, image_url=?,
                            image_urls_json=?, stock=?, enabled=?, sort_order=?, updated_at=?
                        WHERE id=?
                        """,
                        (*row, existing_id),
                    )
                else:
                    connection.execute(
                        """
                        INSERT INTO managed_materials
                        (id, skuId, top, category, series, grade, name, effect, element, price, size,
                         weight, color, shine, image_path, image_url, image_urls_json, stock, enabled,
                         sort_order, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (material_id, *row[:-1], now, row[-1]),
                    )
        if hasattr(connection, "commit"):
            connection.commit()
    print("materials_upserted=true")


def estimate_price(base_price: int, size: int) -> int:
    return int(round(base_price * (size / 8) ** 1.35))


def public_url(args: argparse.Namespace, key: str) -> str:
    if args.cdn_base_url:
        url = f"{args.cdn_base_url.rstrip('/')}/{quote(key)}"
    else:
        url = f"https://{args.bucket}.cos.{args.region}.myqcloud.com/{quote(key)}"
    version = str(args.url_version or "").strip()
    if version:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}v={quote(version)}"
    return url


def material_image_path(key: str) -> str:
    prefix = "materials/"
    return key[len(prefix):] if key.startswith(prefix) else key


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip("\"'")
        if name and value:
            os.environ[name] = value


if __name__ == "__main__":
    main()
