from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Any

from .avatar_storage import AvatarStorage
from .daily_rules import (
    DAILY_RULES_SETTING_KEY,
    default_daily_energy_rules,
    daily_rules_version,
    normalize_daily_energy_rules,
    public_daily_rules_payload,
)
from .materials import (
    MATERIAL_CATALOG,
    clean_image_urls,
    invalidate_material_cache,
    material_url_from_path,
    normalize_material_image_url,
)
from .material_knowledge import (
    enrich_material_with_knowledge,
    enrich_materials_with_knowledge,
    has_explicit_knowledge,
    infer_material_code_from_text,
    material_code_from_payload,
    material_code_token,
    upsert_material_knowledge,
)
from .material_options import (
    element_label,
    normalize_element_key,
    public_material_field_specs,
    public_material_options,
    stable_key,
)
from .repository import DB_PATH
from .database import connect_database, integrity_errors, use_mysql
from .wechat_trade_service import WechatTradeService


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def json_text(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def json_value(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return [] if default is None else default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [] if default is None else default


ADMIN_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{3,40}$")
ADMIN_MANAGER_ROLES = {"admin", "super_admin", "owner"}
ADMIN_ALLOWED_ROLES = {"admin", "operator", "viewer"}
ADMIN_ALLOWED_STATUS = {"active", "disabled"}
ADMIN_MAX_FAILED_LOGIN = 5
ADMIN_LOCK_MINUTES = 15
MATERIAL_REQUIRED_BEAD_SIZES = tuple(range(8, 16))
MATERIAL_OPTION_TYPE_LABELS = {
    "wish_pools": "适用愿景池",
    "chakras": "对应脉轮",
    "color_families": "色彩倾向",
    "grades": "品质等级",
    "effects": "核心功效标签",
    "mood_tags": "情绪标签",
    "visual_tags": "视觉标签",
    "roles": "材料角色",
    "match_rules": "搭配规则",
    "care_tags": "佩戴养护",
    "bead_shapes": "珠体形制",
    "surface_finishes": "表面工艺",
    "transparency_levels": "通透度",
    "texture_features": "纹理/内含特征",
    "batch_variation_levels": "批次差异",
}
MUTABLE_MATERIAL_OPTION_TYPES = set(MATERIAL_OPTION_TYPE_LABELS)
WAREHOUSE_GRADE_OPTIONS = [
    {"key": "ungraded", "label": "未分级"},
    {"key": "entry", "label": "入门级"},
    {"key": "standard", "label": "常规级"},
    {"key": "selected", "label": "精选级"},
    {"key": "premium", "label": "高货级"},
    {"key": "collector", "label": "收藏级"},
    {"key": "flawed", "label": "瑕疵/练手"},
    {"key": "mixed", "label": "混装"},
]
WAREHOUSE_UNIT_OPTIONS = [
    {"key": "piece", "label": "颗"},
    {"key": "strand", "label": "串"},
    {"key": "gram", "label": "克"},
    {"key": "kg", "label": "千克"},
    {"key": "pack", "label": "包"},
    {"key": "box", "label": "盒"},
    {"key": "pair", "label": "对"},
    {"key": "meter", "label": "米"},
]


def zodiac_from_birthday(value: str | None) -> str:
    if not value:
        return ""
    try:
        _, month, day = [int(part) for part in value[:10].split("-")]
    except (ValueError, TypeError):
        return ""
    signs = [
        ((1, 20), "水瓶座"), ((2, 19), "双鱼座"), ((3, 21), "白羊座"),
        ((4, 20), "金牛座"), ((5, 21), "双子座"), ((6, 22), "巨蟹座"),
        ((7, 23), "狮子座"), ((8, 23), "处女座"), ((9, 23), "天秤座"),
        ((10, 24), "天蝎座"), ((11, 23), "射手座"), ((12, 22), "摩羯座"),
    ]
    for (start_month, start_day), sign in reversed(signs):
        if (month, day) >= (start_month, start_day):
            return sign
    return "摩羯座"


def energy_tags_from_assessment(result: dict[str, Any]) -> dict[str, Any]:
    input_summary = result.get("input_summary") or {}
    profile = result.get("final_energy_profile") or {}
    sorted_profile = sorted(profile.items(), key=lambda item: float(item[1] or 0))
    support = [name for name, _ in sorted_profile[:2]]
    dominant = [name for name, _ in sorted(profile.items(), key=lambda item: float(item[1] or 0), reverse=True)[:2]]
    tags = []
    if input_summary.get("mbti"):
        tags.append(str(input_summary["mbti"]).upper())
    zodiac = zodiac_from_birthday(input_summary.get("birthday"))
    if zodiac:
        tags.append(zodiac)
    if support:
        tags.append("喜" + "".join(support))
    return {
        "mbti": str(input_summary.get("mbti") or "").upper(),
        "zodiac": zodiac,
        "support_elements": support,
        "dominant_elements": dominant,
        "energy_profile": profile,
        "tags": tags,
        "input_summary": input_summary,
    }


class AdminService:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._force_sqlite = db_path != DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.wechat_trade = WechatTradeService()
        self.init_db()

    def connect(self):
        return connect_database(self.db_path if self._force_sqlite else None)

    def table_exists(self, connection, table_name: str) -> bool:
        if use_mysql() and not self._force_sqlite:
            row = connection.execute(
                """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = ?
                """,
                (table_name,),
            ).fetchone()
            return bool(row and row["c"])
        return bool(connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone())

    def init_db(self) -> None:
        if use_mysql() and not self._force_sqlite:
            with self.connect() as connection:
                self._ensure_admin_security_schema(connection)
                count = connection.execute("SELECT COUNT(*) AS c FROM managed_materials").fetchone()["c"]
                self._ensure_material_columns(connection)
                self._ensure_material_knowledge_columns(connection)
                self._ensure_community_post_columns(connection)
                if count == 0:
                    self._seed_materials(connection)
                self._ensure_material_taxonomy_schema(connection)
                self._sync_material_taxonomy_from_materials(connection)
                self._repair_material_code_collisions(connection)
                self._ensure_material_option_schema(connection)
                self._seed_material_option_items(connection)
                self._ensure_material_audit_schema(connection)
                self._ensure_warehouse_defaults(connection)
                block_count = connection.execute("SELECT COUNT(*) AS c FROM content_blocks").fetchone()["c"]
                if block_count == 0:
                    self._seed_blocks(connection)
                banner_count = connection.execute("SELECT COUNT(*) AS c FROM home_banners").fetchone()["c"]
                if banner_count == 0:
                    self._seed_home_banners(connection)
            return
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_users (
                    admin_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    role TEXT NOT NULL,
                    display_name TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    failed_login_count INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    last_login_at TEXT,
                    last_login_ip TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    token TEXT PRIMARY KEY,
                    admin_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_admin_security_schema(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS managed_materials (
                    id TEXT PRIMARY KEY,
                    skuId TEXT NOT NULL,
                    top TEXT NOT NULL,
                    category TEXT NOT NULL,
                    series TEXT NOT NULL DEFAULT '',
                    material_code TEXT NOT NULL DEFAULT '',
                    grade TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL,
                    effect TEXT NOT NULL,
                    element TEXT NOT NULL,
                    price REAL NOT NULL,
                    size REAL NOT NULL,
                    weight REAL NOT NULL,
                    cost_price REAL NOT NULL DEFAULT 0,
                    safety_stock INTEGER NOT NULL DEFAULT 0,
                    supplier_name TEXT NOT NULL DEFAULT '',
                    purchase_note TEXT,
                    color TEXT NOT NULL,
                    shine TEXT NOT NULL,
                    image_path TEXT,
                    image_url TEXT,
                    image_urls_json TEXT,
                    stock INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_material_columns(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS material_knowledge (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    primary_element TEXT NOT NULL DEFAULT '',
                    secondary_elements_json TEXT NOT NULL,
                    chakras_json TEXT NOT NULL,
                    chakra_weights_json TEXT NOT NULL,
                    effects_json TEXT NOT NULL,
                    wish_pools_json TEXT NOT NULL,
                    color_family TEXT NOT NULL DEFAULT '',
                    mood_tags_json TEXT NOT NULL,
                    visual_tags_json TEXT NOT NULL,
                    story TEXT,
                    allowed_roles_json TEXT NOT NULL,
                    conflict_codes_json TEXT NOT NULL,
                    match_rules_json TEXT NOT NULL,
                    care_tags_json TEXT NOT NULL,
                    material_params_json TEXT NOT NULL,
                    asset_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_material_knowledge_columns(connection)
            self._ensure_material_taxonomy_schema(connection)
            self._ensure_material_option_schema(connection)
            self._ensure_material_audit_schema(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS content_blocks (
                    block_id TEXT PRIMARY KEY,
                    section TEXT NOT NULL,
                    title TEXT NOT NULL,
                    subtitle TEXT,
                    body TEXT,
                    image_url TEXT,
                    action_text TEXT,
                    action_url TEXT,
                    status TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS home_banners (
                    banner_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    subtitle TEXT,
                    eyebrow TEXT,
                    image_url TEXT,
                    action_text TEXT,
                    action_url TEXT,
                    theme TEXT NOT NULL DEFAULT 'dark',
                    status TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS community_posts (
                    post_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    description TEXT,
                    story TEXT,
                    scene TEXT,
                    author_note TEXT,
                    likes INTEGER NOT NULL DEFAULT 0,
                    tone TEXT,
                    recipe_json TEXT NOT NULL,
                    materials_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    image_url TEXT,
                    is_home_hot INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_community_post_columns(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS recommendation_plans (
                    plan_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    subtitle TEXT,
                    description TEXT,
                    price REAL NOT NULL DEFAULT 0,
                    tone TEXT,
                    recipe_json TEXT NOT NULL,
                    materials_json TEXT NOT NULL,
                    design_story TEXT,
                    design_reason TEXT,
                    scenes_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    image_url TEXT,
                    is_home_hot INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS system_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_warehouse_schema(connection)
            count = connection.execute("SELECT COUNT(*) AS c FROM managed_materials").fetchone()["c"]
            if count == 0:
                self._seed_materials(connection)
            self._sync_material_taxonomy_from_materials(connection)
            self._repair_material_code_collisions(connection)
            self._seed_material_option_items(connection)
            block_count = connection.execute("SELECT COUNT(*) AS c FROM content_blocks").fetchone()["c"]
            if block_count == 0:
                self._seed_blocks(connection)
            banner_count = connection.execute("SELECT COUNT(*) AS c FROM home_banners").fetchone()["c"]
            if banner_count == 0:
                self._seed_home_banners(connection)
            self._ensure_warehouse_defaults(connection)

    def _seed_materials(self, connection) -> None:
        timestamp = now_iso()
        for index, item in enumerate(MATERIAL_CATALOG):
            image_path = item.get("image_path")
            image_url = item.get("image_url") or (
                material_url_from_path(image_path) if image_path else ""
            )
            connection.execute(
                """
                INSERT INTO managed_materials
                (id, skuId, top, category, series, material_code, grade, name, effect, element, price, size, weight, color, shine,
                 image_path, image_url, image_urls_json, enabled, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    item["id"],
                    item["skuId"],
                    item["top"],
                    item["category"],
                    item.get("series") or item["name"],
                    item.get("material_code") or material_code_from_payload(item),
                    item.get("grade", ""),
                    item["name"],
                    item["effect"],
                    item["element"],
                    item["price"],
                    item["size"],
                    item["weight"],
                    item["color"],
                    item["shine"],
                    image_path,
                    image_url,
                    json_text(clean_image_urls(item.get("image_urls"), image_url, image_path or "")),
                    index,
                    timestamp,
                    timestamp,
                ),
            )
            upsert_material_knowledge(item, item, connection=connection, force_update=False)

    def _ensure_admin_security_schema(self, connection) -> None:
        if use_mysql() and not self._force_sqlite:
            rows = connection.execute("SHOW COLUMNS FROM admin_users").fetchall()
            columns = {row["Field"] for row in rows}
            additions = {
                "display_name": "ALTER TABLE admin_users ADD COLUMN display_name VARCHAR(120)",
                "status": "ALTER TABLE admin_users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'",
                "failed_login_count": "ALTER TABLE admin_users ADD COLUMN failed_login_count INT NOT NULL DEFAULT 0",
                "locked_until": "ALTER TABLE admin_users ADD COLUMN locked_until VARCHAR(40)",
                "last_login_at": "ALTER TABLE admin_users ADD COLUMN last_login_at VARCHAR(40)",
                "last_login_ip": "ALTER TABLE admin_users ADD COLUMN last_login_ip VARCHAR(80)",
            }
            for column, sql in additions.items():
                if column not in columns:
                    connection.execute(sql)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_login_logs (
                  log_id VARCHAR(80) PRIMARY KEY,
                  admin_id VARCHAR(80),
                  username VARCHAR(100) NOT NULL,
                  success TINYINT NOT NULL DEFAULT 0,
                  reason VARCHAR(80) NOT NULL,
                  ip VARCHAR(80),
                  user_agent VARCHAR(500),
                  created_at VARCHAR(40) NOT NULL,
                  INDEX idx_admin_login_logs_created (created_at),
                  INDEX idx_admin_login_logs_username (username, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            connection.execute("UPDATE admin_users SET status = 'active' WHERE COALESCE(status, '') = ''")
            connection.execute("UPDATE admin_users SET display_name = username WHERE COALESCE(display_name, '') = ''")
            return

        columns = {row["name"] for row in connection.execute("PRAGMA table_info(admin_users)").fetchall()}
        additions = {
            "display_name": "ALTER TABLE admin_users ADD COLUMN display_name TEXT",
            "status": "ALTER TABLE admin_users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
            "failed_login_count": "ALTER TABLE admin_users ADD COLUMN failed_login_count INTEGER NOT NULL DEFAULT 0",
            "locked_until": "ALTER TABLE admin_users ADD COLUMN locked_until TEXT",
            "last_login_at": "ALTER TABLE admin_users ADD COLUMN last_login_at TEXT",
            "last_login_ip": "ALTER TABLE admin_users ADD COLUMN last_login_ip TEXT",
        }
        for column, sql in additions.items():
            if column not in columns:
                connection.execute(sql)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_login_logs (
                log_id TEXT PRIMARY KEY,
                admin_id TEXT,
                username TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 0,
                reason TEXT NOT NULL,
                ip TEXT,
                user_agent TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute("UPDATE admin_users SET status = 'active' WHERE COALESCE(status, '') = ''")
        connection.execute("UPDATE admin_users SET display_name = username WHERE COALESCE(display_name, '') = ''")

    def _ensure_material_columns(self, connection) -> None:
        if use_mysql() and not self._force_sqlite:
            rows = connection.execute("SHOW COLUMNS FROM managed_materials").fetchall()
            columns = {row["Field"] for row in rows}
            if "series" not in columns:
                connection.execute("ALTER TABLE managed_materials ADD COLUMN series VARCHAR(160) NOT NULL DEFAULT ''")
            if "material_code" not in columns:
                connection.execute("ALTER TABLE managed_materials ADD COLUMN material_code VARCHAR(160) NOT NULL DEFAULT ''")
            if "grade" not in columns:
                connection.execute("ALTER TABLE managed_materials ADD COLUMN grade VARCHAR(40) NOT NULL DEFAULT ''")
            if "stock" not in columns:
                connection.execute("ALTER TABLE managed_materials ADD COLUMN stock INT NOT NULL DEFAULT 0")
            if "image_urls_json" not in columns:
                connection.execute("ALTER TABLE managed_materials ADD COLUMN image_urls_json LONGTEXT")
            if "cost_price" not in columns:
                connection.execute("ALTER TABLE managed_materials ADD COLUMN cost_price DOUBLE NOT NULL DEFAULT 0")
            if "safety_stock" not in columns:
                connection.execute("ALTER TABLE managed_materials ADD COLUMN safety_stock INT NOT NULL DEFAULT 0")
            if "supplier_name" not in columns:
                connection.execute("ALTER TABLE managed_materials ADD COLUMN supplier_name VARCHAR(255) NOT NULL DEFAULT ''")
            if "purchase_note" not in columns:
                connection.execute("ALTER TABLE managed_materials ADD COLUMN purchase_note TEXT")
            connection.execute("UPDATE managed_materials SET series = name WHERE COALESCE(series, '') = ''")
            return
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(managed_materials)").fetchall()}
        if "series" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN series TEXT NOT NULL DEFAULT ''")
        if "material_code" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN material_code TEXT NOT NULL DEFAULT ''")
        if "grade" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN grade TEXT NOT NULL DEFAULT ''")
        if "stock" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN stock INTEGER NOT NULL DEFAULT 0")
        if "image_urls_json" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN image_urls_json TEXT")
        if "cost_price" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN cost_price REAL NOT NULL DEFAULT 0")
        if "safety_stock" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN safety_stock INTEGER NOT NULL DEFAULT 0")
        if "supplier_name" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN supplier_name TEXT NOT NULL DEFAULT ''")
        if "purchase_note" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN purchase_note TEXT")
        connection.execute("UPDATE managed_materials SET series = name WHERE COALESCE(series, '') = ''")

    def _ensure_material_knowledge_columns(self, connection) -> None:
        if not self.table_exists(connection, "material_knowledge"):
            return
        additions = {
            "match_rules_json": "[]",
            "care_tags_json": "[]",
        }
        if use_mysql() and not self._force_sqlite:
            rows = connection.execute("SHOW COLUMNS FROM material_knowledge").fetchall()
            columns = {row["Field"] for row in rows}
            for column, default_value in additions.items():
                if column not in columns:
                    connection.execute(
                        f"ALTER TABLE material_knowledge ADD COLUMN {column} LONGTEXT"
                    )
                    connection.execute(
                        f"UPDATE material_knowledge SET {column} = ? WHERE COALESCE({column}, '') = ''",
                        (default_value,),
                    )
            return
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(material_knowledge)").fetchall()}
        for column, default_value in additions.items():
            if column not in columns:
                connection.execute(f"ALTER TABLE material_knowledge ADD COLUMN {column} TEXT NOT NULL DEFAULT '{default_value}'")

    @staticmethod
    def material_taxonomy_id(kind: str, top: str, name: str, parent_id: str = "") -> str:
        parts = [kind, stable_key(top or "bead", "top")]
        if parent_id:
            parts.append(stable_key(parent_id, "parent")[:18])
        parts.append(stable_key(name, kind))
        return "_".join(parts)[:96]

    @staticmethod
    def material_option_id(option_type: str, option_key: str) -> str:
        return f"opt_{stable_key(option_type, 'type')}_{stable_key(option_key, 'item')}"[:120]

    def _ensure_material_taxonomy_schema(self, connection) -> None:
        if use_mysql() and not self._force_sqlite:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS material_taxonomy (
                    item_id VARCHAR(120) PRIMARY KEY,
                    parent_id VARCHAR(120) NOT NULL DEFAULT '',
                    kind VARCHAR(20) NOT NULL,
                    top VARCHAR(40) NOT NULL DEFAULT 'bead',
                    name VARCHAR(160) NOT NULL,
                    sort_order INT NOT NULL DEFAULT 0,
                    enabled TINYINT NOT NULL DEFAULT 1,
                    created_at VARCHAR(40) NOT NULL,
                    updated_at VARCHAR(40) NOT NULL
                )
                """
            )
            return
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS material_taxonomy (
                item_id TEXT PRIMARY KEY,
                parent_id TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL,
                top TEXT NOT NULL DEFAULT 'bead',
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    def _upsert_taxonomy_if_missing(
        self,
        connection,
        *,
        kind: str,
        top: str,
        name: str,
        parent_id: str = "",
        sort_order: int = 0,
    ) -> str:
        clean_name = str(name or "").strip()
        if not clean_name:
            return ""
        item_id = self.material_taxonomy_id(kind, top, clean_name, parent_id)
        existing = connection.execute("SELECT item_id FROM material_taxonomy WHERE item_id = ?", (item_id,)).fetchone()
        if not existing:
            timestamp = now_iso()
            connection.execute(
                """
                INSERT INTO material_taxonomy
                (item_id, parent_id, kind, top, name, sort_order, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (item_id, parent_id, kind, top or "bead", clean_name, sort_order, timestamp, timestamp),
            )
        return item_id

    def _sync_material_taxonomy_from_materials(self, connection) -> None:
        self._ensure_material_taxonomy_schema(connection)
        rows = connection.execute(
            """
            SELECT top, category, series, MIN(sort_order) AS sort_order
            FROM managed_materials
            WHERE COALESCE(category, '') <> ''
            GROUP BY top, category, series
            ORDER BY MIN(sort_order), category, series
            """
        ).fetchall()
        for row in rows:
            top = row["top"] or "bead"
            category = row["category"] or ""
            series = row["series"] or ""
            sort_order = int(row["sort_order"] or 0)
            category_id = self._upsert_taxonomy_if_missing(
                connection,
                kind="category",
                top=top,
                name=category,
                sort_order=sort_order,
            )
            if series:
                self._upsert_taxonomy_if_missing(
                    connection,
                    kind="series",
                    top=top,
                    name=series,
                    parent_id=category_id,
                    sort_order=sort_order,
                )

    def _repair_material_code_collisions(self, connection) -> None:
        """修复历史编辑导致的「品种正确、内部编码仍是旧品种」问题。"""
        if not self.table_exists(connection, "managed_materials"):
            return
        rows = connection.execute(
            """
            SELECT id, top, category, series, name, effect, image_path, image_url, material_code
            FROM managed_materials
            WHERE COALESCE(material_code, '') <> ''
            """
        ).fetchall()
        timestamp = now_iso()
        changed = False
        for row in rows:
            payload = dict(row)
            current = material_code_token(payload.get("material_code"))
            inferred = infer_material_code_from_text(payload)
            if current == "colorful_phantom" and inferred == "four_seasons_phantom":
                connection.execute(
                    "UPDATE managed_materials SET material_code = ?, updated_at = ? WHERE id = ?",
                    (inferred, timestamp, payload["id"]),
                )
                changed = True
        if changed:
            invalidate_material_cache()

    def material_options_payload(self) -> dict[str, Any]:
        with self.connect() as connection:
            self._ensure_material_taxonomy_schema(connection)
            self._sync_material_taxonomy_from_materials(connection)
            self._ensure_material_option_schema(connection)
            self._seed_material_option_items(connection)
            options = public_material_options()
            option_items = self.list_material_option_items(connection=connection, include_disabled=True)
            enabled_by_type: dict[str, list[dict[str, Any]]] = {}
            for item in option_items:
                if item["enabled"]:
                    enabled_by_type.setdefault(item["option_type"], []).append(
                        {"key": item["key"], "label": item["label"]}
                    )
            for option_type in MUTABLE_MATERIAL_OPTION_TYPES:
                if enabled_by_type.get(option_type):
                    options[option_type] = enabled_by_type[option_type]
            field_specs = public_material_field_specs()
            option_type_specs = {item.get("key"): item for item in field_specs.get("option_types", [])}
            return {
                **options,
                "taxonomy": self.list_material_taxonomy(connection=connection, include_disabled=True),
                "option_items": option_items,
                "option_types": [
                    {**option_type_specs.get(key, {}), "key": key, "label": label}
                    for key, label in MATERIAL_OPTION_TYPE_LABELS.items()
                ],
                "field_specs": field_specs,
            }

    @staticmethod
    def material_payload_list(value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            if value.strip().startswith("["):
                parsed = json_value(value, [])
                value = parsed if isinstance(parsed, list) else [value]
            else:
                value = re.split(r"[,，、\n\r]+", value)
        if not isinstance(value, list):
            value = [value]
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def material_option_lookup(self, connection) -> dict[str, dict[str, str]]:
        defaults = public_material_options()
        lookup: dict[str, dict[str, str]] = {}

        def add(option_type: str, key: Any, label: Any = "") -> None:
            key_text = str(key or "").strip()
            label_text = str(label or "").strip()
            if not key_text:
                return
            bucket = lookup.setdefault(option_type, {})
            for alias in {key_text, key_text.lower(), label_text, label_text.lower()}:
                if alias:
                    bucket[alias] = key_text

        for option_type, items in defaults.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    add(option_type, item.get("key"), item.get("label"))
        for item in self.list_material_option_items(connection=connection, include_disabled=False):
            add(item.get("option_type") or "", item.get("key"), item.get("label"))
        return lookup

    def canonical_material_option_value(
        self,
        value: Any,
        option_type: str,
        lookup: dict[str, dict[str, str]],
        label: str,
        required: bool = False,
    ) -> str:
        text = str(value or "").strip()
        if not text:
            if required:
                raise ValueError(f"{label} 不能为空")
            return ""
        key = lookup.get(option_type, {}).get(text) or lookup.get(option_type, {}).get(text.lower())
        if not key:
            raise ValueError(f"{label} 包含未维护选项：{text}，请先到字段字典维护")
        return key

    def canonical_material_option_list(
        self,
        value: Any,
        option_type: str,
        lookup: dict[str, dict[str, str]],
        label: str,
        required: bool = False,
    ) -> list[str]:
        raw_items = self.material_payload_list(value)
        result: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            key = self.canonical_material_option_value(item, option_type, lookup, label)
            if key and key not in seen:
                result.append(key)
                seen.add(key)
        if required and not result:
            raise ValueError(f"{label} 不能为空")
        return result

    def canonicalize_material_payload_options(self, payload: dict[str, Any], connection) -> dict[str, Any]:
        lookup = self.material_option_lookup(connection)
        clean = dict(payload)
        clean["primary_element"] = self.canonical_material_option_value(
            clean.get("primary_element") or clean.get("element"),
            "elements",
            lookup,
            "主五行",
            required=True,
        )
        if "secondary_elements" in clean or "secondary_element" in clean:
            clean["secondary_elements"] = self.canonical_material_option_list(
                clean.get("secondary_elements") or clean.get("secondary_element"),
                "elements",
                lookup,
                "副五行",
            )
        if clean.get("grade"):
            clean["grade"] = self.canonical_material_option_value(clean.get("grade"), "grades", lookup, "品质等级")
        if clean.get("color_family"):
            clean["color_family"] = self.canonical_material_option_value(
                clean.get("color_family"),
                "color_families",
                lookup,
                "色彩倾向",
            )
        explicit_effects = self.material_payload_list(clean.get("effects"))
        if explicit_effects:
            clean["effects"] = self.canonical_material_option_list(
                explicit_effects,
                "effects",
                lookup,
                "核心功效",
                required=True,
            )
            clean["_legacy_effect_is_structured"] = True
        elif clean.get("effect"):
            try:
                clean["effects"] = [
                    self.canonical_material_option_value(clean.get("effect"), "effects", lookup, "核心功效")
                ]
                clean["_legacy_effect_is_structured"] = True
            except ValueError:
                clean["effects"] = []
                clean["_legacy_effect_is_structured"] = False
        else:
            clean["effects"] = []
            clean["_legacy_effect_is_structured"] = False
        for field, option_type, label, required in (
            ("chakras", "chakras", "对应脉轮", False),
            ("wish_pools", "wish_pools", "适用愿景", False),
            ("mood_tags", "mood_tags", "情绪标签", False),
            ("visual_tags", "visual_tags", "视觉标签", False),
            ("allowed_roles", "roles", "允许角色", False),
            ("match_rules", "match_rules", "搭配规则", False),
            ("care_tags", "care_tags", "佩戴养护", False),
        ):
            if field in clean or required:
                clean[field] = self.canonical_material_option_list(
                    clean.get(field),
                    option_type,
                    lookup,
                    label,
                    required=required,
                )
        material_params = clean.get("material_params")
        material_params = dict(material_params) if isinstance(material_params, dict) else {}
        for field, option_type, label in (
            ("bead_shape", "bead_shapes", "珠体形制"),
            ("surface_finish", "surface_finishes", "表面工艺"),
            ("transparency_level", "transparency_levels", "通透度"),
            ("batch_variation", "batch_variation_levels", "批次差异"),
        ):
            raw_value = clean.get(field) if clean.get(field) not in (None, "") else material_params.get(field)
            if raw_value not in (None, ""):
                canonical = self.canonical_material_option_value(raw_value, option_type, lookup, label)
                clean[field] = canonical
                material_params[field] = canonical
        raw_texture = clean.get("texture_features") or material_params.get("texture_features")
        if raw_texture:
            texture_features = self.canonical_material_option_list(
                raw_texture,
                "texture_features",
                lookup,
                "纹理/内含特征",
            )
            clean["texture_features"] = texture_features
            material_params["texture_features"] = texture_features
        clean["material_params"] = material_params
        return clean

    def canonicalize_material_payload_taxonomy(self, payload: dict[str, Any], connection) -> dict[str, Any]:
        self._ensure_material_taxonomy_schema(connection)
        clean = dict(payload)
        top = str(clean.get("top") or "bead").strip()
        category_name = str(clean.get("category") or "").strip()
        series_name = str(clean.get("series") or clean.get("name") or "").strip()
        if not category_name:
            raise ValueError("分类不能为空，请先到分类/品种维护")
        if not series_name:
            raise ValueError("品种不能为空，请先到分类/品种维护")
        category = connection.execute(
            """
            SELECT * FROM material_taxonomy
            WHERE kind='category' AND top=? AND name=? AND enabled=1
            """,
            (top, category_name),
        ).fetchone()
        if not category:
            raise ValueError(f"分类未维护或已停用：{category_name}，请先到分类/品种维护")
        series = connection.execute(
            """
            SELECT * FROM material_taxonomy
            WHERE kind='series' AND parent_id=? AND name=? AND enabled=1
            """,
            (category["item_id"], series_name),
        ).fetchone()
        if not series:
            raise ValueError(f"品种未维护或已停用：{category_name} / {series_name}，请先到分类/品种维护")
        clean["top"] = category["top"] or top
        clean["category"] = category["name"]
        clean["series"] = series["name"]
        return clean

    def list_material_taxonomy(
        self,
        top: str = "",
        include_disabled: bool = False,
        connection: Any | None = None,
    ) -> list[dict[str, Any]]:
        def run(conn) -> list[dict[str, Any]]:
            self._ensure_material_taxonomy_schema(conn)
            clauses = []
            params: list[Any] = []
            if top:
                clauses.append("top = ?")
                params.append(top)
            if not include_disabled:
                clauses.append("enabled = 1")
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = conn.execute(
                f"SELECT * FROM material_taxonomy {where} ORDER BY sort_order ASC, name ASC",
                params,
            ).fetchall()
            categories: dict[str, dict[str, Any]] = {}
            for raw in rows:
                row = dict(raw)
                item = {
                    "id": row["item_id"],
                    "parent_id": row.get("parent_id") or "",
                    "kind": row["kind"],
                    "top": row["top"],
                    "name": row["name"],
                    "sort_order": row["sort_order"],
                    "enabled": bool(row["enabled"]),
                }
                if item["kind"] == "category":
                    item["series"] = []
                    categories[item["id"]] = item
            for raw in rows:
                row = dict(raw)
                if row["kind"] != "series":
                    continue
                parent_id = row.get("parent_id") or ""
                series_item = {
                    "id": row["item_id"],
                    "parent_id": parent_id,
                    "kind": row["kind"],
                    "top": row["top"],
                    "name": row["name"],
                    "sort_order": row["sort_order"],
                    "enabled": bool(row["enabled"]),
                }
                if parent_id in categories:
                    categories[parent_id]["series"].append(series_item)
            return list(categories.values())

        if connection is not None:
            return run(connection)
        with self.connect() as conn:
            return run(conn)

    def save_material_category(self, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
        top = str(payload.get("top") or "bead").strip()
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("分类名称不能为空")
        item_id = str(payload.get("id") or self.material_taxonomy_id("category", top, name)).strip()
        sort_order = int(payload.get("sort_order") or 0)
        enabled = 1 if payload.get("enabled", True) else 0
        timestamp = now_iso()
        with self.connect() as connection:
            self._ensure_material_taxonomy_schema(connection)
            existing = connection.execute("SELECT * FROM material_taxonomy WHERE item_id = ?", (item_id,)).fetchone()
            before = dict(existing) if existing else None
            if existing:
                connection.execute(
                    """
                    UPDATE material_taxonomy
                    SET top=?, name=?, sort_order=?, enabled=?, updated_at=?
                    WHERE item_id=?
                    """,
                    (top, name, sort_order, enabled, timestamp, item_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO material_taxonomy
                    (item_id, parent_id, kind, top, name, sort_order, enabled, created_at, updated_at)
                    VALUES (?, '', 'category', ?, ?, ?, ?, ?, ?)
                    """,
                    (item_id, top, name, sort_order, enabled, timestamp, timestamp),
                )
            after = {
                "item_id": item_id,
                "parent_id": "",
                "kind": "category",
                "top": top,
                "name": name,
                "sort_order": sort_order,
                "enabled": enabled,
            }
            self.record_material_audit(
                connection,
                action="taxonomy_update" if before else "taxonomy_create",
                target_type="material_taxonomy",
                target_id=item_id,
                before=before,
                after=after,
                actor=actor,
                summary=("更新材料分类：" if before else "新增材料分类：") + name,
            )
        return {"id": item_id, "top": top, "name": name, "sort_order": sort_order, "enabled": bool(enabled)}

    def save_material_series(self, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
        category_id = str(payload.get("category_id") or "").strip()
        name = str(payload.get("name") or "").strip()
        if not category_id:
            raise ValueError("请选择分类")
        if not name:
            raise ValueError("品种名称不能为空")
        sort_order = int(payload.get("sort_order") or 0)
        enabled = 1 if payload.get("enabled", True) else 0
        timestamp = now_iso()
        with self.connect() as connection:
            self._ensure_material_taxonomy_schema(connection)
            category = connection.execute(
                "SELECT * FROM material_taxonomy WHERE item_id = ? AND kind = 'category'",
                (category_id,),
            ).fetchone()
            if not category:
                raise ValueError("分类不存在")
            top = category["top"] or str(payload.get("top") or "bead").strip()
            item_id = str(payload.get("id") or self.material_taxonomy_id("series", top, name, category_id)).strip()
            existing = connection.execute("SELECT * FROM material_taxonomy WHERE item_id = ?", (item_id,)).fetchone()
            before = dict(existing) if existing else None
            if existing:
                connection.execute(
                    """
                    UPDATE material_taxonomy
                    SET parent_id=?, top=?, name=?, sort_order=?, enabled=?, updated_at=?
                    WHERE item_id=?
                    """,
                    (category_id, top, name, sort_order, enabled, timestamp, item_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO material_taxonomy
                    (item_id, parent_id, kind, top, name, sort_order, enabled, created_at, updated_at)
                    VALUES (?, ?, 'series', ?, ?, ?, ?, ?, ?)
                    """,
                    (item_id, category_id, top, name, sort_order, enabled, timestamp, timestamp),
                )
            after = {
                "item_id": item_id,
                "parent_id": category_id,
                "kind": "series",
                "top": top,
                "name": name,
                "sort_order": sort_order,
                "enabled": enabled,
            }
            self.record_material_audit(
                connection,
                action="taxonomy_update" if before else "taxonomy_create",
                target_type="material_taxonomy",
                target_id=item_id,
                before=before,
                after=after,
                actor=actor,
                summary=("更新材料品种：" if before else "新增材料品种：") + name,
            )
        return {
            "id": item_id,
            "category_id": category_id,
            "top": top,
            "name": name,
            "sort_order": sort_order,
            "enabled": bool(enabled),
        }

    def disable_material_taxonomy_item(self, item_id: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
        clean_id = str(item_id or "").strip()
        if not clean_id:
            raise ValueError("请选择要停用的分类或品种")
        timestamp = now_iso()
        with self.connect() as connection:
            self._ensure_material_taxonomy_schema(connection)
            row = connection.execute("SELECT * FROM material_taxonomy WHERE item_id = ?", (clean_id,)).fetchone()
            if not row:
                raise ValueError("分类或品种不存在")
            before = dict(row)
            connection.execute(
                "UPDATE material_taxonomy SET enabled=0, updated_at=? WHERE item_id=? OR parent_id=?",
                (timestamp, clean_id, clean_id),
            )
            after = {**before, "enabled": 0, "updated_at": timestamp}
            self.record_material_audit(
                connection,
                action="taxonomy_disable",
                target_type="material_taxonomy",
                target_id=clean_id,
                before=before,
                after=after,
                actor=actor,
                summary=f"停用材料{'分类' if before.get('kind') == 'category' else '品种'}：{before.get('name') or clean_id}",
            )
        return {"disabled": clean_id}

    def _ensure_material_option_schema(self, connection) -> None:
        if use_mysql() and not self._force_sqlite:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS material_option_items (
                    item_id VARCHAR(120) PRIMARY KEY,
                    option_type VARCHAR(40) NOT NULL,
                    option_key VARCHAR(100) NOT NULL,
                    label VARCHAR(160) NOT NULL,
                    sort_order INT NOT NULL DEFAULT 0,
                    enabled TINYINT NOT NULL DEFAULT 1,
                    created_at VARCHAR(40) NOT NULL,
                    updated_at VARCHAR(40) NOT NULL
                )
                """
            )
            return
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS material_option_items (
                item_id TEXT PRIMARY KEY,
                option_type TEXT NOT NULL,
                option_key TEXT NOT NULL,
                label TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    def _seed_material_option_items(self, connection) -> None:
        self._ensure_material_option_schema(connection)
        defaults = public_material_options()
        timestamp = now_iso()
        for option_type in MUTABLE_MATERIAL_OPTION_TYPES:
            for index, item in enumerate(defaults.get(option_type) or []):
                option_key = str(item.get("key") or "").strip()
                label = str(item.get("label") or "").strip()
                if not option_key or not label:
                    continue
                item_id = self.material_option_id(option_type, option_key)
                existing = connection.execute(
                    "SELECT item_id FROM material_option_items WHERE item_id = ? OR (option_type = ? AND option_key = ?)",
                    (item_id, option_type, option_key),
                ).fetchone()
                if existing:
                    continue
                connection.execute(
                    """
                    INSERT INTO material_option_items
                    (item_id, option_type, option_key, label, sort_order, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (item_id, option_type, option_key, label, index * 10, timestamp, timestamp),
                )

    def public_material_option_item(self, row: dict[str, Any]) -> dict[str, Any]:
        option_type = row.get("option_type") or ""
        return {
            "id": row.get("item_id") or "",
            "option_type": option_type,
            "type": option_type,
            "type_label": MATERIAL_OPTION_TYPE_LABELS.get(option_type, option_type),
            "key": row.get("option_key") or "",
            "label": row.get("label") or "",
            "sort_order": int(row.get("sort_order") or 0),
            "enabled": bool(row.get("enabled", 1)),
        }

    def list_material_option_items(
        self,
        option_type: str = "",
        include_disabled: bool = True,
        connection: Any | None = None,
    ) -> list[dict[str, Any]]:
        def run(conn) -> list[dict[str, Any]]:
            self._ensure_material_option_schema(conn)
            clauses = []
            params: list[Any] = []
            if option_type:
                if option_type not in MUTABLE_MATERIAL_OPTION_TYPES:
                    return []
                clauses.append("option_type = ?")
                params.append(option_type)
            if not include_disabled:
                clauses.append("enabled = 1")
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = conn.execute(
                f"SELECT * FROM material_option_items {where} ORDER BY option_type ASC, sort_order ASC, label ASC",
                params,
            ).fetchall()
            return [self.public_material_option_item(dict(row)) for row in rows]

        if connection is not None:
            return run(connection)
        with self.connect() as conn:
            self._seed_material_option_items(conn)
            return run(conn)

    def save_material_option_item(self, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
        option_type = str(payload.get("option_type") or payload.get("type") or "").strip()
        if option_type not in MUTABLE_MATERIAL_OPTION_TYPES:
            raise ValueError("请选择有效的字段类型")
        label = str(payload.get("label") or "").strip()
        if not label:
            raise ValueError("选项名称不能为空")
        sort_order = int(payload.get("sort_order") or 0)
        enabled = 1 if payload.get("enabled", True) else 0
        timestamp = now_iso()
        with self.connect() as connection:
            self._ensure_material_option_schema(connection)
            self._seed_material_option_items(connection)
            item_id = str(payload.get("id") or "").strip()
            existing = None
            if item_id:
                existing = connection.execute(
                    "SELECT * FROM material_option_items WHERE item_id = ?",
                    (item_id,),
                ).fetchone()
            before = dict(existing) if existing else None
            option_key = str(payload.get("key") or "").strip()
            if existing:
                option_key = existing["option_key"]
                option_type = existing["option_type"]
                item_id = existing["item_id"]
            else:
                option_key = stable_key(option_key or label, option_type)
                item_id = self.material_option_id(option_type, option_key)
                existing = connection.execute(
                    "SELECT * FROM material_option_items WHERE item_id = ? OR (option_type = ? AND option_key = ?)",
                    (item_id, option_type, option_key),
                ).fetchone()
                if existing:
                    item_id = existing["item_id"]
                    before = dict(existing)
            if existing:
                connection.execute(
                    """
                    UPDATE material_option_items
                    SET label=?, sort_order=?, enabled=?, updated_at=?
                    WHERE item_id=?
                    """,
                    (label, sort_order, enabled, timestamp, item_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO material_option_items
                    (item_id, option_type, option_key, label, sort_order, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (item_id, option_type, option_key, label, sort_order, enabled, timestamp, timestamp),
                )
            after = {
                "item_id": item_id,
                "option_type": option_type,
                "option_key": option_key,
                "label": label,
                "sort_order": sort_order,
                "enabled": enabled,
            }
            self.record_material_audit(
                connection,
                action="option_update" if before else "option_create",
                target_type="material_option",
                target_id=item_id,
                before=before,
                after=after,
                actor=actor,
                summary=("更新字段字典：" if before else "新增字段字典：") + f"{MATERIAL_OPTION_TYPE_LABELS.get(option_type, option_type)} / {label}",
            )
        return {
            "id": item_id,
            "option_type": option_type,
            "type": option_type,
            "type_label": MATERIAL_OPTION_TYPE_LABELS.get(option_type, option_type),
            "key": option_key,
            "label": label,
            "sort_order": sort_order,
            "enabled": bool(enabled),
        }

    def disable_material_option_item(self, item_id: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
        clean_id = str(item_id or "").strip()
        if not clean_id:
            raise ValueError("请选择要停用的选项")
        timestamp = now_iso()
        with self.connect() as connection:
            self._ensure_material_option_schema(connection)
            row = connection.execute("SELECT * FROM material_option_items WHERE item_id = ?", (clean_id,)).fetchone()
            if not row:
                raise ValueError("选项不存在")
            before = dict(row)
            connection.execute(
                "UPDATE material_option_items SET enabled=0, updated_at=? WHERE item_id=?",
                (timestamp, clean_id),
            )
            after = {**before, "enabled": 0, "updated_at": timestamp}
            self.record_material_audit(
                connection,
                action="option_disable",
                target_type="material_option",
                target_id=clean_id,
                before=before,
                after=after,
                actor=actor,
                summary=f"停用字段字典：{MATERIAL_OPTION_TYPE_LABELS.get(before.get('option_type'), before.get('option_type'))} / {before.get('label') or clean_id}",
            )
        return {"disabled": clean_id}

    def _ensure_material_audit_schema(self, connection) -> None:
        if use_mysql() and not self._force_sqlite:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS material_audit_logs (
                    log_id VARCHAR(80) PRIMARY KEY,
                    action VARCHAR(40) NOT NULL,
                    target_type VARCHAR(40) NOT NULL DEFAULT 'material',
                    target_id VARCHAR(160) NOT NULL DEFAULT '',
                    material_id VARCHAR(120) NOT NULL DEFAULT '',
                    material_code VARCHAR(160) NOT NULL DEFAULT '',
                    actor_id VARCHAR(80) NOT NULL DEFAULT '',
                    actor_name VARCHAR(120) NOT NULL DEFAULT '',
                    summary VARCHAR(255) NOT NULL DEFAULT '',
                    before_json LONGTEXT,
                    after_json LONGTEXT,
                    created_at VARCHAR(40) NOT NULL,
                    INDEX idx_material_audit_created (created_at),
                    INDEX idx_material_audit_material (material_id, created_at)
                )
                """
            )
            rows = connection.execute("SHOW COLUMNS FROM material_audit_logs").fetchall()
            columns = {row["Field"] for row in rows}
            if "target_type" not in columns:
                connection.execute("ALTER TABLE material_audit_logs ADD COLUMN target_type VARCHAR(40) NOT NULL DEFAULT 'material'")
            if "target_id" not in columns:
                connection.execute("ALTER TABLE material_audit_logs ADD COLUMN target_id VARCHAR(160) NOT NULL DEFAULT ''")
            return
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS material_audit_logs (
                log_id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL DEFAULT 'material',
                target_id TEXT NOT NULL DEFAULT '',
                material_id TEXT NOT NULL DEFAULT '',
                material_code TEXT NOT NULL DEFAULT '',
                actor_id TEXT NOT NULL DEFAULT '',
                actor_name TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                before_json TEXT,
                after_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(material_audit_logs)").fetchall()}
        if "target_type" not in columns:
            connection.execute("ALTER TABLE material_audit_logs ADD COLUMN target_type TEXT NOT NULL DEFAULT 'material'")
        if "target_id" not in columns:
            connection.execute("ALTER TABLE material_audit_logs ADD COLUMN target_id TEXT NOT NULL DEFAULT ''")

    def material_audit_summary(self, action: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> str:
        target = after or before or {}
        name = target.get("name") or target.get("series") or target.get("material_code") or target.get("id") or "材料"
        if action == "create":
            return f"新增材料：{name}"
        if action == "delete":
            return f"删除材料：{name}"
        if action.startswith("batch_"):
            return f"批量{action.replace('batch_', '')}：{name}"
        changed = []
        for key, label in (
            ("price", "价格"),
            ("cost_price", "成本"),
            ("stock", "库存"),
            ("safety_stock", "安全库存"),
            ("enabled", "状态"),
            ("category", "分类"),
            ("series", "品种"),
            ("element", "五行"),
            ("image_url", "主图"),
            ("image_urls_json", "多图"),
        ):
            if (before or {}).get(key) != (after or {}).get(key):
                changed.append(label)
        return f"更新材料：{name}" + (f"（{', '.join(changed[:5])}）" if changed else "")

    def record_material_audit(
        self,
        connection,
        *,
        action: str,
        target_type: str = "material",
        target_id: str = "",
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        actor: dict[str, Any] | None = None,
        summary: str = "",
    ) -> None:
        self._ensure_material_audit_schema(connection)
        target = after or before or {}
        target_type = str(target_type or "material").strip() or "material"
        resolved_target_id = str(target_id or target.get("id") or target.get("item_id") or "").strip()
        material_id = str(target.get("id") or "") if target_type == "material" else ""
        material_code = str(target.get("material_code") or "")
        actor = actor or {}
        timestamp = now_iso()
        connection.execute(
            """
            INSERT INTO material_audit_logs
            (log_id, action, target_type, target_id, material_id, material_code, actor_id, actor_name, summary, before_json, after_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"matlog_{secrets.token_hex(12)}",
                action,
                target_type,
                resolved_target_id,
                material_id,
                material_code,
                str(actor.get("admin_id") or ""),
                str(actor.get("username") or actor.get("display_name") or ""),
                summary or self.material_audit_summary(action, before, after),
                json_text(before or {}),
                json_text(after or {}),
                timestamp,
            ),
        )

    def list_material_audit_logs(
        self,
        material_id: str = "",
        target_type: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 100), 300))
        clauses = []
        params: list[Any] = []
        if material_id:
            clauses.append("material_id = ?")
            params.append(material_id)
        if target_type:
            clauses.append("target_type = ?")
            params.append(target_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as connection:
            self._ensure_material_audit_schema(connection)
            rows = connection.execute(
                f"SELECT * FROM material_audit_logs {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [
            {
                "log_id": row["log_id"],
                "action": row["action"],
                "target_type": row["target_type"] if "target_type" in row.keys() else "material",
                "target_id": row["target_id"] if "target_id" in row.keys() else row["material_id"],
                "material_id": row["material_id"],
                "material_code": row["material_code"],
                "actor_id": row["actor_id"],
                "actor_name": row["actor_name"],
                "summary": row["summary"],
                "before": json_value(row["before_json"], {}),
                "after": json_value(row["after_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def _ensure_community_post_columns(self, connection) -> None:
        if use_mysql() and not self._force_sqlite:
            rows = connection.execute("SHOW COLUMNS FROM community_posts").fetchall()
            columns = {row["Field"] for row in rows}
            if "is_home_hot" not in columns:
                connection.execute("ALTER TABLE community_posts ADD COLUMN is_home_hot TINYINT NOT NULL DEFAULT 0")
            return
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(community_posts)").fetchall()}
        if "is_home_hot" not in columns:
            connection.execute("ALTER TABLE community_posts ADD COLUMN is_home_hot INTEGER NOT NULL DEFAULT 0")

    def _ensure_default_white_quartz_series(self, connection) -> None:
        timestamp = now_iso()
        defaults = [
            ("milkyQuartz8", "milkyQuartz", "白水晶", "奶白水晶", "A", 8, 6, 1.2, "#e7e5df", "#ffffff", "beads/milky-quartz-8.png"),
            ("milkyQuartz10", "milkyQuartz", "白水晶", "奶白水晶", "A", 10, 11, 1.6, "#dedbd4", "#ffffff", "beads/milky-quartz-10.png"),
            ("azeztulite8", "azeztulite", "白水晶", "白阿塞水晶", "AA", 8, 28, 1.2, "#eef0ed", "#ffffff", "beads/azeztulite-8.png"),
            ("azeztulite10", "azeztulite", "白水晶", "白阿塞水晶", "AA", 10, 42, 1.7, "#e5e9e7", "#ffffff", "beads/azeztulite-10.png"),
            ("whiteQuartz8", "whiteQuartz", "白水晶", "白水晶", "A", 8, 4, 1.1, "#e1e4e5", "#ffffff", "beads/white-quartz-8.png"),
            ("whiteQuartz10", "whiteQuartz", "白水晶", "白水晶", "A", 10, 8, 1.5, "#d8dcdd", "#ffffff", "beads/white-quartz-10.png"),
            ("doubleAClearQuartz8", "doubleAClearQuartz", "白水晶", "双A白水", "AA", 8, 9, 1.2, "#edf1f2", "#ffffff", "beads/double-a-clear-quartz-8.png"),
            ("doubleAClearQuartz10", "doubleAClearQuartz", "白水晶", "双A白水", "AA", 10, 16, 1.6, "#e4e9eb", "#ffffff", "beads/double-a-clear-quartz-10.png"),
        ]
        max_sort = connection.execute("SELECT COALESCE(MAX(sort_order), 0) AS m FROM managed_materials").fetchone()["m"]
        for offset, item in enumerate(defaults, start=1):
            (
                item_id,
                sku_id,
                category,
                series,
                grade,
                size,
                price,
                weight,
                color,
                shine,
                image_path,
            ) = item
            exists = connection.execute("SELECT 1 FROM managed_materials WHERE id = ?", (item_id,)).fetchone()
            if exists:
                continue
            connection.execute(
                """
                INSERT INTO managed_materials
                (id, skuId, top, category, series, material_code, grade, name, effect, element, price, size, weight, color, shine,
                 image_path, image_url, enabled, sort_order, created_at, updated_at)
                VALUES (?, ?, 'bead', ?, ?, ?, ?, ?, '净化与放大', '金', ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    item_id,
                    sku_id,
                    category,
                    series,
                    material_code_from_payload({"skuId": sku_id, "id": item_id}),
                    grade,
                    series,
                    price,
                    size,
                    weight,
                    color,
                    shine,
                    image_path,
                    material_url_from_path(image_path),
                    max_sort + offset,
                    timestamp,
                    timestamp,
                ),
            )
            upsert_material_knowledge(
                {
                    "material_code": material_code_from_payload({"skuId": sku_id, "id": item_id}),
                    "name": series,
                    "element": "金",
                    "effect": "净化与放大",
                    "top": "bead",
                },
                connection=connection,
                force_update=False,
            )

    def _seed_blocks(self, connection) -> None:
        timestamp = now_iso()
        defaults = [
            ("home_hero", "home", "宇涧水晶", "用五行、星盘与 MBTI 找到你的专属能量配方", "首页头部品牌文案"),
            ("daily_energy", "daily", "每日能量补给站", "今天适合温柔启动，先做一件小事。", "每日留存模块文案"),
            ("hot_recommend", "home", "热门推荐", "面向转化的推荐商品区", "首页商品推荐板块"),
            ("community_inspiration", "community", "社区灵感", "用户搭配与 DIY 案例展示", "灵感社区板块"),
        ]
        for index, (block_id, section, title, subtitle, body) in enumerate(defaults):
            connection.execute(
                """
                INSERT INTO content_blocks
                (block_id, section, title, subtitle, body, image_url, action_text, action_url, status,
                 sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, '', '', '', 'published', ?, ?, ?)
                """,
                (block_id, section, title, subtitle, body, index, timestamp, timestamp),
            )

    def _seed_home_banners(self, connection) -> None:
        timestamp = now_iso()
        defaults = [
            {
                "banner_id": "home_banner_main",
                "title": "真实自然，灵感有根",
                "subtitle": "实拍选材 · 手围适配 · 成串预览 · 方案留存，让每一串都清清楚楚来处。",
                "eyebrow": "CRYSTAL HANDMADE STUDIO",
                "image_url": "",
                "action_text": "开始定制 →",
                "action_url": "/pages/custom-mode/custom-mode",
                "theme": "dark",
                "status": "published",
                "sort_order": 0,
            },
            {
                "banner_id": "home_banner_workspace",
                "title": "先看见，再下单",
                "subtitle": "进入 DIY 工作台，拖拽珠材、调整腕围、实时查看成串效果。",
                "eyebrow": "DIY WORKBENCH",
                "image_url": "",
                "action_text": "打开工作台 →",
                "action_url": "/pages/workspace/workspace",
                "theme": "warm",
                "status": "published",
                "sort_order": 10,
            },
        ]
        for item in defaults:
            connection.execute(
                """
                INSERT INTO home_banners
                (banner_id, title, subtitle, eyebrow, image_url, action_text, action_url, theme, status,
                 sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["banner_id"], item["title"], item["subtitle"], item["eyebrow"], item["image_url"],
                    item["action_text"], item["action_url"], item["theme"], item["status"], item["sort_order"],
                    timestamp, timestamp,
                ),
            )

    def _ensure_warehouse_schema(self, connection) -> None:
        """SQLite fallback schema for the standalone warehouse inventory module."""
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_suppliers (
                supplier_id TEXT PRIMARY KEY,
                supplier_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                contact_name TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                remark TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_locations (
                location_id TEXT PRIMARY KEY,
                location_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                area TEXT NOT NULL DEFAULT '',
                shelf TEXT NOT NULL DEFAULT '',
                box_no TEXT NOT NULL DEFAULT '',
                remark TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_channels (
                channel_id TEXT PRIMARY KEY,
                channel_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                channel_type TEXT NOT NULL DEFAULT 'manual',
                remark TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_items (
                item_id TEXT PRIMARY KEY,
                item_code TEXT NOT NULL UNIQUE,
                item_type TEXT NOT NULL DEFAULT 'bead',
                category TEXT NOT NULL DEFAULT '',
                material_name TEXT NOT NULL,
                size_mm REAL NOT NULL DEFAULT 0,
                shape TEXT NOT NULL DEFAULT '',
                hole_type TEXT NOT NULL DEFAULT '',
                grade TEXT NOT NULL DEFAULT '',
                color_label TEXT NOT NULL DEFAULT '',
                quality_label TEXT NOT NULL DEFAULT '',
                origin_place TEXT NOT NULL DEFAULT '',
                unit TEXT NOT NULL DEFAULT '颗',
                image_urls_json TEXT,
                remark TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_batches (
                batch_id TEXT PRIMARY KEY,
                batch_no TEXT NOT NULL UNIQUE,
                item_id TEXT NOT NULL,
                supplier_id TEXT,
                location_id TEXT,
                inbound_quantity INTEGER NOT NULL DEFAULT 0,
                remaining_quantity INTEGER NOT NULL DEFAULT 0,
                unit_cost REAL NOT NULL DEFAULT 0,
                total_cost REAL NOT NULL DEFAULT 0,
                purchase_date TEXT NOT NULL DEFAULT '',
                inbound_at TEXT NOT NULL,
                quality_note TEXT,
                image_urls_json TEXT,
                certificate_urls_json TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                remark TEXT,
                created_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_movements (
                movement_id TEXT PRIMARY KEY,
                movement_no TEXT NOT NULL UNIQUE,
                item_id TEXT NOT NULL,
                batch_id TEXT,
                movement_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                before_quantity INTEGER NOT NULL DEFAULT 0,
                after_quantity INTEGER NOT NULL DEFAULT 0,
                unit_cost REAL NOT NULL DEFAULT 0,
                channel_id TEXT,
                external_order_no TEXT NOT NULL DEFAULT '',
                external_platform TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                remark TEXT,
                operator_id TEXT NOT NULL DEFAULT '',
                operator_name TEXT NOT NULL DEFAULT '',
                occurred_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

    def _warehouse_code(self, kind: str) -> str:
        prefixes = {
            "item": "81",
            "batch": "82",
            "movement": "83",
            "supplier": "84",
            "location": "85",
            "channel": "86",
        }
        prefix = prefixes.get(kind, "89")
        return f"{prefix}{datetime.utcnow().strftime('%y%m%d%H%M%S')}{secrets.randbelow(10000):04d}"

    def _unique_warehouse_code(self, connection, table: str, column: str, kind: str) -> str:
        for _ in range(30):
            code = self._warehouse_code(kind)
            if not connection.execute(f"SELECT 1 FROM {table} WHERE {column} = ?", (code,)).fetchone():
                return code
        return f"{self._warehouse_code(kind)}{secrets.randbelow(1000):03d}"

    def _warehouse_urls(self, value: Any) -> list[str]:
        if isinstance(value, list):
            raw = value
        elif isinstance(value, str):
            raw = re.split(r"[\n,，]+", value)
        else:
            raw = []
        return [str(url).strip() for url in raw if str(url).strip()]

    def _warehouse_enum_value(self, value: Any, options: list[dict[str, str]], default: str) -> str:
        text = str(value or "").strip()
        if not text:
            return default
        for option in options:
            if text == option["key"] or text == option["label"]:
                return option["key"]
        raise ValueError(f"枚举值不合法：{text}")

    def _warehouse_enum_label(self, value: Any, options: list[dict[str, str]], default: str = "") -> str:
        text = str(value or "").strip()
        if not text:
            text = default
        for option in options:
            if text == option["key"] or text == option["label"]:
                return option["label"]
        return text

    def _ensure_warehouse_defaults(self, connection) -> None:
        timestamp = now_iso()
        suppliers = [
            ("840000000001", "默认供应商", "默认档案，用于尚未归属供应商的入库"),
        ]
        for code, name, remark in suppliers:
            if not connection.execute("SELECT 1 FROM warehouse_suppliers WHERE supplier_code = ?", (code,)).fetchone():
                connection.execute(
                    """
                    INSERT INTO warehouse_suppliers
                    (supplier_id, supplier_code, name, contact_name, phone, address, remark, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, '', '', '', ?, 1, ?, ?)
                    """,
                    (f"wh_supplier_{code}", code, name, remark, timestamp, timestamp),
                )
        locations = [
            ("850000000001", "主仓", "默认仓位", "", "", "默认存放位置"),
        ]
        for code, name, area, shelf, box_no, remark in locations:
            if not connection.execute("SELECT 1 FROM warehouse_locations WHERE location_code = ?", (code,)).fetchone():
                connection.execute(
                    """
                    INSERT INTO warehouse_locations
                    (location_id, location_code, name, area, shelf, box_no, remark, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (f"wh_location_{code}", code, name, area, shelf, box_no, remark, timestamp, timestamp),
                )
        channels = [
            ("860000000001", "douyin", "抖音", "sale", "抖音渠道手工出库"),
            ("860000000002", "wechat_mp", "小程序", "sale", "小程序渠道手工出库"),
            ("860000000003", "wechat", "微信私域", "sale", "微信私域成交"),
            ("860000000004", "offline", "线下", "sale", "线下销售"),
            ("860000000005", "manual", "人工调整", "manual", "盘点、损耗、调拨等人工调整"),
            ("860000000006", "sample", "样品", "sample", "拍摄、打样、展示样品"),
            ("860000000007", "gift", "赠品", "gift", "赠送或售后补发"),
        ]
        for code, channel_code, name, channel_type, remark in channels:
            if not connection.execute("SELECT 1 FROM warehouse_channels WHERE channel_code = ?", (channel_code,)).fetchone():
                connection.execute(
                    """
                    INSERT INTO warehouse_channels
                    (channel_id, channel_code, name, channel_type, remark, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (f"wh_channel_{code}", channel_code, name, channel_type, remark, timestamp, timestamp),
                )

    def public_warehouse_supplier(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "supplier_id": row["supplier_id"],
            "supplier_code": row["supplier_code"],
            "name": row["name"],
            "contact_name": row.get("contact_name") or "",
            "phone": row.get("phone") or "",
            "address": row.get("address") or "",
            "remark": row.get("remark") or "",
            "enabled": bool(row.get("enabled", 1)),
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    def public_warehouse_location(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "location_id": row["location_id"],
            "location_code": row["location_code"],
            "name": row["name"],
            "area": row.get("area") or "",
            "shelf": row.get("shelf") or "",
            "box_no": row.get("box_no") or "",
            "remark": row.get("remark") or "",
            "enabled": bool(row.get("enabled", 1)),
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    def public_warehouse_channel(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "channel_id": row["channel_id"],
            "channel_code": row["channel_code"],
            "name": row["name"],
            "channel_type": row.get("channel_type") or "manual",
            "remark": row.get("remark") or "",
            "enabled": bool(row.get("enabled", 1)),
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    def public_warehouse_item(self, row: dict[str, Any]) -> dict[str, Any]:
        size = float(row.get("size_mm") or 0)
        return {
            "item_id": row["item_id"],
            "item_code": row["item_code"],
            "item_type": row.get("item_type") or "bead",
            "category": row.get("category") or "",
            "material_name": row.get("material_name") or "",
            "size_mm": size,
            "grade": row.get("grade") or "",
            "grade_label": self._warehouse_enum_label(row.get("grade"), WAREHOUSE_GRADE_OPTIONS, "ungraded"),
            "color_label": row.get("color_label") or "",
            "quality_label": row.get("quality_label") or "",
            "origin_place": row.get("origin_place") or "",
            "unit": row.get("unit") or "颗",
            "unit_label": self._warehouse_enum_label(row.get("unit"), WAREHOUSE_UNIT_OPTIONS, "piece"),
            "image_urls": json_value(row.get("image_urls_json"), []),
            "remark": row.get("remark") or "",
            "enabled": bool(row.get("enabled", 1)),
            "actual_stock": int(row.get("actual_stock") or 0),
            "batch_count": int(row.get("batch_count") or 0),
            "avg_cost": float(row.get("avg_cost") or 0),
            "stock_cost_value": float(row.get("stock_cost_value") or 0),
            "display_name": f"{row.get('material_name') or ''}{f' {size:g}mm' if size else ''}",
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    def public_warehouse_batch(self, row: dict[str, Any]) -> dict[str, Any]:
        item_name = row.get("material_name") or row.get("item_name") or ""
        size = float(row.get("size_mm") or 0)
        return {
            "batch_id": row["batch_id"],
            "batch_no": row["batch_no"],
            "item_id": row["item_id"],
            "item_code": row.get("item_code") or "",
            "item_name": f"{item_name}{f' {size:g}mm' if size else ''}",
            "supplier_id": row.get("supplier_id") or "",
            "supplier_name": row.get("supplier_name") or "",
            "location_id": row.get("location_id") or "",
            "location_name": row.get("location_name") or "",
            "inbound_quantity": int(row.get("inbound_quantity") or 0),
            "remaining_quantity": int(row.get("remaining_quantity") or 0),
            "unit_cost": float(row.get("unit_cost") or 0),
            "total_cost": float(row.get("total_cost") or 0),
            "purchase_date": row.get("purchase_date") or "",
            "inbound_at": row.get("inbound_at") or "",
            "quality_note": row.get("quality_note") or "",
            "image_urls": json_value(row.get("image_urls_json"), []),
            "certificate_urls": json_value(row.get("certificate_urls_json"), []),
            "status": row.get("status") or "active",
            "remark": row.get("remark") or "",
            "created_by": row.get("created_by") or "",
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }

    def public_warehouse_movement(self, row: dict[str, Any]) -> dict[str, Any]:
        item_name = row.get("material_name") or ""
        size = float(row.get("size_mm") or 0)
        return {
            "movement_id": row["movement_id"],
            "movement_no": row["movement_no"],
            "item_id": row["item_id"],
            "item_code": row.get("item_code") or "",
            "item_name": f"{item_name}{f' {size:g}mm' if size else ''}",
            "batch_id": row.get("batch_id") or "",
            "batch_no": row.get("batch_no") or "",
            "movement_type": row.get("movement_type") or "",
            "quantity": int(row.get("quantity") or 0),
            "before_quantity": int(row.get("before_quantity") or 0),
            "after_quantity": int(row.get("after_quantity") or 0),
            "unit_cost": float(row.get("unit_cost") or 0),
            "channel_id": row.get("channel_id") or "",
            "channel_name": row.get("channel_name") or "",
            "external_order_no": row.get("external_order_no") or "",
            "external_platform": row.get("external_platform") or "",
            "reason": row.get("reason") or "",
            "remark": row.get("remark") or "",
            "operator_id": row.get("operator_id") or "",
            "operator_name": row.get("operator_name") or "",
            "occurred_at": row.get("occurred_at") or "",
            "created_at": row.get("created_at") or "",
        }

    def warehouse_options(self) -> dict[str, Any]:
        with self.connect() as connection:
            suppliers = connection.execute("SELECT * FROM warehouse_suppliers ORDER BY enabled DESC, updated_at DESC").fetchall()
            locations = connection.execute("SELECT * FROM warehouse_locations ORDER BY enabled DESC, updated_at DESC").fetchall()
            channels = connection.execute("SELECT * FROM warehouse_channels ORDER BY enabled DESC, channel_code ASC").fetchall()
        return {
            "suppliers": [self.public_warehouse_supplier(dict(row)) for row in suppliers],
            "locations": [self.public_warehouse_location(dict(row)) for row in locations],
            "channels": [self.public_warehouse_channel(dict(row)) for row in channels],
            "movement_types": [
                {"key": "sale_out", "label": "销售出库"},
                {"key": "manual_out", "label": "人工出库"},
                {"key": "manual_in", "label": "人工入库"},
                {"key": "return_in", "label": "退货入库"},
                {"key": "damage_out", "label": "损耗出库"},
                {"key": "sample_out", "label": "样品出库"},
                {"key": "gift_out", "label": "赠品出库"},
                {"key": "stocktake_gain", "label": "盘盈"},
                {"key": "stocktake_loss", "label": "盘亏"},
            ],
            "item_types": [
                {"key": "bead", "label": "散珠"},
                {"key": "accessory", "label": "配件"},
                {"key": "thread", "label": "线材"},
                {"key": "package", "label": "包装"},
                {"key": "tool", "label": "工具/耗材"},
            ],
            "grade_options": WAREHOUSE_GRADE_OPTIONS,
            "unit_options": WAREHOUSE_UNIT_OPTIONS,
        }

    def list_warehouse_items(
        self,
        keyword: str = "",
        category: str = "",
        item_type: str = "",
        enabled: str = "",
        limit: int = 300,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        keyword = (keyword or "").strip().lower()
        if keyword:
            clauses.append("(LOWER(i.item_code) LIKE ? OR LOWER(i.material_name) LIKE ? OR LOWER(i.category) LIKE ? OR LOWER(i.color_label) LIKE ?)")
            params.extend([f"%{keyword}%"] * 4)
        if category:
            clauses.append("i.category = ?")
            params.append(category)
        if item_type:
            clauses.append("i.item_type = ?")
            params.append(item_type)
        if enabled in {"0", "1", "true", "false"}:
            clauses.append("i.enabled = ?")
            params.append(1 if enabled in {"1", "true"} else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit = max(1, min(int(limit or 300), 500))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT i.*,
                       COALESCE(SUM(CASE WHEN b.status = 'active' THEN b.remaining_quantity ELSE 0 END), 0) AS actual_stock,
                       COUNT(CASE WHEN b.status = 'active' AND b.remaining_quantity > 0 THEN 1 END) AS batch_count,
                       COALESCE(SUM(CASE WHEN b.status = 'active' THEN b.remaining_quantity * b.unit_cost ELSE 0 END), 0) AS stock_cost_value,
                       CASE
                         WHEN COALESCE(SUM(CASE WHEN b.status = 'active' THEN b.remaining_quantity ELSE 0 END), 0) > 0
                         THEN COALESCE(SUM(CASE WHEN b.status = 'active' THEN b.remaining_quantity * b.unit_cost ELSE 0 END), 0) /
                              COALESCE(SUM(CASE WHEN b.status = 'active' THEN b.remaining_quantity ELSE 0 END), 1)
                         ELSE 0
                       END AS avg_cost
                FROM warehouse_items i
                LEFT JOIN warehouse_batches b ON b.item_id = i.item_id
                {where}
                GROUP BY i.item_id
                ORDER BY i.enabled DESC, i.updated_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self.public_warehouse_item(dict(row)) for row in rows]

    def save_warehouse_item(
        self,
        payload: dict[str, Any],
        item_id: str | None = None,
        actor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        material_name = str(payload.get("material_name") or payload.get("name") or "").strip()
        if not material_name:
            raise ValueError("请填写库存品名")
        timestamp = now_iso()
        with self.connect() as connection:
            existing = connection.execute("SELECT * FROM warehouse_items WHERE item_id = ?", (item_id or payload.get("item_id") or "",)).fetchone()
            code = str(payload.get("item_code") or "").strip()
            if not code:
                code = existing["item_code"] if existing else self._unique_warehouse_code(connection, "warehouse_items", "item_code", "item")
            data = {
                "item_id": item_id or payload.get("item_id") or f"wh_item_{secrets.token_hex(8)}",
                "item_code": code,
                "item_type": str(payload.get("item_type") or "bead").strip()[:40],
                "category": str(payload.get("category") or "").strip()[:120],
                "material_name": material_name[:160],
                "size_mm": float(payload.get("size_mm") or payload.get("size") or 0),
                "shape": "",
                "hole_type": "",
                "grade": self._warehouse_enum_value(payload.get("grade"), WAREHOUSE_GRADE_OPTIONS, "ungraded"),
                "color_label": str(payload.get("color_label") or "").strip()[:120],
                "quality_label": str(payload.get("quality_label") or "").strip()[:120],
                "origin_place": str(payload.get("origin_place") or "").strip()[:160],
                "unit": self._warehouse_enum_value(payload.get("unit"), WAREHOUSE_UNIT_OPTIONS, "piece"),
                "image_urls_json": json_text(self._warehouse_urls(payload.get("image_urls") or payload.get("image_urls_text"))),
                "remark": str(payload.get("remark") or "").strip(),
                "enabled": 1 if payload.get("enabled", True) else 0,
            }
            try:
                if existing:
                    connection.execute(
                        """
                        UPDATE warehouse_items
                        SET item_code=?, item_type=?, category=?, material_name=?, size_mm=?, shape=?, hole_type=?,
                            grade=?, color_label=?, quality_label=?, origin_place=?, unit=?, image_urls_json=?,
                            remark=?, enabled=?, updated_at=?
                        WHERE item_id=?
                        """,
                        (
                            data["item_code"], data["item_type"], data["category"], data["material_name"],
                            data["size_mm"], data["shape"], data["hole_type"], data["grade"],
                            data["color_label"], data["quality_label"], data["origin_place"], data["unit"],
                            data["image_urls_json"], data["remark"], data["enabled"], timestamp, data["item_id"],
                        ),
                    )
                else:
                    connection.execute(
                        """
                        INSERT INTO warehouse_items
                        (item_id, item_code, item_type, category, material_name, size_mm, shape, hole_type,
                         grade, color_label, quality_label, origin_place, unit, image_urls_json, remark,
                         enabled, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            data["item_id"], data["item_code"], data["item_type"], data["category"],
                            data["material_name"], data["size_mm"], data["shape"], data["hole_type"],
                            data["grade"], data["color_label"], data["quality_label"], data["origin_place"],
                            data["unit"], data["image_urls_json"], data["remark"], data["enabled"],
                            timestamp, timestamp,
                        ),
                    )
            except integrity_errors() as exc:
                raise ValueError("库存编码已存在，请刷新后重试") from exc
            row = connection.execute(
                """
                SELECT i.*, 0 AS actual_stock, 0 AS batch_count, 0 AS stock_cost_value, 0 AS avg_cost
                FROM warehouse_items i WHERE i.item_id=?
                """,
                (data["item_id"],),
            ).fetchone()
        return self.public_warehouse_item(dict(row))

    def delete_warehouse_item(self, item_id: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            stock = connection.execute(
                "SELECT COALESCE(SUM(remaining_quantity), 0) AS stock FROM warehouse_batches WHERE item_id=? AND status='active'",
                (item_id,),
            ).fetchone()["stock"]
            if int(stock or 0) > 0:
                raise ValueError("该库存品仍有余量，不能删除；可先停用")
            connection.execute("UPDATE warehouse_items SET enabled=0, updated_at=? WHERE item_id=?", (now_iso(), item_id))
        return {"item_id": item_id, "enabled": False}

    def list_warehouse_batches(self, keyword: str = "", item_id: str = "", status: str = "", limit: int = 300) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        keyword = (keyword or "").strip().lower()
        if keyword:
            clauses.append("(LOWER(b.batch_no) LIKE ? OR LOWER(i.material_name) LIKE ? OR LOWER(i.item_code) LIKE ?)")
            params.extend([f"%{keyword}%"] * 3)
        if item_id:
            clauses.append("b.item_id = ?")
            params.append(item_id)
        if status:
            clauses.append("b.status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit = max(1, min(int(limit or 300), 500))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT b.*, i.item_code, i.material_name, i.size_mm, s.name AS supplier_name, l.name AS location_name
                FROM warehouse_batches b
                JOIN warehouse_items i ON i.item_id = b.item_id
                LEFT JOIN warehouse_suppliers s ON s.supplier_id = b.supplier_id
                LEFT JOIN warehouse_locations l ON l.location_id = b.location_id
                {where}
                ORDER BY b.inbound_at DESC, b.created_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self.public_warehouse_batch(dict(row)) for row in rows]

    def _record_warehouse_movement(
        self,
        connection,
        item_id: str,
        batch_id: str | None,
        movement_type: str,
        quantity: int,
        before_quantity: int,
        after_quantity: int,
        unit_cost: float = 0,
        channel_id: str | None = "",
        external_order_no: str = "",
        external_platform: str = "",
        reason: str = "",
        remark: str = "",
        actor: dict[str, Any] | None = None,
        occurred_at: str | None = None,
    ) -> str:
        movement_no = self._unique_warehouse_code(connection, "warehouse_movements", "movement_no", "movement")
        movement_id = f"wh_move_{secrets.token_hex(8)}"
        timestamp = now_iso()
        connection.execute(
            """
            INSERT INTO warehouse_movements
            (movement_id, movement_no, item_id, batch_id, movement_type, quantity, before_quantity, after_quantity,
             unit_cost, channel_id, external_order_no, external_platform, reason, remark, operator_id, operator_name,
             occurred_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                movement_id,
                movement_no,
                item_id,
                batch_id or "",
                movement_type,
                quantity,
                before_quantity,
                after_quantity,
                unit_cost,
                channel_id or "",
                external_order_no[:120],
                external_platform[:40],
                reason[:160],
                remark,
                (actor or {}).get("admin_id") or "",
                (actor or {}).get("display_name") or (actor or {}).get("username") or "",
                occurred_at or timestamp,
                timestamp,
            ),
        )
        return movement_id

    def create_warehouse_inbound(self, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
        item_id = str(payload.get("item_id") or "").strip()
        quantity = int(payload.get("quantity") or payload.get("inbound_quantity") or 0)
        if not item_id:
            raise ValueError("请选择入库品")
        if quantity <= 0:
            raise ValueError("入库数量必须大于 0")
        unit_cost = max(0.0, float(payload.get("unit_cost") or 0))
        timestamp = now_iso()
        with self.connect() as connection:
            item = connection.execute("SELECT * FROM warehouse_items WHERE item_id=?", (item_id,)).fetchone()
            if not item:
                raise ValueError("库存品不存在")
            batch_id = f"wh_batch_{secrets.token_hex(8)}"
            batch_no = self._unique_warehouse_code(connection, "warehouse_batches", "batch_no", "batch")
            total_cost = round(quantity * unit_cost, 4)
            connection.execute(
                """
                INSERT INTO warehouse_batches
                (batch_id, batch_no, item_id, supplier_id, location_id, inbound_quantity, remaining_quantity,
                 unit_cost, total_cost, purchase_date, inbound_at, quality_note, image_urls_json,
                 certificate_urls_json, status, remark, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    batch_no,
                    item_id,
                    payload.get("supplier_id") or "",
                    payload.get("location_id") or "",
                    quantity,
                    quantity,
                    unit_cost,
                    total_cost,
                    str(payload.get("purchase_date") or ""),
                    str(payload.get("inbound_at") or timestamp),
                    str(payload.get("quality_note") or ""),
                    json_text(self._warehouse_urls(payload.get("image_urls") or payload.get("image_urls_text"))),
                    json_text(self._warehouse_urls(payload.get("certificate_urls") or payload.get("certificate_urls_text"))),
                    str(payload.get("remark") or ""),
                    (actor or {}).get("admin_id") or "",
                    timestamp,
                    timestamp,
                ),
            )
            self._record_warehouse_movement(
                connection,
                item_id=item_id,
                batch_id=batch_id,
                movement_type="inbound",
                quantity=quantity,
                before_quantity=0,
                after_quantity=quantity,
                unit_cost=unit_cost,
                reason="采购入库",
                remark=str(payload.get("remark") or ""),
                actor=actor,
                occurred_at=str(payload.get("inbound_at") or timestamp),
            )
            row = connection.execute(
                """
                SELECT b.*, i.item_code, i.material_name, i.size_mm, s.name AS supplier_name, l.name AS location_name
                FROM warehouse_batches b
                JOIN warehouse_items i ON i.item_id = b.item_id
                LEFT JOIN warehouse_suppliers s ON s.supplier_id = b.supplier_id
                LEFT JOIN warehouse_locations l ON l.location_id = b.location_id
                WHERE b.batch_id=?
                """,
                (batch_id,),
            ).fetchone()
        return self.public_warehouse_batch(dict(row))

    def create_warehouse_outbound(self, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
        item_id = str(payload.get("item_id") or "").strip()
        batch_id = str(payload.get("batch_id") or "").strip()
        quantity = int(payload.get("quantity") or 0)
        movement_type = str(payload.get("movement_type") or "sale_out").strip()
        if movement_type in {"inbound", "manual_in", "return_in", "stocktake_gain"}:
            raise ValueError("该入口只处理出库，请使用入库或调整入库")
        if not item_id:
            raise ValueError("请选择出库品")
        if quantity <= 0:
            raise ValueError("出库数量必须大于 0")
        timestamp = now_iso()
        entries: list[dict[str, Any]] = []
        with self.connect() as connection:
            item = connection.execute("SELECT * FROM warehouse_items WHERE item_id=?", (item_id,)).fetchone()
            if not item:
                raise ValueError("库存品不存在")
            params: list[Any] = [item_id]
            batch_filter = ""
            if batch_id:
                batch_filter = "AND batch_id = ?"
                params.append(batch_id)
            batches = connection.execute(
                f"""
                SELECT * FROM warehouse_batches
                WHERE item_id=? AND status='active' AND remaining_quantity > 0 {batch_filter}
                ORDER BY inbound_at ASC, created_at ASC
                """,
                tuple(params),
            ).fetchall()
            total_available = sum(int(row["remaining_quantity"] or 0) for row in batches)
            if total_available < quantity:
                raise ValueError(f"库存不足：当前可出 {total_available}，本次需要 {quantity}")
            remaining = quantity
            for row in batches:
                if remaining <= 0:
                    break
                batch = dict(row)
                before = int(batch["remaining_quantity"] or 0)
                take = min(before, remaining)
                after = before - take
                status = "empty" if after <= 0 else "active"
                connection.execute(
                    "UPDATE warehouse_batches SET remaining_quantity=?, status=?, updated_at=? WHERE batch_id=?",
                    (after, status, timestamp, batch["batch_id"]),
                )
                movement_id = self._record_warehouse_movement(
                    connection,
                    item_id=item_id,
                    batch_id=batch["batch_id"],
                    movement_type=movement_type,
                    quantity=take,
                    before_quantity=before,
                    after_quantity=after,
                    unit_cost=float(batch.get("unit_cost") or 0),
                    channel_id=str(payload.get("channel_id") or ""),
                    external_order_no=str(payload.get("external_order_no") or ""),
                    external_platform=str(payload.get("external_platform") or ""),
                    reason=str(payload.get("reason") or ""),
                    remark=str(payload.get("remark") or ""),
                    actor=actor,
                    occurred_at=str(payload.get("occurred_at") or timestamp),
                )
                entries.append({"movement_id": movement_id, "batch_id": batch["batch_id"], "quantity": take})
                remaining -= take
        return {"item_id": item_id, "quantity": quantity, "entries": entries}

    def list_warehouse_movements(
        self,
        keyword: str = "",
        item_id: str = "",
        movement_type: str = "",
        channel_id: str = "",
        start_date: str = "",
        end_date: str = "",
        limit: int = 300,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        keyword = (keyword or "").strip().lower()
        if keyword:
            clauses.append("(LOWER(m.movement_no) LIKE ? OR LOWER(m.external_order_no) LIKE ? OR LOWER(i.material_name) LIKE ? OR LOWER(i.item_code) LIKE ?)")
            params.extend([f"%{keyword}%"] * 4)
        if item_id:
            clauses.append("m.item_id = ?")
            params.append(item_id)
        if movement_type:
            clauses.append("m.movement_type = ?")
            params.append(movement_type)
        if channel_id:
            clauses.append("m.channel_id = ?")
            params.append(channel_id)
        if start_date:
            clauses.append("substr(m.occurred_at, 1, 10) >= ?")
            params.append(start_date[:10])
        if end_date:
            clauses.append("substr(m.occurred_at, 1, 10) <= ?")
            params.append(end_date[:10])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit = max(1, min(int(limit or 300), 500))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT m.*, i.item_code, i.material_name, i.size_mm, b.batch_no, c.name AS channel_name
                FROM warehouse_movements m
                JOIN warehouse_items i ON i.item_id = m.item_id
                LEFT JOIN warehouse_batches b ON b.batch_id = m.batch_id
                LEFT JOIN warehouse_channels c ON c.channel_id = m.channel_id
                {where}
                ORDER BY m.occurred_at DESC, m.created_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self.public_warehouse_movement(dict(row)) for row in rows]

    def warehouse_overview(self) -> dict[str, Any]:
        with self.connect() as connection:
            item_row = connection.execute(
                """
                SELECT COUNT(*) AS item_count,
                       COALESCE(SUM(stock), 0) AS total_stock,
                       COALESCE(SUM(stock_value), 0) AS stock_value,
                       SUM(CASE WHEN stock <= 0 THEN 1 ELSE 0 END) AS zero_stock_items
                FROM (
                    SELECT i.item_id,
                           COALESCE(SUM(CASE WHEN b.status='active' THEN b.remaining_quantity ELSE 0 END), 0) AS stock,
                           COALESCE(SUM(CASE WHEN b.status='active' THEN b.remaining_quantity * b.unit_cost ELSE 0 END), 0) AS stock_value
                    FROM warehouse_items i
                    LEFT JOIN warehouse_batches b ON b.item_id = i.item_id
                    WHERE i.enabled = 1
                    GROUP BY i.item_id
                ) t
                """
            ).fetchone()
            batch_row = connection.execute(
                "SELECT COUNT(*) AS batch_count FROM warehouse_batches WHERE status='active' AND remaining_quantity > 0"
            ).fetchone()
            recent_movements = connection.execute(
                """
                SELECT m.*, i.item_code, i.material_name, i.size_mm, b.batch_no, c.name AS channel_name
                FROM warehouse_movements m
                JOIN warehouse_items i ON i.item_id = m.item_id
                LEFT JOIN warehouse_batches b ON b.batch_id = m.batch_id
                LEFT JOIN warehouse_channels c ON c.channel_id = m.channel_id
                ORDER BY m.occurred_at DESC, m.created_at DESC
                LIMIT 8
                """
            ).fetchall()
            low_rows = connection.execute(
                """
                SELECT i.*,
                       COALESCE(SUM(CASE WHEN b.status='active' THEN b.remaining_quantity ELSE 0 END), 0) AS actual_stock,
                       COUNT(CASE WHEN b.status='active' AND b.remaining_quantity > 0 THEN 1 END) AS batch_count,
                       COALESCE(SUM(CASE WHEN b.status='active' THEN b.remaining_quantity * b.unit_cost ELSE 0 END), 0) AS stock_cost_value,
                       0 AS avg_cost
                FROM warehouse_items i
                LEFT JOIN warehouse_batches b ON b.item_id = i.item_id
                WHERE i.enabled=1
                GROUP BY i.item_id
                HAVING actual_stock <= 10
                ORDER BY actual_stock ASC, i.updated_at DESC
                LIMIT 8
                """
            ).fetchall()
        return {
            "stats": {
                "item_count": int(item_row["item_count"] or 0),
                "total_stock": int(item_row["total_stock"] or 0),
                "stock_value": float(item_row["stock_value"] or 0),
                "zero_stock_items": int(item_row["zero_stock_items"] or 0),
                "batch_count": int(batch_row["batch_count"] or 0),
            },
            "recent_movements": [self.public_warehouse_movement(dict(row)) for row in recent_movements],
            "low_stock_items": [self.public_warehouse_item(dict(row)) for row in low_rows],
        }

    def save_warehouse_supplier(self, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("请填写供应商名称")
        timestamp = now_iso()
        with self.connect() as connection:
            supplier_id = str(payload.get("supplier_id") or "").strip()
            existing = connection.execute("SELECT * FROM warehouse_suppliers WHERE supplier_id=?", (supplier_id,)).fetchone() if supplier_id else None
            code = str(payload.get("supplier_code") or "").strip() or (existing["supplier_code"] if existing else self._unique_warehouse_code(connection, "warehouse_suppliers", "supplier_code", "supplier"))
            supplier_id = supplier_id or f"wh_supplier_{secrets.token_hex(8)}"
            if existing:
                connection.execute(
                    """
                    UPDATE warehouse_suppliers SET supplier_code=?, name=?, contact_name=?, phone=?, address=?,
                        remark=?, enabled=?, updated_at=? WHERE supplier_id=?
                    """,
                    (code, name, payload.get("contact_name") or "", payload.get("phone") or "", payload.get("address") or "", payload.get("remark") or "", 1 if payload.get("enabled", True) else 0, timestamp, supplier_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO warehouse_suppliers
                    (supplier_id, supplier_code, name, contact_name, phone, address, remark, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (supplier_id, code, name, payload.get("contact_name") or "", payload.get("phone") or "", payload.get("address") or "", payload.get("remark") or "", 1 if payload.get("enabled", True) else 0, timestamp, timestamp),
                )
            row = connection.execute("SELECT * FROM warehouse_suppliers WHERE supplier_id=?", (supplier_id,)).fetchone()
        return self.public_warehouse_supplier(dict(row))

    def save_warehouse_location(self, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("请填写仓位名称")
        timestamp = now_iso()
        with self.connect() as connection:
            location_id = str(payload.get("location_id") or "").strip()
            existing = connection.execute("SELECT * FROM warehouse_locations WHERE location_id=?", (location_id,)).fetchone() if location_id else None
            code = str(payload.get("location_code") or "").strip() or (existing["location_code"] if existing else self._unique_warehouse_code(connection, "warehouse_locations", "location_code", "location"))
            location_id = location_id or f"wh_location_{secrets.token_hex(8)}"
            if existing:
                connection.execute(
                    """
                    UPDATE warehouse_locations SET location_code=?, name=?, area=?, shelf=?, box_no=?, remark=?,
                        enabled=?, updated_at=? WHERE location_id=?
                    """,
                    (code, name, payload.get("area") or "", payload.get("shelf") or "", payload.get("box_no") or "", payload.get("remark") or "", 1 if payload.get("enabled", True) else 0, timestamp, location_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO warehouse_locations
                    (location_id, location_code, name, area, shelf, box_no, remark, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (location_id, code, name, payload.get("area") or "", payload.get("shelf") or "", payload.get("box_no") or "", payload.get("remark") or "", 1 if payload.get("enabled", True) else 0, timestamp, timestamp),
                )
            row = connection.execute("SELECT * FROM warehouse_locations WHERE location_id=?", (location_id,)).fetchone()
        return self.public_warehouse_location(dict(row))

    def save_warehouse_channel(self, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("请填写渠道名称")
        channel_code = str(payload.get("channel_code") or "").strip().lower()
        if not channel_code:
            channel_code = f"channel_{self._warehouse_code('channel')}"
        timestamp = now_iso()
        with self.connect() as connection:
            channel_id = str(payload.get("channel_id") or "").strip()
            existing = connection.execute("SELECT * FROM warehouse_channels WHERE channel_id=?", (channel_id,)).fetchone() if channel_id else None
            channel_id = channel_id or f"wh_channel_{secrets.token_hex(8)}"
            if existing:
                connection.execute(
                    """
                    UPDATE warehouse_channels SET channel_code=?, name=?, channel_type=?, remark=?, enabled=?, updated_at=?
                    WHERE channel_id=?
                    """,
                    (channel_code, name, payload.get("channel_type") or "manual", payload.get("remark") or "", 1 if payload.get("enabled", True) else 0, timestamp, channel_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO warehouse_channels
                    (channel_id, channel_code, name, channel_type, remark, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (channel_id, channel_code, name, payload.get("channel_type") or "manual", payload.get("remark") or "", 1 if payload.get("enabled", True) else 0, timestamp, timestamp),
                )
            row = connection.execute("SELECT * FROM warehouse_channels WHERE channel_id=?", (channel_id,)).fetchone()
        return self.public_warehouse_channel(dict(row))

    def hash_password(self, password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000).hex()

    def register(self, username: str, password: str) -> dict[str, Any]:
        username = username.strip()
        if len(username) < 3:
            raise ValueError("用户名至少 3 位")
        if len(password) < 6:
            raise ValueError("密码至少 6 位")
        salt = secrets.token_hex(16)
        timestamp = now_iso()
        admin = {
            "admin_id": f"admin_{secrets.token_hex(8)}",
            "username": username,
            "password_hash": self.hash_password(password, salt),
            "salt": salt,
            "role": "admin",
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO admin_users
                    (admin_id, username, password_hash, salt, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        admin["admin_id"],
                        admin["username"],
                        admin["password_hash"],
                        admin["salt"],
                        admin["role"],
                        admin["created_at"],
                        admin["updated_at"],
                    ),
                )
        except integrity_errors() as exc:
            raise ValueError("用户名已存在") from exc
        return self.public_admin(admin)

    def login(self, username: str, password: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM admin_users WHERE username = ?", (username.strip(),)).fetchone()
            if not row:
                raise ValueError("用户名或密码错误")
            password_hash = self.hash_password(password, row["salt"])
            if not secrets.compare_digest(password_hash, row["password_hash"]):
                raise ValueError("用户名或密码错误")
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.utcnow() + timedelta(days=7)).replace(microsecond=0).isoformat() + "Z"
            connection.execute(
                "INSERT INTO admin_sessions (token, admin_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (token, row["admin_id"], expires_at, now_iso()),
            )
        return {"token": token, "admin": self.public_admin(dict(row)), "expires_at": expires_at}

    def require_admin(self, token: str | None) -> dict[str, Any]:
        if not token:
            raise PermissionError("未登录")
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT admin_users.* FROM admin_sessions
                JOIN admin_users ON admin_users.admin_id = admin_sessions.admin_id
                WHERE admin_sessions.token = ? AND admin_sessions.expires_at > ?
                """,
                (token, now_iso()),
            ).fetchone()
        if not row:
            raise PermissionError("登录已过期")
        return self.public_admin(dict(row))

    def public_admin(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "admin_id": row["admin_id"],
            "username": row["username"],
            "role": row["role"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def normalize_admin_username(self, username: str) -> str:
        return (username or "").strip().lower()

    def validate_admin_username(self, username: str) -> str:
        username = self.normalize_admin_username(username)
        if not ADMIN_USERNAME_RE.match(username):
            raise ValueError("管理员账号需为 3-40 位英文、数字、下划线、点、@ 或短横线")
        return username

    def validate_admin_password(self, password: str, username: str = "") -> None:
        if not isinstance(password, str) or len(password) < 8 or len(password) > 80:
            raise ValueError("密码需为 8-80 位")
        if any(ch.isspace() for ch in password):
            raise ValueError("密码不能包含空格")
        if username and password.lower() == username.lower():
            raise ValueError("密码不能与账号相同")
        has_letter = any(ch.isalpha() for ch in password)
        has_digit = any(ch.isdigit() for ch in password)
        if not (has_letter and has_digit):
            raise ValueError("密码需同时包含字母和数字")

    def assert_admin_manager(self, actor: dict[str, Any] | None) -> None:
        if actor and actor.get("role") not in ADMIN_MANAGER_ROLES:
            raise PermissionError("当前账号没有管理员账号管理权限")

    def _request_ip(self, request_info: dict[str, str] | None) -> str:
        if not request_info:
            return ""
        forwarded = (request_info.get("x_forwarded_for") or "").split(",")[0].strip()
        return forwarded or request_info.get("ip") or ""

    def _request_agent(self, request_info: dict[str, str] | None) -> str:
        return (request_info or {}).get("user_agent", "")[:500]

    def _record_login(
        self,
        connection,
        username: str,
        success: bool,
        reason: str,
        admin_id: str | None = None,
        request_info: dict[str, str] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO admin_login_logs
            (log_id, admin_id, username, success, reason, ip, user_agent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"login_{secrets.token_hex(10)}",
                admin_id or "",
                username[:100],
                1 if success else 0,
                reason[:80],
                self._request_ip(request_info)[:80],
                self._request_agent(request_info),
                now_iso(),
            ),
        )

    def _build_admin_row(
        self,
        username: str,
        password: str,
        role: str = "operator",
        display_name: str | None = "",
        status: str = "active",
    ) -> dict[str, Any]:
        username = self.validate_admin_username(username)
        self.validate_admin_password(password, username)
        role = role if role in ADMIN_ALLOWED_ROLES else "operator"
        status = status if status in ADMIN_ALLOWED_STATUS else "active"
        salt = secrets.token_hex(16)
        timestamp = now_iso()
        return {
            "admin_id": f"admin_{secrets.token_hex(8)}",
            "username": username,
            "password_hash": self.hash_password(password, salt),
            "salt": salt,
            "role": role,
            "display_name": (display_name or username).strip()[:120],
            "status": status,
            "failed_login_count": 0,
            "locked_until": "",
            "last_login_at": "",
            "last_login_ip": "",
            "created_at": timestamp,
            "updated_at": timestamp,
        }

    def register(self, username: str, password: str) -> dict[str, Any]:
        admin = self._build_admin_row(username, password, role="admin", display_name=username)
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO admin_users
                    (admin_id, username, password_hash, salt, role, display_name, status, failed_login_count,
                     locked_until, last_login_at, last_login_ip, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        admin["admin_id"], admin["username"], admin["password_hash"], admin["salt"],
                        admin["role"], admin["display_name"], admin["status"], admin["failed_login_count"],
                        admin["locked_until"], admin["last_login_at"], admin["last_login_ip"],
                        admin["created_at"], admin["updated_at"],
                    ),
                )
        except integrity_errors() as exc:
            raise ValueError("管理员账号已存在") from exc
        return self.public_admin(admin)

    def login(self, username: str, password: str, request_info: dict[str, str] | None = None) -> dict[str, Any]:
        raw_username = (username or "").strip()
        normalized = self.normalize_admin_username(raw_username)
        result: dict[str, Any] | None = None
        error_message = "用户名或密码错误"
        with self.connect() as connection:
            if not ADMIN_USERNAME_RE.match(normalized) or not isinstance(password, str) or len(password) > 80:
                self._record_login(connection, normalized or raw_username, False, "invalid_payload", request_info=request_info)
            else:
                row = connection.execute("SELECT * FROM admin_users WHERE username = ?", (normalized,)).fetchone()
                if not row:
                    self._record_login(connection, normalized, False, "unknown_user", request_info=request_info)
                else:
                    admin = dict(row)
                    now = now_iso()
                    if admin.get("status", "active") != "active":
                        error_message = "账号已停用，请联系管理员"
                        self._record_login(connection, normalized, False, "disabled", admin["admin_id"], request_info)
                    elif admin.get("locked_until") and admin["locked_until"] > now:
                        error_message = "账号已临时锁定，请稍后再试"
                        self._record_login(connection, normalized, False, "locked", admin["admin_id"], request_info)
                    else:
                        password_hash = self.hash_password(password, admin["salt"])
                        if not secrets.compare_digest(password_hash, admin["password_hash"]):
                            failed = int(admin.get("failed_login_count") or 0) + 1
                            locked_until = ""
                            reason = "bad_password"
                            if failed >= ADMIN_MAX_FAILED_LOGIN:
                                locked_until = (
                                    datetime.utcnow() + timedelta(minutes=ADMIN_LOCK_MINUTES)
                                ).replace(microsecond=0).isoformat() + "Z"
                                reason = "locked_bad_password"
                                error_message = f"密码错误次数过多，账号已锁定 {ADMIN_LOCK_MINUTES} 分钟"
                            connection.execute(
                                """
                                UPDATE admin_users
                                SET failed_login_count = ?, locked_until = ?, updated_at = ?
                                WHERE admin_id = ?
                                """,
                                (failed, locked_until, now_iso(), admin["admin_id"]),
                            )
                            self._record_login(connection, normalized, False, reason, admin["admin_id"], request_info)
                        else:
                            token = secrets.token_urlsafe(32)
                            expires_at = (
                                datetime.utcnow() + timedelta(days=7)
                            ).replace(microsecond=0).isoformat() + "Z"
                            login_at = now_iso()
                            login_ip = self._request_ip(request_info)
                            connection.execute("DELETE FROM admin_sessions WHERE expires_at <= ?", (login_at,))
                            connection.execute(
                                """
                                UPDATE admin_users
                                SET failed_login_count = 0, locked_until = '', last_login_at = ?,
                                    last_login_ip = ?, updated_at = ?
                                WHERE admin_id = ?
                                """,
                                (login_at, login_ip, login_at, admin["admin_id"]),
                            )
                            connection.execute(
                                "INSERT INTO admin_sessions (token, admin_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                                (token, admin["admin_id"], expires_at, login_at),
                            )
                            admin.update(
                                failed_login_count=0,
                                locked_until="",
                                last_login_at=login_at,
                                last_login_ip=login_ip,
                                updated_at=login_at,
                            )
                            self._record_login(connection, normalized, True, "success", admin["admin_id"], request_info)
                            result = {"token": token, "admin": self.public_admin(admin), "expires_at": expires_at}
        if result:
            return result
        raise ValueError(error_message)

    def require_admin(self, token: str | None) -> dict[str, Any]:
        if not token:
            raise PermissionError("未登录")
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT admin_users.* FROM admin_sessions
                JOIN admin_users ON admin_users.admin_id = admin_sessions.admin_id
                WHERE admin_sessions.token = ? AND admin_sessions.expires_at > ?
                """,
                (token, now_iso()),
            ).fetchone()
        if not row:
            raise PermissionError("登录已过期")
        admin = dict(row)
        if admin.get("status", "active") != "active":
            raise PermissionError("账号已停用")
        return self.public_admin(admin)

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self.connect() as connection:
            connection.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))

    def public_admin(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "admin_id": row["admin_id"],
            "username": row["username"],
            "role": row["role"],
            "display_name": row.get("display_name") or row["username"],
            "status": row.get("status") or "active",
            "failed_login_count": int(row.get("failed_login_count") or 0),
            "locked_until": row.get("locked_until") or "",
            "last_login_at": row.get("last_login_at") or "",
            "last_login_ip": row.get("last_login_ip") or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_admins(self, actor: dict[str, Any]) -> list[dict[str, Any]]:
        self.assert_admin_manager(actor)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM admin_users ORDER BY updated_at DESC, created_at DESC"
            ).fetchall()
        return [self.public_admin(dict(row)) for row in rows]

    def create_admin_user(self, payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
        self.assert_admin_manager(actor)
        admin = self._build_admin_row(
            username=str(payload.get("username") or ""),
            password=str(payload.get("password") or ""),
            role=str(payload.get("role") or "operator"),
            display_name=str(payload.get("display_name") or ""),
            status=str(payload.get("status") or "active"),
        )
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO admin_users
                    (admin_id, username, password_hash, salt, role, display_name, status, failed_login_count,
                     locked_until, last_login_at, last_login_ip, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        admin["admin_id"], admin["username"], admin["password_hash"], admin["salt"],
                        admin["role"], admin["display_name"], admin["status"], admin["failed_login_count"],
                        admin["locked_until"], admin["last_login_at"], admin["last_login_ip"],
                        admin["created_at"], admin["updated_at"],
                    ),
                )
        except integrity_errors() as exc:
            raise ValueError("管理员账号已存在") from exc
        return self.public_admin(admin)

    def update_admin_user(self, admin_id: str, payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
        self.assert_admin_manager(actor)
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM admin_users WHERE admin_id = ?", (admin_id,)).fetchone()
            if not row:
                raise ValueError("管理员账号不存在")
            current = dict(row)
            role = str(payload.get("role") or current.get("role") or "operator")
            status = str(payload.get("status") or current.get("status") or "active")
            if role not in ADMIN_ALLOWED_ROLES:
                raise ValueError("管理员角色不合法")
            if status not in ADMIN_ALLOWED_STATUS:
                raise ValueError("账号状态不合法")
            if current["admin_id"] == actor.get("admin_id") and status != "active":
                raise ValueError("不能停用当前登录账号")
            display_name = str(payload.get("display_name") or current.get("display_name") or current["username"]).strip()[:120]
            timestamp = now_iso()
            password = str(payload.get("password") or "")
            if password:
                self.validate_admin_password(password, current["username"])
                salt = secrets.token_hex(16)
                password_hash = self.hash_password(password, salt)
                connection.execute(
                    """
                    UPDATE admin_users
                    SET role = ?, display_name = ?, status = ?, password_hash = ?, salt = ?,
                        failed_login_count = 0, locked_until = '', updated_at = ?
                    WHERE admin_id = ?
                    """,
                    (role, display_name, status, password_hash, salt, timestamp, admin_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE admin_users
                    SET role = ?, display_name = ?, status = ?, updated_at = ?
                    WHERE admin_id = ?
                    """,
                    (role, display_name, status, timestamp, admin_id),
                )
            updated = connection.execute("SELECT * FROM admin_users WHERE admin_id = ?", (admin_id,)).fetchone()
        return self.public_admin(dict(updated))

    def disable_admin_user(self, admin_id: str, actor: dict[str, Any]) -> dict[str, Any]:
        return self.update_admin_user(admin_id, {"status": "disabled"}, actor)

    def list_login_logs(self, actor: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        self.assert_admin_manager(actor)
        limit = max(1, min(int(limit or 100), 300))
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT log_id, admin_id, username, success, reason, ip, user_agent, created_at
                FROM admin_login_logs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "log_id": row["log_id"],
                "admin_id": row["admin_id"],
                "username": row["username"],
                "success": bool(row["success"]),
                "reason": row["reason"],
                "ip": row["ip"] or "",
                "user_agent": row["user_agent"] or "",
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def dashboard(self) -> dict[str, Any]:
        with self.connect() as connection:
            today = (datetime.utcnow() + timedelta(hours=8)).date()
            yesterday = today - timedelta(days=1)
            today_text = today.isoformat()
            yesterday_text = yesterday.isoformat()
            orders_ready = self.table_exists(connection, "orders")
            if orders_ready:
                order_row = connection.execute(
                    """
                    SELECT COUNT(*) AS total,
                           COALESCE(SUM(CASE WHEN payment_status = 'paid' THEN total_amount ELSE 0 END), 0) AS revenue,
                           SUM(CASE WHEN status = 'pending_ship' THEN 1 ELSE 0 END) AS pending_ship,
                           SUM(CASE WHEN status IN ('after_sale', 'refund_requested') THEN 1 ELSE 0 END) AS after_sale
                    FROM orders
                    """
                ).fetchone()
                today_order_row = connection.execute(
                    """
                    SELECT COUNT(*) AS total,
                           COALESCE(SUM(CASE WHEN payment_status = 'paid' THEN total_amount ELSE 0 END), 0) AS revenue
                    FROM orders
                    WHERE substr(created_at, 1, 10) = ?
                    """,
                    (today_text,),
                ).fetchone()
                yesterday_order_row = connection.execute(
                    """
                    SELECT COALESCE(SUM(CASE WHEN payment_status = 'paid' THEN total_amount ELSE 0 END), 0) AS revenue
                    FROM orders
                    WHERE substr(created_at, 1, 10) = ?
                    """,
                    (yesterday_text,),
                ).fetchone()
                recent_orders = connection.execute(
                    """
                    SELECT order_id, status, payment_status, total_amount, receiver_json, created_at
                    FROM orders ORDER BY created_at DESC LIMIT 6
                    """
                ).fetchall()
            else:
                order_row = {"total": 0, "revenue": 0, "pending_ship": 0, "after_sale": 0}
                today_order_row = {"total": 0, "revenue": 0}
                yesterday_order_row = {"revenue": 0}
                recent_orders = []
            if self.table_exists(connection, "users"):
                user_row = connection.execute(
                    """
                    SELECT COUNT(*) AS total,
                           SUM(CASE WHEN substr(created_at, 1, 10) = ? THEN 1 ELSE 0 END) AS today
                    FROM users
                    """,
                    (today_text,),
                ).fetchone()
            else:
                user_row = {"total": 0, "today": 0}
            if self.table_exists(connection, "managed_materials"):
                material_row = connection.execute(
                    """
                    SELECT COUNT(*) AS total,
                           SUM(CASE WHEN substr(created_at, 1, 10) = ? THEN 1 ELSE 0 END) AS today
                    FROM managed_materials
                    """,
                    (today_text,),
                ).fetchone()
            else:
                material_row = {"total": 0, "today": 0}
            assessments = (
                connection.execute("SELECT COUNT(*) AS c FROM energy_assessments").fetchone()["c"]
                if self.table_exists(connection, "energy_assessments")
                else 0
            )
            daily_energies = (
                connection.execute("SELECT COUNT(*) AS c FROM daily_energies").fetchone()["c"]
                if self.table_exists(connection, "daily_energies")
                else 0
            )
            content_blocks = (
                connection.execute("SELECT COUNT(*) AS c FROM content_blocks").fetchone()["c"]
                if self.table_exists(connection, "content_blocks")
                else 0
            )
            return {
                "users": user_row["total"] or 0,
                "materials": material_row["total"] or 0,
                "assessments": assessments,
                "daily_energies": daily_energies,
                "content_blocks": content_blocks,
                "orders": order_row["total"] or 0,
                "revenue": round(float(order_row["revenue"] or 0), 2),
                "pending_ship": order_row["pending_ship"] or 0,
                "after_sale": order_row["after_sale"] or 0,
                "metric_deltas": {
                    "users": {"today": user_row["today"] or 0},
                    "orders": {"today": today_order_row["total"] or 0},
                    "revenue": {
                        "today": round(float(today_order_row["revenue"] or 0), 2),
                        "yesterday": round(float(yesterday_order_row["revenue"] or 0), 2),
                    },
                    "materials": {"today": material_row["today"] or 0},
                },
                "recent_orders": [
                    {
                        "order_id": row["order_id"],
                        "status": row["status"],
                        "status_text": self.order_status_text(row["status"]),
                        "payment_status": row["payment_status"],
                        "total_amount": row["total_amount"],
                        "receiver": self.loads(row["receiver_json"], {}),
                        "created_at": row["created_at"],
                    }
                    for row in recent_orders
                ],
            }

    def system_status(self) -> dict[str, Any]:
        checks = [
            {
                "key": "wechat_phone",
                "label": "微信手机号快捷绑定",
                "ready": bool(
                    (os.getenv("WECHAT_APP_ID") or os.getenv("WX_APPID"))
                    and (os.getenv("WECHAT_APP_SECRET") or os.getenv("WX_APP_SECRET"))
                ),
                "hint": "需要 WECHAT_APP_ID 和 WECHAT_APP_SECRET",
            },
            {
                "key": "wechat_pay",
                "label": "微信支付",
                "ready": bool(
                    os.getenv("WECHAT_PAY_APP_ID")
                    and os.getenv("WECHAT_PAY_MCH_ID")
                    and os.getenv("WECHAT_PAY_SERIAL_NO")
                    and os.getenv("WECHAT_PAY_NOTIFY_URL")
                    and (os.getenv("WECHAT_PAY_PRIVATE_KEY_PATH") or os.getenv("WECHAT_PAY_PRIVATE_KEY"))
                ),
                "hint": "检查商户号、证书序列号、回调地址和私钥",
            },
            {
                "key": "kuaidi100",
                "label": "快递100",
                "ready": bool(os.getenv("KUAIDI100_CUSTOMER") and os.getenv("KUAIDI100_KEY")),
                "hint": "需要 KUAIDI100_CUSTOMER 和 KUAIDI100_KEY",
            },
            {
                "key": "cos",
                "label": "腾讯云 COS 素材",
                "ready": bool(
                    os.getenv("TENCENT_COS_SECRET_ID")
                    and os.getenv("TENCENT_COS_SECRET_KEY")
                    and os.getenv("TENCENT_COS_BUCKET")
                ),
                "hint": "检查 COS 密钥、存储桶和区域",
            },
        ]
        return {
            "checks": checks,
            "ready_count": sum(1 for item in checks if item["ready"]),
            "total_count": len(checks),
        }

    def list_users(
        self,
        keyword: str = "",
        profile_status: str = "",
        energy_tag: str = "",
        spend_level: str = "",
        start_date: str = "",
        end_date: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if keyword.strip():
            value = f"%{keyword.strip()}%"
            clauses.append("(u.user_id LIKE ? OR COALESCE(u.nickname, '') LIKE ? OR COALESCE(u.phone_number, '') LIKE ?)")
            params.extend([value, value, value])
        if profile_status == "complete":
            clauses.append("COALESCE(u.nickname, '') <> '' AND COALESCE(u.phone_number, '') <> ''")
        elif profile_status == "incomplete":
            clauses.append("(COALESCE(u.nickname, '') = '' OR COALESCE(u.phone_number, '') = '')")
        if start_date:
            clauses.append("u.created_at >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("u.created_at <= ?")
            params.append(end_date)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT u.user_id, u.openid, u.nickname, u.avatar_url, u.gender, u.phone_number, u.source,
                       u.created_at, u.updated_at,
                       COUNT(o.order_id) AS order_count,
                       COALESCE(SUM(CASE WHEN o.payment_status='paid' THEN o.total_amount ELSE 0 END), 0) AS paid_amount,
                       MAX(o.created_at) AS last_order_at
                FROM users u
                LEFT JOIN orders o ON o.user_id = u.user_id
                {where}
                GROUP BY u.user_id, u.openid, u.nickname, u.avatar_url, u.gender, u.phone_number,
                         u.source, u.created_at, u.updated_at
                ORDER BY u.updated_at DESC LIMIT ?
                """,
                params,
            ).fetchall()
            assessments = connection.execute(
                """
                SELECT assessment_id, user_id, name, core_wish, created_at, result_json
                FROM energy_assessments
                ORDER BY created_at DESC
                """
            ).fetchall()
        latest_by_user: dict[str, dict[str, Any]] = {}
        for row in assessments:
            item = dict(row)
            if item["user_id"] in latest_by_user:
                continue
            try:
                result = json.loads(item.get("result_json") or "{}")
            except json.JSONDecodeError:
                result = {}
            item["energy"] = energy_tags_from_assessment(result)
            latest_by_user[item["user_id"]] = item
        output = []
        for row in rows:
            item = dict(row)
            latest = latest_by_user.get(item["user_id"])
            energy = latest.get("energy") if latest else {"tags": [], "energy_profile": {}, "support_elements": []}
            item["profile_status"] = "complete" if item.get("nickname") and item.get("phone_number") else "incomplete"
            item["profile_status_text"] = "资料完整" if item["profile_status"] == "complete" else "待完善"
            item["paid_amount"] = float(item.get("paid_amount") or 0)
            item["order_count"] = int(item.get("order_count") or 0)
            item["spend_level"] = "high" if item["paid_amount"] >= 1000 else "paid" if item["paid_amount"] > 0 else "none"
            item["spend_level_text"] = {"high": "高客单", "paid": "已消费", "none": "未消费"}[item["spend_level"]]
            item["energy_tags"] = energy.get("tags", [])
            item["energy_profile"] = energy.get("energy_profile", {})
            item["support_elements"] = energy.get("support_elements", [])
            item["latest_assessment_at"] = latest.get("created_at") if latest else ""
            output.append(item)
        if energy_tag:
            output = [item for item in output if energy_tag in "".join(item.get("energy_tags") or [])]
        if spend_level:
            output = [item for item in output if item.get("spend_level") == spend_level]
        return output

    def sync_user_avatars_to_cos(self, limit: int = 100) -> dict[str, Any]:
        storage = AvatarStorage()
        if not storage.enabled:
            raise ValueError("腾讯云 COS 未配置完整，无法同步用户头像")
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT user_id, avatar_url
                FROM users
                WHERE COALESCE(avatar_url, '') <> ''
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        synced: list[dict[str, str]] = []
        skipped = 0
        failed: list[dict[str, str]] = []
        for row in rows:
            user_id = str(row["user_id"])
            avatar_url = str(row["avatar_url"] or "").strip()
            if storage.is_managed_url(avatar_url):
                skipped += 1
                continue
            try:
                result = storage.upload_url(user_id, avatar_url)
                with self.connect() as connection:
                    connection.execute(
                        "UPDATE users SET avatar_url = ?, updated_at = ? WHERE user_id = ?",
                        (result.avatar_url, now_iso(), user_id),
                    )
                synced.append({"user_id": user_id, "avatar_url": result.avatar_url})
            except ValueError as exc:
                failed.append({"user_id": user_id, "error": str(exc)})
        return {
            "checked": len(rows),
            "synced": len(synced),
            "skipped": skipped,
            "failed": failed,
            "items": synced,
        }

    def get_user_detail(self, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            user = connection.execute(
                """
                SELECT user_id, openid, nickname, avatar_url, gender, phone_number, source, created_at, updated_at
                FROM users WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            if not user:
                raise ValueError("用户不存在")
            assessments = connection.execute(
                """
                SELECT assessment_id, user_id, name, core_wish, created_at, result_json
                FROM energy_assessments WHERE user_id = ? ORDER BY created_at DESC LIMIT 20
                """,
                (user_id,),
            ).fetchall()
            daily_rows = connection.execute(
                """
                SELECT user_id, energy_date, mode, assessment_id, result_json, updated_at
                FROM daily_energies WHERE user_id = ? ORDER BY updated_at DESC LIMIT 14
                """,
                (user_id,),
            ).fetchall()
            order_rows = connection.execute(
                "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 30",
                (user_id,),
            ).fetchall()
            design_rows = connection.execute(
                "SELECT * FROM diy_designs WHERE user_id = ? ORDER BY updated_at DESC LIMIT 30",
                (user_id,),
            ).fetchall()
        user_data = dict(user)
        parsed_assessments = []
        for row in assessments:
            item = dict(row)
            try:
                result = json.loads(item.pop("result_json") or "{}")
            except json.JSONDecodeError:
                result = {}
            item["summary"] = result.get("report", {}).get("summary") or result.get("recommendation_copy") or ""
            item["energy"] = energy_tags_from_assessment(result)
            parsed_assessments.append(item)
        daily = []
        for row in daily_rows:
            item = dict(row)
            try:
                result = json.loads(item.pop("result_json") or "{}")
            except json.JSONDecodeError:
                result = {}
            item.update({
                "title": result.get("title") or result.get("theme") or "",
                "score": result.get("score"),
                "lucky_color": result.get("lucky_color") or "",
                "recommended_stone": result.get("recommended_stone") or result.get("lucky_crystal") or "",
            })
            daily.append(item)
        orders = [self.public_order(dict(row)) for row in order_rows]
        designs = []
        for row in design_rows:
            item = dict(row)
            for source, target in [("design_json", "design"), ("sequence_json", "sequence")]:
                try:
                    item[target] = json.loads(item.pop(source) or "{}")
                except json.JSONDecodeError:
                    item[target] = {} if target == "design" else []
            designs.append(item)
        paid_amount = sum(float(order.get("total_amount") or 0) for order in orders if order.get("payment_status") == "paid")
        latest_energy = parsed_assessments[0]["energy"] if parsed_assessments else {"tags": [], "energy_profile": {}, "support_elements": []}
        return {
            "user": {
                **user_data,
                "profile_status": "complete" if user_data.get("nickname") and user_data.get("phone_number") else "incomplete",
                "profile_status_text": "资料完整" if user_data.get("nickname") and user_data.get("phone_number") else "待完善",
            },
            "energy": latest_energy,
            "assets": {
                "points": 0,
                "coupon_count": 0,
                "coupon_balance": 0,
                "note": "积分和优惠券账户表尚未接入，当前为占位看板。",
            },
            "stats": {
                "order_count": len(orders),
                "paid_amount": paid_amount,
                "design_count": len(designs),
                "assessment_count": len(parsed_assessments),
            },
            "assessments": parsed_assessments,
            "daily_energies": daily,
            "orders": orders,
            "designs": designs,
        }

    def list_assessments(
        self,
        keyword: str = "",
        core_wish: str = "",
        hide_tests: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        keyword = keyword.strip()
        clauses = []
        params: list[Any] = []
        if keyword:
            clauses.append("(user_id LIKE ? OR name LIKE ? OR core_wish LIKE ? OR assessment_id LIKE ?)")
            value = f"%{keyword}%"
            params.extend([value, value, value, value])
        if core_wish:
            clauses.append("core_wish LIKE ?")
            params.append(f"%{core_wish}%")
        if hide_tests:
            clauses.append("COALESCE(user_id, '') NOT LIKE '%test%'")
            clauses.append("COALESCE(user_id, '') NOT LIKE '%smoke%'")
            clauses.append("COALESCE(user_id, '') NOT LIKE 'api-%'")
            clauses.append("COALESCE(name, '') NOT LIKE '%测试%'")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT assessment_id, user_id, name, core_wish, created_at, result_json
                FROM energy_assessments
                {where}
                ORDER BY created_at DESC LIMIT ?
                """,
                params,
            ).fetchall()
            order_rows = connection.execute(
                """
                SELECT order_id, user_id, status, payment_status, total_amount, created_at
                FROM orders
                ORDER BY created_at ASC
                """
            ).fetchall()
        orders_by_user: dict[str, list[dict[str, Any]]] = {}
        for order in order_rows:
            item = dict(order)
            orders_by_user.setdefault(item.get("user_id") or "", []).append(item)
        results = []
        for row in rows:
            item = dict(row)
            try:
                result = json.loads(item.pop("result_json"))
            except json.JSONDecodeError:
                result = {}
            item["summary"] = result.get("report", {}).get("summary") or result.get("recommendation_copy") or ""
            item["final_energy_profile"] = result.get("final_energy_profile", {})
            item["formula"] = self.extract_assessment_formula(result)
            item["conversion"] = self.assessment_conversion(item, orders_by_user.get(item.get("user_id") or "", []))
            results.append(item)
        return results

    def extract_assessment_formula(self, result: dict[str, Any]) -> dict[str, Any]:
        primary = result.get("primary_crystal") or {}
        supporting = result.get("supporting_crystals") or []
        if isinstance(supporting, dict):
            supporting = [supporting]
        bracelet_plan = result.get("bracelet_plan") or {}
        layout = bracelet_plan.get("layout") if isinstance(bracelet_plan, dict) else []
        tags = []
        if primary:
            tags.append({"role": "主石", "name": primary.get("name") or primary.get("code") or "-"})
        for item in supporting[:3]:
            if isinstance(item, dict):
                tags.append({"role": "副石", "name": item.get("name") or item.get("code") or "-"})
        if not tags and isinstance(layout, list):
            for item in layout[:4]:
                if isinstance(item, dict):
                    tags.append({"role": item.get("role") or "珠材", "name": item.get("name") or item.get("crystal_code") or "-"})
        return {
            "primary": primary,
            "supporting": supporting,
            "bracelet_plan": bracelet_plan,
            "tags": tags,
        }

    @staticmethod
    def assessment_conversion(assessment: dict[str, Any], orders: list[dict[str, Any]]) -> dict[str, Any]:
        created_at = assessment.get("created_at") or ""
        matched = None
        for order in orders:
            if not created_at or str(order.get("created_at") or "") >= str(created_at):
                matched = order
                break
        if not matched:
            return {"status": "none", "text": "未下单", "order_id": "", "payment_status": "", "amount": 0}
        return {
            "status": "converted",
            "text": f"已转订单: {matched.get('order_id')}",
            "order_id": matched.get("order_id") or "",
            "payment_status": matched.get("payment_status") or "",
            "amount": float(matched.get("total_amount") or 0),
        }

    def list_daily_energies(self, keyword: str = "", limit: int = 100) -> list[dict[str, Any]]:
        keyword = keyword.strip()
        params: list[Any] = []
        where = ""
        if keyword:
            where = "WHERE user_id LIKE ? OR energy_date LIKE ? OR mode LIKE ?"
            value = f"%{keyword}%"
            params.extend([value, value, value])
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT user_id, energy_date, mode, assessment_id, result_json, updated_at
                FROM daily_energies
                {where}
                ORDER BY updated_at DESC LIMIT ?
                """,
                params,
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            try:
                result = json.loads(item.pop("result_json"))
            except json.JSONDecodeError:
                result = {}
            item["title"] = result.get("title", "")
            item["score"] = result.get("score")
            item["lucky_color"] = result.get("lucky_color")
            item["recommended_stone"] = result.get("recommended_stone") or result.get("lucky_crystal")
            results.append(item)
        return results

    def list_checkins(self, keyword: str = "", limit: int = 100) -> list[dict[str, Any]]:
        keyword = keyword.strip()
        params: list[Any] = []
        where = ""
        if keyword:
            where = "WHERE user_id LIKE ? OR checkin_date LIKE ?"
            value = f"%{keyword}%"
            params.extend([value, value])
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT user_id, checkin_date, mood, sleep, stress, created_at, updated_at
                FROM daily_checkins
                {where}
                ORDER BY checkin_date DESC, updated_at DESC LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_setting(self, setting_key: str) -> Any | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT setting_json FROM system_settings WHERE setting_key = ?",
                (setting_key,),
            ).fetchone()
        if not row:
            return None
        return json_value(row["setting_json"], None)

    def save_setting(self, setting_key: str, value: Any, updated_at: str) -> None:
        if use_mysql() and not self._force_sqlite:
            sql = """
                INSERT INTO system_settings (setting_key, setting_json, updated_at)
                VALUES (?, ?, ?)
                ON DUPLICATE KEY UPDATE setting_json=VALUES(setting_json), updated_at=VALUES(updated_at)
            """
        else:
            sql = """
                INSERT INTO system_settings (setting_key, setting_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET
                    setting_json = excluded.setting_json, updated_at = excluded.updated_at
            """
        with self.connect() as connection:
            connection.execute(sql, (setting_key, json_text(value), updated_at))

    def daily_energy_rules(self) -> dict[str, Any]:
        raw = self.get_setting(DAILY_RULES_SETTING_KEY)
        rules = normalize_daily_energy_rules(raw)
        return {
            "rules": rules,
            "public_options": public_daily_rules_payload(rules),
            "rules_version": daily_rules_version(rules),
            "updated_at": "",
        }

    def save_daily_energy_rules(self, payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
        if (actor or {}).get("role") == "viewer":
            raise PermissionError("只读账号不能修改每日能量规则")
        rules_payload = payload.get("rules") if isinstance(payload, dict) and "rules" in payload else payload
        if not isinstance(rules_payload, dict):
            raise ValueError("规则配置必须是 JSON 对象")
        reset_to_default = bool(payload.get("reset_to_default")) if isinstance(payload, dict) else False
        if reset_to_default:
            rules_payload = default_daily_energy_rules()
        rules = normalize_daily_energy_rules(rules_payload)
        timestamp = now_iso()
        self.save_setting(DAILY_RULES_SETTING_KEY, rules, timestamp)
        return {
            "rules": rules,
            "public_options": public_daily_rules_payload(rules),
            "rules_version": daily_rules_version(rules),
            "updated_at": timestamp,
        }

    @staticmethod
    def material_margin(price: Any, cost: Any) -> dict[str, Any]:
        price_value = max(0.0, float(price or 0))
        cost_value = max(0.0, float(cost or 0))
        amount = round(price_value - cost_value, 4)
        rate = round(amount / price_value, 4) if price_value > 0 else 0
        if cost_value <= 0:
            status = "unknown"
        elif price_value <= 0 or amount < 0:
            status = "loss"
        elif rate < 0.25:
            status = "low"
        else:
            status = "normal"
        return {
            "margin_amount": amount,
            "margin_rate": rate,
            "margin_status": status,
        }

    @staticmethod
    def material_inventory_value(price: Any, cost: Any, stock: Any) -> dict[str, Any]:
        price_value = max(0.0, float(price or 0))
        cost_value = max(0.0, float(cost or 0))
        stock_value = max(0, int(float(stock or 0)))
        return {
            "inventory_cost_value": round(cost_value * stock_value, 2),
            "inventory_retail_value": round(price_value * stock_value, 2),
            "inventory_margin_value": round((price_value - cost_value) * stock_value, 2),
        }

    def public_material(self, row: dict[str, Any], connection: Any | None = None) -> dict[str, Any]:
        image_path = row.get("image_path") or ""
        image_url = normalize_material_image_url(row.get("image_url")) or material_url_from_path(image_path)
        image_urls = clean_image_urls(row.get("image_urls_json") or row.get("image_urls"), image_url, image_path)
        if not image_url and image_urls:
            image_url = image_urls[0]
        stock = int(float(row.get("stock") or 0))
        safety_stock = int(float(row.get("safety_stock") or 0))
        stock_status = "out" if stock <= 0 else "low" if safety_stock > 0 and stock <= safety_stock else "normal"
        material = {
            **row,
            "enabled": bool(row.get("enabled", 1)),
            "series": row.get("series") or row.get("name") or "",
            "grade": row.get("grade") or "",
            "image_url": image_url,
            "image_urls": image_urls,
            "image_pool": image_urls,
        }
        result = enrich_material_with_knowledge(material, connection)
        cost_price = float(row.get("cost_price") or 0)
        price = float((result.get("sku") or {}).get("price_per_bead") or row.get("price") or 0)
        ops = {
            "cost_price": cost_price,
            "safety_stock": safety_stock,
            "supplier_name": row.get("supplier_name") or "",
            "purchase_note": row.get("purchase_note") or "",
            "stock_status": stock_status,
            **self.material_margin(price, cost_price),
            **self.material_inventory_value(price, cost_price, stock),
        }
        sku = result.get("sku") or {}
        result["sku"] = {**sku, **ops}
        result["ops"] = ops
        result["quality"] = self.material_quality(result)
        return result

    def material_quality(self, material: dict[str, Any]) -> dict[str, Any]:
        sku = material.get("sku") or {}
        energy = material.get("energy") or {}
        visual = material.get("visual") or {}
        rules = material.get("rules") or {}
        ops = material.get("ops") or {}
        params = visual.get("material_params") or {}
        issues: list[dict[str, str]] = []

        def add(key: str, label: str, severity: str = "warning", group: str = "data") -> None:
            issues.append({"key": key, "label": label, "severity": severity, "group": group})

        if not sku.get("category"):
            add("category_missing", "缺少分类", "critical", "base")
        if not sku.get("series"):
            add("series_missing", "缺少品种", "critical", "base")
        if not sku.get("material_code"):
            add("material_code_missing", "缺少材料编码", "critical", "base")
        if not sku.get("name"):
            add("name_missing", "缺少展示名称", "critical", "base")
        if float(sku.get("price_per_bead") or 0) <= 0:
            add("price_invalid", "单颗价为 0", "critical", "sale")
        if float(sku.get("size_mm") or 0) <= 0:
            add("size_invalid", "珠径无效", "critical", "base")
        if float(sku.get("weight_g") or 0) <= 0:
            add("weight_missing", "缺少重量", "warning", "base")
        if not visual.get("thumbnail_url") and not visual.get("image_url") and not visual.get("image_urls"):
            add("image_missing", "缺少图片", "critical", "visual")
        if not energy.get("primary_element"):
            add("primary_element_missing", "缺少主五行", "critical", "energy")
        if not energy.get("effects"):
            add("effects_missing", "缺少功效标签", "critical", "energy")
        if not energy.get("wish_pools"):
            add("wish_pool_missing", "缺少愿景池", "warning", "energy")
        if not rules.get("allowed_roles"):
            add("roles_missing", "缺少材料角色", "warning", "rules")
        if not rules.get("match_rules"):
            add("match_rules_missing", "缺少搭配规则", "warning", "rules")
        if not params.get("bead_shape"):
            add("bead_shape_missing", "缺少珠体形制", "warning", "material")
        if not params.get("surface_finish"):
            add("surface_finish_missing", "缺少表面工艺", "warning", "material")
        if not params.get("transparency_level"):
            add("transparency_missing", "缺少通透度", "info", "material")
        stock_status = ops.get("stock_status") or sku.get("stock_status")
        if stock_status == "out":
            add("stock_out", "库存为 0", "critical", "stock")
        elif stock_status == "low":
            add("stock_low", "低于安全库存", "warning", "stock")
        if int(float(ops.get("safety_stock") or sku.get("safety_stock") or 0)) <= 0:
            add("safety_stock_missing", "未设安全库存", "info", "stock")
        if float(ops.get("cost_price") or sku.get("cost_price") or 0) <= 0:
            add("cost_missing", "未设成本价", "warning", "ops")
        margin_status = ops.get("margin_status") or sku.get("margin_status")
        if margin_status == "loss":
            add("margin_loss", "成本高于售价", "critical", "ops")
        elif margin_status == "low":
            add("margin_low", "毛利率偏低", "warning", "ops")
        if not str(ops.get("supplier_name") or sku.get("supplier_name") or "").strip():
            add("supplier_missing", "未设供应商", "info", "ops")

        penalty = {"critical": 18, "warning": 8, "info": 3}
        score = max(0, 100 - sum(penalty.get(issue["severity"], 5) for issue in issues))
        critical_count = sum(1 for issue in issues if issue["severity"] == "critical")
        warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
        if critical_count:
            level = "risk"
        elif score >= 90:
            level = "excellent"
        elif score >= 75:
            level = "good"
        else:
            level = "warn"
        return {
            "score": score,
            "level": level,
            "issues": issues,
            "issue_count": len(issues),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "ready_for_sale": critical_count == 0,
        }

    @staticmethod
    def material_matches_quality(material: dict[str, Any], quality: str = "") -> bool:
        key = str(quality or "").strip().lower()
        if not key:
            return True
        data = material.get("quality") or {}
        level = str(data.get("level") or "").lower()
        if key in {"risk", "warn", "good", "excellent"}:
            return level == key
        if key == "ready":
            return bool(data.get("ready_for_sale"))
        if key in {"incomplete", "issue", "issues"}:
            return int(data.get("issue_count") or 0) > 0
        return True

    @staticmethod
    def material_matches_stock_state(material: dict[str, Any], stock_state: str = "") -> bool:
        key = str(stock_state or "").strip().lower()
        if not key:
            return True
        sku = material.get("sku") or {}
        status = str(sku.get("stock_status") or (material.get("ops") or {}).get("stock_status") or "").lower()
        if key in {"out", "low", "normal"}:
            return status == key
        if key == "alert":
            return status in {"out", "low"}
        return True

    @staticmethod
    def material_matches_margin(material: dict[str, Any], margin: str = "") -> bool:
        key = str(margin or "").strip().lower()
        if not key:
            return True
        sku = material.get("sku") or {}
        status = str(sku.get("margin_status") or (material.get("ops") or {}).get("margin_status") or "").lower()
        if key in {"unknown", "loss", "low", "normal"}:
            return status == key
        if key == "risk":
            return status in {"loss", "low"}
        return True

    def list_orders(self, keyword: str = "", status: str = "", limit: int = 100) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if keyword.strip():
            clauses.append(
                "(order_id LIKE ? OR user_id LIKE ? OR receiver_json LIKE ? OR logistics_json LIKE ?)"
            )
            value = f"%{keyword.strip()}%"
            params.extend([value, value, value, value])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM orders {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self.public_order(dict(row)) for row in rows]

    def get_order(self, order_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            user = None
            if row:
                has_users = self.table_exists(connection, "users")
                if has_users:
                    user = connection.execute(
                        """
                        SELECT user_id, openid, nickname, avatar_url, gender, phone_number, source, created_at, updated_at
                        FROM users WHERE user_id = ?
                        """,
                        (row["user_id"],),
                    ).fetchone()
                design_record = None
                has_designs = self.table_exists(connection, "diy_designs")
                if has_designs and row["design_id"]:
                    design_record = connection.execute(
                        "SELECT * FROM diy_designs WHERE design_id = ?",
                        (row["design_id"],),
                    ).fetchone()
            else:
                design_record = None
        if not row:
            raise ValueError("订单不存在")
        order = self.public_order(dict(row))
        snapshot_sequence = []
        for index, sequence_item in enumerate(order["sequence"]):
            item = dict(sequence_item)
            image_urls = clean_image_urls(
                item.get("image_urls") or item.get("image_pool"),
                item.get("image_url") or "",
                item.get("image_path") or "",
            )
            snapshot_sequence.append(
                {
                    **item,
                    "index": item.get("index") or index + 1,
                    "image_url": item.get("image_url") or (image_urls[0] if image_urls else ""),
                    "image_urls": image_urls,
                    "image_pool": image_urls,
                }
            )
        order["sequence"] = snapshot_sequence
        order["customer"] = dict(user) if user else {}
        if design_record:
            saved_design = dict(design_record)
            saved_design["design"] = self.loads(saved_design.pop("design_json"), {})
            saved_design["sequence"] = self.loads(saved_design.pop("sequence_json"), [])
            order["saved_design"] = saved_design
        else:
            order["saved_design"] = {}
        return order

    def ship_order(
        self,
        order_id: str,
        carrier: str,
        tracking_no: str,
        carrier_code: str = "shunfeng",
        phone_tail: str = "",
    ) -> dict[str, Any]:
        order = self.get_order(order_id)
        if order["payment_status"] != "paid":
            raise ValueError("订单未支付，不能发货")
        if not tracking_no.strip():
            raise ValueError("请填写快递单号")
        timestamp = now_iso()
        logistics = {
            "carrier": carrier.strip() or "顺丰速运",
            "carrier_code": carrier_code.strip() or "shunfeng",
            "tracking_no": tracking_no.strip(),
            "phone_tail": phone_tail.strip(),
            "status": "in_transit",
            "status_text": "运输中",
            "updated_at": timestamp,
            "source": "admin",
            "traces": [
                {"time": timestamp, "location": "宇涧工作室", "desc": "商家已打包，待快递揽收"},
                {"time": timestamp, "location": "宇涧工作室", "desc": "商家已填写发货信息，等待物流公司更新轨迹"}
            ],
        }
        try:
            wechat_shipping = self.wechat_trade.upload_shipping(order, logistics)
        except Exception as exc:
            wechat_shipping = {"synced": False, "error": str(exc)}
        logistics["wechat_shipping"] = wechat_shipping
        history = list(order.get("status_history") or [])
        history.append(
            {
                "status": "shipped",
                "label": "后台已发货"
                + ("，发货信息已同步微信" if wechat_shipping.get("synced") else ""),
                "time": timestamp,
            }
        )
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE orders SET status = 'shipped', logistics_json = ?, status_history_json = ?, updated_at = ?
                WHERE order_id = ?
                """,
                (
                    json.dumps(logistics, ensure_ascii=False),
                    json.dumps(history, ensure_ascii=False),
                    timestamp,
                    order_id,
                ),
            )
        return self.get_order(order_id)

    def wechat_trade_status(self) -> dict[str, Any]:
        return self.wechat_trade.status()

    def configure_wechat_order_path(self, path: str = "") -> dict[str, Any]:
        return self.wechat_trade.configure_order_detail_path(path or None)

    def sync_order_shipping_to_wechat(self, order_id: str) -> dict[str, Any]:
        order = self.get_order(order_id)
        logistics = order.get("logistics") or {}
        if not logistics.get("tracking_no"):
            raise ValueError("订单还没有快递单号，无法同步微信发货信息")
        result = self.wechat_trade.upload_shipping(order, logistics)
        logistics["wechat_shipping"] = result
        with self.connect() as connection:
            connection.execute(
                "UPDATE orders SET logistics_json = ?, updated_at = ? WHERE order_id = ?",
                (json.dumps(logistics, ensure_ascii=False), now_iso(), order_id),
            )
        return {"order": self.get_order(order_id), "wechat_shipping": result}

    def update_order_status(self, order_id: str, status: str, note: str = "") -> dict[str, Any]:
        allowed = {
            "pending_payment", "pending_ship", "shipped", "completed",
            "after_sale", "refund_requested", "refunded", "closed",
        }
        if status not in allowed:
            raise ValueError("不支持的订单状态")
        order = self.get_order(order_id)
        timestamp = now_iso()
        history = list(order.get("status_history") or [])
        history.append(
            {
                "status": status,
                "label": note.strip() or f"后台调整为{self.order_status_text(status)}",
                "time": timestamp,
            }
        )
        payment_status = "refunded" if status == "refunded" else order["payment_status"]
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE orders SET status = ?, payment_status = ?, status_history_json = ?, updated_at = ?
                WHERE order_id = ?
                """,
                (status, payment_status, json.dumps(history, ensure_ascii=False), timestamp, order_id),
            )
        return self.get_order(order_id)

    def public_order(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "order_id": row["order_id"],
            "out_trade_no": row.get("out_trade_no") or row["order_id"],
            "user_id": row["user_id"],
            "design_id": row.get("design_id") or "",
            "openid": row.get("openid") or "",
            "status": row["status"],
            "status_text": self.order_status_text(row["status"]),
            "payment_status": row["payment_status"],
            "total_amount": row["total_amount"],
            "total_fee": row.get("total_fee"),
            "currency": row.get("currency") or "CNY",
            "receiver": self.loads(row["receiver_json"], {}),
            "design": self.loads(row["design_json"], {}),
            "sequence": self.loads(row["sequence_json"], []),
            "bom": self.loads(row["bom_json"], []),
            "remark": row.get("remark") or "",
            "payment": self.loads(row.get("payment_json") or "", {}),
            "after_sale_status": row.get("after_sale_status") or "",
            "refund_status": row.get("refund_status") or "",
            "refund": self.loads(row.get("refund_json") or "", {}),
            "logistics": self.loads(row.get("logistics_json") or "", {}),
            "status_history": self.loads(row.get("status_history_json") or "", []),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "paid_at": row.get("paid_at"),
        }

    @staticmethod
    def order_status_text(status: str) -> str:
        return {
            "pending_payment": "待付款",
            "pending_ship": "待发货",
            "shipped": "待收货",
            "completed": "已完成",
            "after_sale": "售后中",
            "refund_requested": "退款中",
            "refunded": "已退款",
            "closed": "已关闭",
        }.get(status, status)

    @staticmethod
    def loads(text: str, default):
        if not text:
            return default
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return default

    def list_materials(
        self,
        keyword: str = "",
        top: str = "",
        category: str = "",
        element: str = "",
        status: str = "",
        quality: str = "",
        stock_state: str = "",
        margin: str = "",
        sort_by: str = "sort_order",
        sort_order: str = "asc",
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if top:
            clauses.append("top = ?")
            params.append(top)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if element:
            element_key = normalize_element_key(element)
            element_values = [item for item in (element_key or element, element_label(element_key or element)) if item]
            element_values = list(dict.fromkeys(element_values))
            placeholders = ", ".join(["?"] * len(element_values))
            clauses.append(f"element IN ({placeholders})")
            params.extend(element_values)
        if status == "enabled":
            clauses.append("enabled = 1")
        elif status == "disabled":
            clauses.append("enabled = 0")
        if keyword.strip():
            clauses.append(
                "(name LIKE ? OR category LIKE ? OR series LIKE ? OR grade LIKE ? OR effect LIKE ? OR element LIKE ? OR material_code LIKE ?)"
            )
            value = f"%{keyword.strip()}%"
            params.extend([value, value, value, value, value, value, value])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sort_columns = {
            "sort_order": "sort_order",
            "price": "price",
            "size": "size",
            "element": "element",
            "stock": "stock",
            "updated_at": "updated_at",
        }
        order_by = sort_columns.get(sort_by, "sort_order")
        direction = "DESC" if str(sort_order).lower() == "desc" else "ASC"
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM managed_materials {where} ORDER BY {order_by} {direction}, updated_at DESC",
                params,
            ).fetchall()
            materials = [self.public_material(dict(row), connection) for row in rows]
        if quality:
            materials = [item for item in materials if self.material_matches_quality(item, quality)]
        if stock_state:
            materials = [item for item in materials if self.material_matches_stock_state(item, stock_state)]
        if margin:
            materials = [item for item in materials if self.material_matches_margin(item, margin)]
        return materials

    def material_spu_group(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        first = items[0]
        first_sku = first.get("sku") or {}
        first_energy = first.get("energy") or {}
        first_visual = first.get("visual") or {}
        sorted_items = sorted(items, key=lambda item: float((item.get("sku") or {}).get("size_mm") or 0))
        prices = [float((item.get("sku") or {}).get("price_per_bead") or 0) for item in sorted_items]
        costs = [float((item.get("sku") or {}).get("cost_price") or 0) for item in sorted_items]
        margin_rates = [float((item.get("sku") or {}).get("margin_rate") or 0) for item in sorted_items]
        margin_risk_count = sum(
            1 for item in sorted_items if (item.get("sku") or {}).get("margin_status") in {"loss", "low"}
        )
        margin_loss_count = sum(1 for item in sorted_items if (item.get("sku") or {}).get("margin_status") == "loss")
        inventory_cost_value = round(
            sum(float((item.get("sku") or {}).get("inventory_cost_value") or 0) for item in sorted_items),
            2,
        )
        inventory_retail_value = round(
            sum(float((item.get("sku") or {}).get("inventory_retail_value") or 0) for item in sorted_items),
            2,
        )
        inventory_margin_value = round(
            sum(float((item.get("sku") or {}).get("inventory_margin_value") or 0) for item in sorted_items),
            2,
        )
        low_stock_count = sum(1 for item in sorted_items if (item.get("sku") or {}).get("stock_status") == "low")
        out_stock_count = sum(1 for item in sorted_items if (item.get("sku") or {}).get("stock_status") == "out")
        quality_scores = [int(((item.get("quality") or {}).get("score") or 0)) for item in sorted_items]
        quality_issue_count = sum(int(((item.get("quality") or {}).get("issue_count") or 0)) for item in sorted_items)
        quality_risk_count = sum(1 for item in sorted_items if (item.get("quality") or {}).get("level") == "risk")
        min_quality_score = min(quality_scores) if quality_scores else 0
        avg_quality_score = round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0
        sizes = [
            f"{(item.get('sku') or {}).get('size_mm')}mm"
            for item in sorted_items
            if (item.get("sku") or {}).get("size_mm")
        ]
        image = ""
        for item in sorted_items:
            visual = item.get("visual") or {}
            image = visual.get("thumbnail_url") or visual.get("image_url") or ""
            if image:
                break
        material_code = first_sku.get("material_code") or first.get("material_code") or ""
        top = first_sku.get("top") or first.get("top") or ""
        category = first_sku.get("category") or first.get("category") or ""
        series = first_sku.get("series") or first.get("series") or first_sku.get("name") or first.get("name") or ""
        spu_key = f"{top}::{category}::{series}::{material_code}"
        numeric_sizes = sorted(
            {
                int(float((item.get("sku") or {}).get("size_mm") or 0))
                for item in sorted_items
                if float((item.get("sku") or {}).get("size_mm") or 0).is_integer()
                and float((item.get("sku") or {}).get("size_mm") or 0) > 0
            }
        )
        required_sizes = list(MATERIAL_REQUIRED_BEAD_SIZES) if top == "bead" else []
        missing_sizes = [size for size in required_sizes if size not in numeric_sizes]
        if top != "bead":
            spec_status = "not_applicable"
        elif not numeric_sizes:
            spec_status = "empty"
        elif missing_sizes:
            spec_status = "partial"
        else:
            spec_status = "complete"
        spec_coverage = (
            round((len(required_sizes) - len(missing_sizes)) / len(required_sizes), 4)
            if required_sizes
            else 1
        )
        return {
            "key": material_code or spu_key,
            "group_key": spu_key,
            "spu": {
                "material_code": material_code,
                "top": top,
                "category": category,
                "series": series,
                "name": series,
                "sku_count": len(sorted_items),
                "total_stock": sum(int(float((item.get("sku") or {}).get("stock") or 0)) for item in sorted_items),
                "enabled_count": sum(1 for item in sorted_items if (item.get("sku") or {}).get("enabled")),
                "min_price": min(prices) if prices else 0,
                "max_price": max(prices) if prices else 0,
                "min_cost": min(costs) if costs else 0,
                "max_cost": max(costs) if costs else 0,
                "min_margin_rate": min(margin_rates) if margin_rates else 0,
                "max_margin_rate": max(margin_rates) if margin_rates else 0,
                "margin_risk_count": margin_risk_count,
                "margin_loss_count": margin_loss_count,
                "inventory_cost_value": inventory_cost_value,
                "inventory_retail_value": inventory_retail_value,
                "inventory_margin_value": inventory_margin_value,
                "low_stock_count": low_stock_count,
                "out_stock_count": out_stock_count,
                "quality_score": avg_quality_score,
                "min_quality_score": min_quality_score,
                "quality_issue_count": quality_issue_count,
                "quality_risk_count": quality_risk_count,
                "sizes": sizes,
                "size_values": numeric_sizes,
                "required_sizes": required_sizes,
                "missing_sizes": missing_sizes,
                "spec_status": spec_status,
                "spec_coverage": spec_coverage,
                "image": image,
            },
            "sku": first_sku,
            "energy": first_energy,
            "visual": first_visual,
            "items": sorted_items,
            "totalStock": sum(int(float((item.get("sku") or {}).get("stock") or 0)) for item in sorted_items),
            "enabledCount": sum(1 for item in sorted_items if (item.get("sku") or {}).get("enabled")),
            "minPrice": min(prices) if prices else 0,
            "maxPrice": max(prices) if prices else 0,
            "minCost": min(costs) if costs else 0,
            "maxCost": max(costs) if costs else 0,
            "minMarginRate": min(margin_rates) if margin_rates else 0,
            "maxMarginRate": max(margin_rates) if margin_rates else 0,
            "marginRiskCount": margin_risk_count,
            "marginLossCount": margin_loss_count,
            "inventoryCostValue": inventory_cost_value,
            "inventoryRetailValue": inventory_retail_value,
            "inventoryMarginValue": inventory_margin_value,
            "lowStockCount": low_stock_count,
            "outStockCount": out_stock_count,
            "qualityScore": avg_quality_score,
            "minQualityScore": min_quality_score,
            "qualityIssueCount": quality_issue_count,
            "qualityRiskCount": quality_risk_count,
            "sizeValues": numeric_sizes,
            "requiredSizes": required_sizes,
            "missingSizes": missing_sizes,
            "specStatus": spec_status,
            "specCoverage": spec_coverage,
            "sizes": " / ".join(dict.fromkeys(sizes)),
            "image": image,
        }

    @staticmethod
    def material_spu_matches_spec_state(group: dict[str, Any], spec_state: str = "") -> bool:
        state = str(spec_state or "").strip().lower()
        if not state:
            return True
        status = str(group.get("specStatus") or (group.get("spu") or {}).get("spec_status") or "").lower()
        if state == "incomplete":
            return status in {"partial", "empty"}
        if state == "applicable":
            return status != "not_applicable"
        return status == state

    def list_material_spus(
        self,
        keyword: str = "",
        top: str = "",
        category: str = "",
        element: str = "",
        status: str = "",
        quality: str = "",
        stock_state: str = "",
        margin: str = "",
        spec_state: str = "",
        sort_by: str = "sort_order",
        sort_order: str = "asc",
    ) -> list[dict[str, Any]]:
        materials = self.list_materials(
            keyword=keyword,
            top=top,
            category=category,
            element=element,
            status=status,
            quality=quality,
            stock_state=stock_state,
            margin=margin,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in materials:
            sku = item.get("sku") or {}
            key = (
                f"{sku.get('top') or item.get('top') or ''}::"
                f"{sku.get('category') or item.get('category') or ''}::"
                f"{sku.get('series') or item.get('series') or item.get('name') or ''}::"
                f"{sku.get('material_code') or item.get('material_code') or ''}"
            )
            groups.setdefault(key, []).append(item)
        result = [self.material_spu_group(items) for items in groups.values()]
        if spec_state:
            result = [group for group in result if self.material_spu_matches_spec_state(group, spec_state)]
        return result

    def save_material(
        self,
        payload: dict[str, Any],
        material_id: str | None = None,
        actor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = now_iso()
        item_id = material_id or payload.get("id") or self.generate_material_id(payload)
        with self.connect() as connection:
            self._ensure_material_taxonomy_schema(connection)
            self._sync_material_taxonomy_from_materials(connection)
            payload = self.canonicalize_material_payload_taxonomy({**payload, "id": item_id}, connection)
            payload = self.canonicalize_material_payload_options(payload, connection)
            item = self.normalize_material(payload)
            item["skuId"] = self.unique_material_sku(connection, item["skuId"], item_id)
            existing = connection.execute("SELECT * FROM managed_materials WHERE id = ?", (item_id,)).fetchone()
            before = dict(existing) if existing else None
            if existing:
                connection.execute(
                    """
                    UPDATE managed_materials SET
                    skuId=?, top=?, category=?, series=?, material_code=?, grade=?, name=?, effect=?, element=?, price=?, size=?, weight=?,
                    cost_price=?, safety_stock=?, supplier_name=?, purchase_note=?,
                    color=?, shine=?, image_path=?, image_url=?, image_urls_json=?, stock=?, enabled=?, sort_order=?, updated_at=?
                    WHERE id=?
                    """,
                    (
                        item["skuId"], item["top"], item["category"], item["series"], item["material_code"], item["grade"],
                        item["name"], item["effect"], item["element"],
                        item["price"], item["size"], item["weight"], item["cost_price"], item["safety_stock"],
                        item["supplier_name"], item["purchase_note"], item["color"], item["shine"],
                        item.get("image_path", ""), item.get("image_url", ""), item["image_urls_json"], item["stock"], item["enabled"],
                        item["sort_order"], timestamp, item_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO managed_materials
                    (id, skuId, top, category, series, material_code, grade, name, effect, element, price, size, weight, color, shine,
                     cost_price, safety_stock, supplier_name, purchase_note, image_path, image_url, image_urls_json, stock, enabled,
                     sort_order, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"], item["skuId"], item["top"], item["category"], item["series"], item["material_code"], item["grade"],
                        item["name"], item["effect"],
                        item["element"], item["price"], item["size"], item["weight"], item["color"], item["shine"],
                        item["cost_price"], item["safety_stock"], item["supplier_name"], item["purchase_note"],
                        item.get("image_path", ""), item.get("image_url", ""), item["image_urls_json"], item["stock"], item["enabled"],
                        item["sort_order"], timestamp, timestamp,
                    ),
                )
            upsert_material_knowledge(
                payload,
                item,
                connection=connection,
                force_update=has_explicit_knowledge(payload),
            )
            self.record_material_audit(
                connection,
                action="update" if before else "create",
                before=before,
                after={**item, "updated_at": timestamp, **({} if before else {"created_at": timestamp})},
                actor=actor,
            )
        invalidate_material_cache()
        return self.get_material(item_id)

    def material_token(self, value: Any, fallback: str = "mat") -> str:
        text = str(value or "").strip().lower()
        token = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
        if token:
            return token[:24]
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8] if text else secrets.token_hex(4)
        return f"{fallback}-{digest}"

    def material_size_token(self, value: Any) -> str:
        size = float(value or 0)
        if size.is_integer():
            return f"{int(size)}mm"
        return f"{str(size).replace('.', 'p')}mm"

    def generate_material_sku(self, payload: dict[str, Any]) -> str:
        top_codes = {
            "bead": "10",
            "accessory": "20",
            "pendant": "30",
            "incense": "40",
        }
        top = str(payload.get("top") or "bead").strip()
        top_code = top_codes.get(top, "90")
        material_code = material_code_from_payload(payload)
        identity = "|".join(
            str(payload.get(key) or "")
            for key in ("top", "category", "series", "name", "grade")
        )
        digest_source = f"{material_code}|{identity}"
        digest = hashlib.sha1(digest_source.encode("utf-8")).hexdigest()
        material_no = int(digest[:10], 16) % 10_000_000
        try:
            size_value = float(payload.get("size_mm") or payload.get("size") or 0)
        except (TypeError, ValueError):
            size_value = 0
        size_code = max(0, min(999, int(round(size_value * 10))))
        check_digit = int(digest[-2:], 16) % 10
        return f"{top_code}{material_no:07d}{size_code:03d}{check_digit}"

    def generate_material_id(self, payload: dict[str, Any]) -> str:
        base = self.generate_material_sku(payload)
        return f"mat_{base}_{secrets.token_hex(3)}"

    def unique_material_sku(self, connection: Any, sku: str, item_id: str) -> str:
        base = re.sub(r"\D+", "", str(sku or "").strip())
        if not base:
            base = str(secrets.randbelow(10**11)).zfill(11)
        candidate = base
        suffix = 2
        while connection.execute(
            "SELECT id FROM managed_materials WHERE skuId = ? AND id <> ?",
            (candidate, item_id),
        ).fetchone():
            candidate = f"{base}{suffix:02d}"
            suffix += 1
        return candidate

    def normalize_material(self, payload: dict[str, Any]) -> dict[str, Any]:
        required = ["id", "top", "category", "name"]
        for key in required:
            if not str(payload.get(key, "")).strip():
                raise ValueError(f"{key} 不能为空")
        effects = payload.get("effects")
        if isinstance(effects, str):
            effects = [item.strip() for item in re.split(r"[,，、\n\r]+", effects) if item.strip()]
        effects = effects if isinstance(effects, list) else []
        primary_element = normalize_element_key(payload.get("primary_element") or payload.get("element"))
        effect_text = str(payload.get("effect") or (effects[0] if effects else "")).strip()
        if not primary_element:
            raise ValueError("请选择主五行")
        if not effect_text:
            raise ValueError("effects 不能为空")
        image_path = str(payload.get("image_path") or "").strip()
        primary_image_url = normalize_material_image_url(
            payload.get("thumbnail_url") or payload.get("image_url") or ""
        )
        image_urls = clean_image_urls(
            payload.get("image_urls") or payload.get("image_pool") or payload.get("image_urls_json"),
            primary_image_url,
            image_path,
        )
        if not primary_image_url and image_urls:
            primary_image_url = image_urls[0]
        stock = max(0, int(float(payload.get("stock") or 0)))
        enabled = 1 if payload.get("enabled", True) and stock > 0 else 0
        raw_sku_id = str(payload.get("skuId") or "").strip()
        sku_id = raw_sku_id if raw_sku_id.isdigit() else self.generate_material_sku(payload)
        return {
            "id": str(payload["id"]).strip(),
            "skuId": sku_id,
            "top": str(payload["top"]).strip(),
            "category": str(payload["category"]).strip(),
            "series": str(payload.get("series") or payload.get("name") or "").strip(),
            "material_code": material_code_from_payload(payload),
            "grade": str(payload.get("grade") or "").strip(),
            "name": str(payload["name"]).strip(),
            "effect": effect_text,
            "element": primary_element,
            "price": float(payload.get("price_per_bead") or payload.get("price") or 0),
            "size": float(payload.get("size_mm") or payload.get("size") or 8),
            "weight": float(payload.get("weight_g") or payload.get("weight") or 1),
            "cost_price": max(0, float(payload.get("cost_price") or payload.get("cost") or 0)),
            "safety_stock": max(0, int(float(payload.get("safety_stock") or payload.get("stock_warning") or 0))),
            "supplier_name": str(payload.get("supplier_name") or payload.get("supplier") or "").strip(),
            "purchase_note": str(payload.get("purchase_note") or payload.get("purchase_remark") or "").strip(),
            "color": str(payload.get("color_hex") or payload.get("color") or "#dfe3e5").strip(),
            "shine": str(payload.get("shine_hex") or payload.get("shine") or "#ffffff").strip(),
            "image_path": image_path,
            "image_url": primary_image_url,
            "image_urls": image_urls,
            "image_urls_json": json_text(image_urls),
            "stock": stock,
            "enabled": enabled,
            "sort_order": int(payload.get("sort_order") or 0),
        }

    def get_material(self, material_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM managed_materials WHERE id = ?", (material_id,)).fetchone()
            if row:
                return self.public_material(dict(row), connection)
        if not row:
            raise ValueError("材料不存在")

    def delete_material(self, material_id: str, actor: dict[str, Any] | None = None) -> None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM managed_materials WHERE id = ?", (material_id,)).fetchone()
            before = dict(row) if row else None
            connection.execute("DELETE FROM managed_materials WHERE id = ?", (material_id,))
            if before:
                self.record_material_audit(connection, action="delete", before=before, actor=actor)
        invalidate_material_cache()

    def batch_update_materials(
        self,
        ids: list[str],
        action: str,
        value: Any = None,
        actor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_ids = [str(item).strip() for item in ids if str(item).strip()]
        if not clean_ids:
            raise ValueError("请选择要操作的珠材")
        placeholders = ", ".join(["?"] * len(clean_ids))
        timestamp = now_iso()
        with self.connect() as connection:
            before_rows = [
                dict(row)
                for row in connection.execute(
                    f"SELECT * FROM managed_materials WHERE id IN ({placeholders})",
                    clean_ids,
                ).fetchall()
            ]
            if action == "enable":
                cursor = connection.execute(
                    f"UPDATE managed_materials SET enabled=CASE WHEN stock > 0 THEN 1 ELSE 0 END, updated_at=? WHERE id IN ({placeholders})",
                    [timestamp, *clean_ids],
                )
            elif action == "disable":
                cursor = connection.execute(
                    f"UPDATE managed_materials SET enabled=0, updated_at=? WHERE id IN ({placeholders})",
                    [timestamp, *clean_ids],
                )
            elif action == "price":
                price = float(value)
                if price < 0:
                    raise ValueError("价格不能小于 0")
                cursor = connection.execute(
                    f"UPDATE managed_materials SET price=?, updated_at=? WHERE id IN ({placeholders})",
                    [price, timestamp, *clean_ids],
                )
            elif action == "stock":
                stock = max(0, int(float(value)))
                cursor = connection.execute(
                    f"UPDATE managed_materials SET stock=?, enabled=CASE WHEN ? > 0 THEN enabled ELSE 0 END, updated_at=? WHERE id IN ({placeholders})",
                    [stock, stock, timestamp, *clean_ids],
                )
            elif action == "safety_stock":
                safety_stock = max(0, int(float(value)))
                cursor = connection.execute(
                    f"UPDATE managed_materials SET safety_stock=?, updated_at=? WHERE id IN ({placeholders})",
                    [safety_stock, timestamp, *clean_ids],
                )
            elif action == "delete":
                cursor = connection.execute(
                    f"DELETE FROM managed_materials WHERE id IN ({placeholders})",
                    clean_ids,
                )
            else:
                raise ValueError("不支持的批量操作")
            affected = cursor.rowcount if cursor.rowcount is not None else len(clean_ids)
            after_by_id = {}
            if action != "delete" and before_rows:
                after_rows = connection.execute(
                    f"SELECT * FROM managed_materials WHERE id IN ({placeholders})",
                    clean_ids,
                ).fetchall()
                after_by_id = {row["id"]: dict(row) for row in after_rows}
            for before in before_rows:
                self.record_material_audit(
                    connection,
                    action=f"batch_{action}",
                    before=before,
                    after=after_by_id.get(before["id"]),
                    actor=actor,
                )
        invalidate_material_cache()
        return {"action": action, "requested": len(clean_ids), "affected": affected}

    def public_home_banner(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("banner_id"),
            "title": row.get("title") or "",
            "subtitle": row.get("subtitle") or "",
            "eyebrow": row.get("eyebrow") or "",
            "image_url": row.get("image_url") or "",
            "actionText": row.get("action_text") or "",
            "actionUrl": row.get("action_url") or "",
            "theme": row.get("theme") or "dark",
            "status": row.get("status") or "draft",
            "sort_order": int(row.get("sort_order") or 0),
            "updated_at": row.get("updated_at"),
        }

    def list_home_banners(
        self,
        keyword: str = "",
        status: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if keyword:
            like = f"%{keyword}%"
            clauses.append("(title LIKE ? OR subtitle LIKE ? OR eyebrow LIKE ?)")
            params.extend([like, like, like])
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM home_banners {where} ORDER BY sort_order ASC, updated_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self.public_home_banner(dict(row)) for row in rows]

    def get_home_banner(self, banner_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM home_banners WHERE banner_id = ?", (banner_id,)).fetchone()
        if not row:
            raise ValueError("首页 Banner 不存在")
        return self.public_home_banner(dict(row))

    def save_home_banner(self, payload: dict[str, Any], banner_id: str | None = None) -> dict[str, Any]:
        timestamp = now_iso()
        item_id = (banner_id or payload.get("id") or payload.get("banner_id") or f"banner_{secrets.token_hex(5)}").strip()
        item = {
            "banner_id": item_id,
            "title": str(payload.get("title") or "").strip(),
            "subtitle": str(payload.get("subtitle") or "").strip(),
            "eyebrow": str(payload.get("eyebrow") or "").strip(),
            "image_url": str(payload.get("image_url") or payload.get("image") or "").strip(),
            "action_text": str(payload.get("actionText") or payload.get("action_text") or "").strip(),
            "action_url": str(payload.get("actionUrl") or payload.get("action_url") or "").strip(),
            "theme": str(payload.get("theme") or "dark").strip(),
            "status": str(payload.get("status") or "draft").strip(),
            "sort_order": int(payload.get("sort_order") or 0),
        }
        if not item["title"]:
            raise ValueError("Banner 标题不能为空")
        with self.connect() as connection:
            existing = connection.execute("SELECT banner_id FROM home_banners WHERE banner_id = ?", (item_id,)).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE home_banners SET title=?, subtitle=?, eyebrow=?, image_url=?, action_text=?,
                    action_url=?, theme=?, status=?, sort_order=?, updated_at=? WHERE banner_id=?
                    """,
                    (
                        item["title"], item["subtitle"], item["eyebrow"], item["image_url"], item["action_text"],
                        item["action_url"], item["theme"], item["status"], item["sort_order"], timestamp, item_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO home_banners
                    (banner_id, title, subtitle, eyebrow, image_url, action_text, action_url, theme, status,
                     sort_order, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["banner_id"], item["title"], item["subtitle"], item["eyebrow"], item["image_url"],
                        item["action_text"], item["action_url"], item["theme"], item["status"], item["sort_order"],
                        timestamp, timestamp,
                    ),
                )
        return self.get_home_banner(item_id)

    def delete_home_banner(self, banner_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM home_banners WHERE banner_id = ?", (banner_id,))

    def list_blocks(self, section: str = "") -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if section:
            where = "WHERE section = ?"
            params.append(section)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM content_blocks {where} ORDER BY sort_order ASC, updated_at DESC",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def save_block(self, payload: dict[str, Any], block_id: str | None = None) -> dict[str, Any]:
        timestamp = now_iso()
        item_id = block_id or payload.get("block_id") or f"block_{secrets.token_hex(6)}"
        item = {
            "block_id": item_id,
            "section": str(payload.get("section") or "home").strip(),
            "title": str(payload.get("title") or "").strip(),
            "subtitle": str(payload.get("subtitle") or "").strip(),
            "body": str(payload.get("body") or "").strip(),
            "image_url": str(payload.get("image_url") or "").strip(),
            "action_text": str(payload.get("action_text") or "").strip(),
            "action_url": str(payload.get("action_url") or "").strip(),
            "status": str(payload.get("status") or "draft").strip(),
            "sort_order": int(payload.get("sort_order") or 0),
        }
        if not item["title"]:
            raise ValueError("标题不能为空")
        with self.connect() as connection:
            existing = connection.execute("SELECT block_id FROM content_blocks WHERE block_id = ?", (item_id,)).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE content_blocks SET section=?, title=?, subtitle=?, body=?, image_url=?,
                    action_text=?, action_url=?, status=?, sort_order=?, updated_at=?
                    WHERE block_id=?
                    """,
                    (
                        item["section"], item["title"], item["subtitle"], item["body"], item["image_url"],
                        item["action_text"], item["action_url"], item["status"], item["sort_order"],
                        timestamp, item_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO content_blocks
                    (block_id, section, title, subtitle, body, image_url, action_text, action_url, status,
                     sort_order, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["block_id"], item["section"], item["title"], item["subtitle"], item["body"],
                        item["image_url"], item["action_text"], item["action_url"], item["status"],
                        item["sort_order"], timestamp, timestamp,
                    ),
                )
        return self.get_block(item_id)

    def get_block(self, block_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM content_blocks WHERE block_id = ?", (block_id,)).fetchone()
        if not row:
            raise ValueError("板块不存在")
        return dict(row)

    def delete_block(self, block_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM content_blocks WHERE block_id = ?", (block_id,))

    def public_community_post(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("post_id"),
            "title": row.get("title") or "",
            "author": row.get("author") or "",
            "desc": row.get("description") or "",
            "story": row.get("story") or "",
            "scene": row.get("scene") or "",
            "authorNote": row.get("author_note") or "",
            "likes": int(row.get("likes") or 0),
            "tone": row.get("tone") or "clear",
            "recipe": json_value(row.get("recipe_json"), []),
            "materials": json_value(row.get("materials_json"), []),
            "tags": json_value(row.get("tags_json"), []),
            "image_url": row.get("image_url") or "",
            "is_home_hot": bool(row.get("is_home_hot")),
            "status": row.get("status") or "draft",
            "sort_order": int(row.get("sort_order") or 0),
            "updated_at": row.get("updated_at"),
        }

    def public_recommendation_from_community_post(self, post: dict[str, Any]) -> dict[str, Any]:
        materials = post.get("materials") or []
        story = post.get("story") or post.get("desc") or ""
        scene = post.get("scene") or ""
        scenes = [scene] if scene else []
        return {
            "id": post.get("id"),
            "source": "community_post",
            "name": post.get("title") or "",
            "title": post.get("title") or "",
            "subtitle": post.get("scene") or post.get("desc") or "",
            "desc": post.get("desc") or post.get("story") or "",
            "price": 0,
            "tone": post.get("tone") or "clear",
            "recipe": post.get("recipe") or [],
            "materials": materials,
            "designStory": story,
            "designReason": post.get("authorNote") or post.get("desc") or "",
            "scenes": scenes,
            "tags": post.get("tags") or [],
            "image_url": post.get("image_url") or "",
            "is_home_hot": bool(post.get("is_home_hot")),
            "status": post.get("status") or "draft",
            "sort_order": int(post.get("sort_order") or 0),
            "updated_at": post.get("updated_at"),
        }

    def list_community_posts(
        self,
        keyword: str = "",
        status: str = "",
        is_home_hot: bool | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if keyword:
            like = f"%{keyword}%"
            clauses.append("(title LIKE ? OR author LIKE ? OR description LIKE ? OR tags_json LIKE ?)")
            params.extend([like, like, like, like])
        if status:
            clauses.append("status = ?")
            params.append(status)
        if is_home_hot is not None:
            clauses.append("is_home_hot = ?")
            params.append(1 if is_home_hot else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM community_posts {where} ORDER BY sort_order ASC, updated_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self.public_community_post(dict(row)) for row in rows]

    def get_community_post(self, post_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM community_posts WHERE post_id = ?", (post_id,)).fetchone()
        if not row:
            raise ValueError("社区灵感不存在")
        return self.public_community_post(dict(row))

    def save_community_post(self, payload: dict[str, Any], post_id: str | None = None) -> dict[str, Any]:
        timestamp = now_iso()
        item_id = (post_id or payload.get("id") or payload.get("post_id") or f"inspo_{secrets.token_hex(5)}").strip()
        item = {
            "post_id": item_id,
            "title": str(payload.get("title") or "").strip(),
            "author": str(payload.get("author") or "宇涧主理人").strip(),
            "description": str(payload.get("desc") or payload.get("description") or "").strip(),
            "story": str(payload.get("story") or "").strip(),
            "scene": str(payload.get("scene") or "").strip(),
            "author_note": str(payload.get("authorNote") or payload.get("author_note") or "").strip(),
            "likes": int(payload.get("likes") or 0),
            "tone": str(payload.get("tone") or "clear").strip(),
            "recipe_json": json_text(payload.get("recipe") or []),
            "materials_json": json_text(payload.get("materials") or []),
            "tags_json": json_text(payload.get("tags") or []),
            "image_url": str(payload.get("image_url") or payload.get("image") or "").strip(),
            "is_home_hot": 1 if payload.get("is_home_hot", False) else 0,
            "status": str(payload.get("status") or "draft").strip(),
            "sort_order": int(payload.get("sort_order") or 0),
        }
        if not item["title"]:
            raise ValueError("标题不能为空")
        with self.connect() as connection:
            existing = connection.execute("SELECT post_id FROM community_posts WHERE post_id = ?", (item_id,)).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE community_posts SET title=?, author=?, description=?, story=?, scene=?, author_note=?,
                    likes=?, tone=?, recipe_json=?, materials_json=?, tags_json=?, image_url=?, is_home_hot=?, status=?,
                    sort_order=?, updated_at=? WHERE post_id=?
                    """,
                    (
                        item["title"], item["author"], item["description"], item["story"], item["scene"],
                        item["author_note"], item["likes"], item["tone"], item["recipe_json"],
                        item["materials_json"], item["tags_json"], item["image_url"], item["is_home_hot"], item["status"],
                        item["sort_order"], timestamp, item_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO community_posts
                    (post_id, title, author, description, story, scene, author_note, likes, tone, recipe_json,
                     materials_json, tags_json, image_url, is_home_hot, status, sort_order, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["post_id"], item["title"], item["author"], item["description"], item["story"],
                        item["scene"], item["author_note"], item["likes"], item["tone"], item["recipe_json"],
                        item["materials_json"], item["tags_json"], item["image_url"], item["is_home_hot"], item["status"],
                        item["sort_order"], timestamp, timestamp,
                    ),
                )
        return self.get_community_post(item_id)

    def delete_community_post(self, post_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM community_posts WHERE post_id = ?", (post_id,))

    def public_recommendation_plan(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("plan_id"),
            "name": row.get("name") or "",
            "subtitle": row.get("subtitle") or "",
            "desc": row.get("description") or "",
            "price": float(row.get("price") or 0),
            "tone": row.get("tone") or "clear",
            "recipe": json_value(row.get("recipe_json"), []),
            "materials": json_value(row.get("materials_json"), []),
            "designStory": row.get("design_story") or "",
            "designReason": row.get("design_reason") or "",
            "scenes": json_value(row.get("scenes_json"), []),
            "tags": json_value(row.get("tags_json"), []),
            "image_url": row.get("image_url") or "",
            "is_home_hot": bool(row.get("is_home_hot")),
            "status": row.get("status") or "draft",
            "sort_order": int(row.get("sort_order") or 0),
            "updated_at": row.get("updated_at"),
        }

    def list_recommendation_plans(
        self,
        keyword: str = "",
        status: str = "",
        is_home_hot: bool | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if keyword:
            like = f"%{keyword}%"
            clauses.append("(name LIKE ? OR subtitle LIKE ? OR description LIKE ? OR tags_json LIKE ?)")
            params.extend([like, like, like, like])
        if status:
            clauses.append("status = ?")
            params.append(status)
        if is_home_hot is not None:
            clauses.append("is_home_hot = ?")
            params.append(1 if is_home_hot else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM recommendation_plans {where} ORDER BY sort_order ASC, updated_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self.public_recommendation_plan(dict(row)) for row in rows]

    def get_recommendation_plan(self, plan_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM recommendation_plans WHERE plan_id = ?", (plan_id,)).fetchone()
        if not row:
            raise ValueError("推荐方案不存在")
        return self.public_recommendation_plan(dict(row))

    def save_recommendation_plan(self, payload: dict[str, Any], plan_id: str | None = None) -> dict[str, Any]:
        timestamp = now_iso()
        item_id = (plan_id or payload.get("id") or payload.get("plan_id") or f"plan_{secrets.token_hex(5)}").strip()
        item = {
            "plan_id": item_id,
            "name": str(payload.get("name") or "").strip(),
            "subtitle": str(payload.get("subtitle") or "").strip(),
            "description": str(payload.get("desc") or payload.get("description") or "").strip(),
            "price": float(payload.get("price") or 0),
            "tone": str(payload.get("tone") or "clear").strip(),
            "recipe_json": json_text(payload.get("recipe") or []),
            "materials_json": json_text(payload.get("materials") or []),
            "design_story": str(payload.get("designStory") or payload.get("design_story") or "").strip(),
            "design_reason": str(payload.get("designReason") or payload.get("design_reason") or "").strip(),
            "scenes_json": json_text(payload.get("scenes") or []),
            "tags_json": json_text(payload.get("tags") or []),
            "image_url": str(payload.get("image_url") or payload.get("image") or "").strip(),
            "is_home_hot": 1 if payload.get("is_home_hot", True) else 0,
            "status": str(payload.get("status") or "draft").strip(),
            "sort_order": int(payload.get("sort_order") or 0),
        }
        if not item["name"]:
            raise ValueError("方案名称不能为空")
        with self.connect() as connection:
            existing = connection.execute("SELECT plan_id FROM recommendation_plans WHERE plan_id = ?", (item_id,)).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE recommendation_plans SET name=?, subtitle=?, description=?, price=?, tone=?,
                    recipe_json=?, materials_json=?, design_story=?, design_reason=?, scenes_json=?, tags_json=?,
                    image_url=?, is_home_hot=?, status=?, sort_order=?, updated_at=? WHERE plan_id=?
                    """,
                    (
                        item["name"], item["subtitle"], item["description"], item["price"], item["tone"],
                        item["recipe_json"], item["materials_json"], item["design_story"], item["design_reason"],
                        item["scenes_json"], item["tags_json"], item["image_url"], item["is_home_hot"],
                        item["status"], item["sort_order"], timestamp, item_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO recommendation_plans
                    (plan_id, name, subtitle, description, price, tone, recipe_json, materials_json,
                     design_story, design_reason, scenes_json, tags_json, image_url, is_home_hot, status,
                     sort_order, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["plan_id"], item["name"], item["subtitle"], item["description"], item["price"],
                        item["tone"], item["recipe_json"], item["materials_json"], item["design_story"],
                        item["design_reason"], item["scenes_json"], item["tags_json"], item["image_url"],
                        item["is_home_hot"], item["status"], item["sort_order"], timestamp, timestamp,
                    ),
                )
        return self.get_recommendation_plan(item_id)

    def delete_recommendation_plan(self, plan_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM recommendation_plans WHERE plan_id = ?", (plan_id,))
