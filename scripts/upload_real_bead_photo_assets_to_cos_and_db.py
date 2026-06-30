from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import connect_database, use_mysql
from app.material_knowledge import material_code_from_payload
from app.repository import DB_PATH


SIZES = tuple(range(8, 16))
GENERIC_PHOTO_RE = re.compile(r"^(IMG|DSC|PXL|WX|MMEXPORT|SCREENSHOT)[_ -]?\d+", re.I)


@dataclass
class AssetGroup:
    series: str
    source_folder: str
    slug: str
    material_code: str
    files: list[Path]
    keys: list[str]
    urls: list[str]


DEFAULT_META = {
    "category": "天然晶石",
    "effect": "calm",
    "element": "earth",
    "color": "#dfe3e5",
    "shine": "#ffffff",
    "sort_order": 600,
}


CODE_OVERRIDES: tuple[tuple[str, str], ...] = (
    ("极光", "aurora_quartz"),
    ("千层幽灵", "layered_phantom"),
    ("巴西白幽灵千层水晶", "layered_phantom"),
    ("幽灵穿发", "phantom_rutilated"),
    ("抹茶幽灵", "matcha_phantom"),
    ("曼波绿幽灵", "green_phantom"),
    ("绿幽灵满天星", "green_phantom"),
    ("绿幽灵聚宝盆半盆", "green_phantom"),
    ("绿幽灵金字塔", "green_phantom"),
    ("翠幽灵", "green_phantom"),
    ("红泥骸骨幽灵", "red_mud_skeletal_phantom"),
    ("红铜发", "red_rutilated_quartz"),
    ("红铜发晶", "red_rutilated_quartz"),
    ("随型", "freeform"),
    ("彩幽灵蛋面", "freeform"),
    ("彩幽灵魔盒", "freeform"),
    ("黄阿赛水晶", "citrine"),
    ("黄阿塞水晶", "citrine"),
    ("金太阳阿鲁沙", "strawberry_quartz"),
    ("彩耀石", "obsidian"),
    ("金耀石", "golden_obsidian"),
    ("金曜石", "golden_obsidian"),
    ("银耀石", "silver_obsidian"),
    ("银曜石", "silver_obsidian"),
    ("陨石曜", "obsidian"),
    ("黑耀石", "obsidian"),
    ("黑曜石", "obsidian"),
)


