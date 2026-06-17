from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from .materials import MATERIAL_CATALOG
from .repository import DB_PATH


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class AdminService:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def init_db(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_users (
                    admin_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    role TEXT NOT NULL,
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
            count = connection.execute("SELECT COUNT(*) AS c FROM managed_materials").fetchone()["c"]
            if count == 0:
                self._seed_materials(connection)
            self._ensure_default_white_quartz_series(connection)
            block_count = connection.execute("SELECT COUNT(*) AS c FROM content_blocks").fetchone()["c"]
            if block_count == 0:
                self._seed_blocks(connection)

    def _seed_materials(self, connection: sqlite3.Connection) -> None:
        timestamp = now_iso()
        for index, item in enumerate(MATERIAL_CATALOG):
            image_path = item.get("image_path")
            image_url = item.get("image_url") or (
                f"https://cdn.yustream.cn/materials/{image_path}" if image_path else ""
            )
            connection.execute(
                """
                INSERT INTO managed_materials
                (id, skuId, top, category, series, grade, name, effect, element, price, size, weight, color, shine,
                 image_path, image_url, enabled, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
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
                    index,
                    timestamp,
                    timestamp,
                ),
            )

    def _ensure_material_columns(self, connection: sqlite3.Connection) -> None:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(managed_materials)").fetchall()}
        if "series" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN series TEXT NOT NULL DEFAULT ''")
        if "grade" not in columns:
            connection.execute("ALTER TABLE managed_materials ADD COLUMN grade TEXT NOT NULL DEFAULT ''")
        connection.execute("UPDATE managed_materials SET series = name WHERE COALESCE(series, '') = ''")

    def _ensure_default_white_quartz_series(self, connection: sqlite3.Connection) -> None:
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
                    f"https://cdn.yustream.cn/materials/{image_path}",
                    max_sort + offset,
                    timestamp,
                    timestamp,
                ),
            )

    def _seed_blocks(self, connection: sqlite3.Connection) -> None:
        timestamp = now_iso()
        defaults = [
            ("home_hero", "home", "星灵水晶", "用五行、星盘与 MBTI 找到你的专属能量配方", "首页头部品牌文案"),
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
        except sqlite3.IntegrityError as exc:
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

    def dashboard(self) -> dict[str, Any]:
        with self.connect() as connection:
            return {
                "users": connection.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"],
                "materials": connection.execute("SELECT COUNT(*) AS c FROM managed_materials").fetchone()["c"],
                "assessments": connection.execute("SELECT COUNT(*) AS c FROM energy_assessments").fetchone()["c"],
                "daily_energies": connection.execute("SELECT COUNT(*) AS c FROM daily_energies").fetchone()["c"],
                "content_blocks": connection.execute("SELECT COUNT(*) AS c FROM content_blocks").fetchone()["c"],
            }

    def list_users(self, keyword: str = "", limit: int = 100) -> list[dict[str, Any]]:
        keyword = f"%{keyword.strip()}%"
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT user_id, openid, nickname, avatar_url, gender, phone_number, source, created_at, updated_at
                FROM users
                WHERE user_id LIKE ? OR COALESCE(nickname, '') LIKE ? OR COALESCE(phone_number, '') LIKE ?
                ORDER BY updated_at DESC LIMIT ?
                """,
                (keyword, keyword, keyword, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_assessments(self, keyword: str = "", limit: int = 100) -> list[dict[str, Any]]:
        keyword = keyword.strip()
        params: list[Any] = []
        where = ""
        if keyword:
            where = "WHERE user_id LIKE ? OR name LIKE ? OR core_wish LIKE ? OR assessment_id LIKE ?"
            value = f"%{keyword}%"
            params.extend([value, value, value, value])
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
        results = []
        for row in rows:
            item = dict(row)
            try:
                result = json.loads(item.pop("result_json"))
            except json.JSONDecodeError:
                result = {}
            item["summary"] = result.get("report", {}).get("summary") or result.get("recommendation_copy") or ""
            item["final_energy_profile"] = result.get("final_energy_profile", {})
            results.append(item)
        return results

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

    def list_materials(self, keyword: str = "", top: str = "") -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if top:
            clauses.append("top = ?")
            params.append(top)
        if keyword.strip():
            clauses.append("(name LIKE ? OR category LIKE ? OR series LIKE ? OR grade LIKE ? OR effect LIKE ? OR element LIKE ?)")
            value = f"%{keyword.strip()}%"
            params.extend([value, value, value, value, value, value])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM managed_materials {where} ORDER BY sort_order ASC, updated_at DESC",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def save_material(self, payload: dict[str, Any], material_id: str | None = None) -> dict[str, Any]:
        timestamp = now_iso()
        item_id = material_id or payload.get("id") or f"mat_{secrets.token_hex(6)}"
        item = self.normalize_material({**payload, "id": item_id})
        with self.connect() as connection:
            existing = connection.execute("SELECT id FROM managed_materials WHERE id = ?", (item_id,)).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE managed_materials SET
                    skuId=?, top=?, category=?, series=?, grade=?, name=?, effect=?, element=?, price=?, size=?, weight=?,
                    color=?, shine=?, image_path=?, image_url=?, enabled=?, sort_order=?, updated_at=?
                    WHERE id=?
                    """,
                    (
                        item["skuId"], item["top"], item["category"], item["series"], item["grade"],
                        item["name"], item["effect"], item["element"],
                        item["price"], item["size"], item["weight"], item["color"], item["shine"],
                        item.get("image_path", ""), item.get("image_url", ""), item["enabled"],
                        item["sort_order"], timestamp, item_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO managed_materials
                    (id, skuId, top, category, series, grade, name, effect, element, price, size, weight, color, shine,
                     image_path, image_url, enabled, sort_order, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"], item["skuId"], item["top"], item["category"], item["series"], item["grade"],
                        item["name"], item["effect"],
                        item["element"], item["price"], item["size"], item["weight"], item["color"], item["shine"],
                        item.get("image_path", ""), item.get("image_url", ""), item["enabled"],
                        item["sort_order"], timestamp, timestamp,
                    ),
                )
        return self.get_material(item_id)

    def normalize_material(self, payload: dict[str, Any]) -> dict[str, Any]:
        required = ["id", "skuId", "top", "category", "name", "effect", "element"]
        for key in required:
            if not str(payload.get(key, "")).strip():
                raise ValueError(f"{key} 不能为空")
        return {
            "id": str(payload["id"]).strip(),
            "skuId": str(payload["skuId"]).strip(),
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
            "image_path": str(payload.get("image_path") or "").strip(),
            "image_url": str(payload.get("image_url") or "").strip(),
            "enabled": 1 if payload.get("enabled", True) else 0,
            "sort_order": int(payload.get("sort_order") or 0),
        }

    def get_material(self, material_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM managed_materials WHERE id = ?", (material_id,)).fetchone()
        if not row:
            raise ValueError("材料不存在")
        return dict(row)

    def delete_material(self, material_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM managed_materials WHERE id = ?", (material_id,))

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
