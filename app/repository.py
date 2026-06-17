from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "yujian_fastapi.db"


class AssessmentRepository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
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

    def get_daily_energy(self, user_id: str, energy_date: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM daily_energies WHERE user_id = ? AND energy_date = ?",
                (user_id, energy_date),
            ).fetchone()
        return json.loads(row["result_json"]) if row else None

    def save_daily_energy(self, result: dict[str, Any]) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                """
                INSERT INTO daily_energies
                (user_id, energy_date, mode, assessment_id, result_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, energy_date) DO UPDATE SET
                    mode = excluded.mode,
                    assessment_id = excluded.assessment_id,
                    result_json = excluded.result_json,
                    updated_at = excluded.updated_at
                """,
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
        with self._lock, self.connect() as connection:
            connection.execute(
                """
                INSERT INTO daily_checkins
                (user_id, checkin_date, mood, sleep, stress, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, checkin_date) DO UPDATE SET
                    mood = excluded.mood,
                    sleep = excluded.sleep,
                    stress = excluded.stress,
                    updated_at = excluded.updated_at
                """,
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

    def upsert_user(self, user: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user["user_id"],),
            ).fetchone()
            created_at = user["updated_at"] if existing is None else existing["created_at"]
            connection.execute(
                """
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
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
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