CODE_META: dict[str, dict[str, object]] = {
    "clear_quartz": {"category": "白色晶石", "effect": "clarity", "element": "metal", "color": "#dfe3e5", "shine": "#ffffff", "sort_order": 80},
    "milky_quartz": {"category": "白色晶石", "effect": "calm", "element": "metal", "color": "#eef0e8", "shine": "#ffffff", "sort_order": 90},
    "rose_quartz": {"category": "粉红晶石", "effect": "love", "element": "wood", "color": "#e8a8b8", "shine": "#fff0f5", "sort_order": 100},
    "strawberry_quartz": {"category": "粉红晶石", "effect": "love", "element": "fire", "color": "#d9878b", "shine": "#fff0f2", "sort_order": 110},
    "rhodochrosite": {"category": "粉红晶石", "effect": "emotion", "element": "fire", "color": "#c36a76", "shine": "#ffe8ee", "sort_order": 120},
    "south_red_agate": {"category": "玛瑙", "effect": "vitality", "element": "fire", "color": "#b94a3d", "shine": "#ffe1df", "sort_order": 160},
    "red_agate": {"category": "玛瑙", "effect": "vitality", "element": "fire", "color": "#b94a3d", "shine": "#ffe1df", "sort_order": 170},
    "salt_source_agate": {"category": "玛瑙", "effect": "emotion", "element": "fire", "color": "#d98d96", "shine": "#fff0f2", "sort_order": 175},
    "alashan_agate": {"category": "玛瑙", "effect": "grounding", "element": "earth", "color": "#b87955", "shine": "#f4dfd5", "sort_order": 178},
    "banded_agate": {"category": "玛瑙", "effect": "focus", "element": "earth", "color": "#7b756d", "shine": "#f0eee9", "sort_order": 179},
    "flower_agate": {"category": "玛瑙", "effect": "love", "element": "fire", "color": "#d98d96", "shine": "#fff0f2", "sort_order": 180},
    "black_agate": {"category": "玛瑙", "effect": "protection", "element": "water", "color": "#2d2d32", "shine": "#d6d8dd", "sort_order": 185},
    "quartz_inclusion": {"category": "胶花水晶", "effect": "inspiration", "element": "fire", "color": "#c98552", "shine": "#fff2df", "sort_order": 210},
    "amethyst": {"category": "紫色晶石", "effect": "calm", "element": "water", "color": "#7f6a9e", "shine": "#eee6ff", "sort_order": 240},
    "ametrine": {"category": "紫色晶石", "effect": "clarity", "element": "fire", "color": "#b99a65", "shine": "#fff0d8", "sort_order": 245},
    "citrine": {"category": "财富晶石", "effect": "wealth", "element": "earth", "color": "#d9a545", "shine": "#fff2c8", "sort_order": 260},
    "titanium_quartz": {"category": "财富晶石", "effect": "wealth", "element": "metal", "color": "#d7b45d", "shine": "#fff4c8", "sort_order": 300},
    "gold_rutilated_quartz": {"category": "发晶", "effect": "wealth", "element": "metal", "color": "#c49a42", "shine": "#fff4c8", "sort_order": 310},
    "silver_rutilated_quartz": {"category": "发晶", "effect": "clarity", "element": "metal", "color": "#d4d6d6", "shine": "#ffffff", "sort_order": 315},
    "black_rutilated_quartz": {"category": "发晶", "effect": "protection", "element": "water", "color": "#343238", "shine": "#d9d9df", "sort_order": 320},
    "red_rutilated_quartz": {"category": "发晶", "effect": "vitality", "element": "fire", "color": "#a64e3d", "shine": "#ffe1d8", "sort_order": 325},
    "green_rutilated_quartz": {"category": "发晶", "effect": "growth", "element": "wood", "color": "#668c62", "shine": "#e8f3df", "sort_order": 330},
    "rabbit_hair_quartz": {"category": "兔毛水晶", "effect": "calm", "element": "metal", "color": "#d7d7d1", "shine": "#ffffff", "sort_order": 360},
    "white_phantom": {"category": "幽灵水晶", "effect": "clarity", "element": "metal", "color": "#dfe3e5", "shine": "#ffffff", "sort_order": 500},
    "green_phantom": {"category": "幽灵水晶", "effect": "growth", "element": "wood", "color": "#6f9a78", "shine": "#e1f2e7", "sort_order": 510},
    "red_phantom": {"category": "幽灵水晶", "effect": "growth", "element": "wood", "color": "#8f4f48", "shine": "#ffe0dc", "sort_order": 520},
    "yellow_phantom": {"category": "幽灵水晶", "effect": "wealth", "element": "earth", "color": "#c8a256", "shine": "#fff0cd", "sort_order": 525},
    "pink_phantom": {"category": "幽灵水晶", "effect": "emotion", "element": "fire", "color": "#d98d96", "shine": "#fff0f2", "sort_order": 526},
    "purple_phantom": {"category": "幽灵水晶", "effect": "calm", "element": "water", "color": "#8b6aa8", "shine": "#eee6ff", "sort_order": 527},
    "colorful_phantom": {"category": "幽灵水晶", "effect": "growth", "element": "wood", "color": "#7c8f72", "shine": "#f2ead8", "sort_order": 530},
    "moonstone": {"category": "白色晶石", "effect": "emotion", "element": "water", "color": "#dce2ea", "shine": "#ffffff", "sort_order": 700},
    "labradorite": {"category": "蓝色晶石", "effect": "inspiration", "element": "water", "color": "#7e8fa0", "shine": "#dfefff", "sort_order": 710},
    "aquamarine": {"category": "蓝色晶石", "effect": "communication", "element": "water", "color": "#a7d4e8", "shine": "#f0fbff", "sort_order": 720},
    "amazonite": {"category": "蓝色晶石", "effect": "communication", "element": "water", "color": "#71c6bf", "shine": "#e6fbf7", "sort_order": 725},
    "larimar": {"category": "蓝色晶石", "effect": "calm", "element": "water", "color": "#7dbbd0", "shine": "#e6f7fb", "sort_order": 730},
    "kyanite": {"category": "蓝色晶石", "effect": "focus", "element": "water", "color": "#476b9e", "shine": "#dce8ff", "sort_order": 735},
    "iolite": {"category": "蓝色晶石", "effect": "focus", "element": "water", "color": "#59617f", "shine": "#e6e9ff", "sort_order": 740},
    "blue_topaz": {"category": "蓝色晶石", "effect": "communication", "element": "water", "color": "#8cc7e8", "shine": "#effbff", "sort_order": 745},
    "lapis_lazuli": {"category": "蓝色晶石", "effect": "wisdom", "element": "water", "color": "#244d9f", "shine": "#dce8ff", "sort_order": 750},
    "fluorite": {"category": "萤石", "effect": "clarity", "element": "water", "color": "#8ca98b", "shine": "#f0fff0", "sort_order": 760},
    "blue_fluorite": {"category": "萤石", "effect": "clarity", "element": "water", "color": "#7aa7c8", "shine": "#eef9ff", "sort_order": 762},
    "yellow_fluorite": {"category": "萤石", "effect": "wealth", "element": "earth", "color": "#d6b65e", "shine": "#fff4ca", "sort_order": 763},
    "purple_fluorite": {"category": "萤石", "effect": "calm", "element": "water", "color": "#7c63a5", "shine": "#eee6ff", "sort_order": 764},
    "prehnite": {"category": "绿色晶石", "effect": "healing", "element": "wood", "color": "#b9d59a", "shine": "#f4ffe9", "sort_order": 770},
    "tourmaline": {"category": "天然晶石", "effect": "balance", "element": "wood", "color": "#8b6a6a", "shine": "#fff0f0", "sort_order": 780},
    "tiger_eye": {"category": "财富晶石", "effect": "confidence", "element": "earth", "color": "#b48435", "shine": "#fff0cf", "sort_order": 790},
    "blue_tiger_eye": {"category": "蓝色晶石", "effect": "focus", "element": "water", "color": "#263a52", "shine": "#dce8ff", "sort_order": 792},
    "obsidian": {"category": "黑曜石", "effect": "protection", "element": "water", "color": "#1f2024", "shine": "#d9d9df", "sort_order": 800},
    "golden_obsidian": {"category": "黑曜石", "effect": "protection", "element": "water", "color": "#2a2115", "shine": "#f1d69a", "sort_order": 802},
    "silver_obsidian": {"category": "黑曜石", "effect": "protection", "element": "water", "color": "#30323a", "shine": "#e7e7ef", "sort_order": 803},
    "layered_phantom": {"category": "幽灵水晶", "effect": "clarity", "element": "metal", "color": "#cfd7d9", "shine": "#ffffff", "sort_order": 540},
    "phantom_rutilated": {"category": "幽灵水晶", "effect": "growth", "element": "wood", "color": "#8a8b7f", "shine": "#eef0e8", "sort_order": 545},
    "matcha_phantom": {"category": "幽灵水晶", "effect": "growth", "element": "wood", "color": "#8aa075", "shine": "#edf6df", "sort_order": 548},
    "red_mud_skeletal_phantom": {"category": "幽灵水晶", "effect": "grounding", "element": "earth", "color": "#9a5b4d", "shine": "#f0d9d2", "sort_order": 555},
    "freeform": {"category": "随型", "effect": "inspiration", "element": "wood", "color": "#7c8f72", "shine": "#f2ead8", "sort_order": 900},
    "garnet": {"category": "紫色晶石", "effect": "vitality", "element": "fire", "color": "#7a2636", "shine": "#ffdce5", "sort_order": 810},
    "smoky_quartz": {"category": "黑色晶石", "effect": "grounding", "element": "earth", "color": "#786a5f", "shine": "#f0e8df", "sort_order": 820},
    "lepidolite": {"category": "紫色晶石", "effect": "calm", "element": "water", "color": "#b09ac8", "shine": "#f3eaff", "sort_order": 830},
    "aurora_quartz": {"category": "天然晶石", "effect": "inspiration", "element": "water", "color": "#b8c7d8", "shine": "#f3f8ff", "sort_order": 840},
}

