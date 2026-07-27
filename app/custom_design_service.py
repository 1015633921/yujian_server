from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .database import connect_database, runtime_schema_mutation_allowed, use_mysql
from .order_service import OrderService
from .reporting import build_report_projection, report_context
from .repository import DB_PATH


DESIGN_STATUSES = {"submitted", "designing", "proposed", "revision_requested", "confirmed", "closed"}
OPEN_STATUSES = {"submitted", "designing", "proposed", "revision_requested"}
DEFAULT_DAILY_CAPACITY = 12
SETTING_KEY = "custom_design_service"
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def json_value(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


class CustomDesignService:
    """Independent human design requests; deliberately unrelated to merchandise orders."""

    def __init__(self, db_path=DB_PATH, order_service: OrderService | None = None):
        self.db_path = Path(db_path)
        self._force_sqlite = self.db_path != DB_PATH
        self.order_service = order_service or OrderService(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self):
        return connect_database(self.db_path if self._force_sqlite else None)

    def init_db(self) -> None:
        # Production MySQL is expanded only through the explicit migration.
        if use_mysql() and not self._force_sqlite and not runtime_schema_mutation_allowed():
            return
        with self.connect() as connection:
            if use_mysql() and not self._force_sqlite:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS custom_design_requests (
                    request_id VARCHAR(80) PRIMARY KEY, user_id VARCHAR(100) NOT NULL,
                    report_id VARCHAR(80) NOT NULL, report_version INT NOT NULL,
                    request_json LONGTEXT NOT NULL, status VARCHAR(40) NOT NULL,
                    first_draft_due_at VARCHAR(40), created_at VARCHAR(40) NOT NULL,
                    updated_at VARCHAR(40) NOT NULL, proposed_at VARCHAR(40), confirmed_at VARCHAR(40),
                    INDEX idx_custom_design_requests_user_created (user_id, created_at),
                    INDEX idx_custom_design_requests_status_created (status, created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
                )
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS custom_design_proposals (
                    proposal_id VARCHAR(80) PRIMARY KEY, request_id VARCHAR(80) NOT NULL,
                    proposal_version INT NOT NULL, title VARCHAR(160) NOT NULL, description TEXT NOT NULL,
                    image_urls_json LONGTEXT NOT NULL, status VARCHAR(20) NOT NULL,
                    workbench_json LONGTEXT, order_id VARCHAR(80), confirmed_at VARCHAR(40),
                    created_by VARCHAR(100) NOT NULL, created_at VARCHAR(40) NOT NULL,
                    UNIQUE KEY uq_custom_design_proposal_version (request_id, proposal_version),
                    INDEX idx_custom_design_proposals_request (request_id, proposal_version)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
                )
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS custom_design_drafts (
                    draft_id VARCHAR(80) PRIMARY KEY, request_id VARCHAR(80) NOT NULL,
                    draft_version INT NOT NULL, workbench_json LONGTEXT NOT NULL,
                    created_by VARCHAR(100) NOT NULL, created_at VARCHAR(40) NOT NULL,
                    updated_at VARCHAR(40) NOT NULL,
                    UNIQUE KEY uq_custom_design_drafts_request (request_id),
                    INDEX idx_custom_design_drafts_updated (updated_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
                )
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS custom_design_events (
                    event_id VARCHAR(80) PRIMARY KEY, request_id VARCHAR(80) NOT NULL,
                    event_type VARCHAR(40) NOT NULL, from_status VARCHAR(40) NOT NULL DEFAULT '',
                    to_status VARCHAR(40) NOT NULL DEFAULT '', actor_type VARCHAR(20) NOT NULL,
                    actor_id VARCHAR(100) NOT NULL, note VARCHAR(500) NOT NULL DEFAULT '', created_at VARCHAR(40) NOT NULL,
                    INDEX idx_custom_design_events_request_created (request_id, created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
                )
                return
            connection.execute(
                """CREATE TABLE IF NOT EXISTS system_settings (
                setting_key TEXT PRIMARY KEY, setting_json TEXT NOT NULL, updated_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS custom_design_requests (
                request_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, report_id TEXT NOT NULL,
                report_version INTEGER NOT NULL, request_json TEXT NOT NULL, status TEXT NOT NULL,
                first_draft_due_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                proposed_at TEXT, confirmed_at TEXT
                )"""
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_custom_design_requests_user_created ON custom_design_requests(user_id, created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_custom_design_requests_status_created ON custom_design_requests(status, created_at DESC)")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS custom_design_proposals (
                proposal_id TEXT PRIMARY KEY, request_id TEXT NOT NULL, proposal_version INTEGER NOT NULL,
                title TEXT NOT NULL, description TEXT NOT NULL, image_urls_json TEXT NOT NULL,
                workbench_json TEXT, order_id TEXT, confirmed_at TEXT,
                status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(request_id, proposal_version)
                )"""
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_custom_design_proposals_request ON custom_design_proposals(request_id, proposal_version DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_custom_design_proposals_order ON custom_design_proposals(order_id)")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS custom_design_drafts (
                draft_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
                draft_version INTEGER NOT NULL, workbench_json TEXT NOT NULL,
                created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )"""
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_custom_design_drafts_updated ON custom_design_drafts(updated_at DESC)")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS custom_design_events (
                event_id TEXT PRIMARY KEY, request_id TEXT NOT NULL, event_type TEXT NOT NULL,
                from_status TEXT NOT NULL DEFAULT '', to_status TEXT NOT NULL DEFAULT '', actor_type TEXT NOT NULL,
                actor_id TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
                )"""
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_custom_design_events_request_created ON custom_design_events(request_id, created_at)")

    def _settings(self, connection) -> dict[str, Any]:
        row = connection.execute("SELECT setting_json FROM system_settings WHERE setting_key = ?", (SETTING_KEY,)).fetchone()
        saved = json_value(row["setting_json"], {}) if row else {}
        return {"daily_capacity": max(0, min(int(saved.get("daily_capacity", DEFAULT_DAILY_CAPACITY)), 200)), "sla_hours": max(1, min(int(saved.get("sla_hours", 24)), 168))}

    def get_settings(self) -> dict[str, int]:
        with self.connect() as connection:
            return self._settings(connection)

    def save_settings(self, payload: dict[str, Any]) -> dict[str, int]:
        capacity = max(0, min(int(payload.get("daily_capacity", DEFAULT_DAILY_CAPACITY)), 200))
        sla_hours = max(1, min(int(payload.get("sla_hours", 24)), 168))
        timestamp = now_iso()
        sql = (
            "INSERT INTO system_settings (setting_key, setting_json, updated_at) VALUES (?, ?, ?) "
            "ON DUPLICATE KEY UPDATE setting_json=VALUES(setting_json), updated_at=VALUES(updated_at)"
            if use_mysql() and not self._force_sqlite
            else "INSERT INTO system_settings (setting_key, setting_json, updated_at) VALUES (?, ?, ?) ON CONFLICT(setting_key) DO UPDATE SET setting_json=excluded.setting_json, updated_at=excluded.updated_at"
        )
        saved = {"daily_capacity": capacity, "sla_hours": sla_hours}
        with self.connect() as connection:
            connection.execute(sql, (SETTING_KEY, json.dumps(saved, ensure_ascii=False), timestamp))
        return saved

    @staticmethod
    def _request_id() -> str:
        return f"CD{int(datetime.now().timestamp() * 1000)}{secrets.token_hex(3).upper()}"

    def _event(self, connection, request_id: str, event_type: str, actor_type: str, actor_id: str, *, from_status: str = "", to_status: str = "", note: str = "") -> None:
        connection.execute(
            "INSERT INTO custom_design_events (event_id, request_id, event_type, from_status, to_status, actor_type, actor_id, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (secrets.token_hex(16), request_id, event_type, from_status, to_status, actor_type, actor_id, note[:500], now_iso()),
        )

    def _public(self, row: dict[str, Any], *, include_request: bool = True) -> dict[str, Any]:
        item = dict(row)
        item["request"] = json_value(item.pop("request_json", "{}"), {}) if include_request else {}
        item["proposals"] = json_value(item.pop("proposals_json", "[]"), [])
        item["events"] = json_value(item.pop("events_json", "[]"), [])
        return item

    def _detail_query(
        self,
        connection,
        where: str,
        params: list[Any],
        *,
        include_draft: bool = False,
    ) -> list[dict[str, Any]]:
        rows = connection.execute(f"SELECT r.* FROM custom_design_requests r {where} ORDER BY r.updated_at DESC", params).fetchall()
        result = []
        for row in rows:
            item = self._public({**dict(row), "proposals_json": "[]", "events_json": "[]"})
            report = connection.execute(
                "SELECT report_code, input_snapshot_json, output_snapshot_json "
                "FROM report_snapshots WHERE report_id = ? AND report_version = ?",
                (item["report_id"], item["report_version"]),
            ).fetchone()
            item["report_code"] = str(report["report_code"]) if report and report["report_code"] else item["report_id"]
            output = json_value(report["output_snapshot_json"], {}) if report else {}
            input_snapshot = json_value(report["input_snapshot_json"], {}) if report else {}

            # 兼容报告版本化上线前创建的人工搭配工单：旧工单保存的是
            # ``assessment:<assessment_id>``，报告正文仍在 energy_assessments.result_json。
            # 如果只查 report_snapshots，会导致后台详情所有测算字段显示“未提供”。
            if not report and str(item.get("report_id") or "").startswith("assessment:"):
                legacy_assessment_id = str(item["report_id"])[len("assessment:"):].strip()
                legacy = connection.execute(
                    "SELECT name, core_wish, result_json FROM energy_assessments WHERE assessment_id = ?",
                    (legacy_assessment_id,),
                ).fetchone() if legacy_assessment_id else None
                if legacy:
                    output = json_value(legacy["result_json"], {})
                    input_snapshot = output.get("input_summary") or {
                        "name": legacy["name"] or "",
                        "core_wishes": [legacy["core_wish"]] if legacy["core_wish"] else [],
                    }
            projection = json_value(output.get("report_projection"), {})
            context = json_value(output.get("report_context"), {})
            if not projection and (
                output.get("final_energy_profile")
                or output.get("interpretation")
                or output.get("useful_elements")
            ):
                projection = build_report_projection(output)
            if not context and input_snapshot:
                context = report_context(input_snapshot)
            item["report_summary"] = {
                "core_conclusion": projection.get("core_conclusion") or {},
                "elements": projection.get("elements") or [],
                "ranking": projection.get("ranking") or {},
                "balance": projection.get("balance") or {},
                "style_guidance": projection.get("style_guidance") or {},
                "adjustment_strategy": projection.get("adjustment_strategy") or [],
                "keywords": projection.get("keywords") or [],
                "core_wishes": context.get("core_wishes") or [],
                "useful_elements": output.get("useful_elements") or [],
                "strongest_element": output.get("strongest_element") or output.get("strongest") or "",
                "weakest_element": output.get("weakest_element") or output.get("weakest") or "",
                "interpretation": output.get("interpretation") or {},
                "mbti_analysis": output.get("mbti_analysis") or {},
                "chakra_analysis": output.get("chakra_analysis") or {},
                "mood_analysis": output.get("mood_analysis") or {},
                "zodiac_analysis": output.get("zodiac_analysis") or {},
            }
            proposals = connection.execute(
                "SELECT proposal_id, proposal_version, title, description, image_urls_json, "
                "workbench_json, order_id, confirmed_at, status, created_at "
                "FROM custom_design_proposals WHERE request_id = ? ORDER BY proposal_version DESC",
                (item["request_id"],),
            ).fetchall()
            item["proposals"] = []
            for proposal in proposals:
                record = dict(proposal)
                record["image_urls"] = json_value(record.pop("image_urls_json", "[]"), [])
                record["workbench"] = json_value(record.pop("workbench_json", "{}"), {})
                item["proposals"].append(record)
            if include_draft:
                draft = connection.execute(
                    "SELECT draft_id, draft_version, workbench_json, created_by, created_at, "
                    "updated_at FROM custom_design_drafts WHERE request_id = ?",
                    (item["request_id"],),
                ).fetchone()
                if draft:
                    draft_record = dict(draft)
                    draft_record["workbench"] = json_value(
                        draft_record.pop("workbench_json", "{}"),
                        {},
                    )
                    item["draft"] = draft_record
                else:
                    item["draft"] = None
            item["events"] = [dict(event) for event in connection.execute(
                "SELECT event_type, from_status, to_status, actor_type, note, created_at FROM custom_design_events WHERE request_id = ? ORDER BY created_at ASC",
                (item["request_id"],),
            ).fetchall()]
            result.append(item)
        return result

    def create(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        timestamp = now_iso()
        with self.connect() as connection:
            settings = self._settings(connection)
            existing = connection.execute(
                "SELECT request_id FROM custom_design_requests WHERE user_id = ? AND report_id = ? AND report_version = ? AND status NOT IN ('confirmed', 'closed') ORDER BY updated_at DESC LIMIT 1",
                (user_id, payload["report_id"], payload["report_version"]),
            ).fetchone()
            if existing:
                raise ValueError("这份报告已有进行中的人工搭配申请")
            now_local = datetime.now(BEIJING_TZ)
            day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
            day_end = day_start + timedelta(days=1)
            start_text = day_start.isoformat(timespec="seconds").replace("+00:00", "Z")
            end_text = day_end.isoformat(timespec="seconds").replace("+00:00", "Z")
            count = connection.execute("SELECT COUNT(*) AS c FROM custom_design_requests WHERE created_at >= ? AND created_at < ?", (start_text, end_text)).fetchone()["c"]
            if count >= settings["daily_capacity"]:
                raise ValueError("今日人工搭配名额已满，请明日再来")
            request_id = self._request_id()
            due = (datetime.now(timezone.utc) + timedelta(hours=settings["sla_hours"])).isoformat(timespec="seconds").replace("+00:00", "Z")
            request = {key: payload.get(key) for key in ("assessment_id", "wrist_size_cm", "bead_size_mm", "budget", "style_preference", "color_preference", "accessory_preference", "wear_scene", "note")}
            connection.execute(
                "INSERT INTO custom_design_requests (request_id, user_id, report_id, report_version, request_json, status, first_draft_due_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'submitted', ?, ?, ?)",
                (request_id, user_id, payload["report_id"], payload["report_version"], json.dumps(request, ensure_ascii=False), due, timestamp, timestamp),
            )
            self._event(connection, request_id, "submitted", "user", user_id, to_status="submitted")
        return self.get_for_user(request_id, user_id)

    def get_for_user(self, request_id: str, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            result = self._detail_query(connection, "WHERE r.request_id = ? AND r.user_id = ?", [request_id, user_id])
        if not result:
            raise ValueError("人工搭配申请不存在")
        return result[0]

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return self._detail_query(connection, "WHERE r.user_id = ?", [user_id])

    def list_for_admin(self, status: str = "", limit: int = 100) -> list[dict[str, Any]]:
        clauses, params = [], []
        if status:
            clauses.append("r.status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as connection:
            rows = self._detail_query(connection, where, params, include_draft=True)
        return rows[:max(1, min(limit, 300))]

    def save_draft(
        self,
        request_id: str,
        actor_id: str,
        workbench: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(workbench, dict) or not (workbench.get("layout") or []):
            raise ValueError("设计草稿至少需要一颗有效材料")
        with self.connect() as connection:
            request = connection.execute(
                "SELECT status FROM custom_design_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if not request:
                raise ValueError("人工搭配申请不存在")
            previous = str(request["status"])
            if previous in {"confirmed", "closed"}:
                raise ValueError("已结束的申请不能再编辑")
            existing = connection.execute(
                "SELECT draft_id, draft_version, created_at FROM custom_design_drafts "
                "WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            timestamp = now_iso()
            if existing:
                connection.execute(
                    "UPDATE custom_design_drafts SET draft_version = ?, workbench_json = ?, "
                    "created_by = ?, updated_at = ? WHERE request_id = ?",
                    (
                        int(existing["draft_version"]) + 1,
                        json.dumps(workbench, ensure_ascii=False),
                        actor_id,
                        timestamp,
                        request_id,
                    ),
                )
            else:
                connection.execute(
                    "INSERT INTO custom_design_drafts "
                    "(draft_id, request_id, draft_version, workbench_json, created_by, created_at, updated_at) "
                    "VALUES (?, ?, 1, ?, ?, ?, ?)",
                    (
                        secrets.token_hex(16),
                        request_id,
                        json.dumps(workbench, ensure_ascii=False),
                        actor_id,
                        timestamp,
                        timestamp,
                    ),
                )
            if previous in {"submitted", "revision_requested"}:
                connection.execute(
                    "UPDATE custom_design_requests SET status = 'designing', updated_at = ? "
                    "WHERE request_id = ?",
                    (timestamp, request_id),
                )
                self._event(
                    connection,
                    request_id,
                    "draft_saved",
                    "admin",
                    actor_id,
                    from_status=previous,
                    to_status="designing",
                    note="设计师已保存结构化草稿",
                )
            else:
                connection.execute(
                    "UPDATE custom_design_requests SET updated_at = ? WHERE request_id = ?",
                    (timestamp, request_id),
                )
        return self.get_for_admin(request_id)

    def publish_proposal(self, request_id: str, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        workbench = payload.get("workbench")
        if not isinstance(workbench, dict) or not (workbench.get("layout") or []):
            raise ValueError("发布方案前请先完成结构化珠子排布")
        with self.connect() as connection:
            request = connection.execute("SELECT * FROM custom_design_requests WHERE request_id = ?", (request_id,)).fetchone()
            if not request:
                raise ValueError("人工搭配申请不存在")
            previous = str(request["status"])
            if previous in {"confirmed", "closed"}:
                raise ValueError("已结束的申请不能再提交方案")
            version = connection.execute("SELECT COALESCE(MAX(proposal_version), 0) AS n FROM custom_design_proposals WHERE request_id = ?", (request_id,)).fetchone()["n"] + 1
            timestamp = now_iso()
            connection.execute("UPDATE custom_design_proposals SET status = 'superseded' WHERE request_id = ? AND status = 'active'", (request_id,))
            proposal_id = secrets.token_hex(16)
            connection.execute(
                "INSERT INTO custom_design_proposals "
                "(proposal_id, request_id, proposal_version, title, description, "
                "image_urls_json, workbench_json, status, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)",
                (
                    proposal_id,
                    request_id,
                    version,
                    payload["title"],
                    payload.get("description", ""),
                    json.dumps(payload.get("image_urls") or [], ensure_ascii=False),
                    json.dumps(payload["workbench"], ensure_ascii=False),
                    actor_id,
                    timestamp,
                ),
            )
            connection.execute(
                "DELETE FROM custom_design_drafts WHERE request_id = ?",
                (request_id,),
            )
            connection.execute("UPDATE custom_design_requests SET status = 'proposed', proposed_at = ?, updated_at = ? WHERE request_id = ?", (timestamp, timestamp, request_id))
            self._event(connection, request_id, "proposal_published", "admin", actor_id, from_status=previous, to_status="proposed", note=f"第 {version} 版方案已提交")
        return self.get_for_admin(request_id)

    def get_for_admin(self, request_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            result = self._detail_query(
                connection,
                "WHERE r.request_id = ?",
                [request_id],
                include_draft=True,
            )
        if not result:
            raise ValueError("人工搭配申请不存在")
        return result[0]

    def user_response(self, request_id: str, user_id: str, action: str, note: str = "") -> dict[str, Any]:
        if action not in {"confirm", "revision"}:
            raise ValueError("不支持的方案操作")
        if action == "confirm":
            return self.confirm_proposal(request_id, user_id, note)
        with self.connect() as connection:
            row = connection.execute("SELECT status FROM custom_design_requests WHERE request_id = ? AND user_id = ?", (request_id, user_id)).fetchone()
            if not row:
                raise ValueError("人工搭配申请不存在")
            previous = row["status"]
            if previous != "proposed":
                raise ValueError("当前没有待确认的方案")
            next_status = "revision_requested"
            timestamp = now_iso()
            connection.execute(
                "UPDATE custom_design_requests SET status = ?, confirmed_at = NULL, "
                "updated_at = ? WHERE request_id = ?",
                (next_status, timestamp, request_id),
            )
            self._event(
                connection,
                request_id,
                "revision_requested",
                "user",
                user_id,
                from_status=previous,
                to_status=next_status,
                note=note,
            )
        return self.get_for_user(request_id, user_id)

    def confirm_proposal(
        self,
        request_id: str,
        user_id: str,
        note: str = "",
    ) -> dict[str, Any]:
        with self.connect() as connection:
            request = connection.execute(
                "SELECT status FROM custom_design_requests "
                "WHERE request_id = ? AND user_id = ?",
                (request_id, user_id),
            ).fetchone()
            if not request:
                raise ValueError("人工搭配申请不存在")
            proposal = connection.execute(
                "SELECT proposal_id, title, description, workbench_json, order_id "
                "FROM custom_design_proposals "
                "WHERE request_id = ? AND status = 'active' "
                "ORDER BY proposal_version DESC LIMIT 1",
                (request_id,),
            ).fetchone()
            if not proposal:
                raise ValueError("当前没有待确认的方案")
            if str(request["status"]) == "confirmed" and proposal["order_id"]:
                detail = self.get_for_user(request_id, user_id)
                detail["order"] = self.order_service.get_order(str(proposal["order_id"]))
                detail["idempotent_replay"] = True
                return detail
            if str(request["status"]) != "proposed":
                raise ValueError("当前没有待确认的方案")
            proposal_record = dict(proposal)

        workbench = json_value(proposal_record.get("workbench_json"), {})
        layout = workbench.get("layout") or []
        if not layout:
            raise ValueError("方案缺少结构化材料，暂不能确认")
        proposal_id = str(proposal_record["proposal_id"])
        source_context = {
            "source": "custom_design",
            "source_label": "设计师搭配",
            "request_id": request_id,
            "proposal_id": proposal_id,
            "title": proposal_record.get("title") or "专属手串方案",
        }
        design = {
            "name": proposal_record.get("title") or "专属手串方案",
            "title": proposal_record.get("title") or "专属手串方案",
            "description": proposal_record.get("description") or "",
            "wristSize": workbench.get("wrist_size_cm") or 16,
            "beadSize": workbench.get("bead_size_mm") or 8,
            "selected": [str(item.get("id") or "") for item in layout],
            "placements": [
                {
                    **item,
                    "id": str(item.get("id") or ""),
                    "image_url": item.get("selected_image_url")
                    or item.get("image_url")
                    or "",
                }
                for item in layout
            ],
            "sourceContext": source_context,
            "summary": workbench.get("summary") or {},
        }
        order_result = self.order_service.create_pending_order(
            {
                "user_id": user_id,
                "receiver": {},
                "design": design,
                "sequence": layout,
                "remark": f"人工搭配服务单：{request_id}",
                "idempotency_key": f"custom-design:{proposal_id}",
            }
        )
        order = order_result["order"]
        timestamp = now_iso()
        with self.connect() as connection:
            current = connection.execute(
                "SELECT status FROM custom_design_requests "
                "WHERE request_id = ? AND user_id = ?",
                (request_id, user_id),
            ).fetchone()
            if not current:
                raise ValueError("人工搭配申请不存在")
            if str(current["status"]) not in {"proposed", "confirmed"}:
                raise ValueError("方案状态已变化，请刷新后重试")
            connection.execute(
                "UPDATE custom_design_proposals SET order_id = ?, confirmed_at = ? "
                "WHERE proposal_id = ?",
                (order["order_id"], timestamp, proposal_id),
            )
            if str(current["status"]) == "proposed":
                connection.execute(
                    "UPDATE custom_design_requests SET status = 'confirmed', "
                    "confirmed_at = ?, updated_at = ? WHERE request_id = ?",
                    (timestamp, timestamp, request_id),
                )
                self._event(
                    connection,
                    request_id,
                    "proposal_confirmed",
                    "user",
                    user_id,
                    from_status="proposed",
                    to_status="confirmed",
                    note=note,
                )
                self._event(
                    connection,
                    request_id,
                    "order_created",
                    "system",
                    "order-service",
                    from_status="confirmed",
                    to_status="confirmed",
                    note=f"已生成待支付订单 {order['order_id']}",
                )
        detail = self.get_for_user(request_id, user_id)
        detail["order"] = self.order_service.get_order(order["order_id"])
        detail["idempotent_replay"] = bool(order_result.get("idempotent_replay"))
        return detail
