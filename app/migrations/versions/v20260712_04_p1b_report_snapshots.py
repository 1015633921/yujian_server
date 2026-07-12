from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from app.reporting import build_report_projection, report_context


VERSION = "20260712_04_p1b_report_snapshots"


def _sqlite_columns(connection, table: str) -> set[str]:
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}


def _sqlite_table_exists(connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table,),
    ).fetchone() is not None


def _mysql_columns(connection, database: str, table: str) -> set[str]:
    rows = connection.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?",
        (database, table),
    ).fetchall()
    return {row["COLUMN_NAME"] for row in rows}


def _mysql_table_exists(connection, database: str, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? LIMIT 1",
        (database, table),
    ).fetchone() is not None


def _legacy_report_id(assessment_id: str) -> str:
    digest = hashlib.sha256(assessment_id.encode("utf-8")).hexdigest()[:48]
    return f"legacy_{digest}"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _backfill_legacy_reports(connection, backend: str) -> None:
    if backend == "mysql":
        database = connection.execute("SELECT DATABASE() AS name").fetchone()["name"]
        if not _mysql_table_exists(connection, database, "energy_assessments"):
            return
    elif not _sqlite_table_exists(connection, "energy_assessments"):
        return
    rows = connection.execute(
        """
        SELECT assessment_id, user_id, fingerprint, result_json, created_at
        FROM energy_assessments
        ORDER BY user_id, created_at, assessment_id
        """
    ).fetchall()
    versions: dict[str, int] = defaultdict(int)
    insert_prefix = "INSERT IGNORE" if backend == "mysql" else "INSERT OR IGNORE"
    for row in rows:
        try:
            result = json.loads(row["result_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            result = {}
        input_snapshot = result.get("input_summary") if isinstance(result.get("input_summary"), dict) else {}
        user_id = str(row["user_id"] or input_snapshot.get("user_id") or f"legacy_unowned:{row['assessment_id']}")
        versions[user_id] += 1
        output_snapshot = {key: value for key, value in result.items() if key != "input_summary"}
        output_snapshot["report_projection"] = build_report_projection(result)
        output_snapshot["report_context"] = report_context(input_snapshot)
        source_hash = str(row["fingerprint"] or "") or hashlib.sha256(_json(input_snapshot).encode("utf-8")).hexdigest()
        connection.execute(
            f"""
            {insert_prefix} INTO report_snapshots
            (report_id, assessment_id, user_id, report_version, source_input_hash,
             algorithm_version, schema_version, calibration_version, calibration_status,
             calibration_source, calibration_reason_code, input_snapshot_json,
             output_snapshot_json, created_at)
            VALUES (?, ?, ?, ?, ?, 'legacy_unknown', 1, 'legacy_unknown', 'legacy_unknown',
                    'legacy_record', 'metadata_not_recoverable', ?, ?, ?)
            """,
            (
                _legacy_report_id(str(row["assessment_id"])),
                row["assessment_id"],
                user_id,
                versions[user_id],
                source_hash,
                _json(input_snapshot),
                _json(output_snapshot),
                row["created_at"],
            ),
        )
    for user_id, version in versions.items():
        if backend == "mysql":
            connection.execute(
                """
                INSERT INTO report_version_counters(user_id, last_version, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE last_version=GREATEST(last_version, VALUES(last_version)),
                                        updated_at=VALUES(updated_at)
                """,
                (user_id, version),
            )
        else:
            connection.execute(
                """
                INSERT INTO report_version_counters(user_id, last_version, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                  last_version=MAX(last_version, excluded.last_version), updated_at=excluded.updated_at
                """,
                (user_id, version),
            )


def upgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS report_snapshots (
              report_id VARCHAR(100) PRIMARY KEY,
              assessment_id VARCHAR(80) NOT NULL,
              user_id VARCHAR(100) NOT NULL,
              report_version INT NOT NULL,
              source_input_hash CHAR(64) NOT NULL,
              algorithm_version VARCHAR(80) NOT NULL,
              schema_version INT NOT NULL,
              calibration_version VARCHAR(80) NOT NULL,
              calibration_status VARCHAR(32) NOT NULL,
              calibration_source VARCHAR(80) NOT NULL,
              calibration_reason_code VARCHAR(100) NOT NULL DEFAULT '',
              input_snapshot_json LONGTEXT NOT NULL,
              output_snapshot_json LONGTEXT NOT NULL,
              created_at VARCHAR(40) NOT NULL,
              UNIQUE KEY ux_report_snapshots_assessment (assessment_id),
              UNIQUE KEY ux_report_snapshots_user_version (user_id, report_version),
              INDEX idx_report_snapshots_user_created (user_id, created_at),
              INDEX idx_report_snapshots_input_hash (user_id, source_input_hash)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS report_generation_requests (
              request_id VARCHAR(80) PRIMARY KEY,
              user_id VARCHAR(100) NOT NULL,
              idempotency_key VARCHAR(128) NOT NULL,
              source_input_hash CHAR(64) NOT NULL,
              assessment_id VARCHAR(80),
              report_id VARCHAR(100),
              status VARCHAR(32) NOT NULL,
              failure_reason VARCHAR(100) NOT NULL DEFAULT '',
              created_at VARCHAR(40) NOT NULL,
              updated_at VARCHAR(40) NOT NULL,
              UNIQUE KEY ux_report_generation_user_key (user_id, idempotency_key),
              INDEX idx_report_generation_report (report_id),
              INDEX idx_report_generation_status_updated (status, updated_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS report_version_counters (
              user_id VARCHAR(100) PRIMARY KEY,
              last_version INT NOT NULL,
              updated_at VARCHAR(40) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        if _mysql_table_exists(connection, database, "assessment_recommendations"):
            columns = _mysql_columns(connection, database, "assessment_recommendations")
            if "report_id" not in columns:
                connection.execute("ALTER TABLE assessment_recommendations ADD COLUMN report_id VARCHAR(100)")
            if "report_version" not in columns:
                connection.execute("ALTER TABLE assessment_recommendations ADD COLUMN report_version INT")
            indexes = {
                row["INDEX_NAME"]
                for row in connection.execute(
                    "SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'assessment_recommendations'",
                    (database,),
                ).fetchall()
            }
            if "idx_assessment_recommendations_report" not in indexes:
                connection.execute(
                    "CREATE INDEX idx_assessment_recommendations_report ON assessment_recommendations(report_id, report_version)"
                )
        _backfill_legacy_reports(connection, backend)
        return

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS report_snapshots (
          report_id TEXT PRIMARY KEY,
          assessment_id TEXT NOT NULL UNIQUE,
          user_id TEXT NOT NULL,
          report_version INTEGER NOT NULL,
          source_input_hash TEXT NOT NULL,
          algorithm_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          calibration_version TEXT NOT NULL,
          calibration_status TEXT NOT NULL,
          calibration_source TEXT NOT NULL,
          calibration_reason_code TEXT NOT NULL DEFAULT '',
          input_snapshot_json TEXT NOT NULL,
          output_snapshot_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(user_id, report_version)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_snapshots_user_created ON report_snapshots(user_id, created_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_snapshots_input_hash ON report_snapshots(user_id, source_input_hash)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS report_generation_requests (
          request_id TEXT PRIMARY KEY,
          user_id TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          source_input_hash TEXT NOT NULL,
          assessment_id TEXT,
          report_id TEXT,
          status TEXT NOT NULL,
          failure_reason TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(user_id, idempotency_key)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_generation_report ON report_generation_requests(report_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_generation_status_updated ON report_generation_requests(status, updated_at)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS report_version_counters (
          user_id TEXT PRIMARY KEY,
          last_version INTEGER NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    if _sqlite_table_exists(connection, "assessment_recommendations"):
        columns = _sqlite_columns(connection, "assessment_recommendations")
        if "report_id" not in columns:
            connection.execute("ALTER TABLE assessment_recommendations ADD COLUMN report_id TEXT")
        if "report_version" not in columns:
            connection.execute("ALTER TABLE assessment_recommendations ADD COLUMN report_version INTEGER")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_assessment_recommendations_report ON assessment_recommendations(report_id, report_version)"
        )
    _backfill_legacy_reports(connection, backend)


def downgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        if _mysql_table_exists(connection, database, "assessment_recommendations"):
            indexes = {
                row["INDEX_NAME"]
                for row in connection.execute(
                    "SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'assessment_recommendations'",
                    (database,),
                ).fetchall()
            }
            if "idx_assessment_recommendations_report" in indexes:
                connection.execute("DROP INDEX idx_assessment_recommendations_report ON assessment_recommendations")
            columns = _mysql_columns(connection, database, "assessment_recommendations")
            if "report_version" in columns:
                connection.execute("ALTER TABLE assessment_recommendations DROP COLUMN report_version")
            if "report_id" in columns:
                connection.execute("ALTER TABLE assessment_recommendations DROP COLUMN report_id")
        connection.execute("DROP TABLE IF EXISTS report_generation_requests")
        connection.execute("DROP TABLE IF EXISTS report_version_counters")
        connection.execute("DROP TABLE IF EXISTS report_snapshots")
        return

    if _sqlite_table_exists(connection, "assessment_recommendations"):
        connection.execute("DROP INDEX IF EXISTS idx_assessment_recommendations_report")
        columns = _sqlite_columns(connection, "assessment_recommendations")
        if "report_version" in columns:
            connection.execute("ALTER TABLE assessment_recommendations DROP COLUMN report_version")
        if "report_id" in columns:
            connection.execute("ALTER TABLE assessment_recommendations DROP COLUMN report_id")
    connection.execute("DROP INDEX IF EXISTS idx_report_generation_status_updated")
    connection.execute("DROP INDEX IF EXISTS idx_report_generation_report")
    connection.execute("DROP INDEX IF EXISTS idx_report_snapshots_input_hash")
    connection.execute("DROP INDEX IF EXISTS idx_report_snapshots_user_created")
    connection.execute("DROP TABLE IF EXISTS report_generation_requests")
    connection.execute("DROP TABLE IF EXISTS report_version_counters")
    connection.execute("DROP TABLE IF EXISTS report_snapshots")
