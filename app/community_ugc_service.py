from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .database import DEFAULT_SQLITE_PATH, MySQLConnection, connect_database, use_mysql
from .feature_flags import community_moderation_required
from .migrations.versions.v20260717_09_community_ugc_core import TABLES, VERSION


class CommunityNotFound(ValueError):
    pass


class CommunityConflict(ValueError):
    pass


class CommunityValidation(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


POST_SELECT = """
SELECT p.*,
       u.nickname AS author_nickname,
       u.avatar_url AS author_avatar_url,
       (SELECT COUNT(*) FROM community_ugc_likes l WHERE l.post_id = p.post_id) AS like_count,
       (SELECT COUNT(*) FROM community_ugc_saves s WHERE s.post_id = p.post_id) AS save_count,
       (SELECT COUNT(*) FROM community_ugc_comments c
        WHERE c.post_id = p.post_id AND c.status = 'active') AS comment_count
FROM community_ugc_posts p
LEFT JOIN users u ON u.user_id = p.owner_user_id
"""


class CommunityUGCService:
    """Database-backed UGC core, separate from editorial ``community_posts``."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_SQLITE_PATH
        self._force_sqlite = db_path is not None
        self._readiness_lock = threading.Lock()
        self._readiness_condition = threading.Condition(self._readiness_lock)
        self._readiness_cached_at = 0.0
        self._readiness_cache: dict[str, Any] | None = None
        self._readiness_refreshing = False
        self._readiness_generation = 0

    @property
    def mysql(self) -> bool:
        return not self._force_sqlite and use_mysql()

    def connect(self):
        return connect_database(self.db_path if self._force_sqlite else None)

    @staticmethod
    def _json_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        try:
            decoded = json.loads(str(value or "[]"))
        except (TypeError, json.JSONDecodeError):
            return []
        return decoded if isinstance(decoded, list) else []

    @classmethod
    def _post(cls, row: Any) -> dict[str, Any]:
        data = dict(row)
        return {
            "post_id": str(data["post_id"]),
            "title": data["title"],
            "content": data["content"],
            "image_urls": cls._json_list(data.get("image_urls_json")),
            "tags": cls._json_list(data.get("tags_json")),
            "design_id": data.get("design_id"),
            "source_post_id": data.get("source_post_id"),
            "status": data["status"],
            "submitted_at": data.get("submitted_at"),
            "published_at": data.get("published_at"),
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "author": {
                "user_id": str(data["owner_user_id"]),
                "nickname": data.get("author_nickname") or "宇涧用户",
                "avatar_url": data.get("author_avatar_url"),
            },
            "stats": {
                "likes": int(data.get("like_count") or 0),
                "saves": int(data.get("save_count") or 0),
                "comments": int(data.get("comment_count") or 0),
            },
        }

    @staticmethod
    def _comment(row: Any) -> dict[str, Any]:
        data = dict(row)
        return {
            "comment_id": str(data["comment_id"]),
            "post_id": str(data["post_id"]),
            "content": data["content"] if data["status"] == "active" else "",
            "status": data["status"],
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "author": {
                "user_id": str(data["author_user_id"]),
                "nickname": data.get("author_nickname") or "宇涧用户",
                "avatar_url": data.get("author_avatar_url"),
            },
        }

    @staticmethod
    def _readiness_cache_ttl() -> float:
        try:
            value = float(os.getenv("COMMUNITY_READINESS_CACHE_TTL_SECONDS", "5"))
        except ValueError:
            value = 5.0
        return min(max(value, 0.1), 60.0)

    @staticmethod
    def _copy_readiness(value: dict[str, Any]) -> dict[str, Any]:
        copied = dict(value)
        copied["missing_tables"] = list(value.get("missing_tables") or [])
        return copied

    def clear_readiness_cache(self) -> None:
        """Invalidate the process-local readiness cache after migrations or in tests."""

        with self._readiness_condition:
            self._readiness_cache = None
            self._readiness_cached_at = 0.0
            self._readiness_generation += 1
            self._readiness_condition.notify_all()

    def readiness(self) -> dict[str, Any]:
        while True:
            now = time.monotonic()
            with self._readiness_condition:
                if (
                    self._readiness_cache is not None
                    and now - self._readiness_cached_at < self._readiness_cache_ttl()
                ):
                    return self._copy_readiness(self._readiness_cache)
                if not self._readiness_refreshing:
                    self._readiness_refreshing = True
                    generation = self._readiness_generation
                    break
                self._readiness_condition.wait(timeout=self._readiness_cache_ttl())

        try:
            result = self._readiness_uncached()
        except BaseException:
            with self._readiness_condition:
                self._readiness_refreshing = False
                self._readiness_condition.notify_all()
            raise
        with self._readiness_condition:
            if generation == self._readiness_generation:
                self._readiness_cache = result
                self._readiness_cached_at = time.monotonic()
            self._readiness_refreshing = False
            self._readiness_condition.notify_all()
        return self._copy_readiness(result)

    def _readiness_uncached(self) -> dict[str, Any]:
        try:
            if self.mysql:
                connection = MySQLConnection()
                try:
                    database = os.environ["MYSQL_DATABASE"]
                    existing = {
                        row["TABLE_NAME"]
                        for row in connection.execute(
                            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ?",
                            (database,),
                        ).fetchall()
                    }
                    missing = sorted(set(TABLES) - existing)
                    applied = False
                    if "schema_migrations" in existing:
                        applied = bool(
                            connection.execute(
                                "SELECT 1 FROM schema_migrations WHERE version = ? LIMIT 1", (VERSION,)
                            ).fetchone()
                        )
                finally:
                    connection.raw.close()
            else:
                if not self.db_path.exists():
                    return {
                        "schema_ready": False,
                        "migration_version": VERSION,
                        "migration_applied": False,
                        "missing_tables": list(reversed(TABLES)),
                        "reason": "database_missing",
                    }
                uri = f"file:{self.db_path.resolve()}?mode=ro"
                connection = sqlite3.connect(uri, uri=True)
                connection.row_factory = sqlite3.Row
                try:
                    existing = {
                        row["name"]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'table'"
                        ).fetchall()
                    }
                    missing = sorted(set(TABLES) - existing)
                    applied = False
                    if "schema_migrations" in existing:
                        applied = bool(
                            connection.execute(
                                "SELECT 1 FROM schema_migrations WHERE version = ? LIMIT 1", (VERSION,)
                            ).fetchone()
                        )
                finally:
                    connection.close()
            return {
                "schema_ready": not missing and applied,
                "migration_version": VERSION,
                "migration_applied": applied,
                "missing_tables": missing,
            }
        except Exception as exc:
            return {
                "schema_ready": False,
                "migration_version": VERSION,
                "migration_applied": False,
                "missing_tables": list(reversed(TABLES)),
                "error_type": type(exc).__name__,
            }

    def _begin_write_transaction(self, connection) -> None:
        if not self.mysql:
            connection.execute("BEGIN IMMEDIATE")

    def _begin_read_transaction(self, connection) -> None:
        if not self.mysql:
            connection.execute("BEGIN")

    def _post_lock_suffix(self, lock: bool) -> str:
        return " FOR UPDATE" if lock and self.mysql else ""

    def _require_users(self, connection, *user_ids: str) -> None:
        expected = sorted(set(user_ids))
        if not expected:
            return
        placeholders = ", ".join("?" for _ in expected)
        rows = connection.execute(
            "SELECT user_id FROM users "
            f"WHERE user_id IN ({placeholders}) ORDER BY user_id"
            f"{self._post_lock_suffix(True)}",
            tuple(expected),
        ).fetchall()
        if {str(row["user_id"]) for row in rows} != set(expected):
            raise CommunityNotFound("用户不存在")

    def _owned_post_state(self, connection, post_id: str, user_id: str, *, lock: bool = False):
        row = connection.execute(
            "SELECT post_id, owner_user_id, status, design_id, source_post_id, deleted_at "
            "FROM community_ugc_posts WHERE post_id = ? AND owner_user_id = ? "
            f"AND deleted_at IS NULL LIMIT 1{self._post_lock_suffix(lock)}",
            (post_id, user_id),
        ).fetchone()
        if not row:
            raise CommunityNotFound("帖子不存在")
        return row

    def _post_state(self, connection, post_id: str, *, lock: bool = False):
        row = connection.execute(
            "SELECT post_id, owner_user_id, status, design_id, source_post_id, deleted_at "
            "FROM community_ugc_posts WHERE post_id = ? AND deleted_at IS NULL "
            f"LIMIT 1{self._post_lock_suffix(lock)}",
            (post_id,),
        ).fetchone()
        if not row:
            raise CommunityNotFound("帖子不存在")
        return row

    def _lock_post_states(self, connection, *post_ids: str | None) -> dict[str, Any]:
        expected = sorted({str(post_id) for post_id in post_ids if post_id})
        if not expected:
            return {}
        placeholders = ", ".join("?" for _ in expected)
        rows = connection.execute(
            "SELECT post_id, owner_user_id, status, design_id, source_post_id, deleted_at "
            f"FROM community_ugc_posts WHERE post_id IN ({placeholders}) "
            "AND deleted_at IS NULL ORDER BY post_id"
            f"{self._post_lock_suffix(True)}",
            tuple(expected),
        ).fetchall()
        return {str(row["post_id"]): row for row in rows}

    @staticmethod
    def _validate_locked_source(
        states: dict[str, Any], source_post_id: str | None, post_id: str
    ) -> None:
        if not source_post_id:
            return
        if source_post_id == post_id:
            raise CommunityValidation("帖子不能引用自身作为来源")
        source = states.get(source_post_id)
        if not source or source["status"] != "published":
            raise CommunityValidation("source_post_id 不是可见的已发布帖子")

    def _owned_post_row(self, post_id: str, user_id: str, include_deleted: bool = False):
        deleted = "" if include_deleted else " AND p.deleted_at IS NULL"
        with self.connect() as connection:
            row = connection.execute(
                POST_SELECT + f" WHERE p.post_id = ? AND p.owner_user_id = ?{deleted} LIMIT 1",
                (post_id, user_id),
            ).fetchone()
        if not row:
            raise CommunityNotFound("帖子不存在")
        return row

    def _public_post_row(self, post_id: str):
        with self.connect() as connection:
            row = connection.execute(
                POST_SELECT
                + " WHERE p.post_id = ? AND p.status = 'published' AND p.deleted_at IS NULL LIMIT 1",
                (post_id,),
            ).fetchone()
        if not row:
            raise CommunityNotFound("帖子不存在")
        return row

    def _require_public_post(self, connection, post_id: str, *, lock: bool = False):
        row = connection.execute(
            "SELECT post_id, source_post_id FROM community_ugc_posts "
            "WHERE post_id = ? AND status = 'published' AND deleted_at IS NULL "
            f"LIMIT 1{self._post_lock_suffix(lock)}",
            (post_id,),
        ).fetchone()
        if not row:
            raise CommunityNotFound("帖子不存在")
        return row

    def _lock_post_if_present(self, connection, post_id: str) -> None:
        connection.execute(
            "SELECT post_id FROM community_ugc_posts WHERE post_id = ? "
            f"LIMIT 1{self._post_lock_suffix(True)}",
            (post_id,),
        ).fetchone()

    def get_public_post(self, post_id: str) -> dict[str, Any]:
        return self._post(self._public_post_row(post_id))

    def get_owned_post(self, post_id: str, user_id: str) -> dict[str, Any]:
        return self._post(self._owned_post_row(post_id, user_id))

    def list_public_posts(self, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                POST_SELECT
                + " WHERE p.status = 'published' AND p.deleted_at IS NULL "
                "ORDER BY p.published_at DESC, p.post_id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._post(row) for row in rows]

    def list_owned_posts(self, user_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                POST_SELECT
                + " WHERE p.owner_user_id = ? AND p.deleted_at IS NULL "
                "ORDER BY p.updated_at DESC, p.post_id DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            ).fetchall()
        return [self._post(row) for row in rows]

    def _validate_design_reference(
        self,
        connection,
        design_id: str | None,
        user_id: str,
        *,
        lock: bool = False,
    ) -> None:
        if not design_id:
            return
        row = connection.execute(
            "SELECT design_id FROM diy_designs WHERE design_id = ? AND user_id = ? "
            f"LIMIT 1{self._post_lock_suffix(lock)}",
            (design_id, user_id),
        ).fetchone()
        if not row:
            raise CommunityValidation("design_id 不是当前用户的有效设计")

    def _validate_source_reference(
        self,
        connection,
        source_post_id: str | None,
        post_id: str | None = None,
        *,
        lock: bool = False,
    ) -> None:
        if not source_post_id:
            return
        if post_id and source_post_id == post_id:
            raise CommunityValidation("帖子不能引用自身作为来源")
        row = connection.execute(
            "SELECT 1 FROM community_ugc_posts "
            "WHERE post_id = ? AND status = 'published' AND deleted_at IS NULL "
            f"LIMIT 1{self._post_lock_suffix(lock)}",
            (source_post_id,),
        ).fetchone()
        if not row:
            raise CommunityValidation("source_post_id 不是可见的已发布帖子")

    def create_post(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        post_id = f"ugc_{uuid4().hex}"
        timestamp = now_iso()
        with self.connect() as connection:
            self._begin_write_transaction(connection)
            self._require_users(connection, user_id)
            self._validate_design_reference(
                connection, payload.get("design_id"), user_id, lock=True
            )
            self._validate_source_reference(
                connection, payload.get("source_post_id"), lock=True
            )
            connection.execute(
                """
                INSERT INTO community_ugc_posts
                (post_id, owner_user_id, title, content, image_urls_json, tags_json,
                 design_id, source_post_id, status, submitted_at, published_at, deleted_at,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', NULL, NULL, NULL, ?, ?)
                """,
                (
                    post_id,
                    user_id,
                    payload["title"],
                    payload["content"],
                    json.dumps(payload.get("image_urls") or [], ensure_ascii=False),
                    json.dumps(payload.get("tags") or [], ensure_ascii=False),
                    payload.get("design_id"),
                    payload.get("source_post_id"),
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_owned_post(post_id, user_id)

    def update_post(self, post_id: str, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        values = dict(payload)
        if not values:
            raise CommunityValidation("至少需要提供一个待更新字段")
        column_map = {
            "title": "title",
            "content": "content",
            "image_urls": "image_urls_json",
            "tags": "tags_json",
            "design_id": "design_id",
            "source_post_id": "source_post_id",
        }
        assignments: list[str] = []
        params: list[Any] = []
        with self.connect() as connection:
            self._begin_write_transaction(connection)
            self._require_users(connection, user_id)
            preliminary = self._owned_post_state(connection, post_id, user_id)
            if "design_id" in values:
                self._validate_design_reference(
                    connection, values["design_id"], user_id, lock=True
                )
            source_post_id = values.get("source_post_id") if "source_post_id" in values else None
            states = self._lock_post_states(connection, post_id, source_post_id)
            state = states.get(post_id)
            if not state or state["owner_user_id"] != user_id:
                raise CommunityNotFound("帖子不存在")
            if state["status"] != "draft":
                raise CommunityConflict("只有草稿可以编辑，请先撤回待审帖子")
            if (
                state["status"] != preliminary["status"]
                or state["design_id"] != preliminary["design_id"]
                or state["source_post_id"] != preliminary["source_post_id"]
            ):
                raise CommunityConflict("帖子状态已变化，请刷新后重试")
            if "source_post_id" in values:
                self._validate_locked_source(states, values["source_post_id"], post_id)
            for key, value in values.items():
                if key not in column_map:
                    continue
                assignments.append(f"{column_map[key]} = ?")
                params.append(
                    json.dumps(value, ensure_ascii=False) if key in {"image_urls", "tags"} else value
                )
            if not assignments:
                raise CommunityValidation("没有可更新的字段")
            assignments.append("updated_at = ?")
            params.extend((now_iso(), post_id, user_id))
            cursor = connection.execute(
                f"UPDATE community_ugc_posts SET {', '.join(assignments)} "
                "WHERE post_id = ? AND owner_user_id = ? AND status = 'draft' AND deleted_at IS NULL",
                tuple(params),
            )
            if cursor.rowcount != 1:
                current = connection.execute(
                    "SELECT status, deleted_at FROM community_ugc_posts "
                    "WHERE post_id = ? AND owner_user_id = ? LIMIT 1",
                    (post_id, user_id),
                ).fetchone()
                if not current or current["deleted_at"] is not None:
                    raise CommunityNotFound("帖子不存在")
                if current["status"] != "draft":
                    raise CommunityConflict("帖子状态已变化，请刷新后重试")
        return self.get_owned_post(post_id, user_id)

    def delete_post(self, post_id: str, user_id: str) -> dict[str, Any]:
        timestamp = now_iso()
        with self.connect() as connection:
            self._begin_write_transaction(connection)
            self._require_users(connection, user_id)
            self._owned_post_state(connection, post_id, user_id, lock=True)
            cursor = connection.execute(
                "UPDATE community_ugc_posts SET status = 'deleted', deleted_at = ?, updated_at = ? "
                "WHERE post_id = ? AND owner_user_id = ? AND deleted_at IS NULL",
                (timestamp, timestamp, post_id, user_id),
            )
            if cursor.rowcount != 1:
                raise CommunityConflict("帖子状态已变化，请刷新后重试")
        return {"post_id": post_id, "deleted": True, "changed": cursor.rowcount == 1}

    def submit_post(self, post_id: str, user_id: str) -> dict[str, Any]:
        moderation_required = community_moderation_required()
        timestamp = now_iso()
        next_status = "pending" if moderation_required else "published"
        published_at = None if next_status == "pending" else timestamp
        changed = False
        with self.connect() as connection:
            self._begin_write_transaction(connection)
            self._require_users(connection, user_id)
            preliminary = self._owned_post_state(connection, post_id, user_id)
            transitioning = preliminary["status"] == "draft"
            if transitioning:
                self._validate_design_reference(
                    connection, preliminary["design_id"], user_id, lock=True
                )
            states = self._lock_post_states(
                connection,
                post_id,
                preliminary["source_post_id"] if transitioning else None,
            )
            current = states.get(post_id)
            if not current or current["owner_user_id"] != user_id:
                raise CommunityNotFound("帖子不存在")
            if (
                current["status"] != preliminary["status"]
                or current["design_id"] != preliminary["design_id"]
                or current["source_post_id"] != preliminary["source_post_id"]
            ):
                raise CommunityConflict("帖子状态已变化，请刷新后重试")
            if current["status"] == "pending":
                pass
            elif current["status"] == "published" and not moderation_required:
                pass
            elif current["status"] != "draft":
                raise CommunityConflict("当前状态不能提交审核")
            else:
                self._validate_locked_source(states, current["source_post_id"], post_id)
                cursor = connection.execute(
                    "UPDATE community_ugc_posts SET status = ?, submitted_at = ?, "
                    "published_at = ?, updated_at = ? WHERE post_id = ? AND owner_user_id = ? "
                    "AND status = 'draft' AND deleted_at IS NULL",
                    (next_status, timestamp, published_at, timestamp, post_id, user_id),
                )
                if cursor.rowcount != 1:
                    raise CommunityConflict("帖子状态已变化，请刷新后重试")
                changed = True
        return {**self.get_owned_post(post_id, user_id), "changed": changed}

    def withdraw_post(self, post_id: str, user_id: str) -> dict[str, Any]:
        timestamp = now_iso()
        changed = False
        with self.connect() as connection:
            self._begin_write_transaction(connection)
            self._require_users(connection, user_id)
            current = self._owned_post_state(connection, post_id, user_id, lock=True)
            if current["status"] == "draft":
                pass
            elif current["status"] not in {"pending", "published"}:
                raise CommunityConflict("当前状态不能撤回")
            else:
                cursor = connection.execute(
                    "UPDATE community_ugc_posts SET status = 'draft', submitted_at = NULL, "
                    "published_at = NULL, updated_at = ? WHERE post_id = ? AND owner_user_id = ? "
                    "AND status = ? AND deleted_at IS NULL",
                    (timestamp, post_id, user_id, current["status"]),
                )
                if cursor.rowcount != 1:
                    raise CommunityConflict("帖子状态已变化，请刷新后重试")
                changed = True
        return {**self.get_owned_post(post_id, user_id), "changed": changed}

    def publish_for_moderation(self, post_id: str) -> dict[str, Any]:
        """Trusted service operation reserved for a future moderation adapter.

        This is intentionally not wired to a user or administrator HTTP endpoint.
        """

        timestamp = now_iso()
        with self.connect() as connection:
            self._begin_write_transaction(connection)
            observed = self._post_state(connection, post_id)
            owner_user_id = str(observed["owner_user_id"])
            self._require_users(connection, owner_user_id)
            preliminary = self._post_state(connection, post_id)
            transitioning = preliminary["status"] == "pending"
            if transitioning:
                self._validate_design_reference(
                    connection,
                    preliminary["design_id"],
                    owner_user_id,
                    lock=True,
                )
            states = self._lock_post_states(
                connection,
                post_id,
                preliminary["source_post_id"] if transitioning else None,
            )
            current = states.get(post_id)
            if not current or str(current["owner_user_id"]) != owner_user_id:
                raise CommunityNotFound("帖子不存在")
            if (
                current["status"] != preliminary["status"]
                or current["design_id"] != preliminary["design_id"]
                or current["source_post_id"] != preliminary["source_post_id"]
            ):
                raise CommunityConflict("帖子状态已变化，请刷新后重试")
            if current["status"] == "published":
                pass
            elif current["status"] != "pending":
                raise CommunityConflict("只有待审核帖子可以发布")
            else:
                self._validate_locked_source(states, current["source_post_id"], post_id)
                cursor = connection.execute(
                    "UPDATE community_ugc_posts SET status = 'published', published_at = ?, "
                    "updated_at = ? WHERE post_id = ? AND status = 'pending' AND deleted_at IS NULL",
                    (timestamp, timestamp, post_id),
                )
                if cursor.rowcount != 1:
                    raise CommunityConflict("帖子状态已变化，请刷新后重试")
        return self.get_public_post(post_id)

    def _insert_ignore(self, connection, table: str, columns: tuple[str, ...], values: tuple[Any, ...]) -> bool:
        placeholders = ", ".join("?" for _ in columns)
        verb = "INSERT IGNORE" if self.mysql else "INSERT OR IGNORE"
        cursor = connection.execute(
            f"{verb} INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", values
        )
        return cursor.rowcount == 1

    @staticmethod
    def _count(connection, table: str, column: str, value: str) -> int:
        row = connection.execute(
            f"SELECT COUNT(*) AS total FROM {table} WHERE {column} = ?", (value,)
        ).fetchone()
        return int(row["total"] or 0)

    def set_like(self, post_id: str, user_id: str, active: bool) -> dict[str, Any]:
        with self.connect() as connection:
            self._begin_write_transaction(connection)
            self._require_users(connection, user_id)
            if active:
                self._require_public_post(connection, post_id, lock=True)
                changed = self._insert_ignore(
                    connection,
                    "community_ugc_likes",
                    ("post_id", "user_id", "created_at"),
                    (post_id, user_id, now_iso()),
                )
            else:
                self._lock_post_if_present(connection, post_id)
                changed = connection.execute(
                    "DELETE FROM community_ugc_likes WHERE post_id = ? AND user_id = ?",
                    (post_id, user_id),
                ).rowcount == 1
            count = self._count(connection, "community_ugc_likes", "post_id", post_id)
        return {"post_id": post_id, "liked": active, "changed": changed, "like_count": count}

    def set_save(self, post_id: str, user_id: str, active: bool) -> dict[str, Any]:
        with self.connect() as connection:
            self._begin_write_transaction(connection)
            self._require_users(connection, user_id)
            if active:
                self._require_public_post(connection, post_id, lock=True)
                changed = self._insert_ignore(
                    connection,
                    "community_ugc_saves",
                    ("post_id", "user_id", "created_at"),
                    (post_id, user_id, now_iso()),
                )
            else:
                self._lock_post_if_present(connection, post_id)
                changed = connection.execute(
                    "DELETE FROM community_ugc_saves WHERE post_id = ? AND user_id = ?",
                    (post_id, user_id),
                ).rowcount == 1
            count = self._count(connection, "community_ugc_saves", "post_id", post_id)
        return {"post_id": post_id, "saved": active, "changed": changed, "save_count": count}

    def list_saved_posts(self, user_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                POST_SELECT
                + " JOIN community_ugc_saves own_save ON own_save.post_id = p.post_id "
                "WHERE own_save.user_id = ? AND p.status = 'published' AND p.deleted_at IS NULL "
                "ORDER BY own_save.created_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            ).fetchall()
        return [self._post(row) for row in rows]

    def list_comments(self, post_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self.connect() as connection:
            self._begin_read_transaction(connection)
            self._require_public_post(connection, post_id, lock=self.mysql)
            rows = connection.execute(
                """
                SELECT c.*, u.nickname AS author_nickname, u.avatar_url AS author_avatar_url
                FROM community_ugc_comments c
                LEFT JOIN users u ON u.user_id = c.author_user_id
                WHERE c.post_id = ? AND c.status = 'active'
                ORDER BY c.created_at ASC, c.comment_id ASC LIMIT ? OFFSET ?
                """,
                (post_id, limit, offset),
            ).fetchall()
        return [self._comment(row) for row in rows]

    def create_comment(self, post_id: str, user_id: str, content: str) -> dict[str, Any]:
        comment_id = f"ugc_comment_{uuid4().hex}"
        timestamp = now_iso()
        with self.connect() as connection:
            self._begin_write_transaction(connection)
            self._require_users(connection, user_id)
            self._require_public_post(connection, post_id, lock=True)
            connection.execute(
                "INSERT INTO community_ugc_comments "
                "(comment_id, post_id, author_user_id, content, status, deleted_at, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'active', NULL, ?, ?)",
                (comment_id, post_id, user_id, content, timestamp, timestamp),
            )
            row = connection.execute(
                """
                SELECT c.*, u.nickname AS author_nickname, u.avatar_url AS author_avatar_url
                FROM community_ugc_comments c
                LEFT JOIN users u ON u.user_id = c.author_user_id
                WHERE c.comment_id = ?
                """,
                (comment_id,),
            ).fetchone()
        return self._comment(row)

    def delete_comment(self, comment_id: str, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            self._begin_write_transaction(connection)
            self._require_users(connection, user_id)
            row = connection.execute(
                "SELECT comment_id, status FROM community_ugc_comments "
                "WHERE comment_id = ? AND author_user_id = ? "
                f"LIMIT 1{self._post_lock_suffix(True)}",
                (comment_id, user_id),
            ).fetchone()
            if not row:
                raise CommunityNotFound("评论不存在")
            if row["status"] == "deleted":
                return {"comment_id": comment_id, "deleted": True, "changed": False}
            timestamp = now_iso()
            cursor = connection.execute(
                "UPDATE community_ugc_comments SET status = 'deleted', deleted_at = ?, updated_at = ? "
                "WHERE comment_id = ? AND author_user_id = ? AND status = 'active'",
                (timestamp, timestamp, comment_id, user_id),
            )
        return {"comment_id": comment_id, "deleted": True, "changed": cursor.rowcount == 1}

    def set_follow(self, followed_user_id: str, follower_user_id: str, active: bool) -> dict[str, Any]:
        if followed_user_id == follower_user_id:
            raise CommunityValidation("不能关注自己")
        with self.connect() as connection:
            self._begin_write_transaction(connection)
            required_users = (
                (follower_user_id, followed_user_id) if active else (follower_user_id,)
            )
            self._require_users(connection, *required_users)
            if active:
                changed = self._insert_ignore(
                    connection,
                    "community_ugc_follows",
                    ("follower_user_id", "followed_user_id", "created_at"),
                    (follower_user_id, followed_user_id, now_iso()),
                )
            else:
                changed = connection.execute(
                    "DELETE FROM community_ugc_follows "
                    "WHERE follower_user_id = ? AND followed_user_id = ?",
                    (follower_user_id, followed_user_id),
                ).rowcount == 1
            count = self._count(
                connection, "community_ugc_follows", "followed_user_id", followed_user_id
            )
        return {
            "user_id": followed_user_id,
            "following": active,
            "changed": changed,
            "follower_count": count,
        }

    def list_following(self, user_id: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT f.followed_user_id AS user_id, f.created_at,
                       u.nickname, u.avatar_url
                FROM community_ugc_follows f
                LEFT JOIN users u ON u.user_id = f.followed_user_id
                WHERE f.follower_user_id = ?
                ORDER BY f.created_at DESC LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()
        return [
            {
                "user_id": str(row["user_id"]),
                "nickname": row["nickname"] or "宇涧用户",
                "avatar_url": row["avatar_url"],
                "followed_at": row["created_at"],
            }
            for row in rows
        ]

    def _validate_report_target(
        self, connection, target_type: str, target_id: str, *, lock: bool = False
    ) -> None:
        if target_type == "post":
            row = connection.execute(
                "SELECT post_id FROM community_ugc_posts "
                "WHERE post_id = ? AND status = 'published' AND deleted_at IS NULL"
                f"{self._post_lock_suffix(lock)}",
                (target_id,),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT p.post_id FROM community_ugc_comments c "
                "JOIN community_ugc_posts p ON p.post_id = c.post_id "
                "WHERE c.comment_id = ? AND c.status = 'active' "
                "AND p.status = 'published' AND p.deleted_at IS NULL"
                f"{self._post_lock_suffix(lock)}",
                (target_id,),
            ).fetchone()
        if not row:
            raise CommunityNotFound("举报对象不存在")

    def create_report(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        report_id = f"ugc_report_{uuid4().hex}"
        timestamp = now_iso()
        with self.connect() as connection:
            self._begin_write_transaction(connection)
            self._require_users(connection, user_id)
            self._validate_report_target(
                connection, payload["target_type"], payload["target_id"], lock=True
            )
            changed = self._insert_ignore(
                connection,
                "community_ugc_reports",
                (
                    "report_id",
                    "reporter_user_id",
                    "target_type",
                    "target_id",
                    "reason",
                    "detail",
                    "status",
                    "created_at",
                    "updated_at",
                ),
                (
                    report_id,
                    user_id,
                    payload["target_type"],
                    payload["target_id"],
                    payload["reason"],
                    payload.get("detail"),
                    "open",
                    timestamp,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT report_id, target_type, target_id, reason, status, created_at "
                "FROM community_ugc_reports "
                "WHERE reporter_user_id = ? AND target_type = ? AND target_id = ? LIMIT 1",
                (user_id, payload["target_type"], payload["target_id"]),
            ).fetchone()
        result = dict(row)
        result["duplicate"] = not changed
        return result


community_ugc_service = CommunityUGCService()
