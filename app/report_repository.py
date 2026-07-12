from __future__ import annotations

import json
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from .database import DEFAULT_SQLITE_PATH, connect_database, integrity_errors, use_mysql
from .reporting import stable_hash


class ReportConflictError(ValueError):
    code = "report_idempotency_conflict"


class ReportVersionConflictError(ValueError):
    code = "report_version_conflict"


class ReportRepository:
    def __init__(self, db_path: Path = DEFAULT_SQLITE_PATH):
        self.db_path = db_path
        self._force_sqlite = db_path != DEFAULT_SQLITE_PATH

    def connect(self):
        return connect_database(self.db_path if self._force_sqlite else None)

    @property
    def mysql(self) -> bool:
        return use_mysql() and not self._force_sqlite

    def begin(self, connection) -> None:
        if not self.mysql:
            connection.execute("BEGIN IMMEDIATE")

    @staticmethod
    def normalize_key(value: str | None) -> str:
        key = str(value or "").strip()
        if len(key) < 8 or len(key) > 128:
            raise ValueError("Idempotency-Key 必须为 8 至 128 个字符")
        return key

    @staticmethod
    def _loads(value: str | None) -> dict[str, Any]:
        try:
            parsed = json.loads(value or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _next_version(self, connection, user_id: str, timestamp: str) -> int:
        if self.mysql:
            connection.execute(
                """
                INSERT INTO report_version_counters(user_id, last_version, updated_at)
                VALUES (?, 0, ?)
                ON DUPLICATE KEY UPDATE user_id=VALUES(user_id)
                """,
                (user_id, timestamp),
            )
            suffix = " FOR UPDATE"
        else:
            connection.execute(
                """
                INSERT INTO report_version_counters(user_id, last_version, updated_at)
                VALUES (?, 0, ?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (user_id, timestamp),
            )
            suffix = ""
        row = connection.execute(
            f"SELECT last_version FROM report_version_counters WHERE user_id = ?{suffix}",
            (user_id,),
        ).fetchone()
        version = int(row["last_version"] or 0) + 1
        connection.execute(
            "UPDATE report_version_counters SET last_version = ?, updated_at = ? WHERE user_id = ?",
            (version, timestamp, user_id),
        )
        return version

    def create_snapshot(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        source_input_hash: str,
        fingerprint: str,
        input_snapshot: dict[str, Any],
        output_snapshot: dict[str, Any],
        assessment_id: str,
        created_at: str,
        algorithm_version: str,
        schema_version: int,
        calibration_version: str,
        calibration_status: str,
        calibration_source: str,
        calibration_reason_code: str,
    ) -> tuple[dict[str, Any], bool]:
        key = self.normalize_key(idempotency_key)
        report_id = f"rpt_{secrets.token_urlsafe(24)}"
        request_id = f"rr_{secrets.token_hex(16)}"
        try:
            with self.connect() as connection:
                self.begin(connection)
                connection.execute(
                    """
                    INSERT INTO report_generation_requests
                    (request_id, user_id, idempotency_key, source_input_hash, assessment_id,
                     report_id, status, failure_reason, created_at, updated_at)
                    VALUES (?, ?, ?, ?, NULL, NULL, 'processing', '', ?, ?)
                    """,
                    (request_id, user_id, key, source_input_hash, created_at, created_at),
                )
                report_version = self._next_version(connection, user_id, created_at)
                connection.execute(
                    """
                    INSERT INTO energy_assessments
                    (assessment_id, user_id, fingerprint, name, core_wish, result_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        assessment_id,
                        user_id,
                        fingerprint,
                        input_snapshot.get("name") or "",
                        (input_snapshot.get("core_wishes") or [""])[0],
                        json.dumps({**output_snapshot, "input_summary": input_snapshot}, ensure_ascii=False),
                        created_at,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO report_snapshots
                    (report_id, assessment_id, user_id, report_version, source_input_hash,
                     algorithm_version, schema_version, calibration_version, calibration_status,
                     calibration_source, calibration_reason_code, input_snapshot_json,
                     output_snapshot_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_id,
                        assessment_id,
                        user_id,
                        report_version,
                        source_input_hash,
                        algorithm_version,
                        schema_version,
                        calibration_version,
                        calibration_status,
                        calibration_source,
                        calibration_reason_code,
                        json.dumps(input_snapshot, ensure_ascii=False, sort_keys=True),
                        json.dumps(output_snapshot, ensure_ascii=False, sort_keys=True),
                        created_at,
                    ),
                )
                connection.execute(
                    """
                    UPDATE report_generation_requests
                    SET assessment_id = ?, report_id = ?, status = 'completed', updated_at = ?
                    WHERE request_id = ?
                    """,
                    (assessment_id, report_id, created_at, request_id),
                )
            return self.get(report_id), False
        except (sqlite3.IntegrityError, *integrity_errors()) as exc:
            existing = self.get_request(user_id, key)
            if not existing:
                raise ReportConflictError("报告生成请求冲突，请重试") from exc
            if existing["source_input_hash"] != source_input_hash:
                raise ReportConflictError("同一 Idempotency-Key 不能用于不同的测算输入") from exc
            if existing["status"] != "completed" or not existing.get("report_id"):
                raise ReportConflictError("报告正在生成，请使用原请求稍后重试") from exc
            return self.get(str(existing["report_id"])), True

    def get_request(self, user_id: str, idempotency_key: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM report_generation_requests
                WHERE user_id = ? AND idempotency_key = ?
                """,
                (user_id, idempotency_key),
            ).fetchone()
        return dict(row) if row else None

    def get(self, report_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM report_snapshots WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        if not row:
            return None
        snapshot = dict(row)
        snapshot["input_snapshot"] = self._loads(snapshot.pop("input_snapshot_json", "{}"))
        snapshot["output_snapshot"] = self._loads(snapshot.pop("output_snapshot_json", "{}"))
        return snapshot

    def get_by_assessment(self, assessment_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT report_id FROM report_snapshots WHERE assessment_id = ?",
                (assessment_id,),
            ).fetchone()
        return self.get(str(row["report_id"])) if row else None

    def owned(self, report_id: str, user_id: str, expected_version: int | None = None) -> dict[str, Any] | None:
        snapshot = self.get(report_id)
        if not snapshot or snapshot["user_id"] != user_id:
            return None
        if expected_version is not None and int(snapshot["report_version"]) != int(expected_version):
            raise ReportVersionConflictError("报告版本不匹配，请重新加载指定报告")
        return snapshot

    @staticmethod
    def detail_dto(snapshot: dict[str, Any]) -> dict[str, Any]:
        output = dict(snapshot["output_snapshot"])
        output.pop("solar_time", None)
        metadata = {
            "report_id": snapshot["report_id"],
            "assessment_id": snapshot["assessment_id"],
            "report_version": int(snapshot["report_version"]),
            "created_at": snapshot["created_at"],
            "algorithm_version": snapshot["algorithm_version"],
            "schema_version": int(snapshot["schema_version"]),
            "calibration_version": snapshot["calibration_version"],
            "calibration_status": snapshot["calibration_status"],
        }
        return {**output, **metadata}

    @staticmethod
    def basis_dto(snapshot: dict[str, Any]) -> dict[str, Any]:
        inputs = dict(snapshot["input_snapshot"])
        inputs.pop("user_id", None)
        output = snapshot["output_snapshot"]
        return {
            "report_id": snapshot["report_id"],
            "report_version": int(snapshot["report_version"]),
            "created_at": snapshot["created_at"],
            "algorithm_version": snapshot["algorithm_version"],
            "schema_version": int(snapshot["schema_version"]),
            "calibration": {
                "status": snapshot["calibration_status"],
                "source": snapshot["calibration_source"],
                "version": snapshot["calibration_version"],
                "reason_code": snapshot["calibration_reason_code"],
                "details": output.get("solar_time") or {},
            },
            "input_snapshot": inputs,
            "bazi_basis": output.get("bazi_basis") or {},
            "mbti_analysis": output.get("mbti_analysis") or {},
            "chakra_analysis": output.get("chakra_analysis") or {},
            "mood_analysis": output.get("mood_analysis") or {},
            "zodiac_analysis": output.get("zodiac_analysis") or {},
        }

    @staticmethod
    def poster_dto(snapshot: dict[str, Any]) -> dict[str, Any]:
        projection = dict((snapshot["output_snapshot"] or {}).get("report_projection") or {})
        payload = {
            "report_id": snapshot["report_id"],
            "report_version": int(snapshot["report_version"]),
            "created_at": snapshot["created_at"],
            "core_conclusion": projection.get("core_conclusion") or {},
            "style_guidance": projection.get("style_guidance") or {},
            "adjustment_strategy": projection.get("adjustment_strategy") or [],
            "elements": projection.get("elements") or [],
            "balance": projection.get("balance") or {},
            "keywords": projection.get("keywords") or [],
            "brand": "宇涧水晶",
        }
        return {**payload, "sanitized_payload_hash": stable_hash(payload)}
