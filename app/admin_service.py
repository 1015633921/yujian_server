from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Any

from .avatar_storage import AvatarStorage
from .materials import (
    MATERIAL_CATALOG,
    clean_image_urls,
    invalidate_material_cache,
    material_url_from_path,
    normalize_material_image_url,
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
                self._ensure_community_post_columns(connection)
                if count == 0:
                    self._seed_materials(connection)
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
                    grade TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL,
                    effect TEXT NOT NULL,
                    element TEXT NOT NULL,
                    price REAL NOT NULL,
                    size REAL NOT NULL,
                    weight REAL NOT NULL,
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
            count = connection.execute("SELECT COUNT(*) AS c FROM managed_materials").fetchone()["c"]
            if count == 0:
                self._seed_materials(connection)
            block_count = connection.execute("SELECT COUNT(*) AS c FROM content_blocks").fetchone()["c"]
            if block_count == 0:
                self._seed_blocks(connection)
            banner_count = connection.execute("SELECT COUNT(*) AS c FROM home_banners").fetchone()["c"]
            if banner_count == 0:
                self._seed_home_banners(connection)

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
                (id, skuId, top, category, series, grade, name, effect, element, price, size, weight, color, shine,
                 image_path, image_url, image_urls_json, enabled, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    item["id"],
                    item["skuId"],
                    item["top"],
                    item["category"],
                    item.get("series") or item["name"],
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
            if "grade" not in columns:
                connection.execute("ALTER TABLE managed_materials ADD COLUMN grade VARCHAR(40) NOT NULL DEFAULT ''")
            if "stock" not in columns:
                connection.execute("ALTER TABLE managed_materials ADD COLUMN stock INT NOT NULL DEFAULT 0")
            if "image_urls_json" not in columns:
                connection.execute("ALTER TABLE managed_materials ADD COLUMN image_urls_json LONGTEXT")
            connection.execute("UPDATE managed_materials SET series = name WHERE COALESCE(series, '') = ''")
            return
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(managed_materials)").fetchall()}
        if "series" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN series TEXT NOT NULL DEFAULT ''")
        if "grade" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN grade TEXT NOT NULL DEFAULT ''")
        if "stock" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN stock INTEGER NOT NULL DEFAULT 0")
        if "image_urls_json" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN image_urls_json TEXT")
        connection.execute("UPDATE managed_materials SET series = name WHERE COALESCE(series, '') = ''")

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
                (id, skuId, top, category, series, grade, name, effect, element, price, size, weight, color, shine,
                 image_path, image_url, enabled, sort_order, created_at, updated_at)
                VALUES (?, ?, 'bead', ?, ?, ?, ?, '净化与放大', '金', ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    item_id,
                    sku_id,
                    category,
                    series,
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

    def public_material(self, row: dict[str, Any]) -> dict[str, Any]:
        image_path = row.get("image_path") or ""
        image_url = normalize_material_image_url(row.get("image_url")) or material_url_from_path(image_path)
        image_urls = clean_image_urls(row.get("image_urls_json") or row.get("image_urls"), image_url, image_path)
        if not image_url and image_urls:
            image_url = image_urls[0]
        return {
            **row,
            "enabled": bool(row.get("enabled", 1)),
            "series": row.get("series") or row.get("name") or "",
            "grade": row.get("grade") or "",
            "image_url": image_url,
            "image_urls": image_urls,
            "image_pool": image_urls,
        }

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
        element: str = "",
        status: str = "",
        sort_by: str = "sort_order",
        sort_order: str = "asc",
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if top:
            clauses.append("top = ?")
            params.append(top)
        if element:
            clauses.append("element = ?")
            params.append(element)
        if status == "enabled":
            clauses.append("enabled = 1")
        elif status == "disabled":
            clauses.append("enabled = 0")
        if keyword.strip():
            clauses.append("(name LIKE ? OR category LIKE ? OR series LIKE ? OR grade LIKE ? OR effect LIKE ? OR element LIKE ?)")
            value = f"%{keyword.strip()}%"
            params.extend([value, value, value, value, value, value])
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
        return [self.public_material(dict(row)) for row in rows]

    def save_material(self, payload: dict[str, Any], material_id: str | None = None) -> dict[str, Any]:
        timestamp = now_iso()
        item_id = material_id or payload.get("id") or self.generate_material_id(payload)
        item = self.normalize_material({**payload, "id": item_id})
        with self.connect() as connection:
            item["skuId"] = self.unique_material_sku(connection, item["skuId"], item_id)
            existing = connection.execute("SELECT id FROM managed_materials WHERE id = ?", (item_id,)).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE managed_materials SET
                    skuId=?, top=?, category=?, series=?, grade=?, name=?, effect=?, element=?, price=?, size=?, weight=?,
                    color=?, shine=?, image_path=?, image_url=?, image_urls_json=?, stock=?, enabled=?, sort_order=?, updated_at=?
                    WHERE id=?
                    """,
                    (
                        item["skuId"], item["top"], item["category"], item["series"], item["grade"],
                        item["name"], item["effect"], item["element"],
                        item["price"], item["size"], item["weight"], item["color"], item["shine"],
                        item.get("image_path", ""), item.get("image_url", ""), item["image_urls_json"], item["stock"], item["enabled"],
                        item["sort_order"], timestamp, item_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO managed_materials
                    (id, skuId, top, category, series, grade, name, effect, element, price, size, weight, color, shine,
                     image_path, image_url, image_urls_json, stock, enabled, sort_order, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"], item["skuId"], item["top"], item["category"], item["series"], item["grade"],
                        item["name"], item["effect"],
                        item["element"], item["price"], item["size"], item["weight"], item["color"], item["shine"],
                        item.get("image_path", ""), item.get("image_url", ""), item["image_urls_json"], item["stock"], item["enabled"],
                        item["sort_order"], timestamp, timestamp,
                    ),
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
        top = self.material_token(payload.get("top") or "bead", "type")
        name = self.material_token(payload.get("series") or payload.get("name") or payload.get("category"), "item")
        size = self.material_size_token(payload.get("size") or 8)
        return f"{top}-{name}-{size}"

    def generate_material_id(self, payload: dict[str, Any]) -> str:
        base = self.generate_material_sku(payload)
        return f"mat_{base}_{secrets.token_hex(3)}"

    def unique_material_sku(self, connection: Any, sku: str, item_id: str) -> str:
        base = sku.strip() or f"sku-{secrets.token_hex(4)}"
        candidate = base
        suffix = 2
        while connection.execute(
            "SELECT id FROM managed_materials WHERE skuId = ? AND id <> ?",
            (candidate, item_id),
        ).fetchone():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def normalize_material(self, payload: dict[str, Any]) -> dict[str, Any]:
        required = ["id", "top", "category", "name", "effect", "element"]
        for key in required:
            if not str(payload.get(key, "")).strip():
                raise ValueError(f"{key} 不能为空")
        image_path = str(payload.get("image_path") or "").strip()
        primary_image_url = normalize_material_image_url(payload.get("image_url") or "")
        image_urls = clean_image_urls(
            payload.get("image_urls") or payload.get("image_pool") or payload.get("image_urls_json"),
            primary_image_url,
            image_path,
        )
        if not primary_image_url and image_urls:
            primary_image_url = image_urls[0]
        stock = max(0, int(float(payload.get("stock") or 0)))
        enabled = 1 if payload.get("enabled", True) and stock > 0 else 0
        return {
            "id": str(payload["id"]).strip(),
            "skuId": str(payload.get("skuId") or self.generate_material_sku(payload)).strip(),
            "top": str(payload["top"]).strip(),
            "category": str(payload["category"]).strip(),
            "series": str(payload.get("series") or payload.get("name") or "").strip(),
            "grade": str(payload.get("grade") or "").strip(),
            "name": str(payload["name"]).strip(),
            "effect": str(payload["effect"]).strip(),
            "element": str(payload["element"]).strip(),
            "price": float(payload.get("price") or 0),
            "size": float(payload.get("size") or 8),
            "weight": float(payload.get("weight") or 1),
            "color": str(payload.get("color") or "#dfe3e5").strip(),
            "shine": str(payload.get("shine") or "#ffffff").strip(),
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
        if not row:
            raise ValueError("材料不存在")
        return self.public_material(dict(row))

    def delete_material(self, material_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM managed_materials WHERE id = ?", (material_id,))
        invalidate_material_cache()

    def batch_update_materials(self, ids: list[str], action: str, value: Any = None) -> dict[str, Any]:
        clean_ids = [str(item).strip() for item in ids if str(item).strip()]
        if not clean_ids:
            raise ValueError("请选择要操作的珠材")
        placeholders = ", ".join(["?"] * len(clean_ids))
        timestamp = now_iso()
        with self.connect() as connection:
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
            elif action == "delete":
                cursor = connection.execute(
                    f"DELETE FROM managed_materials WHERE id IN ({placeholders})",
                    clean_ids,
                )
            else:
                raise ValueError("不支持的批量操作")
            affected = cursor.rowcount if cursor.rowcount is not None else len(clean_ids)
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
