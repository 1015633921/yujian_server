from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .database import DEFAULT_SQLITE_PATH, connect_database, use_mysql

DB_PATH = DEFAULT_SQLITE_PATH


class AssessmentRepository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._force_sqlite = db_path != DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def connect(self):
        return connect_database(self.db_path if self._force_sqlite else None)

    def _init_db(self) -> None:
        if use_mysql() and not self._force_sqlite:
            with self.connect():
                pass
            return
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS energy_assessments (
                    assessment_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    fingerprint TEXT NOT NULL,
                    name TEXT NOT NULL,
                    core_wish TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_energy_assessments_user_created "
                "ON energy_assessments(user_id, created_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS assessment_recommendations (
                    assessment_id TEXT NOT NULL,
                    wrist_size_tenths INTEGER NOT NULL,
                    bead_size_mm INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (assessment_id, wrist_size_tenths, bead_size_mm, algorithm_version)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_energies (
                    user_id TEXT NOT NULL,
                    energy_date TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    assessment_id TEXT,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, energy_date)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_checkins (
                    user_id TEXT NOT NULL,
                    checkin_date TEXT NOT NULL,
                    mood INTEGER NOT NULL,
                    sleep INTEGER NOT NULL,
                    stress INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, checkin_date)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    openid TEXT,
                    unionid TEXT,
                    nickname TEXT,
                    avatar_url TEXT,
                    gender TEXT,
                    phone_number TEXT,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_openid ON users(openid)"
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

    def find_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM energy_assessments WHERE fingerprint = ? ORDER BY created_at DESC LIMIT 1",
                (fingerprint,),
            ).fetchone()
        return json.loads(row["result_json"]) if row else None

    def save(self, result: dict[str, Any], fingerprint: str) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                """
                INSERT INTO energy_assessments
                (assessment_id, user_id, fingerprint, name, core_wish, result_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result["assessment_id"],
                    result["input_summary"].get("user_id"),
                    fingerprint,
                    result["input_summary"]["name"],
                    result["input_summary"]["core_wish"],
                    json.dumps(result, ensure_ascii=False),
                    result["created_at"],
                ),
            )

    def update(self, result: dict[str, Any]) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                """
                UPDATE energy_assessments
                SET result_json = ?
                WHERE assessment_id = ?
                """,
                (json.dumps(result, ensure_ascii=False), result["assessment_id"]),
            )

    def get(self, assessment_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM energy_assessments WHERE assessment_id = ?",
                (assessment_id,),
            ).fetchone()
        return json.loads(row["result_json"]) if row else None

    @staticmethod
    def recommendation_wrist_key(wrist_size_cm: float) -> int:
        return int(round(float(wrist_size_cm) * 10))

    def get_cached_recommendation(
        self,
        assessment_id: str,
        wrist_size_cm: float,
        bead_size_mm: int,
        algorithm_version: str,
        report_id: str | None = None,
        report_version: int | None = None,
    ) -> dict[str, Any] | None:
        version_clause = ""
        values: list[Any] = [
            assessment_id,
            self.recommendation_wrist_key(wrist_size_cm),
            int(bead_size_mm),
            algorithm_version,
        ]
        if report_id is not None:
            version_clause = " AND report_id = ? AND report_version = ?"
            values.extend([report_id, int(report_version or 0)])
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT result_json FROM assessment_recommendations
                WHERE assessment_id = ? AND wrist_size_tenths = ?
                  AND bead_size_mm = ? AND algorithm_version = ?{version_clause}
                """,
                values,
            ).fetchone()
        return json.loads(row["result_json"]) if row else None

    def save_cached_recommendation(
        self,
        assessment_id: str,
        wrist_size_cm: float,
        bead_size_mm: int,
        algorithm_version: str,
        result: dict[str, Any],
        timestamp: str,
        report_id: str | None = None,
        report_version: int | None = None,
    ) -> None:
        if report_id is not None:
            if use_mysql() and not self._force_sqlite:
                sql = """
                    INSERT INTO assessment_recommendations
                    (assessment_id, wrist_size_tenths, bead_size_mm, algorithm_version,
                     result_json, created_at, updated_at, report_id, report_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON DUPLICATE KEY UPDATE result_json=VALUES(result_json), updated_at=VALUES(updated_at),
                                            report_id=VALUES(report_id), report_version=VALUES(report_version)
                """
            else:
                sql = """
                    INSERT INTO assessment_recommendations
                    (assessment_id, wrist_size_tenths, bead_size_mm, algorithm_version,
                     result_json, created_at, updated_at, report_id, report_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(assessment_id, wrist_size_tenths, bead_size_mm, algorithm_version)
                    DO UPDATE SET result_json=excluded.result_json, updated_at=excluded.updated_at,
                                  report_id=excluded.report_id, report_version=excluded.report_version
                """
            with self._lock, self.connect() as connection:
                connection.execute(
                    sql,
                    (
                        assessment_id,
                        self.recommendation_wrist_key(wrist_size_cm),
                        int(bead_size_mm),
                        algorithm_version,
                        json.dumps(result, ensure_ascii=False),
                        timestamp,
                        timestamp,
                        report_id,
                        int(report_version or 0),
                    ),
                )
            return
        if use_mysql() and not self._force_sqlite:
            sql = """
                INSERT INTO assessment_recommendations
                (assessment_id, wrist_size_tenths, bead_size_mm, algorithm_version,
                 result_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE result_json=VALUES(result_json), updated_at=VALUES(updated_at)
            """
        else:
            sql = """
                INSERT INTO assessment_recommendations
                (assessment_id, wrist_size_tenths, bead_size_mm, algorithm_version,
                 result_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(assessment_id, wrist_size_tenths, bead_size_mm, algorithm_version)
                DO UPDATE SET result_json=excluded.result_json, updated_at=excluded.updated_at
            """
        with self._lock, self.connect() as connection:
            connection.execute(
                sql,
                (
                    assessment_id,
                    self.recommendation_wrist_key(wrist_size_cm),
                    int(bead_size_mm),
                    algorithm_version,
                    json.dumps(result, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
            )

    def history(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT result_json FROM energy_assessments
                WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [json.loads(row["result_json"]) for row in rows]

    def latest_for_user(self, user_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT result_json FROM energy_assessments
                WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return json.loads(row["result_json"]) if row else None

    def privacy_data_summary(self, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            assessment_row = connection.execute(
                "SELECT COUNT(*) AS total FROM energy_assessments WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            daily_row = connection.execute(
                "SELECT COUNT(*) AS total FROM daily_energies WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            checkin_row = connection.execute(
                "SELECT COUNT(*) AS total FROM daily_checkins WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            report_row = None
            if self.table_exists(connection, "report_snapshots"):
                report_row = connection.execute(
                    "SELECT COUNT(*) AS total FROM report_snapshots WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
        latest = self.latest_for_user(user_id)
        user = self.get_user(user_id)
        return {
            "profile": {
                "nickname": (user or {}).get("nickname") or "",
                "gender": (user or {}).get("gender") or "",
                "phone_number": (user or {}).get("phone_number") or "",
            },
            "latest_input": (latest or {}).get("input_summary") or {},
            "latest_profile": {
                "assessment_id": (latest or {}).get("assessment_id") or "",
                "created_at": (latest or {}).get("created_at") or "",
                "strongest_element": (latest or {}).get("strongest_element") or "",
                "weakest_element": (latest or {}).get("weakest_element") or "",
            },
            "counts": {
                "assessments": int((assessment_row or {})["total"] or 0),
                "reports": int((report_row or {"total": 0})["total"] or 0),
                "daily_energies": int((daily_row or {})["total"] or 0),
                "daily_checkins": int((checkin_row or {})["total"] or 0),
            },
        }

    def delete_personalization_data(self, user_id: str) -> dict[str, Any]:
        summary = self.privacy_data_summary(user_id)
        with self._lock, self.connect() as connection:
            if self.table_exists(connection, "report_snapshots"):
                connection.execute(
                    """
                    DELETE FROM assessment_recommendations
                    WHERE report_id IN (
                        SELECT report_id FROM report_snapshots WHERE user_id = ?
                    )
                    """,
                    (user_id,),
                )
            if self.table_exists(connection, "report_generation_requests"):
                connection.execute("DELETE FROM report_generation_requests WHERE user_id = ?", (user_id,))
            if self.table_exists(connection, "report_snapshots"):
                connection.execute("DELETE FROM report_snapshots WHERE user_id = ?", (user_id,))
            if self.table_exists(connection, "report_version_counters"):
                connection.execute("DELETE FROM report_version_counters WHERE user_id = ?", (user_id,))
            connection.execute(
                """
                DELETE FROM assessment_recommendations
                WHERE assessment_id IN (
                    SELECT assessment_id FROM energy_assessments WHERE user_id = ?
                )
                """,
                (user_id,),
            )
            connection.execute("DELETE FROM daily_checkins WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM daily_energies WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM energy_assessments WHERE user_id = ?", (user_id,))
        return {"deleted": True, "counts": summary["counts"]}

    def get_daily_energy(self, user_id: str, energy_date: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM daily_energies WHERE user_id = ? AND energy_date = ?",
                (user_id, energy_date),
            ).fetchone()
        return json.loads(row["result_json"]) if row else None

    def save_daily_energy(self, result: dict[str, Any]) -> None:
        if use_mysql() and not self._force_sqlite:
            sql = """
                INSERT INTO daily_energies
                (user_id, energy_date, mode, assessment_id, result_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE mode=VALUES(mode), assessment_id=VALUES(assessment_id),
                result_json=VALUES(result_json), updated_at=VALUES(updated_at)
            """
        else:
            sql = """
                INSERT INTO daily_energies
                (user_id, energy_date, mode, assessment_id, result_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, energy_date) DO UPDATE SET
                    mode = excluded.mode, assessment_id = excluded.assessment_id,
                    result_json = excluded.result_json, updated_at = excluded.updated_at
            """
        with self._lock, self.connect() as connection:
            connection.execute(
                sql,
                (
                    result["user_id"],
                    result["date"],
                    result["mode"],
                    result.get("assessment_id"),
                    json.dumps(result, ensure_ascii=False),
                    result["calculated_at"],
                    result["calculated_at"],
                ),
            )

    def save_checkin(self, checkin: dict[str, Any]) -> None:
        if use_mysql() and not self._force_sqlite:
            sql = """
                INSERT INTO daily_checkins
                (user_id, checkin_date, mood, sleep, stress, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE mood=VALUES(mood), sleep=VALUES(sleep),
                stress=VALUES(stress), updated_at=VALUES(updated_at)
            """
        else:
            sql = """
                INSERT INTO daily_checkins
                (user_id, checkin_date, mood, sleep, stress, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, checkin_date) DO UPDATE SET
                    mood = excluded.mood, sleep = excluded.sleep, stress = excluded.stress,
                    updated_at = excluded.updated_at
            """
        with self._lock, self.connect() as connection:
            connection.execute(
                sql,
                (
                    checkin["user_id"],
                    checkin["date"],
                    checkin["mood"],
                    checkin["sleep"],
                    checkin["stress"],
                    checkin["created_at"],
                    checkin["created_at"],
                ),
            )

    def recent_checkins(self, user_id: str, start_date: str, limit: int = 7) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT checkin_date, mood, sleep, stress FROM daily_checkins
                WHERE user_id = ? AND checkin_date >= ?
                ORDER BY checkin_date DESC LIMIT ?
                """,
                (user_id, start_date, limit),
            ).fetchall()
        return [
            {"date": row["checkin_date"], "mood": row["mood"], "sleep": row["sleep"], "stress": row["stress"]}
            for row in rows
        ]

    def get_setting(self, setting_key: str) -> Any | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT setting_json FROM system_settings WHERE setting_key = ?",
                (setting_key,),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["setting_json"])
        except (TypeError, json.JSONDecodeError):
            return None

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
        with self._lock, self.connect() as connection:
            connection.execute(
                sql,
                (setting_key, json.dumps(value, ensure_ascii=False), updated_at),
            )

    def upsert_user(self, user: dict[str, Any]) -> dict[str, Any]:
        if use_mysql() and not self._force_sqlite:
            sql = """
                INSERT INTO users
                (user_id, openid, unionid, nickname, avatar_url, gender, phone_number, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                    openid=COALESCE(VALUES(openid), openid), unionid=COALESCE(VALUES(unionid), unionid),
                    nickname=COALESCE(VALUES(nickname), nickname), avatar_url=COALESCE(VALUES(avatar_url), avatar_url),
                    gender=COALESCE(VALUES(gender), gender), phone_number=COALESCE(VALUES(phone_number), phone_number),
                    source=VALUES(source), updated_at=VALUES(updated_at)
            """
        else:
            sql = """
                INSERT INTO users
                (user_id, openid, unionid, nickname, avatar_url, gender, phone_number, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    openid = COALESCE(excluded.openid, users.openid),
                    unionid = COALESCE(excluded.unionid, users.unionid),
                    nickname = COALESCE(excluded.nickname, users.nickname),
                    avatar_url = COALESCE(excluded.avatar_url, users.avatar_url),
                    gender = COALESCE(excluded.gender, users.gender),
                    phone_number = COALESCE(excluded.phone_number, users.phone_number),
                    source = excluded.source, updated_at = excluded.updated_at
            """
        with self._lock, self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user["user_id"],),
            ).fetchone()
            created_at = user["updated_at"] if existing is None else existing["created_at"]
            connection.execute(
                sql,
                (
                    user["user_id"],
                    user.get("openid"),
                    user.get("unionid"),
                    user.get("nickname"),
                    user.get("avatar_url"),
                    user.get("gender"),
                    user.get("phone_number"),
                    user.get("source", "wechat"),
                    created_at,
                    user["updated_at"],
                ),
            )
        return self.get_user(user["user_id"])

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_openid(self, openid: str | None) -> dict[str, Any] | None:
        if not openid:
            return None
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE openid = ? ORDER BY created_at ASC LIMIT 1",
                (openid,),
            ).fetchone()
        return dict(row) if row else None

    def user_id_exists(self, user_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM users WHERE user_id = ? LIMIT 1",
                (user_id,),
            ).fetchone()
        return row is not None

    @property
    def _uses_mysql(self) -> bool:
        return use_mysql() and not self._force_sqlite

    def _merge_community_post_relation(
        self,
        connection,
        table: str,
        old_user_id: str,
        new_user_id: str,
    ) -> None:
        """Merge a post/user relation while preserving its earliest timestamp."""

        if not self.table_exists(connection, table):
            return
        lock = " FOR UPDATE" if self._uses_mysql else ""
        rows = connection.execute(
            f"SELECT post_id, user_id, created_at FROM {table} "
            f"WHERE user_id IN (?, ?) ORDER BY post_id, user_id{lock}",
            (old_user_id, new_user_id),
        ).fetchall()
        if not rows:
            return
        merged: dict[str, str] = {}
        for row in rows:
            post_id = str(row["post_id"])
            created_at = str(row["created_at"])
            merged[post_id] = min(merged.get(post_id, created_at), created_at)
        connection.execute(
            f"DELETE FROM {table} WHERE user_id IN (?, ?)",
            (old_user_id, new_user_id),
        )
        for post_id, created_at in merged.items():
            connection.execute(
                f"INSERT INTO {table} (post_id, user_id, created_at) VALUES (?, ?, ?)",
                (post_id, new_user_id, created_at),
            )

    def _merge_community_favorites(
        self,
        connection,
        old_user_id: str,
        new_user_id: str,
    ) -> None:
        """Merge legacy editorial favorites by newest snapshot and earliest creation."""

        table = "community_favorites"
        if not self.table_exists(connection, table):
            return
        lock = " FOR UPDATE" if self._uses_mysql else ""
        rows = connection.execute(
            "SELECT user_id, post_id, item_json, created_at, updated_at "
            f"FROM {table} WHERE user_id IN (?, ?) ORDER BY post_id, updated_at, user_id{lock}",
            (old_user_id, new_user_id),
        ).fetchall()
        if not rows:
            return
        merged: dict[str, dict[str, Any]] = {}
        for row in rows:
            candidate = dict(row)
            post_id = str(candidate["post_id"])
            current = merged.get(post_id)
            if current is None:
                candidate["created_at"] = str(candidate["created_at"])
                merged[post_id] = candidate
                continue
            earliest = min(str(current["created_at"]), str(candidate["created_at"]))
            candidate_order = (
                str(candidate["updated_at"]),
                candidate["user_id"] == new_user_id,
            )
            current_order = (
                str(current["updated_at"]),
                current["user_id"] == new_user_id,
            )
            winner = candidate if candidate_order > current_order else current
            winner["created_at"] = earliest
            merged[post_id] = winner
        connection.execute(
            f"DELETE FROM {table} WHERE user_id IN (?, ?)",
            (old_user_id, new_user_id),
        )
        for row in merged.values():
            connection.execute(
                f"INSERT INTO {table} (user_id, post_id, item_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    new_user_id,
                    row["post_id"],
                    row["item_json"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )

    def _merge_community_follows(
        self,
        connection,
        old_user_id: str,
        new_user_id: str,
    ) -> None:
        table = "community_ugc_follows"
        if not self.table_exists(connection, table):
            return
        lock = " FOR UPDATE" if self._uses_mysql else ""
        rows = connection.execute(
            "SELECT follower_user_id, followed_user_id, created_at "
            f"FROM {table} WHERE follower_user_id IN (?, ?) OR followed_user_id IN (?, ?) "
            f"ORDER BY follower_user_id, followed_user_id{lock}",
            (old_user_id, new_user_id, old_user_id, new_user_id),
        ).fetchall()
        if not rows:
            return
        merged: dict[tuple[str, str], str] = {}
        for row in rows:
            follower = (
                new_user_id
                if row["follower_user_id"] == old_user_id
                else str(row["follower_user_id"])
            )
            followed = (
                new_user_id
                if row["followed_user_id"] == old_user_id
                else str(row["followed_user_id"])
            )
            if follower == followed:
                continue
            key = (follower, followed)
            created_at = str(row["created_at"])
            merged[key] = min(merged.get(key, created_at), created_at)
        connection.execute(
            f"DELETE FROM {table} WHERE follower_user_id IN (?, ?) OR followed_user_id IN (?, ?)",
            (old_user_id, new_user_id, old_user_id, new_user_id),
        )
        for (follower, followed), created_at in merged.items():
            connection.execute(
                f"INSERT INTO {table} (follower_user_id, followed_user_id, created_at) "
                "VALUES (?, ?, ?)",
                (follower, followed, created_at),
            )

    def _merge_community_reports(
        self,
        connection,
        old_user_id: str,
        new_user_id: str,
    ) -> None:
        table = "community_ugc_reports"
        if not self.table_exists(connection, table):
            return
        lock = " FOR UPDATE" if self._uses_mysql else ""
        rows = connection.execute(
            "SELECT report_id, reporter_user_id, target_type, target_id, reason, detail, "
            f"status, created_at, updated_at FROM {table} "
            f"WHERE reporter_user_id IN (?, ?) ORDER BY target_type, target_id, created_at, report_id{lock}",
            (old_user_id, new_user_id),
        ).fetchall()
        if not rows:
            return
        winners: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            candidate = dict(row)
            key = (str(candidate["target_type"]), str(candidate["target_id"]))
            current = winners.get(key)
            candidate_order = (str(candidate["created_at"]), str(candidate["report_id"]))
            if current is None or candidate_order < (
                str(current["created_at"]),
                str(current["report_id"]),
            ):
                winners[key] = candidate
        connection.execute(
            f"DELETE FROM {table} WHERE reporter_user_id IN (?, ?)",
            (old_user_id, new_user_id),
        )
        for row in winners.values():
            connection.execute(
                f"INSERT INTO {table} "
                "(report_id, reporter_user_id, target_type, target_id, reason, detail, status, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["report_id"],
                    new_user_id,
                    row["target_type"],
                    row["target_id"],
                    row["reason"],
                    row["detail"],
                    row["status"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )

    def _reassign_community_user_id(
        self,
        connection,
        old_user_id: str,
        new_user_id: str,
    ) -> None:
        if self.table_exists(connection, "community_ugc_posts"):
            connection.execute(
                "UPDATE community_ugc_posts SET owner_user_id = ? WHERE owner_user_id = ?",
                (new_user_id, old_user_id),
            )
        for table in ("community_ugc_likes", "community_ugc_saves"):
            self._merge_community_post_relation(connection, table, old_user_id, new_user_id)
        if self.table_exists(connection, "community_ugc_comments"):
            connection.execute(
                "UPDATE community_ugc_comments SET author_user_id = ? WHERE author_user_id = ?",
                (new_user_id, old_user_id),
            )
        self._merge_community_follows(connection, old_user_id, new_user_id)
        self._merge_community_reports(connection, old_user_id, new_user_id)

    def reassign_user_id(self, old_user_id: str, new_user_id: str, updated_at: str) -> dict[str, Any]:
        if old_user_id == new_user_id:
            user = self.get_user(new_user_id)
            if not user:
                raise ValueError("user not found")
            return user
        with self._lock, self.connect() as connection:
            if not self._uses_mysql:
                connection.execute("BEGIN IMMEDIATE")
            lock = " FOR UPDATE" if self._uses_mysql else ""
            locked_user_ids = tuple(sorted((old_user_id, new_user_id)))
            locked_users = connection.execute(
                "SELECT * FROM users WHERE user_id IN (?, ?) ORDER BY user_id"
                f"{lock}",
                locked_user_ids,
            ).fetchall()
            users_by_id = {str(row["user_id"]): row for row in locked_users}
            existing = users_by_id.get(old_user_id)
            if existing is None:
                raise ValueError("user not found")
            if new_user_id in users_by_id:
                raise ValueError("new user_id already exists")
            for table in (
                "energy_assessments",
                "report_snapshots",
                "report_generation_requests",
                "report_version_counters",
                "daily_energies",
                "daily_checkins",
                "orders",
                "diy_designs",
                "cart_items",
                "user_addresses",
                "user_coupons",
                "user_sessions",
            ):
                if not self.table_exists(connection, table):
                    continue
                connection.execute(
                    f"UPDATE {table} SET user_id = ? WHERE user_id = ?",
                    (new_user_id, old_user_id),
                )
            self._merge_community_favorites(connection, old_user_id, new_user_id)
            self._reassign_community_user_id(connection, old_user_id, new_user_id)
            connection.execute(
                "UPDATE users SET user_id = ?, updated_at = ? WHERE user_id = ?",
                (new_user_id, updated_at, old_user_id),
            )
        return self.get_user(new_user_id)

    def table_exists(self, connection, table: str) -> bool:
        if use_mysql() and not self._force_sqlite:
            row = connection.execute("SHOW TABLES LIKE ?", (table,)).fetchone()
            return row is not None
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None