EFFECT_ALIASES = {
    "clarity": "focus",
    "grounding": "calm",
    "growth": "career",
    "wisdom": "focus",
    "healing": "emotion",
    "balance": "calm",
    "confidence": "vitality",
}


def normalize_effect_key(value: object) -> str:
    effect = str(value or DEFAULT_META["effect"]).strip()
    effect = EFFECT_ALIASES.get(effect, effect)
    return effect if effect in {
        "calm",
        "career",
        "communication",
        "emotion",
        "focus",
        "inspiration",
        "love",
        "protection",
        "sleep",
        "vitality",
        "wealth",
    } else DEFAULT_META["effect"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload processed real bead photos to COS and bind them to materials.")
    parser.add_argument("--assets-root", type=Path, default=ROOT / "static" / "materials" / "beads" / "real-photos")
    parser.add_argument("--manifest-root", type=Path, default=ROOT / "outputs" / "real-bead-photos")
    parser.add_argument("--cos-prefix", default="materials/beads/real-photos")
    parser.add_argument("--bucket", default=os.getenv("TENCENT_COS_BUCKET"))
    parser.add_argument("--region", default=os.getenv("TENCENT_COS_REGION"))
    parser.add_argument("--secret-id", default=os.getenv("TENCENT_COS_SECRET_ID"))
    parser.add_argument("--secret-key", default=os.getenv("TENCENT_COS_SECRET_KEY"))
    parser.add_argument("--cdn-base-url", default=os.getenv("TENCENT_COS_CDN_BASE_URL", ""))
    parser.add_argument("--url-version", default=datetime.now().strftime("%Y%m%d%H%M%S"))
    parser.add_argument("--app-env", default=None)
    parser.add_argument("--mysql-database", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--create-missing", action="store_true", default=True)
    return parser.parse_args()


def clean_series_name(value: str) -> str:
    name = Path(value).stem.strip()
    name = re.sub(r"(?:图片|照片|实拍图)$", "", name)
    name = re.sub(r"[\s_-]*\d+$", "", name)
    return name.strip()


def is_generic_source_name(value: str) -> bool:
    return bool(GENERIC_PHOTO_RE.match(Path(value).stem))


def infer_material_code(series: str, source_folder: str = "") -> str:
    text = f"{series} {source_folder}"
    for keyword, code in CODE_OVERRIDES:
        if keyword in text:
            return code
    return material_code_from_payload({"top": "bead", "category": source_folder, "series": series, "name": series})


def infer_group_series(row: dict) -> str:
    for key in ("final_series", "series_label", "material_series"):
        value = str(row.get(key) or "").strip()
        if value:
            return clean_series_name(value)
    source_name = Path(row.get("source", "")).stem
    if source_name and not is_generic_source_name(source_name):
        return clean_series_name(source_name)
    return clean_series_name(str(row.get("series") or ""))


def infer_group_category(row: dict) -> str:
    for key in ("final_category", "category", "source_category"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return str(row.get("series") or "").strip()


def group_slug(series: str, material_code: str) -> str:
    text = material_code or series
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if text:
        return text
    return "material"


def load_asset_groups(args: argparse.Namespace) -> list[AssetGroup]:
    raw_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for manifest in sorted(args.manifest_root.glob("*/manifest.json")):
        rows = json.loads(manifest.read_text(encoding="utf-8"))
        for row in rows:
            app_file = Path(row["app_webp"])
            if not app_file.exists():
                continue
            series = infer_group_series(row)
            if not series:
                continue
            source_folder = infer_group_category(row)
            material_code = str(row.get("material_code") or "").strip() or infer_material_code(series, source_folder)
            raw_groups[(material_code, series)].append(
                {**row, "series_label": series, "source_folder": source_folder, "material_code": material_code}
            )

    groups: list[AssetGroup] = []
    prefix = args.cos_prefix.strip("/")
    for (material_code, series), rows in sorted(raw_groups.items(), key=lambda item: (item[0][0], item[0][1])):
        slug = group_slug(series, material_code)
        files = [Path(row["app_webp"]) for row in rows]
        keys = [f"{prefix}/{slug}/{index:02d}-{path.name}" for index, path in enumerate(files, start=1)]
        urls = [public_url(args, key) for key in keys]
        groups.append(
            AssetGroup(
                series=series,
                source_folder=str(rows[0].get("source_folder") or rows[0].get("series") or ""),
                slug=slug,
                material_code=material_code,
                files=files,
                keys=keys,
                urls=urls,
            )
        )
    return groups


def public_url(args: argparse.Namespace, key: str) -> str:
    if args.cdn_base_url:
        url = f"{args.cdn_base_url.rstrip('/')}/{quote(key)}"
    else:
        url = f"https://{args.bucket}.cos.{args.region}.myqcloud.com/{quote(key)}"
    version = str(args.url_version or "").strip()
    if version:
        url = f"{url}{'&' if '?' in url else '?'}v={quote(version)}"
    return url


def material_image_path(key: str) -> str:
    prefix = "materials/"
    return key[len(prefix) :] if key.startswith(prefix) else key


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


def validate_runtime(args: argparse.Namespace) -> None:
    if args.app_env:
        os.environ["APP_ENV"] = args.app_env
    if args.mysql_database:
        os.environ["MYSQL_DATABASE"] = args.mysql_database
    app_env = os.getenv("APP_ENV", "").lower()
    if app_env not in {"test", "testing", "staging"}:
        raise SystemExit(f"Refusing to write outside test environment: APP_ENV={app_env or '<empty>'}")
    if args.bucket:
        os.environ["TENCENT_COS_BUCKET"] = args.bucket
    if args.region:
        os.environ["TENCENT_COS_REGION"] = args.region
    if args.secret_id:
        os.environ["TENCENT_COS_SECRET_ID"] = args.secret_id
    if args.secret_key:
        os.environ["TENCENT_COS_SECRET_KEY"] = args.secret_key


def validate_cos_args(args: argparse.Namespace) -> None:
    missing = [
        name
        for name in ("bucket", "region", "secret_id", "secret_key")
        if not getattr(args, name.replace("-", "_"), None)
    ]
    if missing:
        raise SystemExit("Missing COS config: " + ", ".join(missing))


def upload_groups(args: argparse.Namespace, groups: list[AssetGroup]) -> None:
    from qcloud_cos import CosConfig, CosS3Client

    client = CosS3Client(
        CosConfig(Region=args.region, SecretId=args.secret_id, SecretKey=args.secret_key, Scheme="https")
    )
    uploaded = 0
    total = sum(len(group.files) for group in groups)
    for group in groups:
        for path, key in zip(group.files, group.keys, strict=True):
            client.put_object_from_local_file(
                Bucket=args.bucket,
                LocalFilePath=str(path),
                Key=key,
            )
            uploaded += 1
            if uploaded == 1 or uploaded % 50 == 0 or uploaded == total:
                print(f"uploaded={uploaded}/{total}", flush=True)


def backup_database() -> str:
    if use_mysql():
        return "mysql-no-local-file-backup"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB_PATH.with_name(f"{DB_PATH.stem}.before_real_photo_upload_{timestamp}{DB_PATH.suffix}")
    shutil.copy2(DB_PATH, backup)
    return str(backup)


def row_value(row, key: str, default=None):
    if row is None:
        return default
    try:
        return row[key]
    except Exception:
        return default


def select_existing_rows(connection, group: AssetGroup) -> list[dict]:
    exact = connection.execute(
        """
        SELECT * FROM managed_materials
        WHERE top = ? AND series = ?
        ORDER BY size
        """,
        ("bead", group.series),
    ).fetchall()
    if exact:
        return [dict(row) for row in exact]
    return []


def meta_for_group(group: AssetGroup, existing: list[dict]) -> dict:
    if existing:
        first = existing[0]
        return {
            "category": first.get("category") or DEFAULT_META["category"],
            "effect": first.get("effect") or DEFAULT_META["effect"],
            "element": first.get("element") or DEFAULT_META["element"],
            "color": first.get("color") or DEFAULT_META["color"],
            "shine": first.get("shine") or DEFAULT_META["shine"],
            "sort_order": int(first.get("sort_order") or DEFAULT_META["sort_order"]),
            "price": float(first.get("price") or 0.01),
            "stock": int(first.get("stock") or 99),
        }
    meta = {**DEFAULT_META, **CODE_META.get(group.material_code, {})}
    if group.source_folder:
        meta["category"] = group.source_folder
    meta["effect"] = normalize_effect_key(meta.get("effect"))
    return {**meta, "price": 0.01, "stock": 99}


def deterministic_id(group: AssetGroup, size: int) -> str:
    digest = hashlib.sha1(f"{group.material_code}|{group.series}|{size}".encode("utf-8")).hexdigest()[:18]
    return f"real_{digest}"


def deterministic_sku(group: AssetGroup, size: int) -> str:
    value = int(hashlib.sha1(f"sku|{group.material_code}|{group.series}|{size}".encode("utf-8")).hexdigest()[:13], 16)
    return f"{value % 10_000_000_000_000:013d}"


def insert_material_row(connection, group: AssetGroup, meta: dict, size: int, offset: int, now: str) -> None:
    image_path = material_image_path(group.keys[0])
    primary_url = group.urls[0]
    urls_json = json.dumps(group.urls, ensure_ascii=False)
    connection.execute(
        """
        INSERT INTO managed_materials
        (id, skuId, top, category, series, material_code, grade, name, effect, element, price, size, weight, color, shine,
         cost_price, safety_stock, supplier_name, purchase_note, image_path, image_url, image_urls_json, stock, enabled,
         sort_order, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            deterministic_id(group, size),
            deterministic_sku(group, size),
            "bead",
            meta["category"],
            group.series,
            group.material_code,
            "天然级",
            group.series,
            meta["effect"],
            meta["element"],
            meta["price"],
            float(size),
            round((size / 8) ** 3 * 1.2, 2),
            meta["color"],
            meta["shine"],
            0,
            10,
            "",
            "",
            image_path,
            primary_url,
            urls_json,
            meta["stock"],
            1,
            int(meta["sort_order"]) + offset,
            now,
            now,
        ),
    )


def bind_groups(groups: list[AssetGroup], create_missing: bool) -> dict[str, int]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    stats = {"groups": 0, "updated_rows": 0, "created_rows": 0, "created_groups": 0, "skipped_groups": 0}
    with connect_database() as connection:
        total = len(groups)
        for index, group in enumerate(groups, start=1):
            existing = select_existing_rows(connection, group)
            meta = meta_for_group(group, existing)
            image_path = material_image_path(group.keys[0])
            primary_url = group.urls[0]
            urls_json = json.dumps(group.urls, ensure_ascii=False)
            if existing:
                existing_sizes = {int(round(float(row.get("size") or 0))) for row in existing}
                for row in existing:
                    connection.execute(
                        """
                        UPDATE managed_materials
                        SET image_path=?, image_url=?, image_urls_json=?, material_code=?, updated_at=?
                        WHERE id=?
                        """,
                        (image_path, primary_url, urls_json, group.material_code, now, row["id"]),
                    )
                    stats["updated_rows"] += 1
                for offset, size in enumerate(SIZES):
                    if size not in existing_sizes:
                        insert_material_row(connection, group, meta, size, offset, now)
                        stats["created_rows"] += 1
            else:
                if not create_missing:
                    stats["skipped_groups"] += 1
                    continue
                stats["created_groups"] += 1
                for offset, size in enumerate(SIZES):
                    insert_material_row(connection, group, meta, size, offset, now)
                    stats["created_rows"] += 1
            stats["groups"] += 1
            if index == 1 or index % 10 == 0 or index == total:
                print(
                    f"bound={index}/{total} updated_rows={stats['updated_rows']} created_rows={stats['created_rows']}",
                    flush=True,
                )
        try:
            from app.materials import invalidate_material_cache

            invalidate_material_cache()
        except Exception:
            pass
    return stats


def print_preview(groups: list[AssetGroup]) -> None:
    with connect_database() as connection:
        for group in groups:
            existing = select_existing_rows(connection, group)
            action = "update" if existing else "create"
            print(
                f"{action:6s} code={group.material_code:<28s} series={group.series} "
                f"assets={len(group.files)} rows={len(existing)} slug={group.slug}"
            )


def main() -> None:
    load_local_env(ROOT / ".env")
    load_local_env(ROOT / ".env.local")
    load_local_env(ROOT / ".env.test")
    args = parse_args()
    validate_runtime(args)
    groups = load_asset_groups(args)
    print_preview(groups)
    print(f"groups={len(groups)} assets={sum(len(group.files) for group in groups)} dry_run={args.dry_run}")
    if args.dry_run:
        return
    validate_cos_args(args)
    if not args.skip_upload:
        upload_groups(args, groups)
    backup = backup_database()
    stats = bind_groups(groups, create_missing=args.create_missing)
    print(f"database_backup={backup}")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
