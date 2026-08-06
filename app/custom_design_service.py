from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from .database import connect_database, runtime_schema_mutation_allowed, use_mysql
from .design_brief import build_design_brief
from .order_service import OrderService, WechatPayConfig, settlement_fee_for_config
from .reporting import build_report_projection, report_context
from .repository import DB_PATH


DESIGN_STATUSES = {"deposit_pending", "submitted", "designing", "proposed", "revision_requested", "completed", "confirmed", "closed"}
OPEN_STATUSES = {"deposit_pending", "submitted", "designing", "proposed", "revision_requested"}
DEFAULT_DAILY_CAPACITY = 12
DEFAULT_DEPOSIT_AMOUNT_FEE = 990
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
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS custom_design_deposits (
                    deposit_id VARCHAR(80) PRIMARY KEY, request_id VARCHAR(80) NOT NULL,
                    user_id VARCHAR(100) NOT NULL, out_trade_no VARCHAR(64) NOT NULL,
                    out_refund_no VARCHAR(64), amount_fee INT NOT NULL,
                    currency VARCHAR(8) NOT NULL DEFAULT 'CNY', status VARCHAR(40) NOT NULL,
                    payment_transaction_id VARCHAR(80), payment_json LONGTEXT NOT NULL,
                    refund_json LONGTEXT NOT NULL, created_at VARCHAR(40) NOT NULL,
                    updated_at VARCHAR(40) NOT NULL, paid_at VARCHAR(40),
                    refund_requested_at VARCHAR(40), refunded_at VARCHAR(40),
                    UNIQUE KEY uq_custom_design_deposits_request (request_id),
                    UNIQUE KEY uq_custom_design_deposits_trade (out_trade_no),
                    UNIQUE KEY uq_custom_design_deposits_refund (out_refund_no),
                    INDEX idx_custom_design_deposits_user_created (user_id, created_at),
                    INDEX idx_custom_design_deposits_status_updated (status, updated_at)
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
            connection.execute(
                """CREATE TABLE IF NOT EXISTS custom_design_deposits (
                deposit_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, user_id TEXT NOT NULL,
                out_trade_no TEXT NOT NULL UNIQUE, out_refund_no TEXT UNIQUE, amount_fee INTEGER NOT NULL,
                currency TEXT NOT NULL DEFAULT 'CNY', status TEXT NOT NULL,
                payment_transaction_id TEXT, payment_json TEXT NOT NULL, refund_json TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, paid_at TEXT,
                refund_requested_at TEXT, refunded_at TEXT
                )"""
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_custom_design_deposits_user_created ON custom_design_deposits(user_id, created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_custom_design_deposits_status_updated ON custom_design_deposits(status, updated_at DESC)")

    def _settings(self, connection) -> dict[str, Any]:
        row = connection.execute("SELECT setting_json FROM system_settings WHERE setting_key = ?", (SETTING_KEY,)).fetchone()
        saved = json_value(row["setting_json"], {}) if row else {}
        return {
            "daily_capacity": max(0, min(int(saved.get("daily_capacity", DEFAULT_DAILY_CAPACITY)), 200)),
            "sla_hours": max(1, min(int(saved.get("sla_hours", 24)), 168)),
            "deposit_amount_fee": max(100, min(int(saved.get("deposit_amount_fee", DEFAULT_DEPOSIT_AMOUNT_FEE)), 100000)),
        }

    def get_settings(self) -> dict[str, int]:
        with self.connect() as connection:
            return self._settings(connection)

    def save_settings(self, payload: dict[str, Any]) -> dict[str, int]:
        capacity = max(0, min(int(payload.get("daily_capacity", DEFAULT_DAILY_CAPACITY)), 200))
        sla_hours = max(1, min(int(payload.get("sla_hours", 24)), 168))
        deposit_amount_fee = max(100, min(int(payload.get("deposit_amount_fee", DEFAULT_DEPOSIT_AMOUNT_FEE)), 100000))
        timestamp = now_iso()
        sql = (
            "INSERT INTO system_settings (setting_key, setting_json, updated_at) VALUES (?, ?, ?) "
            "ON DUPLICATE KEY UPDATE setting_json=VALUES(setting_json), updated_at=VALUES(updated_at)"
            if use_mysql() and not self._force_sqlite
            else "INSERT INTO system_settings (setting_key, setting_json, updated_at) VALUES (?, ?, ?) ON CONFLICT(setting_key) DO UPDATE SET setting_json=excluded.setting_json, updated_at=excluded.updated_at"
        )
        saved = {"daily_capacity": capacity, "sla_hours": sla_hours, "deposit_amount_fee": deposit_amount_fee}
        with self.connect() as connection:
            connection.execute(sql, (SETTING_KEY, json.dumps(saved, ensure_ascii=False), timestamp))
        return saved

    @staticmethod
    def _request_id() -> str:
        return f"CD{int(datetime.now().timestamp() * 1000)}{secrets.token_hex(3).upper()}"

    @staticmethod
    def _deposit_id() -> str:
        return f"CDD{int(datetime.now().timestamp() * 1000)}{secrets.token_hex(3).upper()}"

    @staticmethod
    def _deposit_trade_no() -> str:
        return f"CDP{int(datetime.now().timestamp() * 1000)}{secrets.token_hex(3).upper()}"[:64]

    @staticmethod
    def _deposit_refund_no(deposit_id: str) -> str:
        return f"CDR{deposit_id}"[:64]

    @staticmethod
    def _amount_text(amount_fee: Any) -> str:
        return f"{int(amount_fee or 0) / 100:.2f}"

    def _public_deposit(self, row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not row:
            return None
        item = dict(row)
        payment = json_value(item.pop("payment_json", "{}"), {})
        refund = json_value(item.pop("refund_json", "{}"), {})
        item.pop("payment_transaction_id", None)
        item.pop("out_trade_no", None)
        item.pop("out_refund_no", None)
        item["amount_text"] = self._amount_text(item.get("amount_fee"))
        item["payment"] = {
            key: payment.get(key)
            for key in ("provider", "state", "paid_at")
            if payment.get(key) not in (None, "")
        }
        item["refund"] = {
            key: refund.get(key)
            for key in ("status", "reason", "requested_at", "success_time", "failed_reason")
            if refund.get(key) not in (None, "")
        }
        return item

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

    def _admin_report_context(self, connection, item: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
        """Build the design-facing report projection without loading any workbench data."""
        report = connection.execute(
            "SELECT report_code, input_snapshot_json, output_snapshot_json "
            "FROM report_snapshots WHERE report_id = ? AND report_version = ?",
            (item["report_id"], item["report_version"]),
        ).fetchone()
        report_code = str(report["report_code"]) if report and report["report_code"] else item["report_id"]
        output = json_value(report["output_snapshot_json"], {}) if report else {}
        input_snapshot = json_value(report["input_snapshot_json"], {}) if report else {}

        # Old service requests can point at an assessment instead of a versioned report.
        raw_report_id = str(item.get("report_id") or "").strip()
        decoded_report_id = unquote(raw_report_id)
        request_data = item.get("request") or {}
        legacy_assessment_id = str(request_data.get("assessment_id") or "").strip()
        if not legacy_assessment_id and decoded_report_id.startswith("assessment:"):
            legacy_assessment_id = decoded_report_id.split(":", 1)[1].strip()
        if not report and legacy_assessment_id:
            report = connection.execute(
                "SELECT report_code, input_snapshot_json, output_snapshot_json "
                "FROM report_snapshots WHERE assessment_id = ? AND report_version = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (legacy_assessment_id, item["report_version"]),
            ).fetchone()
            if report:
                report_code = str(report["report_code"]) if report["report_code"] else item["report_id"]
                output = json_value(report["output_snapshot_json"], {})
                input_snapshot = json_value(report["input_snapshot_json"], {})
        if not report and legacy_assessment_id:
            legacy = connection.execute(
                "SELECT name, core_wish, result_json FROM energy_assessments WHERE assessment_id = ?",
                (legacy_assessment_id,),
            ).fetchone()
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
        summary = {
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
        brief = build_design_brief(
            summary,
            item.get("request") or {},
            report_id=str(item.get("report_id") or ""),
            report_code=report_code,
            report_version=int(item.get("report_version") or 1),
        )
        return report_code, summary, brief

    @staticmethod
    def _proposal_overview(row: dict[str, Any], *, include_content: bool = False) -> dict[str, Any]:
        result = {
            "proposal_id": str(row.get("proposal_id") or ""),
            "proposal_version": int(row.get("proposal_version") or 0),
            "title": str(row.get("title") or ""),
            "status": str(row.get("status") or ""),
            "order_id": str(row.get("order_id") or ""),
            "confirmed_at": row.get("confirmed_at"),
            "created_at": row.get("created_at"),
        }
        if include_content:
            result["description"] = str(row.get("description") or "")
            result["image_urls"] = json_value(row.get("image_urls_json"), [])
        return result

    def _admin_detail_base(self, connection, request_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT * FROM custom_design_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if not row:
            raise ValueError("人工搭配申请不存在")
        return self._public({**dict(row), "proposals_json": "[]", "events_json": "[]"})

    def get_admin_overview(self, request_id: str) -> dict[str, Any]:
        """First-screen DTO for the V2 work order; intentionally excludes large regions."""
        with self.connect() as connection:
            item = self._admin_detail_base(connection, request_id)
            report_code, _summary, brief = self._admin_report_context(connection, item)
            latest = connection.execute(
                "SELECT proposal_id, proposal_version, title, status, order_id, confirmed_at, created_at "
                "FROM custom_design_proposals WHERE request_id = ? "
                "ORDER BY proposal_version DESC LIMIT 1",
                (request_id,),
            ).fetchone()
            proposal_count = int(connection.execute(
                "SELECT COUNT(*) AS c FROM custom_design_proposals WHERE request_id = ?", (request_id,)
            ).fetchone()["c"] or 0)
            draft = connection.execute(
                "SELECT draft_id, draft_version, created_by, created_at, updated_at "
                "FROM custom_design_drafts WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            deposit = connection.execute(
                "SELECT * FROM custom_design_deposits WHERE request_id = ?", (request_id,)
            ).fetchone()
        safe_request = self._admin_list_request(item.get("request") or {})
        return {
            "request_id": item["request_id"],
            "report_id": item["report_id"],
            "report_code": report_code,
            "report_version": item["report_version"],
            "request": safe_request,
            "status": item["status"],
            "first_draft_due_at": item.get("first_draft_due_at"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "deposit": self._public_deposit(dict(deposit)) if deposit else None,
            "design_brief": brief,
            "proposal_count": proposal_count,
            "latest_proposal": self._proposal_overview(dict(latest)) if latest else None,
            "draft": dict(draft) if draft else None,
        }

    def get_admin_workbench(self, request_id: str) -> dict[str, Any]:
        """Return one editable design source without hydrating historical detail regions.

        The saved source keeps the validated material snapshots required to restore a
        draft or the latest proposal.  The material library itself is intentionally
        fetched through the paginated admin material endpoint by the client.
        """
        overview = self.get_admin_overview(request_id)
        with self.connect() as connection:
            draft = connection.execute(
                "SELECT draft_id, draft_version, workbench_json, created_by, created_at, updated_at "
                "FROM custom_design_drafts WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            proposal = None
            if not draft:
                proposal = connection.execute(
                    "SELECT proposal_id, proposal_version, title, description, image_urls_json, "
                    "workbench_json, status, created_at FROM custom_design_proposals "
                    "WHERE request_id = ? ORDER BY proposal_version DESC LIMIT 1",
                    (request_id,),
                ).fetchone()

        source_kind = "empty"
        workbench: dict[str, Any] = {}
        proposal_meta: dict[str, Any] | None = None
        if draft:
            source_kind = "draft"
            workbench = json_value(draft["workbench_json"], {})
        elif proposal:
            source_kind = "proposal"
            workbench = json_value(proposal["workbench_json"], {})
            proposal_meta = {
                "proposal_id": str(proposal["proposal_id"] or ""),
                "proposal_version": int(proposal["proposal_version"] or 0),
                "title": str(proposal["title"] or ""),
                "description": str(proposal["description"] or ""),
                "image_urls": json_value(proposal["image_urls_json"], []),
                "status": str(proposal["status"] or ""),
                "created_at": proposal["created_at"],
            }
        return {
            "overview": overview,
            "source_kind": source_kind,
            "workbench": workbench if isinstance(workbench, dict) else {},
            "proposal": proposal_meta,
        }

    def get_admin_assessment_evidence(self, request_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            item = self._admin_detail_base(connection, request_id)
            report_code, summary, _brief = self._admin_report_context(connection, item)
        return {
            "request_id": item["request_id"],
            "report_id": item["report_id"],
            "report_code": report_code,
            "report_version": item["report_version"],
            "report_summary": summary,
        }

    def list_admin_proposals(self, request_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            self._admin_detail_base(connection, request_id)
            rows = connection.execute(
                "SELECT proposal_id, proposal_version, title, description, image_urls_json, status, "
                "order_id, confirmed_at, created_at FROM custom_design_proposals "
                "WHERE request_id = ? ORDER BY proposal_version DESC",
                (request_id,),
            ).fetchall()
        return [self._proposal_overview(dict(row), include_content=True) for row in rows]

    def get_admin_proposal_composition(self, request_id: str, proposal_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT proposal_id, proposal_version, workbench_json FROM custom_design_proposals "
                "WHERE request_id = ? AND proposal_id = ?",
                (request_id, proposal_id),
            ).fetchone()
        if not row:
            raise ValueError("搭配方案不存在")
        workbench = json_value(row["workbench_json"], {})
        layout = workbench.get("layout") if isinstance(workbench, dict) else []
        return {
            "proposal_id": str(row["proposal_id"]),
            "proposal_version": int(row["proposal_version"] or 0),
            "wrist_size_cm": workbench.get("wrist_size_cm") if isinstance(workbench, dict) else None,
            "bead_size_mm": workbench.get("bead_size_mm") if isinstance(workbench, dict) else None,
            "layout": layout if isinstance(layout, list) else [],
        }

    def list_admin_events(self, request_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            self._admin_detail_base(connection, request_id)
            rows = connection.execute(
                "SELECT event_type, from_status, to_status, actor_type, note, created_at "
                "FROM custom_design_events WHERE request_id = ? ORDER BY created_at ASC",
                (request_id,),
            ).fetchall()
        return [dict(row) for row in rows]

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
            # ``assessment:<assessment_id>``（有些客户端会把冒号编码为
            # ``%3A``），报告正文仍在 energy_assessments.result_json。优先按
            # assessment_id 查版本化快照，最后再回退到旧测算表，避免后台详情
            # 所有测算字段显示“未提供”。
            raw_report_id = str(item.get("report_id") or "").strip()
            decoded_report_id = unquote(raw_report_id)
            request_data = item.get("request") or {}
            legacy_assessment_id = str(request_data.get("assessment_id") or "").strip()
            if not legacy_assessment_id and decoded_report_id.startswith("assessment:"):
                legacy_assessment_id = decoded_report_id.split(":", 1)[1].strip()
            if not report and legacy_assessment_id:
                report = connection.execute(
                    "SELECT report_code, input_snapshot_json, output_snapshot_json "
                    "FROM report_snapshots WHERE assessment_id = ? AND report_version = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (legacy_assessment_id, item["report_version"]),
                ).fetchone()
                if report:
                    item["report_code"] = str(report["report_code"]) if report["report_code"] else item["report_id"]
                    output = json_value(report["output_snapshot_json"], {})
                    input_snapshot = json_value(report["input_snapshot_json"], {})
            if not report and legacy_assessment_id:
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
            item["design_brief"] = build_design_brief(
                item["report_summary"],
                item.get("request") or {},
                report_id=str(item.get("report_id") or ""),
                report_code=str(item.get("report_code") or ""),
                report_version=int(item.get("report_version") or 1),
            )
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
            deposit = connection.execute(
                "SELECT * FROM custom_design_deposits WHERE request_id = ?",
                (item["request_id"],),
            ).fetchone()
            item["deposit"] = self._public_deposit(dict(deposit)) if deposit else None
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
            request = {key: payload.get(key) for key in (
                "assessment_id", "wrist_size_cm", "bead_size_mm", "budget", "style_preference",
                "color_preference", "accessory_preference", "wear_scene", "preference_confirmed", "note",
            )}
            connection.execute(
                "INSERT INTO custom_design_requests (request_id, user_id, report_id, report_version, request_json, status, first_draft_due_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'deposit_pending', NULL, ?, ?)",
                (request_id, user_id, payload["report_id"], payload["report_version"], json.dumps(request, ensure_ascii=False), timestamp, timestamp),
            )
            deposit_id = self._deposit_id()
            connection.execute(
                "INSERT INTO custom_design_deposits (deposit_id, request_id, user_id, out_trade_no, amount_fee, currency, status, payment_json, refund_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'CNY', 'unpaid', '{}', '{}', ?, ?)",
                (deposit_id, request_id, user_id, self._deposit_trade_no(), settings["deposit_amount_fee"], timestamp, timestamp),
            )
            self._event(connection, request_id, "deposit_created", "user", user_id, to_status="deposit_pending", note="等待支付可退设计保证金")
        return self.get_for_user(request_id, user_id)

    def _set_deposit_paid(
        self,
        connection,
        deposit: dict[str, Any],
        *,
        provider: str,
        transaction_id: str,
        paid_at: str,
        appid: str = "",
        mchid: str = "",
    ) -> None:
        existing = str(deposit.get("payment_transaction_id") or "")
        if existing and existing != transaction_id:
            raise ValueError("保证金支付流水不一致")
        if str(deposit["status"]) in {"paid", "refund_submitting", "refunding", "refunded"}:
            return
        if str(deposit["status"]) not in {"unpaid", "prepay_ready", "processing"}:
            raise ValueError("当前保证金状态不能确认支付")
        request = connection.execute(
            "SELECT status FROM custom_design_requests WHERE request_id = ?",
            (deposit["request_id"],),
        ).fetchone()
        if not request:
            raise ValueError("人工搭配申请不存在")
        timestamp = now_iso()
        settings = self._settings(connection)
        due = (datetime.now(timezone.utc) + timedelta(hours=settings["sla_hours"])).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")
        payment = {
            "provider": provider,
            "state": "SUCCESS",
            "transaction_id": transaction_id,
            "paid_at": paid_at,
            "appid": appid,
            "mchid": mchid,
        }
        connection.execute(
            "UPDATE custom_design_deposits SET status = 'paid', payment_transaction_id = ?, payment_json = ?, paid_at = ?, updated_at = ? WHERE deposit_id = ?",
            (transaction_id, json.dumps(payment, ensure_ascii=False), paid_at, timestamp, deposit["deposit_id"]),
        )
        if str(request["status"]) == "deposit_pending":
            connection.execute(
                "UPDATE custom_design_requests SET status = 'submitted', first_draft_due_at = ?, updated_at = ? WHERE request_id = ?",
                (due, timestamp, deposit["request_id"]),
            )
            self._event(
                connection,
                str(deposit["request_id"]),
                "deposit_paid",
                "system",
                provider,
                from_status="deposit_pending",
                to_status="submitted",
                note="设计保证金已支付，工单已进入设计队列",
            )

    def request_deposit_payment(self, request_id: str, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT d.*, r.status AS request_status FROM custom_design_deposits d JOIN custom_design_requests r ON r.request_id = d.request_id WHERE d.request_id = ? AND d.user_id = ?",
                (request_id, user_id),
            ).fetchone()
            if not row:
                raise ValueError("人工搭配申请不存在")
            deposit = dict(row)
            if deposit["status"] in {"paid", "refund_submitting", "refunding", "refunded"}:
                return {"deposit": self._public_deposit(deposit), "payment": {"available": False, "state": "already_paid", "message": "设计保证金已支付"}}
            if deposit["request_status"] != "deposit_pending":
                raise ValueError("当前申请不需要支付设计保证金")

        config = WechatPayConfig()
        if not config.ready:
            raise ValueError(f"微信支付未配置：缺少 {', '.join(config.missing)}")
        user = self.order_service.get_user(user_id) or {}
        openid = str(user.get("openid") or "")
        if not openid or openid.startswith("dev_"):
            raise ValueError("当前用户没有真实微信 openid，无法调起微信支付")
        body = {
            "appid": config.app_id,
            "mchid": config.mch_id,
            "description": "宇涧人工搭配可退设计保证金",
            "out_trade_no": deposit["out_trade_no"],
            "notify_url": config.notify_url,
            "amount": {"total": settlement_fee_for_config(config, deposit["amount_fee"]), "currency": deposit["currency"]},
            "payer": {"openid": openid},
        }
        response = self.order_service.wechat_request(
            "POST", "/v3/pay/transactions/jsapi", body, config, error_label="设计保证金预下单失败"
        )
        prepay_id = str(response.get("prepay_id") or "")
        if not prepay_id:
            raise ValueError("微信支付预下单未返回预支付单号")
        timestamp = now_iso()
        with self.connect() as connection:
            connection.execute(
                "UPDATE custom_design_deposits SET status = 'prepay_ready', payment_json = ?, updated_at = ? WHERE deposit_id = ? AND status IN ('unpaid', 'prepay_ready', 'processing')",
                (json.dumps({"provider": "wechat_pay", "state": "prepay_ready", "prepay_id": prepay_id}, ensure_ascii=False), timestamp, deposit["deposit_id"]),
            )
        return {
            "deposit": self.get_for_user(request_id, user_id)["deposit"],
            "payment": {
                "available": True,
                "state": "prepay_ready",
                "message": "微信支付预下单成功",
                "pay_params": self.order_service.build_miniprogram_pay_params(prepay_id, config),
            },
        }

    def mark_deposit_paid_for_dev(self, request_id: str, user_id: str) -> dict[str, Any]:
        config = WechatPayConfig()
        if not config.test_mode:
            raise ValueError("正式环境已禁用模拟支付")
        with self.connect() as connection:
            deposit_row = connection.execute(
                "SELECT * FROM custom_design_deposits WHERE request_id = ? AND user_id = ?",
                (request_id, user_id),
            ).fetchone()
            if not deposit_row:
                raise ValueError("人工搭配申请不存在")
            deposit = dict(deposit_row)
            self._set_deposit_paid(
                connection,
                deposit,
                provider="dev_mock",
                transaction_id=f"dev_{deposit['out_trade_no']}",
                paid_at=now_iso(),
            )
        return self.get_for_user(request_id, user_id)

    def is_deposit_trade(self, out_trade_no: str) -> bool:
        with self.connect() as connection:
            return bool(connection.execute(
                "SELECT 1 FROM custom_design_deposits WHERE out_trade_no = ?", (out_trade_no,)
            ).fetchone())

    def handle_wechat_payment_transaction(self, transaction: dict[str, Any], config: WechatPayConfig) -> dict[str, Any]:
        out_trade_no = str(transaction.get("out_trade_no") or "").strip()
        trade_state = str(transaction.get("trade_state") or "").upper()
        amount = transaction.get("amount") or {}
        transaction_id = str(transaction.get("transaction_id") or "").strip()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM custom_design_deposits WHERE out_trade_no = ?", (out_trade_no,)).fetchone()
            if not row:
                raise ValueError("保证金支付单不存在")
            deposit = dict(row)
            if str(transaction.get("appid") or "") != str(config.app_id or "") or str(transaction.get("mchid") or "") != str(config.mch_id or ""):
                raise ValueError("保证金支付回调商户信息不匹配")
            if int(amount.get("total") or 0) != settlement_fee_for_config(config, deposit["amount_fee"]) or str(amount.get("currency") or "").upper() != str(deposit["currency"]).upper():
                raise ValueError("保证金支付回调金额不匹配")
            if trade_state == "SUCCESS":
                if not transaction_id:
                    raise ValueError("保证金支付回调缺少交易号")
                transaction_owner = connection.execute(
                    "SELECT deposit_id FROM custom_design_deposits WHERE payment_transaction_id = ? AND deposit_id <> ?",
                    (transaction_id, deposit["deposit_id"]),
                ).fetchone()
                if transaction_owner:
                    raise ValueError("微信支付交易号已属于其他保证金")
                self._set_deposit_paid(
                    connection,
                    deposit,
                    provider="wechat_pay",
                    transaction_id=transaction_id,
                    paid_at=str(transaction.get("success_time") or now_iso()),
                    appid=str(config.app_id or ""),
                    mchid=str(config.mch_id or ""),
                )
                state = "succeeded"
            elif trade_state == "USERPAYING":
                connection.execute("UPDATE custom_design_deposits SET status = 'processing', updated_at = ? WHERE deposit_id = ? AND status IN ('unpaid', 'prepay_ready', 'processing')", (now_iso(), deposit["deposit_id"]))
                state = "processing"
            elif trade_state == "NOTPAY":
                state = "ignored"
            else:
                connection.execute("UPDATE custom_design_deposits SET status = 'unpaid', payment_json = ?, updated_at = ? WHERE deposit_id = ?", (json.dumps({"provider": "wechat_pay", "state": trade_state}, ensure_ascii=False), now_iso(), deposit["deposit_id"]))
                state = "failed"
        return {"processing_status": state, "merchant_order_no": out_trade_no, "transaction_id": transaction_id}

    def get_for_user(self, request_id: str, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            result = self._detail_query(connection, "WHERE r.request_id = ? AND r.user_id = ?", [request_id, user_id])
        if not result:
            raise ValueError("人工搭配申请不存在")
        return result[0]

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return self._detail_query(connection, "WHERE r.user_id = ?", [user_id])

    @staticmethod
    def _admin_list_request(value: Any) -> dict[str, Any]:
        """Return only the request fields needed by the admin queue."""
        source = json_value(value, {})
        if not isinstance(source, dict):
            return {}
        fields = (
            "wrist_size_cm",
            "bead_size_mm",
            "budget",
            "style_preference",
            "color_preference",
            "accessory_preference",
            "wear_scene",
            "preference_confirmed",
            "note",
        )
        return {field: source[field] for field in fields if field in source}

    def _admin_list_deposit(self, row: dict[str, Any]) -> dict[str, Any] | None:
        status = str(row.pop("deposit_status", "") or "").strip()
        if not status:
            return None
        amount_fee = int(row.pop("deposit_amount_fee", 0) or 0)
        return {
            "amount_fee": amount_fee,
            "currency": str(row.pop("deposit_currency", "") or "CNY"),
            "status": status,
            "amount_text": self._amount_text(amount_fee),
        }

    @staticmethod
    def _admin_list_proposal(row: dict[str, Any]) -> dict[str, Any]:
        """Proposal queue DTO: deliberately excludes description, images and workbench."""
        return {
            "proposal_id": str(row.get("proposal_id") or ""),
            "proposal_version": int(row.get("proposal_version") or 0),
            "title": str(row.get("title") or ""),
            "status": str(row.get("status") or ""),
            "order_id": str(row.get("order_id") or ""),
            "confirmed_at": row.get("confirmed_at"),
            "created_at": row.get("created_at"),
        }

    def list_for_admin(
        self,
        status: str = "",
        limit: int = 100,
        offset: int = 0,
        *,
        include_meta: bool = False,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Read the admin queue without hydrating per-request design details.

        The old implementation reused ``_detail_query`` which read full report
        snapshots, design briefs, drafts, events and every proposal workbench for
        each row.  The queue only needs its row-level summary, so it limits the
        request relation first and then fetches proposal summaries in one batch.
        ``include_meta`` is opt-in to keep existing admin clients receiving the
        historical array response.
        """
        safe_limit = max(1, min(int(limit), 300))
        safe_offset = max(0, min(int(offset), 100000))
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limited_requests = (
            "SELECT request_id, report_id, report_version, request_json, status, "
            "first_draft_due_at, created_at, updated_at "
            "FROM custom_design_requests "
            f"{where} "
            "ORDER BY updated_at DESC, request_id DESC LIMIT ? OFFSET ?"
        )
        queue_sql = (
            "SELECT r.request_id, r.report_id, r.report_version, r.request_json, "
            "r.status, r.first_draft_due_at, r.created_at, r.updated_at, "
            "s.report_code AS snapshot_report_code, "
            "d.amount_fee AS deposit_amount_fee, d.currency AS deposit_currency, "
            "d.status AS deposit_status "
            f"FROM ({limited_requests}) r "
            "LEFT JOIN report_snapshots s "
            "ON s.report_id = r.report_id AND s.report_version = r.report_version "
            "LEFT JOIN custom_design_deposits d ON d.request_id = r.request_id "
            "ORDER BY r.updated_at DESC, r.request_id DESC"
        )
        with self.connect() as connection:
            rows = connection.execute(
                queue_sql,
                [*params, safe_limit, safe_offset],
            ).fetchall()
            total = 0
            if include_meta:
                total = int(
                    connection.execute(
                        f"SELECT COUNT(*) AS c FROM custom_design_requests {where}",
                        params,
                    ).fetchone()["c"]
                    or 0
                )

            items: list[dict[str, Any]] = []
            legacy_pairs: dict[str, tuple[str, int]] = {}
            for row in rows:
                record = dict(row)
                raw_request = json_value(record.pop("request_json", "{}"), {})
                request = self._admin_list_request(raw_request)
                report_id = str(record.get("report_id") or "")
                report_version = int(record.get("report_version") or 1)
                item = {
                    "request_id": str(record.get("request_id") or ""),
                    "report_id": report_id,
                    "report_code": str(record.pop("snapshot_report_code", "") or report_id),
                    "report_version": report_version,
                    "request": request,
                    "status": str(record.get("status") or ""),
                    "deposit": self._admin_list_deposit(record),
                    "first_draft_due_at": record.get("first_draft_due_at"),
                    "proposal_count": 0,
                    "latest_proposal": None,
                    "proposals": [],
                    "created_at": record.get("created_at"),
                    "updated_at": record.get("updated_at"),
                }
                if item["report_code"] == report_id:
                    assessment_id = str(
                        raw_request.get("assessment_id") if isinstance(raw_request, dict) else ""
                    ).strip()
                    decoded_report_id = unquote(report_id)
                    if not assessment_id and decoded_report_id.startswith("assessment:"):
                        assessment_id = decoded_report_id.split(":", 1)[1].strip()
                    if assessment_id:
                        legacy_pairs[item["request_id"]] = (assessment_id, report_version)
                items.append(item)

            request_ids = [item["request_id"] for item in items]
            if request_ids:
                placeholders = ", ".join("?" for _ in request_ids)
                proposal_rows = connection.execute(
                    "SELECT request_id, proposal_id, proposal_version, title, status, order_id, "
                    "confirmed_at, created_at FROM custom_design_proposals "
                    f"WHERE request_id IN ({placeholders}) "
                    "ORDER BY request_id ASC, proposal_version DESC",
                    request_ids,
                ).fetchall()
                proposals_by_request: dict[str, list[dict[str, Any]]] = {
                    request_id: [] for request_id in request_ids
                }
                for proposal_row in proposal_rows:
                    proposal = self._admin_list_proposal(dict(proposal_row))
                    proposals_by_request.setdefault(
                        str(proposal_row["request_id"]), []
                    ).append(proposal)
                for item in items:
                    proposals = proposals_by_request.get(item["request_id"], [])
                    item["proposals"] = proposals
                    item["proposal_count"] = len(proposals)
                    item["latest_proposal"] = proposals[0] if proposals else None

            if legacy_pairs:
                assessment_ids = sorted({pair[0] for pair in legacy_pairs.values()})
                placeholders = ", ".join("?" for _ in assessment_ids)
                legacy_rows = connection.execute(
                    "SELECT assessment_id, report_version, report_code FROM report_snapshots "
                    f"WHERE assessment_id IN ({placeholders})",
                    assessment_ids,
                ).fetchall()
                legacy_codes = {
                    (str(row["assessment_id"]), int(row["report_version"] or 1)): str(
                        row["report_code"] or ""
                    )
                    for row in legacy_rows
                }
                for item in items:
                    pair = legacy_pairs.get(item["request_id"])
                    if pair and legacy_codes.get(pair):
                        item["report_code"] = legacy_codes[pair]

        if include_meta:
            return {
                "items": items,
                "total": total,
                "limit": safe_limit,
                "offset": safe_offset,
            }
        return items

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
            if previous in {"deposit_pending", "completed", "confirmed", "closed"}:
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
            if previous in {"deposit_pending", "completed", "confirmed", "closed"}:
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

    def _submit_deposit_refund(self, request_id: str, user_id: str) -> dict[str, Any]:
        already_submitted = False
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM custom_design_deposits WHERE request_id = ? AND user_id = ?",
                (request_id, user_id),
            ).fetchone()
            if not row:
                raise ValueError("设计保证金记录不存在")
            deposit = dict(row)
            if deposit["status"] == "refunded":
                already_submitted = True
            if deposit["status"] in {"refund_submitting", "refunding"}:
                already_submitted = True
            if not already_submitted and deposit["status"] not in {"paid", "refund_failed"}:
                raise ValueError("设计保证金尚未支付，不能发起退款")
            if already_submitted:
                # Let the transaction close before reading the full request through another connection.
                pass
            else:
                config = WechatPayConfig()
                if not config.test_mode and not config.ready:
                    raise ValueError(f"微信退款未配置：缺少 {', '.join(config.missing)}")
                refund_no = str(deposit.get("out_refund_no") or self._deposit_refund_no(str(deposit["deposit_id"])))
                timestamp = now_iso()
                connection.execute(
                    "UPDATE custom_design_deposits SET status = 'refund_submitting', out_refund_no = ?, refund_json = ?, refund_requested_at = ?, updated_at = ? WHERE deposit_id = ?",
                    (refund_no, json.dumps({"status": "refund_submitting", "reason": "用户确认设计完成", "requested_at": timestamp}, ensure_ascii=False), timestamp, timestamp, deposit["deposit_id"]),
                )

        if already_submitted:
            return self.get_for_user(request_id, user_id)

        if config.test_mode:
            result = {"status": "SUCCESS", "out_refund_no": refund_no, "success_time": now_iso(), "refund_id": f"dev_{refund_no}"}
        else:
            try:
                result = self.order_service.create_wechat_refund(
                    {
                        "out_trade_no": deposit["out_trade_no"],
                        "total_fee": int(deposit["amount_fee"]),
                        "currency": deposit["currency"],
                        "payment": json_value(deposit.get("payment_json"), {}),
                    },
                    refund_no,
                    int(deposit["amount_fee"]),
                    int(deposit["amount_fee"]),
                    "用户确认设计完成，退还设计保证金",
                    config,
                )
                if str(result.get("out_refund_no") or "") != refund_no:
                    raise ValueError("微信退款返回单号与本地退款单不一致")
            except Exception as exc:
                with self.connect() as connection:
                    connection.execute(
                        "UPDATE custom_design_deposits SET status = 'refund_failed', refund_json = ?, updated_at = ? WHERE deposit_id = ?",
                        (json.dumps({"status": "refund_failed", "failed_reason": str(exc)[:300]}, ensure_ascii=False), now_iso(), deposit["deposit_id"]),
                    )
                    self._event(connection, request_id, "deposit_refund_failed", "system", "wechat_pay", note="退款提交失败，等待重试")
                raise ValueError("设计已确认，保证金退款提交失败，请稍后重试") from exc
        self.apply_deposit_refund_result(result)
        return self.get_for_user(request_id, user_id)

    def apply_deposit_refund_result(self, refund_result: dict[str, Any]) -> dict[str, Any]:
        out_refund_no = str(refund_result.get("out_refund_no") or "").strip()
        status = str(refund_result.get("status") or refund_result.get("refund_status") or "").upper()
        if status not in {"SUCCESS", "PROCESSING", "ABNORMAL", "CLOSED"}:
            raise ValueError("微信退款结果状态非法")
        already_refunded = False
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM custom_design_deposits WHERE out_refund_no = ?", (out_refund_no,)).fetchone()
            if not row:
                raise ValueError("设计保证金退款单不存在")
            deposit = dict(row)
            if deposit["status"] == "refunded" and status == "SUCCESS":
                already_refunded = True
            if not already_refunded:
                result_status = {"SUCCESS": "refunded", "PROCESSING": "refunding", "ABNORMAL": "refund_failed", "CLOSED": "refund_failed"}[status]
                refund = {
                    "status": result_status,
                    "wechat_status": status,
                    "refund_id": str(refund_result.get("refund_id") or ""),
                    "success_time": str(refund_result.get("success_time") or ""),
                    "failed_reason": str(refund_result.get("user_received_account") or "") if result_status == "refund_failed" else "",
                }
                connection.execute(
                    "UPDATE custom_design_deposits SET status = ?, refund_json = ?, refunded_at = ?, updated_at = ? WHERE deposit_id = ?",
                    (result_status, json.dumps(refund, ensure_ascii=False), now_iso() if result_status == "refunded" else None, now_iso(), deposit["deposit_id"]),
                )
                self._event(
                    connection, str(deposit["request_id"]),
                    "deposit_refunded" if result_status == "refunded" else "deposit_refund_processing" if result_status == "refunding" else "deposit_refund_failed",
                    "system", "wechat_pay", note="设计保证金已原路退回" if result_status == "refunded" else "设计保证金退款处理中" if result_status == "refunding" else "设计保证金退款异常，等待重试",
                )
        return self.get_for_user(str(deposit["request_id"]), str(deposit["user_id"]))

    def handle_wechat_refund_result(self, refund_result: dict[str, Any], config: WechatPayConfig) -> dict[str, Any]:
        out_trade_no = str(refund_result.get("out_trade_no") or "")
        if not self.is_deposit_trade(out_trade_no):
            raise ValueError("设计保证金退款原支付单不存在")
        if str(refund_result.get("mchid") or "") != str(config.mch_id or ""):
            raise ValueError("设计保证金退款回调商户信息不匹配")
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM custom_design_deposits WHERE out_trade_no = ?", (out_trade_no,)).fetchone()
            if not row:
                raise ValueError("设计保证金退款原支付单不存在")
            deposit = dict(row)
            amount = refund_result.get("amount") or {}
            expected_fee = settlement_fee_for_config(config, deposit["amount_fee"])
            if int(amount.get("total") or 0) != expected_fee or int(amount.get("refund") or 0) != expected_fee:
                raise ValueError("设计保证金退款金额不匹配")
            if amount.get("currency") and str(amount["currency"]).upper() != str(deposit["currency"]).upper():
                raise ValueError("设计保证金退款币种不匹配")
            transaction_id = str(refund_result.get("transaction_id") or "")
            if transaction_id != str(deposit.get("payment_transaction_id") or ""):
                raise ValueError("设计保证金退款交易号不匹配")
        detail = self.apply_deposit_refund_result(refund_result)
        return {"processing_status": detail["deposit"]["status"], "merchant_order_no": out_trade_no, "transaction_id": transaction_id}

    def confirm_proposal(self, request_id: str, user_id: str, note: str = "") -> dict[str, Any]:
        already_completed = False
        with self.connect() as connection:
            request = connection.execute("SELECT status FROM custom_design_requests WHERE request_id = ? AND user_id = ?", (request_id, user_id)).fetchone()
            deposit = connection.execute("SELECT status FROM custom_design_deposits WHERE request_id = ? AND user_id = ?", (request_id, user_id)).fetchone()
            proposal = connection.execute("SELECT proposal_id, workbench_json FROM custom_design_proposals WHERE request_id = ? AND status = 'active' ORDER BY proposal_version DESC LIMIT 1", (request_id,)).fetchone()
            if not request or not deposit:
                raise ValueError("人工搭配申请不存在")
            if str(deposit["status"]) not in {"paid", "refund_failed", "refund_submitting", "refunding", "refunded"}:
                raise ValueError("请先支付设计保证金")
            if str(request["status"]) == "completed":
                already_completed = True
            if not already_completed and (str(request["status"]) != "proposed" or not proposal):
                raise ValueError("当前没有待确认的方案")
            if not already_completed and not (json_value(proposal["workbench_json"], {}).get("layout") or []):
                raise ValueError("方案缺少结构化材料，暂不能确认")
            if not already_completed:
                timestamp = now_iso()
                connection.execute("UPDATE custom_design_requests SET status = 'completed', confirmed_at = ?, updated_at = ? WHERE request_id = ?", (timestamp, timestamp, request_id))
                connection.execute("UPDATE custom_design_proposals SET confirmed_at = ? WHERE proposal_id = ?", (timestamp, proposal["proposal_id"]))
                self._event(connection, request_id, "proposal_confirmed", "user", user_id, from_status="proposed", to_status="completed", note=note or "用户确认设计方案完成")
        return self._submit_deposit_refund(request_id, user_id)

    def create_order_from_proposal(self, request_id: str, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            request = connection.execute("SELECT status FROM custom_design_requests WHERE request_id = ? AND user_id = ?", (request_id, user_id)).fetchone()
            proposal = connection.execute("SELECT proposal_id, title, description, workbench_json, order_id FROM custom_design_proposals WHERE request_id = ? AND status = 'active' ORDER BY proposal_version DESC LIMIT 1", (request_id,)).fetchone()
            if not request or not proposal:
                raise ValueError("人工搭配申请不存在")
            if str(request["status"]) not in {"completed", "confirmed"}:
                raise ValueError("请先确认设计方案完成")
            if proposal["order_id"]:
                detail = self.get_for_user(request_id, user_id)
                detail["order"] = self.order_service.get_order(str(proposal["order_id"]))
                detail["idempotent_replay"] = True
                return detail
            proposal_record = dict(proposal)
        workbench = json_value(proposal_record.get("workbench_json"), {})
        layout = workbench.get("layout") or []
        if not layout:
            raise ValueError("方案缺少结构化材料，暂不能下单")
        proposal_id = str(proposal_record["proposal_id"])
        design = {
            "name": proposal_record.get("title") or "专属手串方案", "title": proposal_record.get("title") or "专属手串方案",
            "description": proposal_record.get("description") or "", "wristSize": workbench.get("wrist_size_cm") or 16,
            "beadSize": workbench.get("bead_size_mm") or 8, "selected": [str(item.get("id") or "") for item in layout],
            "placements": [{**item, "id": str(item.get("id") or ""), "image_url": item.get("selected_image_url") or item.get("image_url") or ""} for item in layout],
            "sourceContext": {"source": "custom_design", "source_label": "设计师搭配", "request_id": request_id, "proposal_id": proposal_id, "title": proposal_record.get("title") or "专属手串方案"},
            "summary": workbench.get("summary") or {},
        }
        order_result = self.order_service.create_pending_order({"user_id": user_id, "receiver": {}, "design": design, "sequence": layout, "remark": f"人工搭配服务单：{request_id}", "idempotency_key": f"custom-design:{proposal_id}"})
        order = order_result["order"]
        with self.connect() as connection:
            connection.execute("UPDATE custom_design_proposals SET order_id = ? WHERE proposal_id = ?", (order["order_id"], proposal_id))
            self._event(connection, request_id, "order_created", "system", "order-service", from_status="completed", to_status="completed", note=f"已生成待支付订单 {order['order_id']}")
        detail = self.get_for_user(request_id, user_id)
        detail["order"] = self.order_service.get_order(order["order_id"])
        detail["idempotent_replay"] = bool(order_result.get("idempotent_replay"))
        return detail
