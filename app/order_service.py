from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import httpx

from .repository import DB_PATH
from .database import connect_database, integrity_errors, runtime_schema_mutation_allowed, use_mysql
from .feature_flags import kuaidi100_subscribe_enabled, mock_trade_enabled, payment_enabled
from .materials import clean_image_urls, fetch_db_series_assets, series_asset_key
from .money import stored_cents
from .observability import current_request_id, log_event, metrics


payment_logger = logging.getLogger("yujian.payment")
logistics_logger = logging.getLogger("yujian.logistics")
external_logger = logging.getLogger("yujian.external")


def load_local_env() -> None:
    env_path = DB_PATH.parent.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_local_env()


ORDER_STATUS_TEXT = {
    "pending_payment": "待付款",
    "pending_ship": "待发货",
    "shipped": "待收货",
    "completed": "已完成",
    "refund_requested": "退款中",
    "refunded": "已退款",
    "closed": "已关闭",
}

ORDER_STATE_TRANSITIONS = {
    "pending_payment": {"pending_ship", "closed"},
    "pending_ship": {"shipped", "refund_requested"},
    "shipped": {"completed", "refund_requested"},
    "completed": {"refund_requested"},
    "refund_requested": {"refunded", "pending_ship"},
    "refunded": set(),
    "closed": set(),
}

AFTER_SALE_TYPE_TEXT = {
    "return_refund": "退货退款",
    "resize": "修改手围",
    "repair": "重新穿制／维修",
    "resend": "缺件／补发",
    "other": "其他问题",
}
AFTER_SALE_REASON_CODES = {
    "return_refund": {"quality_issue", "damaged", "not_as_expected", "other"},
    "resize": {"size_large", "size_small", "wearing_uncomfortable", "other"},
    "repair": {"cord_loose", "bead_damaged", "accessory_issue", "other"},
    "resend": {"item_missing", "logistics_damage", "wrong_item", "other"},
    "other": {"care_question", "service_consulting", "other"},
}
AFTER_SALE_REASON_TEXT = {
    "quality_issue": "商品质量问题",
    "damaged": "商品破损",
    "not_as_expected": "与预期不符",
    "size_small": "手围偏小",
    "size_large": "手围偏大",
    "wearing_uncomfortable": "佩戴不舒适",
    "cord_loose": "弹力线松动",
    "bead_damaged": "珠子损坏",
    "accessory_issue": "配件问题",
    "item_missing": "商品或配件缺失",
    "logistics_damage": "物流破损",
    "wrong_item": "收到错误商品",
    "care_question": "保养与使用问题",
    "service_consulting": "其他服务咨询",
    "other": "其他问题",
}
AFTER_SALE_STATUS_TEXT = {
    "requested": "待审核",
    "approved": "已同意",
    "awaiting_return": "等待寄回",
    "returning": "寄回中",
    "service_processing": "处理中",
    "refund_pending": "待确认退款",
    "refund_submitting": "退款提交中",
    "refunding": "退款处理中",
    "resolved": "已完成",
    "rejected": "已拒绝",
    "canceled": "已取消",
}
AFTER_SALE_ACTIVE_STATUSES = {
    "requested", "approved", "awaiting_return", "returning", "service_processing",
    "refund_pending", "refund_submitting", "refunding",
}

PAYMENT_EVENT_STATES = {
    "TRANSACTION.SUCCESS": "SUCCESS",
    "TRANSACTION.CLOSED": "CLOSED",
    "TRANSACTION.PAYERROR": "PAYERROR",
    "TRANSACTION.USERPAYING": "USERPAYING",
    "TRANSACTION.NOTPAY": "NOTPAY",
}
REFUND_EVENT_STATES = {
    "REFUND.SUCCESS": "SUCCESS",
    "REFUND.ABNORMAL": "ABNORMAL",
    "REFUND.CLOSED": "CLOSED",
    "REFUND.PROCESSING": "PROCESSING",
}
WEBHOOK_TERMINAL_STATUSES = {"succeeded", "ignored", "compensation_required", "compensation_resolved"}
KUAIDI100_PHONE_REQUIRED_COMPANIES = {"shunfeng", "shunfengkuaiyun", "zhongtong"}
KUAIDI100_CALLBACK_MAX_BYTES = 512 * 1024
SIGNED_AUTO_COMPLETE_DAYS = 7
REFUND_SUBMISSION_RETRY_DELAY_SECONDS = 60


class OrderConflictError(ValueError):
    pass


class OrderPricingError(ValueError):
    pass


class OrderPriceChangedError(OrderConflictError):
    pass


class WechatPayRequestError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        provider_code: str = "",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider_code = provider_code
        self.retryable = retryable

    @property
    def resource_not_found(self) -> bool:
        return self.status_code == 404 and self.provider_code in {
            "RESOURCE_NOT_EXISTS",
            "REFUND_NOT_EXIST",
        }


class PaymentWebhookError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class WebhookEventConflictError(PaymentWebhookError):
    pass


class LogisticsCallbackSignatureError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


_ORDER_NO_LOCK = threading.Lock()
_ORDER_NO_LAST_MILLISECOND = -1
_ORDER_NO_SEQUENCE = 0


def generate_numeric_order_no() -> str:
    """20位纯数字：UTC年月日时分秒毫秒17位 + 同毫秒序号3位。"""
    global _ORDER_NO_LAST_MILLISECOND, _ORDER_NO_SEQUENCE
    with _ORDER_NO_LOCK:
        while True:
            now = datetime.now(timezone.utc)
            millisecond = int(now.timestamp() * 1000)
            if millisecond != _ORDER_NO_LAST_MILLISECOND:
                _ORDER_NO_LAST_MILLISECOND = millisecond
                _ORDER_NO_SEQUENCE = 0
                break
            if _ORDER_NO_SEQUENCE < 999:
                _ORDER_NO_SEQUENCE += 1
                break
            time.sleep(0.001)
        timestamp = now.strftime("%Y%m%d%H%M%S") + f"{now.microsecond // 1000:03d}"
        return f"{timestamp}{_ORDER_NO_SEQUENCE:03d}"


class WechatPayConfig:
    def __init__(self) -> None:
        self.app_id = os.getenv("WECHAT_PAY_APP_ID") or os.getenv("WECHAT_APP_ID") or os.getenv("WX_APPID")
        self.mch_id = os.getenv("WECHAT_PAY_MCH_ID") or os.getenv("WX_MCH_ID")
        self.serial_no = os.getenv("WECHAT_PAY_SERIAL_NO") or os.getenv("WX_PAY_SERIAL_NO")
        self.notify_url = os.getenv("WECHAT_PAY_NOTIFY_URL") or os.getenv("WX_PAY_NOTIFY_URL")
        self.refund_notify_url = (
            os.getenv("WECHAT_PAY_REFUND_NOTIFY_URL")
            or os.getenv("WX_PAY_REFUND_NOTIFY_URL")
            or self.default_refund_notify_url(self.notify_url)
        )
        self.private_key_path = os.getenv("WECHAT_PAY_PRIVATE_KEY_PATH") or os.getenv("WX_PAY_PRIVATE_KEY_PATH")
        self.private_key_text = os.getenv("WECHAT_PAY_PRIVATE_KEY") or os.getenv("WX_PAY_PRIVATE_KEY")
        self.api_v3_key = os.getenv("WECHAT_PAY_API_V3_KEY") or os.getenv("WX_PAY_API_V3_KEY")
        self.platform_cert_path = os.getenv("WECHAT_PAY_PLATFORM_CERT_PATH")
        self.platform_cert_text = os.getenv("WECHAT_PAY_PLATFORM_CERT")
        self.public_key_path = os.getenv("WECHAT_PAY_PUBLIC_KEY_PATH")
        self.public_key_text = os.getenv("WECHAT_PAY_PUBLIC_KEY")
        self.public_key_id = os.getenv("WECHAT_PAY_PUBLIC_KEY_ID")

    @property
    def missing(self) -> list[str]:
        missing = []
        if not self.app_id:
            missing.append("WECHAT_PAY_APP_ID")
        if not self.mch_id:
            missing.append("WECHAT_PAY_MCH_ID")
        if not self.serial_no:
            missing.append("WECHAT_PAY_SERIAL_NO")
        if not self.notify_url:
            missing.append("WECHAT_PAY_NOTIFY_URL")
        if not (self.private_key_path or self.private_key_text):
            missing.append("WECHAT_PAY_PRIVATE_KEY_PATH")
        return missing

    @property
    def ready(self) -> bool:
        return not self.missing

    def private_key_bytes(self) -> bytes:
        if self.private_key_text:
            return self.private_key_text.replace("\\n", "\n").encode("utf-8")
        if self.private_key_path:
            return Path(self.private_key_path).read_bytes()
        raise ValueError("缺少微信支付商户私钥")

    @staticmethod
    def default_refund_notify_url(notify_url: str | None) -> str:
        if not notify_url:
            return ""
        if "/wechat-pay/notify" in notify_url:
            return notify_url.replace("/wechat-pay/notify", "/wechat-pay/refund-notify")
        return notify_url.rstrip("/") + "/refund-notify"

    @property
    def test_mode(self) -> bool:
        return mock_trade_enabled()

    def platform_cert_bytes(self) -> bytes | None:
        if self.platform_cert_text:
            return self.platform_cert_text.replace("\\n", "\n").encode("utf-8")
        if self.platform_cert_path and Path(self.platform_cert_path).exists():
            return Path(self.platform_cert_path).read_bytes()
        return None

    def public_key_bytes(self) -> bytes | None:
        if self.public_key_text:
            return self.public_key_text.replace("\\n", "\n").encode("utf-8")
        if self.public_key_path and Path(self.public_key_path).exists():
            return Path(self.public_key_path).read_bytes()
        return None


class Kuaidi100Config:
    def __init__(self) -> None:
        self.customer = os.getenv("KUAIDI100_CUSTOMER") or os.getenv("KUAIDI100_CUSTOMER_ID")
        self.key = os.getenv("KUAIDI100_KEY") or os.getenv("KUAIDI100_SECRET")
        self.query_url = os.getenv("KUAIDI100_QUERY_URL") or "https://poll.kuaidi100.com/poll/query.do"
        self.subscribe_url = os.getenv("KUAIDI100_SUBSCRIBE_URL") or "https://poll.kuaidi100.com/poll"
        self.callback_url = str(os.getenv("KUAIDI100_CALLBACK_URL") or "").strip()
        self.callback_salt = str(os.getenv("KUAIDI100_CALLBACK_SALT") or "").strip()
        self.resultv2 = str(os.getenv("KUAIDI100_SUBSCRIBE_RESULTV2") or "1").strip() or "1"

    @property
    def ready(self) -> bool:
        return bool(self.customer and self.key)

    @property
    def subscription_ready(self) -> bool:
        return bool(self.key and self.callback_url and self.callback_salt)

    @property
    def callback_ready(self) -> bool:
        return bool(self.callback_salt)


class OrderService:
    def __init__(self, db_path=DB_PATH) -> None:
        self.db_path = db_path
        self._force_sqlite = db_path != DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self):
        return connect_database(self.db_path if self._force_sqlite else None)

    @staticmethod
    def parse_utc_datetime(value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def init_db(self) -> None:
        if use_mysql() and not self._force_sqlite:
            if not runtime_schema_mutation_allowed():
                return
            with self.connect() as connection:
                self.backfill_order_designs(connection)
            return
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    out_trade_no TEXT NOT NULL UNIQUE,
                    user_id TEXT NOT NULL,
                    openid TEXT,
                    status TEXT NOT NULL,
                    payment_status TEXT NOT NULL,
                    total_amount REAL NOT NULL,
                    total_fee INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    receiver_json TEXT NOT NULL,
                    design_json TEXT NOT NULL,
                    sequence_json TEXT NOT NULL,
                    bom_json TEXT NOT NULL,
                    remark TEXT,
                    payment_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    paid_at TEXT,
                    after_sale_status TEXT,
                    refund_status TEXT,
                    refund_json TEXT,
                    logistics_json TEXT,
                    status_history_json TEXT,
                    logistics_signed_at TEXT,
                    auto_complete_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS diy_designs (
                    design_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    design_json TEXT NOT NULL,
                    sequence_json TEXT NOT NULL,
                    order_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS after_sale_cases (
                    case_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    case_type TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    order_snapshot_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_refund_fee INTEGER NOT NULL DEFAULT 0,
                    approved_refund_fee INTEGER NOT NULL DEFAULT 0,
                    resolution_type TEXT NOT NULL DEFAULT '',
                    review_note TEXT NOT NULL DEFAULT '',
                    reviewed_by TEXT NOT NULL DEFAULT '',
                    reviewed_at TEXT,
                    resolved_at TEXT,
                    idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    return_carrier TEXT NOT NULL DEFAULT '',
                    return_tracking_no TEXT NOT NULL DEFAULT '',
                    return_submitted_at TEXT,
                    canceled_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (user_id, idempotency_key)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS after_sale_events (
                    event_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    from_status TEXT NOT NULL DEFAULT '',
                    to_status TEXT NOT NULL,
                    operator_type TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cart_items (
                    cart_item_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    item_id TEXT,
                    item_json TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS community_favorites (
                    user_id TEXT NOT NULL,
                    post_id TEXT NOT NULL,
                    item_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, post_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_addresses (
                    address_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    region_json TEXT NOT NULL,
                    detail_address TEXT NOT NULL,
                    address TEXT NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_coupons (
                    coupon_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    coupon_type TEXT NOT NULL DEFAULT 'amount',
                    value REAL NOT NULL DEFAULT 0,
                    min_amount REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'unused',
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self.ensure_columns(connection)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id, created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, payment_status)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_orders_auto_complete ON orders(status, auto_complete_at)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_diy_designs_user_updated ON diy_designs(user_id, updated_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cart_items_user_updated ON cart_items(user_id, updated_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_community_favorites_user_updated ON community_favorites(user_id, updated_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_user_addresses_user_updated ON user_addresses(user_id, updated_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_user_coupons_user_status ON user_coupons(user_id, status, expires_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_after_sale_order_created ON after_sale_cases(order_id, created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_after_sale_status_created ON after_sale_cases(status, created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_after_sale_events_case_created ON after_sale_events(case_id, created_at)")
            self.backfill_order_designs(connection)

    def ensure_columns(self, connection) -> None:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(orders)").fetchall()}
        migrations = {
            "after_sale_status": "ALTER TABLE orders ADD COLUMN after_sale_status TEXT",
            "refund_status": "ALTER TABLE orders ADD COLUMN refund_status TEXT",
            "refund_json": "ALTER TABLE orders ADD COLUMN refund_json TEXT",
            "logistics_json": "ALTER TABLE orders ADD COLUMN logistics_json TEXT",
            "status_history_json": "ALTER TABLE orders ADD COLUMN status_history_json TEXT",
            "design_id": "ALTER TABLE orders ADD COLUMN design_id TEXT",
            "logistics_signed_at": "ALTER TABLE orders ADD COLUMN logistics_signed_at TEXT",
            "auto_complete_at": "ALTER TABLE orders ADD COLUMN auto_complete_at TEXT",
        }
        for column, sql in migrations.items():
            if column not in columns:
                connection.execute(sql)

    def backfill_order_designs(self, connection) -> None:
        rows = connection.execute(
            """
            SELECT order_id, user_id, design_json, sequence_json, created_at, updated_at
            FROM orders WHERE COALESCE(design_id, '') = ''
            """
        ).fetchall()
        for row in rows:
            design_id = f"LEGACY-{row['order_id']}"
            insert_keyword = "INSERT IGNORE" if use_mysql() and not self._force_sqlite else "INSERT OR IGNORE"
            connection.execute(
                f"""
                {insert_keyword} INTO diy_designs
                (design_id, user_id, status, design_json, sequence_json, order_id, created_at, updated_at)
                VALUES (?, ?, 'ordered_snapshot', ?, ?, ?, ?, ?)
                """,
                (
                    design_id,
                    row["user_id"],
                    row["design_json"],
                    row["sequence_json"],
                    row["order_id"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )
            connection.execute(
                "UPDATE orders SET design_id = ? WHERE order_id = ?",
                (design_id, row["order_id"]),
            )

    def save_design(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            raise ValueError("user_id 不能为空")
        design_id = str(payload.get("design_id") or "").strip() or f"DIY{int(time.time() * 1000)}{secrets.token_hex(3).upper()}"
        timestamp = now_iso()
        design = payload.get("design") or {}
        sequence = payload.get("sequence") or []
        if sequence:
            self.validate_attachment_sequence(sequence)
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT design_id, user_id FROM diy_designs WHERE design_id = ?",
                (design_id,),
            ).fetchone()
            if existing and existing["user_id"] != user_id:
                for _ in range(5):
                    design_id = f"DIY{int(time.time() * 1000)}{secrets.token_hex(3).upper()}"
                    existing = connection.execute(
                        "SELECT design_id, user_id FROM diy_designs WHERE design_id = ?",
                        (design_id,),
                    ).fetchone()
                    if not existing:
                        break
                if existing:
                    raise ValueError("DIY 方案编号冲突，请重试")
            if existing:
                connection.execute(
                    """
                    UPDATE diy_designs SET status = ?, design_json = ?, sequence_json = ?, updated_at = ?
                    WHERE design_id = ? AND user_id = ?
                    """,
                    (
                        payload.get("status") or "saved",
                        json.dumps(design, ensure_ascii=False),
                        json.dumps(sequence, ensure_ascii=False),
                        timestamp,
                        design_id,
                        user_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO diy_designs
                    (design_id, user_id, status, design_json, sequence_json, order_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        design_id,
                        user_id,
                        payload.get("status") or "saved",
                        json.dumps(design, ensure_ascii=False),
                        json.dumps(sequence, ensure_ascii=False),
                        timestamp,
                        timestamp,
                    ),
                )
        return self.get_design(design_id)

    def get_design(self, design_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM diy_designs WHERE design_id = ?", (design_id,)).fetchone()
        if not row:
            raise ValueError("DIY 方案不存在")
        return self.public_design(dict(row))

    def publish_design(self, design_id: str, user_id: str) -> dict[str, Any]:
        design = self.get_design(design_id)
        if design["user_id"] != user_id:
            raise ValueError("DIY 方案不存在")
        share_token = secrets.token_urlsafe(48)
        timestamp = now_iso()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE diy_designs
                SET share_status = 'shared', share_token_hash = ?,
                    share_published_at = ?, share_revoked_at = NULL, updated_at = ?
                WHERE design_id = ? AND user_id = ?
                """,
                (
                    hashlib.sha256(share_token.encode("utf-8")).hexdigest(),
                    timestamp,
                    timestamp,
                    design_id,
                    user_id,
                ),
            )
        return {"share_token": share_token, "published_at": timestamp}

    def revoke_design_share(self, design_id: str, user_id: str) -> dict[str, Any]:
        design = self.get_design(design_id)
        if design["user_id"] != user_id:
            raise ValueError("DIY 方案不存在")
        timestamp = now_iso()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE diy_designs
                SET share_status = 'revoked', share_token_hash = NULL,
                    share_revoked_at = ?, updated_at = ?
                WHERE design_id = ? AND user_id = ?
                """,
                (timestamp, timestamp, design_id, user_id),
            )
        return {"revoked": True, "revoked_at": timestamp}

    def get_shared_design(self, share_token: str) -> dict[str, Any]:
        token = str(share_token or "").strip()
        if len(token) < 32 or len(token) > 512:
            raise ValueError("分享内容不存在")
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM diy_designs
                WHERE share_token_hash = ? AND share_status = 'shared'
                LIMIT 1
                """,
                (digest,),
            ).fetchone()
        if not row:
            raise ValueError("分享内容不存在")
        return self.public_shared_design(dict(row))

    def list_designs(self, user_id: str, limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM diy_designs WHERE user_id = ?"
        params: list[Any] = [user_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self.public_design(dict(row)) for row in rows]

    def delete_design(self, design_id: str, user_id: str) -> dict[str, Any]:
        design = self.get_design(design_id)
        if design["user_id"] != user_id:
            raise ValueError("no permission to delete this DIY design")
        if design.get("order_id"):
            raise ValueError("ordered DIY design snapshots cannot be deleted")
        with self.connect() as connection:
            connection.execute("DELETE FROM diy_designs WHERE design_id = ? AND user_id = ?", (design_id, user_id))
        return {"design_id": design_id, "deleted": True}

    def list_cart_items(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM cart_items WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [self.public_cart_item(dict(row)) for row in rows]

    def save_cart_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            raise ValueError("user_id cannot be empty")
        quantity = int(payload.get("quantity") or 1)
        if quantity < 1:
            raise ValueError("cart item quantity must be greater than 0")
        idempotency_key = str(payload.get("idempotency_key") or "").strip()[:128]
        if idempotency_key:
            digest = hashlib.sha256(f"{user_id}\0{idempotency_key}".encode("utf-8")).hexdigest()[:32].upper()
            cart_item_id = f"CARTIDEM{digest}"
        else:
            cart_item_id = str(payload.get("cart_item_id") or "").strip() or f"CART{int(time.time() * 1000)}{secrets.token_hex(3).upper()}"
        item_type = str(payload.get("item_type") or "plan").strip()[:40]
        item_id = str(payload.get("item_id") or "").strip()
        item = payload.get("item") or {}
        timestamp = now_iso()
        with self.connect() as connection:
            insert_keyword = "INSERT IGNORE" if use_mysql() and not self._force_sqlite else "INSERT OR IGNORE"
            item_json = json.dumps(item, ensure_ascii=False)
            connection.execute(
                f"""
                {insert_keyword} INTO cart_items
                (cart_item_id, user_id, item_type, item_id, item_json, quantity, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cart_item_id,
                    user_id,
                    item_type,
                    item_id,
                    item_json,
                    quantity,
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                """
                UPDATE cart_items SET item_type = ?, item_id = ?, item_json = ?, quantity = ?, updated_at = ?
                WHERE cart_item_id = ? AND user_id = ?
                """,
                (
                    item_type,
                    item_id,
                    item_json,
                    quantity,
                    timestamp,
                    cart_item_id,
                    user_id,
                ),
            )
        return self.get_cart_item(cart_item_id, user_id)

    def get_cart_item(self, cart_item_id: str, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM cart_items WHERE cart_item_id = ? AND user_id = ?",
                (cart_item_id, user_id),
            ).fetchone()
        if not row:
            raise ValueError("cart item does not exist")
        return self.public_cart_item(dict(row))

    def update_cart_item(self, cart_item_id: str, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.get_cart_item(cart_item_id, user_id)
        item = payload["item"] if payload.get("item") is not None else current["item"]
        quantity = int(payload["quantity"] if payload.get("quantity") is not None else current["quantity"])
        if quantity < 1:
            raise ValueError("cart item quantity must be greater than 0")
        with self.connect() as connection:
            connection.execute(
                "UPDATE cart_items SET item_json = ?, quantity = ?, updated_at = ? WHERE cart_item_id = ? AND user_id = ?",
                (json.dumps(item, ensure_ascii=False), quantity, now_iso(), cart_item_id, user_id),
            )
        return self.get_cart_item(cart_item_id, user_id)

    def delete_cart_item(self, cart_item_id: str, user_id: str) -> dict[str, Any]:
        self.get_cart_item(cart_item_id, user_id)
        with self.connect() as connection:
            connection.execute("DELETE FROM cart_items WHERE cart_item_id = ? AND user_id = ?", (cart_item_id, user_id))
        return {"cart_item_id": cart_item_id, "deleted": True}

    def clear_cart(self, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        return {"user_id": user_id, "cleared": True}

    def list_community_favorites(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM community_favorites WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [self.public_community_favorite(dict(row)) for row in rows]

    def save_community_favorite(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = str(payload.get("user_id") or "").strip()
        post_id = str(payload.get("post_id") or payload.get("id") or "").strip()
        if not user_id:
            raise ValueError("user_id cannot be empty")
        if not post_id:
            raise ValueError("post_id cannot be empty")
        item = payload.get("item") or {}
        if not isinstance(item, dict):
            item = {}
        item = {**item, "id": item.get("id") or post_id, "post_id": post_id}
        timestamp = now_iso()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT user_id FROM community_favorites WHERE user_id = ? AND post_id = ?",
                (user_id, post_id),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE community_favorites SET item_json = ?, updated_at = ?
                    WHERE user_id = ? AND post_id = ?
                    """,
                    (json.dumps(item, ensure_ascii=False), timestamp, user_id, post_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO community_favorites
                    (user_id, post_id, item_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, post_id, json.dumps(item, ensure_ascii=False), timestamp, timestamp),
                )
        return self.get_community_favorite(user_id, post_id)

    def get_community_favorite(self, user_id: str, post_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM community_favorites WHERE user_id = ? AND post_id = ?",
                (user_id, post_id),
            ).fetchone()
        if not row:
            raise ValueError("community favorite does not exist")
        return self.public_community_favorite(dict(row))

    def delete_community_favorite(self, user_id: str, post_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM community_favorites WHERE user_id = ? AND post_id = ?",
                (user_id, post_id),
            )
        return {"user_id": user_id, "post_id": post_id, "deleted": True}

    def list_addresses(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM user_addresses WHERE user_id = ? ORDER BY is_default DESC, updated_at DESC",
                (user_id,),
            ).fetchall()
        return [self.public_address(dict(row)) for row in rows]

    def save_address(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            raise ValueError("user_id cannot be empty")
        address_id = str(payload.get("address_id") or "").strip() or f"ADDR{int(time.time() * 1000)}{secrets.token_hex(3).upper()}"
        region = payload.get("region") or []
        detail_address = str(payload.get("detail_address") or "").strip()
        address_text = str(payload.get("address") or " ".join([*region, detail_address])).strip()
        timestamp = now_iso()
        with self.connect() as connection:
            count_row = connection.execute("SELECT COUNT(*) AS count FROM user_addresses WHERE user_id = ?", (user_id,)).fetchone()
            is_first = int(count_row["count"] if count_row else 0) == 0
            is_default = 1 if (payload.get("is_default") or is_first) else 0
            if is_default:
                connection.execute("UPDATE user_addresses SET is_default = 0 WHERE user_id = ?", (user_id,))
            existing = connection.execute(
                "SELECT address_id FROM user_addresses WHERE address_id = ? AND user_id = ?",
                (address_id, user_id),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE user_addresses
                    SET name = ?, phone = ?, region_json = ?, detail_address = ?, address = ?, is_default = ?, updated_at = ?
                    WHERE address_id = ? AND user_id = ?
                    """,
                    (
                        payload.get("name"),
                        payload.get("phone"),
                        json.dumps(region, ensure_ascii=False),
                        detail_address,
                        address_text,
                        is_default,
                        timestamp,
                        address_id,
                        user_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO user_addresses
                    (address_id, user_id, name, phone, region_json, detail_address, address, is_default, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        address_id,
                        user_id,
                        payload.get("name"),
                        payload.get("phone"),
                        json.dumps(region, ensure_ascii=False),
                        detail_address,
                        address_text,
                        is_default,
                        timestamp,
                        timestamp,
                    ),
                )
        return self.get_address(address_id, user_id)

    def get_address(self, address_id: str, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM user_addresses WHERE address_id = ? AND user_id = ?",
                (address_id, user_id),
            ).fetchone()
        if not row:
            raise ValueError("address does not exist")
        return self.public_address(dict(row))

    def delete_address(self, address_id: str, user_id: str) -> dict[str, Any]:
        address = self.get_address(address_id, user_id)
        with self.connect() as connection:
            connection.execute("DELETE FROM user_addresses WHERE address_id = ? AND user_id = ?", (address_id, user_id))
            if address.get("is_default"):
                next_row = connection.execute(
                    "SELECT address_id FROM user_addresses WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                    (user_id,),
                ).fetchone()
                if next_row:
                    connection.execute("UPDATE user_addresses SET is_default = 1 WHERE address_id = ?", (next_row["address_id"],))
        return {"address_id": address_id, "deleted": True}

    def set_default_address(self, address_id: str, user_id: str) -> dict[str, Any]:
        self.get_address(address_id, user_id)
        with self.connect() as connection:
            connection.execute("UPDATE user_addresses SET is_default = 0 WHERE user_id = ?", (user_id,))
            connection.execute(
                "UPDATE user_addresses SET is_default = 1, updated_at = ? WHERE address_id = ? AND user_id = ?",
                (now_iso(), address_id, user_id),
            )
        return self.get_address(address_id, user_id)

    @staticmethod
    def normalize_order_receiver(receiver: dict[str, Any]) -> dict[str, Any]:
        name = str(receiver.get("name") or receiver.get("receiver") or "").strip()
        phone = str(receiver.get("phone") or receiver.get("mobile") or "").strip()
        region_value = receiver.get("region") or []
        region = [str(item).strip() for item in region_value if str(item).strip()] if isinstance(region_value, list) else []
        region_text = str(receiver.get("regionText") or receiver.get("region_text") or " ".join(region)).strip()
        detail_address = str(
            receiver.get("detailAddress")
            or receiver.get("detail_address")
            or receiver.get("detail")
            or ""
        ).strip()
        address = str(receiver.get("address") or " ".join([region_text, detail_address])).strip()
        if not name:
            raise ValueError("请填写收货人")
        if not phone:
            raise ValueError("请填写手机号")
        if not address:
            raise ValueError("请填写详细地址")
        return {
            **receiver,
            "name": name,
            "phone": phone,
            "region": region,
            "regionText": region_text,
            "detailAddress": detail_address,
            "address": address,
        }

    def list_coupons(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM user_coupons WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [self.public_coupon(dict(row)) for row in rows]

    def available_coupons(self, user_id: str, amount: float = 0) -> list[dict[str, Any]]:
        timestamp = now_iso()
        coupons = self.list_coupons(user_id)
        return [
            coupon for coupon in coupons
            if coupon["status"] in {"unused", "active"}
            and float(coupon.get("min_amount") or 0) <= amount
            and (not coupon.get("expires_at") or str(coupon["expires_at"]) >= timestamp)
        ]

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            raise ValueError("user_id 不能为空")
        idempotency_key = self.normalize_idempotency_key(payload.get("idempotency_key"))
        request_hash = self.order_request_hash(payload)
        replay = self.resolve_idempotent_order(user_id, idempotency_key, request_hash, wait=False)
        if replay:
            return replay
        receiver = self.normalize_order_receiver(payload.get("receiver") or {})
        design = payload.get("design") or {}
        design_id = str(payload.get("design_id") or design.get("design_id") or "").strip()
        sequence = payload.get("sequence") or []
        if not sequence:
            raise ValueError("订单材料不能为空")
        user = self.get_user(user_id) or {}
        timestamp = now_iso()
        expires_at = self.reservation_expiry(timestamp)
        history = [{"status": "pending_payment", "label": "订单已创建，等待支付", "time": timestamp}]
        order_id = generate_numeric_order_no()

        try:
            with self.connect() as connection:
                self.begin_order_transaction(connection)
                connection.execute(
                    """
                    INSERT INTO order_requests
                    (user_id, idempotency_key, request_hash, order_id, status, created_at, updated_at)
                    VALUES (?, ?, ?, NULL, 'processing', ?, ?)
                    """,
                    (user_id, idempotency_key, request_hash, timestamp, timestamp),
                )
                snapshots, reservations = self.lock_validate_and_snapshot_items(connection, sequence)
                total_fee = sum(int(item["subtotal_cents"]) for item in snapshots)
                if total_fee <= 0:
                    raise OrderPricingError("订单金额无效，订单未创建")
                total_amount = self.cents_text(total_fee)
                bom = self.rebuild_bom_from_sequence(snapshots)
                if isinstance(design, dict):
                    summary = dict(design.get("summary") or {})
                    summary["price"] = total_amount
                    summary["priceText"] = total_amount
                    summary["total_fee"] = total_fee
                    design = {**design, "summary": summary}
                candidate = {
                    "order_id": order_id,
                    "out_trade_no": order_id,
                    "user_id": user_id,
                    "design_id": design_id or None,
                    "openid": user.get("openid"),
                    "status": "pending_payment",
                    "payment_status": "unpaid",
                    "total_amount": total_amount,
                    "total_fee": total_fee,
                    "currency": "CNY",
                    "receiver_json": json.dumps(receiver, ensure_ascii=False),
                    "design_json": json.dumps(design, ensure_ascii=False),
                    "sequence_json": json.dumps(snapshots, ensure_ascii=False),
                    "bom_json": json.dumps(bom, ensure_ascii=False),
                    "remark": str(payload.get("remark") or "").strip(),
                    "payment_json": "",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "paid_at": None,
                    "after_sale_status": "",
                    "refund_status": "",
                    "refund_json": "",
                    "logistics_json": "",
                    "status_history_json": json.dumps(history, ensure_ascii=False),
                    "idempotency_key": idempotency_key,
                    "request_hash": request_hash,
                    "reservation_expires_at": expires_at,
                }
                connection.execute(
                    """
                    INSERT INTO orders
                    (order_id, out_trade_no, user_id, design_id, openid, status, payment_status,
                     total_amount, total_fee, currency, receiver_json, design_json, sequence_json,
                     bom_json, remark, payment_json, created_at, updated_at, paid_at,
                     after_sale_status, refund_status, refund_json, logistics_json,
                     status_history_json, idempotency_key, request_hash, reservation_expires_at)
                    VALUES
                    (:order_id, :out_trade_no, :user_id, :design_id, :openid, :status,
                     :payment_status, :total_amount, :total_fee, :currency, :receiver_json,
                     :design_json, :sequence_json, :bom_json, :remark, :payment_json,
                     :created_at, :updated_at, :paid_at, :after_sale_status, :refund_status,
                     :refund_json, :logistics_json, :status_history_json, :idempotency_key,
                     :request_hash, :reservation_expires_at)
                    """,
                    candidate,
                )
                self.reserve_inventory(connection, order_id, reservations, expires_at, timestamp)
                if design_id:
                    connection.execute(
                        """
                        UPDATE diy_designs SET status = 'ordered', order_id = ?, updated_at = ?
                        WHERE design_id = ? AND user_id = ?
                        """,
                        (order_id, timestamp, design_id, user_id),
                    )
                connection.execute(
                    """
                    UPDATE order_requests SET order_id = ?, status = 'created', updated_at = ?
                    WHERE user_id = ? AND idempotency_key = ?
                    """,
                    (order_id, timestamp, user_id, idempotency_key),
                )
        except (sqlite3.IntegrityError, *integrity_errors()) as exc:
            replay = self.resolve_idempotent_order(user_id, idempotency_key, request_hash, wait=True)
            if replay:
                return replay
            raise OrderConflictError("订单请求冲突，请勿重复提交") from exc

        order = self.get_order(order_id)
        try:
            payment = self.create_wechat_payment(order)
        except Exception:
            self.fail_order_and_release(order_id, "支付预下单失败，库存预占已释放")
            self.complete_order_request(user_id, idempotency_key)
            raise
        self.complete_order_request(user_id, idempotency_key)
        return {"order": self.get_order(order_id), "payment": payment, "idempotent_replay": False}

    @property
    def mysql_transactions(self) -> bool:
        return use_mysql() and not self._force_sqlite

    def begin_order_transaction(self, connection) -> None:
        if not self.mysql_transactions:
            connection.execute("BEGIN IMMEDIATE")

    @staticmethod
    def normalize_idempotency_key(value: Any) -> str:
        key = str(value or "").strip()
        if len(key) < 8 or len(key) > 128:
            raise ValueError("Idempotency-Key 必须为 8 至 128 个字符")
        return key

    @staticmethod
    def order_request_hash(payload: dict[str, Any]) -> str:
        body = {key: value for key, value in payload.items() if key != "idempotency_key"}
        canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def reservation_ttl_seconds() -> int:
        try:
            configured = int(os.getenv("INVENTORY_RESERVATION_TTL_SECONDS", "900"))
        except ValueError:
            configured = 900
        return max(60, min(configured, 24 * 60 * 60))

    @classmethod
    def reservation_expiry(cls, created_at: str) -> str:
        created = datetime.fromisoformat(created_at)
        return (created + timedelta(seconds=cls.reservation_ttl_seconds())).isoformat()

    @staticmethod
    def cents_text(cents: int) -> str:
        return f"{Decimal(int(cents)) / Decimal('100'):.2f}"

    def resolve_idempotent_order(
        self,
        user_id: str,
        idempotency_key: str,
        request_hash: str,
        wait: bool,
    ) -> dict[str, Any] | None:
        attempts = 30 if wait else 1
        for attempt in range(attempts):
            with self.connect() as connection:
                row = connection.execute(
                    """
                    SELECT request_hash, order_id, status FROM order_requests
                    WHERE user_id = ? AND idempotency_key = ?
                    """,
                    (user_id, idempotency_key),
                ).fetchone()
            if not row:
                if wait and attempt + 1 < attempts:
                    time.sleep(0.05)
                    continue
                return None
            if str(row["request_hash"]) != request_hash:
                raise OrderConflictError("同一 Idempotency-Key 不能用于不同的订单内容")
            order_id = str(row["order_id"] or "")
            if order_id and (row["status"] == "completed" or attempt + 1 == attempts or not wait):
                order = self.get_order(order_id)
                return {
                    "order": order,
                    "payment": order.get("payment") or {},
                    "idempotent_replay": True,
                }
            time.sleep(0.05)
        return None

    def complete_order_request(self, user_id: str, idempotency_key: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE order_requests SET status = 'completed', updated_at = ?
                WHERE user_id = ? AND idempotency_key = ?
                """,
                (now_iso(), user_id, idempotency_key),
            )

    @staticmethod
    def item_quantity(item: dict[str, Any]) -> int:
        raw = item.get("quantity", item.get("qty", 1))
        if isinstance(raw, bool):
            raise ValueError("SKU 数量必须为正整数")
        try:
            decimal_value = Decimal(str(raw))
            quantity = int(decimal_value)
        except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("SKU 数量必须为正整数") from exc
        if decimal_value != Decimal(quantity) or quantity <= 0 or quantity > 999:
            raise ValueError("SKU 数量必须为 1 至 999 的正整数")
        return quantity

    @staticmethod
    def material_price_cents(material: dict[str, Any]) -> int:
        if material.get("price_cents") in (None, ""):
            raise OrderPricingError("SKU 缺少有效价格，订单未创建")
        try:
            return stored_cents(material.get("price_cents"), field_name="SKU 价格", allow_zero=False)
        except ValueError as exc:
            raise OrderPricingError("SKU 价格字段非法，订单未创建") from exc

    @staticmethod
    def client_price_cents(item: dict[str, Any]) -> int | None:
        value = None
        for key in ("price", "priceText", "unit_price"):
            if item.get(key) is not None and item.get(key) != "":
                value = item.get(key)
                break
        if value is None:
            return None
        try:
            price = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise OrderPriceChangedError("价格已更新，请确认") from exc
        if not price.is_finite():
            raise OrderPriceChangedError("价格已更新，请确认")
        try:
            rounded = price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError) as exc:
            raise OrderPriceChangedError("价格已更新，请确认") from exc
        return int(rounded * 100)

    def lock_validate_and_snapshot_items(
        self,
        connection,
        sequence: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        self.validate_attachment_sequence(sequence)
        requested: list[tuple[dict[str, Any], str, int]] = []
        references: set[str] = set()
        for raw_item in sequence:
            if not isinstance(raw_item, dict):
                raise ValueError("订单 SKU 格式无效")
            reference = str(
                raw_item.get("sku")
                or raw_item.get("skuId")
                or raw_item.get("sku_id")
                or raw_item.get("id")
                or ""
            ).strip()
            if not reference:
                raise OrderPricingError("SKU 不存在，订单未创建")
            quantity = self.item_quantity(raw_item)
            requested.append((raw_item, reference, quantity))
            references.add(reference)

        try:
            rows = self.fetch_locked_material_rows(connection, references)
        except Exception as exc:
            raise OrderPricingError("SKU 数据查询失败，订单未创建") from exc

        row_dicts = [dict(raw_row) for raw_row in rows]
        series_assets = fetch_db_series_assets(connection, row_dicts)
        by_reference: dict[str, dict[str, Any]] = {}
        for material in row_dicts:
            series_asset = series_assets.get(series_asset_key(material), {})
            image_urls = series_asset.get("image_urls") or []
            material["image_path"] = series_asset.get("image_path") or ""
            material["image_url"] = series_asset.get("image_url") or (image_urls[0] if image_urls else "")
            material["image_urls_json"] = json.dumps(image_urls, ensure_ascii=False)
            for key in (str(material.get("id") or ""), str(material.get("skuId") or "")):
                if key:
                    existing = by_reference.get(key)
                    if existing and existing.get("id") != material.get("id"):
                        raise OrderPricingError("SKU 标识冲突，订单未创建")
                    by_reference[key] = material

        snapshots: list[dict[str, Any]] = []
        reservations: dict[str, dict[str, Any]] = {}
        changed: list[str] = []
        for item, reference, quantity in requested:
            material = by_reference.get(reference)
            if not material:
                raise OrderPricingError(f"SKU 不存在，订单未创建：{reference}")
            if not bool(material.get("enabled")):
                raise OrderPricingError(f"SKU 已下架，订单未创建：{material.get('name') or reference}")
            unit_cents = self.material_price_cents(material)
            client_cents = self.client_price_cents(item)
            if client_cents is not None and client_cents != unit_cents:
                changed.append(str(material.get("name") or reference))
            material_id = str(material.get("id") or "").strip()
            sku_code = str(material.get("skuId") or material_id).strip()
            if not material_id:
                raise OrderPricingError("SKU 数据不完整，订单未创建")
            subtotal_cents = unit_cents * quantity
            snapshot = {
                **{
                    key: value
                    for key, value in item.items()
                    if key not in {"price", "priceText", "amount", "total", "subtotal", "unit_price"}
                },
                "sku_id": material_id,
                "id": material_id,
                "sku": sku_code,
                "skuId": sku_code,
                "name": str(material.get("name") or "SKU"),
                "category": material.get("category") or "",
                "series": material.get("series") or "",
                "effect": material.get("effect") or "",
                "element": material.get("element") or "",
                "size": material.get("size") or 0,
                "image_url": material.get("image_url") or "",
                "image_urls": clean_image_urls(
                    material.get("image_urls_json"),
                    material.get("image_url") or "",
                    material.get("image_path") or "",
                ),
                "quantity": quantity,
                "unit_price_cents": unit_cents,
                "unit_price": self.cents_text(unit_cents),
                "price": self.cents_text(unit_cents),
                "subtotal_cents": subtotal_cents,
                "subtotal": self.cents_text(subtotal_cents),
                "price_version": str(material.get("updated_at") or ""),
            }
            snapshots.append(snapshot)
            reservation = reservations.setdefault(
                material_id,
                {
                    "sku_id": material_id,
                    "sku_code": sku_code,
                    "name": snapshot["name"],
                    "quantity": 0,
                    "stock": int(material.get("stock") or 0),
                    "reserved_stock": int(material.get("reserved_stock") or 0),
                },
            )
            reservation["quantity"] += quantity

        if changed:
            raise OrderPriceChangedError(f"价格已更新，请确认：{'、'.join(changed[:5])}")
        for reservation in reservations.values():
            available = reservation["stock"] - reservation["reserved_stock"]
            if reservation["quantity"] > available:
                raise OrderPricingError(
                    f"SKU 库存不足：{reservation['name']}，可用 {max(0, available)}"
                )
        return snapshots, reservations

    @staticmethod
    def validate_attachment_sequence(sequence: list[dict[str, Any]]) -> None:
        base_count = sum(
            1
            for item in sequence
            if isinstance(item, dict)
            and item.get("attachment_mode") != "bead_cap"
            and not (
                isinstance(item.get("attachment"), dict)
                and item["attachment"].get("mode") == "bead_cap"
            )
        )
        occupied_slots: set[tuple[int, str]] = set()
        for item in sequence:
            if not isinstance(item, dict):
                continue
            attachment = item.get("attachment")
            is_bead_cap = item.get("attachment_mode") == "bead_cap" or (
                isinstance(attachment, dict) and attachment.get("mode") == "bead_cap"
            )
            if not is_bead_cap:
                continue
            if item.get("placement_mode") != "attached_side":
                raise ValueError("包珠隔片安装方式无效")
            if not isinstance(attachment, dict):
                raise ValueError("包珠隔片缺少主珠位置")
            side = str(attachment.get("side") or "")
            try:
                host_index = int(attachment.get("host_index"))
            except (TypeError, ValueError) as exc:
                raise ValueError("包珠隔片主珠位置无效") from exc
            if side not in {"left", "right"} or host_index < 1 or host_index > base_count:
                raise ValueError("包珠隔片主珠位置无效")
            slot = (host_index, side)
            if slot in occupied_slots:
                raise ValueError("同一主珠侧面不能重复安装包珠隔片")
            occupied_slots.add(slot)

    def fetch_locked_material_rows(self, connection, references: set[str]):
        marks = ", ".join(["?"] * len(references))
        lock_clause = " FOR UPDATE" if self.mysql_transactions else ""
        return connection.execute(
            f"""
            SELECT id, skuId, top, category, series, grade, name, effect, element,
                   price_cents, size, weight, color, shine, image_path, image_url,
                   image_urls_json, stock, reserved_stock, enabled, updated_at
            FROM managed_materials
            WHERE id IN ({marks}) OR skuId IN ({marks})
            ORDER BY id{lock_clause}
            """,
            [*sorted(references), *sorted(references)],
        ).fetchall()

    def reserve_inventory(
        self,
        connection,
        order_id: str,
        reservations: dict[str, dict[str, Any]],
        expires_at: str,
        timestamp: str,
    ) -> None:
        for sku_id in sorted(reservations):
            reservation = reservations[sku_id]
            quantity = int(reservation["quantity"])
            cursor = connection.execute(
                """
                UPDATE managed_materials
                SET reserved_stock = reserved_stock + ?
                WHERE id = ? AND enabled = 1 AND stock - reserved_stock >= ?
                """,
                (quantity, sku_id, quantity),
            )
            if cursor.rowcount != 1:
                raise OrderPricingError(f"SKU 库存不足：{reservation['name']}")
            connection.execute(
                """
                INSERT INTO inventory_reservations
                (reservation_id, order_id, sku_id, sku_code, quantity, status,
                 expires_at, created_at, updated_at, confirmed_at, released_at)
                VALUES (?, ?, ?, ?, ?, 'reserved', ?, ?, ?, NULL, NULL)
                """,
                (
                    f"ir_{secrets.token_hex(16)}",
                    order_id,
                    sku_id,
                    reservation["sku_code"],
                    quantity,
                    expires_at,
                    timestamp,
                    timestamp,
                ),
            )

    def reservation_rows(self, connection, order_id: str, lock: bool = True) -> list[dict[str, Any]]:
        lock_clause = " FOR UPDATE" if lock and self.mysql_transactions else ""
        rows = connection.execute(
            f"""
            SELECT * FROM inventory_reservations
            WHERE order_id = ? ORDER BY sku_id{lock_clause}
            """,
            (order_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def confirm_reservations(self, connection, order_id: str) -> int:
        rows = self.reservation_rows(connection, order_id)
        confirmed = 0
        timestamp = now_iso()
        for row in rows:
            if row["status"] == "confirmed":
                continue
            if row["status"] != "reserved":
                raise ValueError("库存预占已释放，不能确认支付")
            quantity = int(row["quantity"])
            cursor = connection.execute(
                """
                UPDATE managed_materials
                SET stock = stock - ?, reserved_stock = reserved_stock - ?
                WHERE id = ? AND stock >= ? AND reserved_stock >= ?
                """,
                (quantity, quantity, row["sku_id"], quantity, quantity),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("库存预占确认失败，事务已回滚")
            connection.execute(
                """
                UPDATE inventory_reservations
                SET status = 'confirmed', confirmed_at = ?, updated_at = ?
                WHERE reservation_id = ? AND status = 'reserved'
                """,
                (timestamp, timestamp, row["reservation_id"]),
            )
            confirmed += 1
        return confirmed

    def release_reservations(self, connection, order_id: str, target_status: str = "released") -> int:
        if target_status not in {"released", "expired"}:
            raise ValueError("库存释放状态无效")
        rows = self.reservation_rows(connection, order_id)
        released = 0
        timestamp = now_iso()
        for row in rows:
            if row["status"] in {"released", "expired"}:
                continue
            if row["status"] == "confirmed":
                continue
            quantity = int(row["quantity"])
            cursor = connection.execute(
                """
                UPDATE managed_materials
                SET reserved_stock = reserved_stock - ?
                WHERE id = ? AND reserved_stock >= ?
                """,
                (quantity, row["sku_id"], quantity),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("库存预占释放失败，事务已回滚")
            connection.execute(
                """
                UPDATE inventory_reservations
                SET status = ?, released_at = ?, updated_at = ?
                WHERE reservation_id = ? AND status = 'reserved'
                """,
                (target_status, timestamp, timestamp, row["reservation_id"]),
            )
            released += 1
        return released

    def restock_confirmed_reservations(self, connection, order_id: str) -> int:
        rows = self.reservation_rows(connection, order_id)
        restocked = 0
        timestamp = now_iso()
        for row in rows:
            if row["status"] == "restocked":
                continue
            if row["status"] != "confirmed":
                continue
            quantity = int(row["quantity"])
            cursor = connection.execute(
                "UPDATE inventory_reservations "
                "SET status = 'restocked', released_at = ?, updated_at = ? "
                "WHERE reservation_id = ? AND status = 'confirmed'",
                (timestamp, timestamp, row["reservation_id"]),
            )
            if cursor.rowcount != 1:
                continue
            connection.execute(
                "UPDATE managed_materials SET stock = stock + ? WHERE id = ?",
                (quantity, row["sku_id"]),
            )
            restocked += 1
        return restocked

    def apply_refund_inventory_disposition(
        self,
        connection,
        order: dict[str, Any],
        refund: dict[str, Any],
    ) -> dict[str, Any]:
        updated = dict(refund)
        if updated.get("inventory_disposition") == "restocked":
            return updated
        source_status = str(updated.get("source_order_status") or "")
        is_full_refund = int(updated.get("refund_fee") or 0) == int(order.get("total_fee") or 0)
        has_tracking = bool((order.get("logistics") or {}).get("tracking_no"))
        if source_status == "pending_ship" and is_full_refund and not has_tracking:
            count = self.restock_confirmed_reservations(connection, order["order_id"])
            updated["inventory_disposition"] = "restocked"
            updated["restocked_reservation_count"] = count
            updated["restocked_at"] = now_iso()
        else:
            updated["inventory_disposition"] = "pending_manual_inspection"
        return updated

    def order_row_for_update(self, connection, order_id: str) -> dict[str, Any] | None:
        lock_clause = " FOR UPDATE" if self.mysql_transactions else ""
        row = connection.execute(
            f"SELECT * FROM orders WHERE order_id = ?{lock_clause}",
            (order_id,),
        ).fetchone()
        return dict(row) if row else None

    def fail_order_and_release(self, order_id: str, reason: str) -> None:
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                return
            order = self.public_order(row)
            if order["payment_status"] == "paid":
                return
            self.release_reservations(connection, order_id, "released")
            if order["status"] == "pending_payment":
                self.transition_order(
                    order,
                    "closed",
                    event_label=reason,
                    connection=connection,
                    payment_status="failed",
                )

    def expire_order_reservations(self, order_id: str, timestamp: str | None = None) -> dict[str, Any]:
        current = timestamp or now_iso()
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                return {"order_id": order_id, "released": 0, "missing": True}
            order = self.public_order(row)
            reservations = self.reservation_rows(connection, order_id)
            active = [row for row in reservations if row["status"] == "reserved" and row["expires_at"] <= current]
            if not active:
                return {"order_id": order_id, "released": 0, "missing": False}
            if order["payment_status"] == "paid":
                confirmed = self.confirm_reservations(connection, order_id)
                return {"order_id": order_id, "released": 0, "confirmed": confirmed}
            if order["payment_status"] == "processing":
                return {
                    "order_id": order_id,
                    "released": 0,
                    "deferred_processing": True,
                    "missing": False,
                }
            released = self.release_reservations(connection, order_id, "expired")
            if order["status"] == "pending_payment":
                self.transition_order(
                    order,
                    "closed",
                    event_label="订单超时，库存预占已释放",
                    connection=connection,
                    payment_status="expired",
                )
            return {"order_id": order_id, "released": released, "missing": False}

    def release_expired_reservations(self, limit: int = 100, timestamp: str | None = None) -> dict[str, Any]:
        current = timestamp or now_iso()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT order_id FROM inventory_reservations
                WHERE status = 'reserved' AND expires_at <= ?
                ORDER BY order_id LIMIT ?
                """,
                (current, max(1, min(int(limit), 1000))),
            ).fetchall()
        results = [self.expire_order_reservations(str(row["order_id"]), current) for row in rows]
        return {
            "processed_orders": len(results),
            "released_reservations": sum(int(item.get("released") or 0) for item in results),
            "deferred_processing": sum(
                1 for item in results if item.get("deferred_processing")
            ),
            "results": results,
        }

    def create_wechat_payment(self, order: dict[str, Any]) -> dict[str, Any]:
        if order.get("payment_status") == "paid":
            return {"available": False, "state": "already_paid", "message": "订单已支付", "pay_params": None}
        if not payment_enabled():
            return {
                "available": False,
                "state": "payment_disabled",
                "message": "微信支付当前未开放",
                "pay_params": None,
            }
        if not order.get("openid") or str(order["openid"]).startswith("dev_"):
            user = self.get_user(order["user_id"]) or {}
            refreshed_openid = user.get("openid")
            if refreshed_openid and not str(refreshed_openid).startswith("dev_"):
                with self.connect() as connection:
                    connection.execute(
                        "UPDATE orders SET openid = ?, updated_at = ? WHERE order_id = ?",
                        (refreshed_openid, now_iso(), order["order_id"]),
                    )
                order = {**order, "openid": refreshed_openid}
        config = WechatPayConfig()
        if not config.ready:
            return {
                "available": False,
                "state": "not_configured",
                "message": f"微信支付未配置：缺少 {', '.join(config.missing)}",
                "pay_params": None,
            }
        if not order.get("openid") or str(order["openid"]).startswith("dev_"):
            return {
                "available": False,
                "state": "openid_required",
                "message": "当前用户没有真实微信 openid，无法调起微信支付",
                "pay_params": None,
            }

        body = {
            "appid": config.app_id,
            "mchid": config.mch_id,
            "description": "宇涧水晶 DIY 手串",
            "out_trade_no": order["out_trade_no"],
            "notify_url": config.notify_url,
            "amount": {"total": int(order["total_fee"]), "currency": order["currency"]},
            "payer": {"openid": order["openid"]},
        }
        url_path = "/v3/pay/transactions/jsapi"
        response = self.wechat_request("POST", url_path, body, config, error_label="微信支付预下单失败")
        prepay_id = response["prepay_id"]
        pay_params = self.build_miniprogram_pay_params(prepay_id, config)
        payment = {
            "available": True,
            "state": "prepay_ready",
            "message": "微信支付预下单成功",
            "prepay_id": prepay_id,
            "pay_params": pay_params,
        }
        self.update_payment(
            order["order_id"],
            payment,
            provider="wechat_pay",
            appid=config.app_id or "",
            mchid=config.mch_id or "",
            currency=order.get("currency") or "CNY",
        )
        return payment

    def request_payment(self, order_id: str, user_id: str) -> dict[str, Any]:
        order = self.get_order(order_id)
        self.ensure_order_owner(order, user_id)
        if order.get("reservation_expires_at") and order["reservation_expires_at"] <= now_iso():
            self.expire_order_reservations(order_id)
            raise ValueError("订单已超时，请重新确认价格与库存")
        if order["status"] != "pending_payment" or order["payment_status"] != "unpaid":
            raise ValueError("当前订单状态不能继续支付")
        return {"order": order, "payment": self.create_wechat_payment(order)}

    def mark_paid_for_dev(self, order_id: str, user_id: str) -> dict[str, Any]:
        if not WechatPayConfig().test_mode:
            raise ValueError("正式环境已禁用模拟支付")
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            order = self.public_order(row)
            self.ensure_order_owner(order, user_id)
            if order["payment_status"] == "paid":
                return order
            self.confirm_reservations(connection, order_id)
            transaction_id = f"dev_{order_id}"
            paid_at = now_iso()
            payment = {
                **dict(order.get("payment") or {}),
                "provider": "dev_mock",
                "transaction_id": transaction_id,
                "trade_state": "SUCCESS",
                "success_time": paid_at,
            }
            connection.execute(
                """
                UPDATE orders
                SET payment_json = ?, payment_provider = 'dev_mock',
                    payment_transaction_id = ?, payment_currency = ?,
                    payment_confirmed_at = ?, updated_at = ?
                WHERE order_id = ?
                """,
                (
                    json.dumps(payment, ensure_ascii=False),
                    transaction_id,
                    order.get("currency") or "CNY",
                    paid_at,
                    paid_at,
                    order_id,
                ),
            )
            self.transition_order(
                order,
                "pending_ship",
                event_label="支付成功，等待商家发货",
                connection=connection,
                payment_status="paid",
                paid_at=paid_at,
            )
        return self.get_order(order_id)

    def mark_shipped_for_dev(
        self,
        order_id: str,
        user_id: str,
        carrier: str = "顺丰速运",
        tracking_no: str | None = None,
        carrier_code: str = "shunfeng",
        phone_tail: str | None = None,
    ) -> dict[str, Any]:
        if not WechatPayConfig().test_mode:
            raise ValueError("正式环境已禁用模拟发货")
        dev_tracking_no = str(tracking_no or "").strip() or (
            f"YJ{int(time.time())}{secrets.token_hex(3).upper()}"
        )
        return self.ship_paid_order(
            order_id,
            carrier=carrier,
            tracking_no=dev_tracking_no,
            carrier_code=carrier_code,
            phone_tail=phone_tail,
            source="dev",
            expected_user_id=user_id,
        )

    def ship_paid_order(
        self,
        order_id: str,
        carrier: str,
        tracking_no: str | None,
        carrier_code: str = "shunfeng",
        phone_tail: str | None = None,
        source: str = "admin",
        expected_user_id: str = "",
    ) -> dict[str, Any]:
        normalized_tracking = str(tracking_no or "").strip()
        if not normalized_tracking:
            raise ValueError("请填写快递单号")
        logistics = self.build_logistics(
            carrier,
            normalized_tracking,
            carrier_code,
            phone_tail,
            source=source,
        )
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            order = self.public_order(row)
            if expected_user_id:
                self.ensure_order_owner(order, expected_user_id)
            existing = dict(order.get("logistics") or {})
            if order["status"] == "shipped":
                if str(existing.get("tracking_no") or "").strip() == normalized_tracking:
                    return order
                raise OrderConflictError("订单已经发货，不能更换快递单号")
            if order["status"] != "pending_ship":
                raise ValueError("仅待发货订单可以发货")
            if order["payment_status"] != "paid":
                raise ValueError("订单未支付，不能发货")
            if order.get("refund_status") in {"requested", "approved", "submitting", "processing", "success"}:
                raise ValueError("订单正在退款或已退款，不能发货")
            self.transition_order(
                order,
                "shipped",
                event_label="商家已发货，等待快递揽收",
                connection=connection,
                logistics=logistics,
            )
        return self.get_order(order_id)

    def confirm_receipt(self, order_id: str, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            order = self.public_order(row)
            self.ensure_order_owner(order, user_id)
            if order["status"] == "completed":
                return order
            if order["status"] != "shipped":
                raise ValueError("订单尚未发货，不能确认收货")
            self.transition_order(
                order,
                "completed",
                event_label="用户确认收货",
                connection=connection,
            )
        return self.get_order(order_id)

    def cancel_order(self, order_id: str, user_id: str, reason: str = "") -> dict[str, Any]:
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            order = self.public_order(row)
            self.ensure_order_owner(order, user_id)
            if order["status"] == "closed":
                return order
            if order["status"] != "pending_payment" or order["payment_status"] != "unpaid":
                raise ValueError("仅待付款订单可以直接取消；已付款订单请申请退款")
            remark = f"{order.get('remark') or ''}\n取消原因：{reason or '用户主动取消'}".strip()
            self.release_reservations(connection, order_id, "released")
            self.transition_order(
                order,
                "closed",
                event_label="用户取消订单",
                connection=connection,
                remark=remark,
                payment_status="cancelled",
            )
        return self.get_order(order_id)

    def update_order_receiver(self, order_id: str, user_id: str, receiver: dict[str, Any]) -> dict[str, Any]:
        clean_receiver = self.normalize_order_receiver(receiver)
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            order = self.public_order(row)
            self.ensure_order_owner(order, user_id)
            if order["status"] not in {"pending_payment", "pending_ship"}:
                raise ValueError("订单已发货，不能修改收货地址")
            self.append_order_event(
                order,
                status=order["status"],
                label="用户修改收货地址",
                connection=connection,
            )
            connection.execute(
                """
                UPDATE orders SET receiver_json = ?, updated_at = ?
                WHERE order_id = ? AND status = ?
                """,
                (
                    json.dumps(clean_receiver, ensure_ascii=False),
                    now_iso(),
                    order_id,
                    order["status"],
                ),
            )
        return self.get_order(order_id)

    @staticmethod
    def after_sale_request_hash(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def public_after_sale_case(cls, row: dict[str, Any]) -> dict[str, Any]:
        requested_refund_fee = int(row.get("requested_refund_fee") or 0)
        approved_refund_fee = int(row.get("approved_refund_fee") or 0)
        return {
            "case_id": row["case_id"],
            "order_id": row["order_id"],
            "user_id": row["user_id"],
            "type": row["case_type"],
            "type_text": AFTER_SALE_TYPE_TEXT.get(row["case_type"], row["case_type"]),
            "reason_code": row["reason_code"],
            "reason_text": AFTER_SALE_REASON_TEXT.get(row["reason_code"], row["reason_code"]),
            "reason": row["reason"],
            "evidence_urls": cls.loads(row.get("evidence_json") or "", []),
            "order_snapshot": cls.loads(row.get("order_snapshot_json") or "", {}),
            "status": row["status"],
            "status_text": AFTER_SALE_STATUS_TEXT.get(row["status"], row["status"]),
            "requested_refund_fee": requested_refund_fee,
            "requested_refund_amount": cls.cents_text(requested_refund_fee),
            "approved_refund_fee": approved_refund_fee,
            "approved_refund_amount": cls.cents_text(approved_refund_fee),
            "resolution_type": row.get("resolution_type") or "",
            "review_note": row.get("review_note") or "",
            "reviewed_by": row.get("reviewed_by") or "",
            "reviewed_at": row.get("reviewed_at") or "",
            "resolved_at": row.get("resolved_at") or "",
            "return_carrier": row.get("return_carrier") or "",
            "return_tracking_no": row.get("return_tracking_no") or "",
            "return_submitted_at": row.get("return_submitted_at") or "",
            "canceled_at": row.get("canceled_at") or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_after_sale_cases(self, order_id: str, user_id: str) -> list[dict[str, Any]]:
        order = self.get_order(order_id)
        self.ensure_order_owner(order, user_id)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM after_sale_cases
                WHERE order_id = ? AND user_id = ?
                ORDER BY created_at DESC
                """,
                (order_id, user_id),
            ).fetchall()
        return [self.public_after_sale_case(dict(row)) for row in rows]

    def create_after_sale_case(
        self,
        order_id: str,
        user_id: str,
        case_type: str,
        reason_code: str,
        reason: str,
        evidence_urls: list[str] | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        normalized_type = str(case_type or "").strip()
        normalized_reason_code = str(reason_code or "").strip()
        normalized_reason = str(reason or "").strip()
        if normalized_type not in AFTER_SALE_TYPE_TEXT:
            raise ValueError("请选择有效的售后类型")
        if normalized_reason_code not in AFTER_SALE_REASON_CODES[normalized_type]:
            raise ValueError("请选择与售后类型匹配的问题原因")
        if len(normalized_reason) < 5:
            raise ValueError("请至少填写 5 个字的问题说明")
        if len(normalized_reason) > 500:
            raise ValueError("问题说明不能超过 500 个字")
        clean_evidence = []
        for raw_url in evidence_urls or []:
            url = str(raw_url or "").strip()
            if not url:
                continue
            if not url.startswith("https://") or len(url) > 2000:
                raise ValueError("售后凭证必须是有效的 HTTPS 地址")
            if url not in clean_evidence:
                clean_evidence.append(url)
        if len(clean_evidence) > 3:
            raise ValueError("售后凭证最多上传 3 张")
        key = self.normalize_idempotency_key(idempotency_key)
        request_payload = {
            "order_id": order_id,
            "type": normalized_type,
            "reason_code": normalized_reason_code,
            "reason": normalized_reason,
            "evidence_urls": clean_evidence,
        }
        request_hash = self.after_sale_request_hash(request_payload)
        timestamp = now_iso()
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            locked_row = self.order_row_for_update(connection, order_id)
            if not locked_row:
                raise ValueError("订单不存在")
            order = self.public_order(locked_row)
            self.ensure_order_owner(order, user_id)
            replay = connection.execute(
                "SELECT * FROM after_sale_cases WHERE user_id = ? AND idempotency_key = ?",
                (user_id, key),
            ).fetchone()
            if replay:
                replay_row = dict(replay)
                if replay_row["request_hash"] != request_hash:
                    raise OrderConflictError("同一提交标识不能用于不同的售后申请")
                return self.public_after_sale_case(replay_row)
            if order["payment_status"] != "paid":
                raise ValueError("只有已支付订单可以申请售后")
            if order["status"] not in {"shipped", "completed"}:
                raise ValueError("当前订单状态暂不能申请售后")
            if order.get("refund_status") in {"processing", "success"}:
                raise ValueError("订单退款正在处理或已完成，不能重复申请售后")
            placeholders = ",".join("?" for _ in AFTER_SALE_ACTIVE_STATUSES)
            active = connection.execute(
                f"""
                SELECT case_id FROM after_sale_cases
                WHERE order_id = ? AND status IN ({placeholders})
                LIMIT 1
                """,
                (order_id, *sorted(AFTER_SALE_ACTIVE_STATUSES)),
            ).fetchone()
            if active:
                raise OrderConflictError("该订单已有进行中的售后申请")
            case_id = f"AS{int(time.time() * 1000)}{secrets.token_hex(3).upper()}"
            event_id = f"ase_{secrets.token_hex(12)}"
            requested_refund_fee = int(order.get("total_fee") or 0) if normalized_type == "return_refund" else 0
            order_snapshot = {
                "order_id": order["order_id"],
                "out_trade_no": order.get("out_trade_no") or "",
                "status": order["status"],
                "payment_status": order["payment_status"],
                "total_fee": int(order.get("total_fee") or 0),
                "total_amount": order.get("total_amount") or "0.00",
                "currency": order.get("currency") or "CNY",
                "design_id": order.get("design_id") or "",
                "receiver": order.get("receiver") or {},
                "sequence": order.get("sequence") or [],
                "bom": order.get("bom") or [],
            }
            connection.execute(
                """
                INSERT INTO after_sale_cases
                (case_id, order_id, user_id, case_type, reason_code, reason, evidence_json,
                 order_snapshot_json, status, requested_refund_fee, approved_refund_fee,
                 resolution_type, review_note, reviewed_by, reviewed_at, resolved_at,
                 idempotency_key, request_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'requested', ?, 0, '', '', '', NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    case_id, order_id, user_id, normalized_type, normalized_reason_code,
                    normalized_reason, json.dumps(clean_evidence, ensure_ascii=False),
                    json.dumps(order_snapshot, ensure_ascii=False), requested_refund_fee,
                    key, request_hash, timestamp, timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO after_sale_events
                (event_id, case_id, event_type, from_status, to_status, operator_type,
                 operator_id, note, created_at)
                VALUES (?, ?, 'submitted', '', 'requested', 'user', ?, ?, ?)
                """,
                (event_id, case_id, user_id, normalized_reason, timestamp),
            )
            connection.execute(
                "UPDATE orders SET after_sale_status = 'requested', updated_at = ? WHERE order_id = ?",
                (timestamp, order_id),
            )
            created = connection.execute(
                "SELECT * FROM after_sale_cases WHERE case_id = ?",
                (case_id,),
            ).fetchone()
        return self.public_after_sale_case(dict(created))

    def submit_after_sale_return_shipment(
        self,
        order_id: str,
        case_id: str,
        user_id: str,
        carrier: str,
        tracking_no: str,
    ) -> dict[str, Any]:
        normalized_carrier = str(carrier or "").strip()
        normalized_tracking = str(tracking_no or "").strip()
        if not normalized_carrier or len(normalized_carrier) > 50:
            raise ValueError("请填写有效的退回快递公司")
        if len(normalized_tracking) < 6 or len(normalized_tracking) > 80:
            raise ValueError("请填写有效的退回快递单号")
        timestamp = now_iso()
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            order_row = self.order_row_for_update(connection, order_id)
            if not order_row:
                raise ValueError("订单不存在")
            order = self.public_order(order_row)
            self.ensure_order_owner(order, user_id)
            case_row = self.after_sale_case_row_for_update(connection, case_id)
            if not case_row or case_row["order_id"] != order_id or case_row["user_id"] != user_id:
                raise ValueError("售后工单不存在")
            if case_row["case_type"] != "return_refund":
                raise ValueError("当前售后工单不需要寄回商品")
            if case_row["status"] == "returning":
                if (
                    str(case_row.get("return_carrier") or "") == normalized_carrier
                    and str(case_row.get("return_tracking_no") or "") == normalized_tracking
                ):
                    return self.public_after_sale_case(case_row)
                raise OrderConflictError("退回物流已提交，不能更换快递单号")
            if case_row["status"] != "awaiting_return":
                raise ValueError("当前售后工单不能提交退回物流")
            connection.execute(
                """
                UPDATE after_sale_cases
                SET status = 'returning', return_carrier = ?, return_tracking_no = ?,
                    return_submitted_at = ?, updated_at = ?
                WHERE case_id = ? AND status = 'awaiting_return'
                """,
                (normalized_carrier, normalized_tracking, timestamp, timestamp, case_id),
            )
            connection.execute(
                "UPDATE orders SET after_sale_status = 'returning', updated_at = ? WHERE order_id = ?",
                (timestamp, order_id),
            )
            self.append_after_sale_event(
                connection,
                case_id,
                "return_shipped",
                "awaiting_return",
                "returning",
                user_id,
                f"{normalized_carrier} {normalized_tracking}",
                operator_type="user",
            )
            updated = self.after_sale_case_row_for_update(connection, case_id)
        return self.public_after_sale_case(updated)

    def cancel_after_sale_case(
        self,
        order_id: str,
        case_id: str,
        user_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        normalized_reason = str(reason or "用户取消售后申请").strip()[:500]
        timestamp = now_iso()
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            order_row = self.order_row_for_update(connection, order_id)
            if not order_row:
                raise ValueError("订单不存在")
            order = self.public_order(order_row)
            self.ensure_order_owner(order, user_id)
            case_row = self.after_sale_case_row_for_update(connection, case_id)
            if not case_row or case_row["order_id"] != order_id or case_row["user_id"] != user_id:
                raise ValueError("售后工单不存在")
            if case_row["status"] == "canceled":
                return self.public_after_sale_case(case_row)
            if case_row["status"] not in {"requested", "awaiting_return"}:
                raise ValueError("当前售后工单已进入处理，不能取消")
            previous = case_row["status"]
            connection.execute(
                """
                UPDATE after_sale_cases
                SET status = 'canceled', canceled_at = ?, resolved_at = ?, updated_at = ?
                WHERE case_id = ? AND status = ?
                """,
                (timestamp, timestamp, timestamp, case_id, previous),
            )
            connection.execute(
                "UPDATE orders SET after_sale_status = 'canceled', updated_at = ? WHERE order_id = ?",
                (timestamp, order_id),
            )
            self.append_after_sale_event(
                connection,
                case_id,
                "canceled",
                previous,
                "canceled",
                user_id,
                normalized_reason,
                operator_type="user",
            )
            updated = self.after_sale_case_row_for_update(connection, case_id)
        return self.public_after_sale_case(updated)

    def admin_list_after_sale_cases(
        self,
        keyword: str = "",
        status: str = "",
        case_type: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        normalized_status = str(status or "").strip()
        normalized_type = str(case_type or "").strip()
        if normalized_status and normalized_status not in AFTER_SALE_STATUS_TEXT:
            raise ValueError("不支持的售后状态")
        if normalized_type and normalized_type not in AFTER_SALE_TYPE_TEXT:
            raise ValueError("不支持的售后类型")
        clauses: list[str] = []
        params: list[Any] = []
        if normalized_status:
            clauses.append("c.status = ?")
            params.append(normalized_status)
        if normalized_type:
            clauses.append("c.case_type = ?")
            params.append(normalized_type)
        normalized_keyword = str(keyword or "").strip()
        if normalized_keyword:
            value = f"%{normalized_keyword}%"
            clauses.append(
                "(c.case_id LIKE ? OR c.order_id LIKE ? OR c.user_id LIKE ? "
                "OR c.reason LIKE ? OR o.receiver_json LIKE ?)"
            )
            params.extend([value, value, value, value, value])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(int(limit or 100), 500)))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT c.*, o.status AS current_order_status,
                       o.payment_status AS current_payment_status,
                       o.total_fee AS current_total_fee,
                       o.receiver_json AS current_receiver_json,
                       o.refund_status AS current_refund_status,
                       o.refund_json AS current_refund_json
                FROM after_sale_cases c
                LEFT JOIN orders o ON o.order_id = c.order_id
                {where}
                ORDER BY
                  CASE c.status
                    WHEN 'requested' THEN 0
                    WHEN 'awaiting_return' THEN 1
                    WHEN 'returning' THEN 2
                    WHEN 'service_processing' THEN 3
                    WHEN 'refund_pending' THEN 4
                    WHEN 'refund_submitting' THEN 5
                    WHEN 'refunding' THEN 6
                    ELSE 7
                  END,
                  c.created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        result = []
        for raw_row in rows:
            row = dict(raw_row)
            item = self.public_after_sale_case(row)
            order_status = row.get("current_order_status") or ""
            total_fee = int(row.get("current_total_fee") or 0)
            item["order"] = {
                "status": order_status,
                "status_text": ORDER_STATUS_TEXT.get(order_status, order_status),
                "payment_status": row.get("current_payment_status") or "",
                "total_fee": total_fee,
                "total_amount": self.cents_text(total_fee),
                "receiver": self.loads(row.get("current_receiver_json") or "", {}),
                "refund_status": row.get("current_refund_status") or "",
                "refund": self.loads(row.get("current_refund_json") or "", {}),
            }
            result.append(item)
        return result

    def admin_get_after_sale_case(self, case_id: str) -> dict[str, Any]:
        normalized_case_id = str(case_id or "").strip()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM after_sale_cases WHERE case_id = ?",
                (normalized_case_id,),
            ).fetchone()
            if not row:
                raise ValueError("售后工单不存在")
            events = connection.execute(
                """
                SELECT event_id, event_type, from_status, to_status, operator_type,
                       operator_id, note, created_at
                FROM after_sale_events
                WHERE case_id = ?
                ORDER BY created_at ASC, event_id ASC
                """,
                (normalized_case_id,),
            ).fetchall()
        item = self.public_after_sale_case(dict(row))
        item["order"] = self.get_order(item["order_id"])
        item["events"] = [dict(event) for event in events]
        return item

    def after_sale_case_row_for_update(self, connection, case_id: str) -> dict[str, Any] | None:
        lock_clause = " FOR UPDATE" if self.mysql_transactions else ""
        row = connection.execute(
            f"SELECT * FROM after_sale_cases WHERE case_id = ?{lock_clause}",
            (case_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def append_after_sale_event(
        connection,
        case_id: str,
        event_type: str,
        from_status: str,
        to_status: str,
        operator_id: str,
        note: str,
        operator_type: str = "admin",
    ) -> None:
        connection.execute(
            """
            INSERT INTO after_sale_events
            (event_id, case_id, event_type, from_status, to_status, operator_type,
             operator_id, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"ase_{secrets.token_hex(12)}", case_id, event_type, from_status, to_status,
                operator_type, operator_id, note, datetime.now(timezone.utc).isoformat(),
            ),
        )

    def prepare_after_sale_refund(
        self,
        connection,
        case_row: dict[str, Any],
        order: dict[str, Any],
        operator: str,
        note: str,
    ) -> None:
        if case_row["case_type"] != "return_refund":
            raise ValueError("只有退货退款工单可以进入退款流程")
        if order["payment_status"] != "paid":
            raise ValueError("订单未处于已支付状态，不能准备退款")
        if order["status"] not in {"shipped", "completed"}:
            raise ValueError("订单当前履约状态不能进入退款流程")
        refund = dict(order.get("refund") or {})
        if order.get("refund_status") in {"requested", "approved", "submitting", "processing", "success"} or refund.get("status") in {
            "requested", "approved", "submitting", "processing", "success"
        }:
            raise ValueError("订单已有退款流程，不能重复准备退款")
        total_fee = int(order.get("total_fee") or 0)
        approved_fee = int(case_row.get("requested_refund_fee") or total_fee)
        if total_fee <= 0 or approved_fee <= 0 or approved_fee > total_fee:
            raise ValueError("退款金额异常，不能进入退款流程")
        timestamp = now_iso()
        refund.update(
            {
                "after_sale_case_id": case_row["case_id"],
                "status": "approved",
                "reason": case_row["reason"],
                "requested_at": case_row["created_at"],
                "prepared_at": timestamp,
                "approved_by": operator,
                "approve_note": note,
                "out_refund_no": f"RF{case_row['case_id']}"[:64],
                "refund_fee": approved_fee,
                "total_fee": total_fee,
                "currency": order.get("currency") or "CNY",
                "source_order_status": order["status"],
            }
        )
        self.transition_order(
            order,
            "refund_requested",
            event_label="售后审核通过，等待运营确认原路退款",
            connection=connection,
            after_sale_status="refund_pending",
            refund_status="approved",
            refund=refund,
        )

    def review_after_sale_case(
        self,
        case_id: str,
        action: str,
        operator: str,
        note: str = "",
    ) -> dict[str, Any]:
        normalized_action = str(action or "").strip()
        normalized_operator = str(operator or "admin").strip()[:100] or "admin"
        normalized_note = str(note or "").strip()
        if len(normalized_note) > 500:
            raise ValueError("审核备注不能超过 500 个字")
        if normalized_action == "reject" and len(normalized_note) < 2:
            raise ValueError("请填写拒绝原因")
        timestamp = now_iso()
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            case_lookup = connection.execute(
                "SELECT order_id FROM after_sale_cases WHERE case_id = ?",
                (case_id,),
            ).fetchone()
            if not case_lookup:
                raise ValueError("售后工单不存在")
            order_row = self.order_row_for_update(connection, case_lookup["order_id"])
            if not order_row:
                raise ValueError("关联订单不存在")
            order = self.public_order(order_row)
            case_row = self.after_sale_case_row_for_update(connection, case_id)
            if not case_row or case_row["order_id"] != order["order_id"]:
                raise OrderConflictError("售后工单关联订单已变化，请刷新后重试")
            current_status = case_row["status"]
            event_type = normalized_action
            resolution_type = case_row.get("resolution_type") or ""
            resolved_at = case_row.get("resolved_at")

            if normalized_action == "reject":
                if current_status != "requested":
                    raise ValueError("只有待审核工单可以拒绝")
                target_status = "rejected"
                resolution_type = "rejected"
                resolved_at = timestamp
            elif normalized_action == "approve_service":
                if current_status != "requested" or case_row["case_type"] == "return_refund":
                    raise ValueError("当前工单不能接受为服务处理")
                target_status = "service_processing"
                resolution_type = case_row["case_type"]
            elif normalized_action == "request_return":
                if current_status != "requested" or case_row["case_type"] != "return_refund":
                    raise ValueError("当前工单不能要求寄回商品")
                target_status = "awaiting_return"
                resolution_type = "return_refund"
            elif normalized_action == "prepare_direct_refund":
                if current_status != "requested" or case_row["case_type"] != "return_refund":
                    raise ValueError("当前工单不能免退进入退款")
                target_status = "refund_pending"
                resolution_type = "direct_refund"
                self.prepare_after_sale_refund(connection, case_row, order, normalized_operator, normalized_note)
            elif normalized_action == "confirm_return":
                if current_status not in {"awaiting_return", "returning"} or case_row["case_type"] != "return_refund":
                    raise ValueError("当前工单不能确认收货")
                target_status = "refund_pending"
                resolution_type = "return_refund"
                self.prepare_after_sale_refund(connection, case_row, order, normalized_operator, normalized_note)
            elif normalized_action == "complete":
                if current_status != "service_processing":
                    raise ValueError("只有处理中的服务工单可以完成")
                target_status = "resolved"
                resolved_at = timestamp
            else:
                raise ValueError("不支持的售后审核操作")

            approved_fee = int(case_row.get("approved_refund_fee") or 0)
            if target_status == "refund_pending":
                approved_fee = int(case_row.get("requested_refund_fee") or order.get("total_fee") or 0)
            connection.execute(
                """
                UPDATE after_sale_cases
                SET status = ?, approved_refund_fee = ?, resolution_type = ?, review_note = ?,
                    reviewed_by = ?, reviewed_at = ?, resolved_at = ?, updated_at = ?
                WHERE case_id = ?
                """,
                (
                    target_status, approved_fee, resolution_type, normalized_note,
                    normalized_operator, timestamp, resolved_at, timestamp, case_id,
                ),
            )
            self.append_after_sale_event(
                connection,
                case_id,
                event_type,
                current_status,
                target_status,
                normalized_operator,
                normalized_note,
            )
            if target_status != "refund_pending":
                connection.execute(
                    "UPDATE orders SET after_sale_status = ?, updated_at = ? WHERE order_id = ?",
                    (target_status, timestamp, order["order_id"]),
                )
        return self.admin_get_after_sale_case(case_id)

    def resolve_linked_after_sale_case(
        self,
        connection,
        order: dict[str, Any],
        operator: str = "wechat",
    ) -> None:
        refund = dict(order.get("refund") or {})
        case_id = str(refund.get("after_sale_case_id") or "").strip()
        if not case_id:
            return
        refund_status = str(order.get("refund_status") or refund.get("status") or "").lower()
        if refund_status not in {"submitting", "processing", "success", "abnormal", "closed"}:
            return
        timestamp = now_iso()
        case_row = self.after_sale_case_row_for_update(connection, case_id)
        if not case_row:
            raise ValueError("退款关联的售后工单不存在")
        if case_row["order_id"] != order["order_id"]:
            raise ValueError("退款与售后工单关联不一致")
        if refund_status == "submitting":
            if case_row["status"] == "refund_pending":
                connection.execute(
                    "UPDATE after_sale_cases SET status = 'refund_submitting', updated_at = ? WHERE case_id = ?",
                    (timestamp, case_id),
                )
                connection.execute(
                    "UPDATE orders SET after_sale_status = 'refund_submitting', updated_at = ? WHERE order_id = ?",
                    (timestamp, order["order_id"]),
                )
                self.append_after_sale_event(
                    connection,
                    case_id,
                    "refund_submitting",
                    "refund_pending",
                    "refund_submitting",
                    str(operator or "system")[:100],
                    "退款指令已登记，等待微信接口结果",
                    operator_type="system",
                )
                return
            if case_row["status"] != "refund_submitting":
                raise ValueError("售后工单当前状态不能提交退款")
            return
        if refund_status == "processing":
            if case_row["status"] in {"refund_pending", "refund_submitting"}:
                previous = case_row["status"]
                connection.execute(
                    "UPDATE after_sale_cases SET status = 'refunding', updated_at = ? WHERE case_id = ?",
                    (timestamp, case_id),
                )
                connection.execute(
                    "UPDATE orders SET after_sale_status = 'refunding', updated_at = ? WHERE order_id = ?",
                    (timestamp, order["order_id"]),
                )
                self.append_after_sale_event(
                    connection,
                    case_id,
                    "refund_submitted",
                    previous,
                    "refunding",
                    str(operator or "wechat")[:100],
                    "已提交微信原路退款",
                    operator_type="system",
                )
                return
            if case_row["status"] != "refunding":
                raise ValueError("售后工单当前状态不能进入退款处理")
            return
        if refund_status in {"abnormal", "closed"}:
            if case_row["status"] in {"refund_submitting", "refunding"}:
                previous = case_row["status"]
                connection.execute(
                    "UPDATE after_sale_cases SET status = 'refund_pending', updated_at = ? WHERE case_id = ?",
                    (timestamp, case_id),
                )
                connection.execute(
                    "UPDATE orders SET after_sale_status = 'refund_pending', updated_at = ? WHERE order_id = ?",
                    (timestamp, order["order_id"]),
                )
                self.append_after_sale_event(
                    connection,
                    case_id,
                    "refund_failed",
                    previous,
                    "refund_pending",
                    str(operator or "wechat")[:100],
                    f"微信退款状态为 {refund_status.upper()}，已退回待确认退款",
                    operator_type="system",
                )
                return
            if case_row["status"] != "refund_pending":
                raise ValueError("售后工单当前状态不能恢复退款")
            return
        if case_row["status"] == "resolved":
            connection.execute(
                "UPDATE orders SET after_sale_status = 'resolved', updated_at = ? WHERE order_id = ?",
                (timestamp, order["order_id"]),
            )
            return
        if case_row["status"] not in {"refund_pending", "refund_submitting", "refunding"}:
            raise ValueError("售后工单当前状态不能完成退款")
        connection.execute(
            """
            UPDATE after_sale_cases
            SET status = 'resolved', resolved_at = ?, updated_at = ?
            WHERE case_id = ?
            """,
            (timestamp, timestamp, case_id),
        )
        connection.execute(
            "UPDATE orders SET after_sale_status = 'resolved', updated_at = ? WHERE order_id = ?",
            (timestamp, order["order_id"]),
        )
        self.append_after_sale_event(
            connection,
            case_id,
            "refund_success",
            case_row["status"],
            "resolved",
            str(operator or "wechat")[:100],
            "微信原路退款成功",
            operator_type="system",
        )

    def sync_linked_after_sale_case(self, order: dict[str, Any], operator: str = "wechat") -> None:
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order["order_id"])
            if not row:
                raise ValueError("订单不存在")
            self.resolve_linked_after_sale_case(connection, self.public_order(row), operator)

    def submit_after_sale_refund(self, case_id: str, operator: str, note: str = "") -> dict[str, Any]:
        case = self.admin_get_after_sale_case(case_id)
        if case["type"] != "return_refund" or case["status"] != "refund_pending":
            raise ValueError("当前售后工单不能发起退款")
        refund = dict((case.get("order") or {}).get("refund") or {})
        if refund.get("after_sale_case_id") != case_id:
            raise ValueError("订单退款记录与售后工单不一致")
        self.approve_refund(
            case["order_id"],
            operator=operator,
            note=note,
            expected_after_sale_case_id=case_id,
        )
        return self.admin_get_after_sale_case(case_id)

    def sync_after_sale_refund(self, case_id: str, operator: str) -> dict[str, Any]:
        case = self.admin_get_after_sale_case(case_id)
        if case["type"] != "return_refund" or case["status"] not in {
            "refund_pending", "refund_submitting", "refunding"
        }:
            raise ValueError("当前售后工单不能同步退款")
        refund = dict((case.get("order") or {}).get("refund") or {})
        if refund.get("after_sale_case_id") != case_id:
            raise ValueError("订单退款记录与售后工单不一致")
        order = self.sync_wechat_refund(case["order_id"], operator=operator)
        self.sync_linked_after_sale_case(order, operator=operator)
        return self.admin_get_after_sale_case(case_id)

    def retry_after_sale_refund(self, case_id: str, operator: str, note: str = "") -> dict[str, Any]:
        case = self.admin_get_after_sale_case(case_id)
        if case["type"] != "return_refund" or case["status"] not in {
            "refund_pending", "refund_submitting", "refunding"
        }:
            raise ValueError("当前售后工单不能恢复退款")
        refund = dict((case.get("order") or {}).get("refund") or {})
        if refund.get("after_sale_case_id") != case_id:
            raise ValueError("订单退款记录与售后工单不一致")
        self.retry_refund_submission(
            case["order_id"],
            operator=operator,
            note=note,
            expected_after_sale_case_id=case_id,
        )
        return self.admin_get_after_sale_case(case_id)

    def request_refund(self, order_id: str, user_id: str, reason: str = "") -> dict[str, Any]:
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            order = self.public_order(row)
            self.ensure_order_owner(order, user_id)
            if order["payment_status"] != "paid":
                raise ValueError("未支付订单不能申请退款")
            if order["status"] == "refund_requested":
                refund = dict(order.get("refund") or {})
                if refund.get("source_order_status") == "pending_ship" and not refund.get("after_sale_case_id"):
                    return order
                raise OrderConflictError("订单已进入其他退款流程，请刷新后查看")
            if order["status"] != "pending_ship":
                raise ValueError("仅待发货订单可直接申请退款；已发货订单请申请退货退款")
            requested_at = now_iso()
            refund = {
                **(order.get("refund") or {}),
                "status": "requested",
                "out_refund_no": str((order.get("refund") or {}).get("out_refund_no") or f"RF{order_id}")[:64],
                "reason": reason or "用户申请退款",
                "requested_at": requested_at,
                "source_order_status": order["status"],
                "refund_fee": int(order.get("total_fee") or self.to_cents(Decimal(str(order.get("total_amount") or 0)))),
                "total_fee": int(order.get("total_fee") or 0),
                "currency": order.get("currency") or "CNY",
            }
            remark = f"{order.get('remark') or ''}\n退款原因：{reason}".strip()
            self.transition_order(
                order,
                "refund_requested",
                event_label="用户申请退款",
                connection=connection,
                remark=remark,
                refund_status="requested",
                refund=refund,
            )
        return self.get_order(order_id)

    def approve_refund(
        self,
        order_id: str,
        operator: str = "",
        note: str = "",
        expected_after_sale_case_id: str = "",
    ) -> dict[str, Any]:
        config = WechatPayConfig()
        if not config.ready:
            raise ValueError(f"微信支付未配置：缺少 {', '.join(config.missing)}")

        linked_case_id = ""
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            order = self.public_order(row)
            if order["status"] != "refund_requested":
                raise ValueError("仅退款申请中的订单可以同意退款")
            if order["payment_status"] != "paid":
                raise ValueError("订单未处于已支付状态，不能发起原路退款")
            refund = dict(order.get("refund") or {})
            current_refund_status = str(order.get("refund_status") or refund.get("status") or "").lower()
            if current_refund_status in {"submitting", "processing", "success"}:
                raise OrderConflictError("退款已提交，请同步微信退款状态，不要重复发起")
            if current_refund_status in {"abnormal", "closed"}:
                raise OrderConflictError("原退款未生效，请使用退款恢复入口核对后重试")
            if current_refund_status not in {"requested", "approved"}:
                raise ValueError("退款状态异常，不能发起原路退款")
            linked_case_id = str(refund.get("after_sale_case_id") or "").strip()
            if linked_case_id and not expected_after_sale_case_id:
                raise ValueError("该退款来自售后工单，请在售后审核页确认退款")
            if expected_after_sale_case_id and linked_case_id != expected_after_sale_case_id:
                raise ValueError("订单退款记录与售后工单不一致")
            if linked_case_id:
                case_row = self.after_sale_case_row_for_update(connection, linked_case_id)
                if not case_row or case_row["order_id"] != order_id:
                    raise ValueError("订单退款记录与售后工单不一致")
                if case_row["status"] != "refund_pending":
                    raise OrderConflictError("售后退款状态已更新，请刷新后重试")
            total_fee = int(order.get("total_fee") or self.to_cents(Decimal(str(order.get("total_amount") or 0))))
            if total_fee <= 0:
                raise ValueError("订单金额异常，不能退款")
            refund_fee = int(refund.get("refund_fee") or total_fee)
            if refund_fee <= 0 or refund_fee > total_fee:
                raise ValueError("退款金额异常，不能超过原订单金额")
            out_refund_no = str(refund.get("out_refund_no") or f"RF{order['order_id']}")[:64]
            timestamp = now_iso()
            refund.update(
                {
                    "status": "submitting",
                    "out_refund_no": out_refund_no,
                    "refund_fee": refund_fee,
                    "total_fee": total_fee,
                    "currency": order.get("currency") or "CNY",
                    "approved_at": timestamp,
                    "approved_by": operator,
                    "approve_note": note,
                    "submission_started_at": timestamp,
                    "submission_attempt_id": secrets.token_hex(12),
                    "submission_attempts": int(refund.get("submission_attempts") or 0) + 1,
                }
            )
            self.append_order_event(
                order,
                status=order["status"],
                label="退款指令已登记，等待微信接口结果",
                connection=connection,
                refund_status="submitting",
                refund=refund,
            )
            self.resolve_linked_after_sale_case(
                connection,
                {**order, "refund_status": "submitting", "refund": refund},
                operator=operator or "admin",
            )

        response = self.create_wechat_refund(
            order,
            out_refund_no,
            refund_fee,
            total_fee,
            note or refund.get("reason") or "用户申请退款",
            config,
        )
        return self.finalize_wechat_refund_submission(
            order_id,
            out_refund_no,
            response,
            operator=operator or "admin",
        )

    def finalize_wechat_refund_submission(
        self,
        order_id: str,
        out_refund_no: str,
        response: dict[str, Any],
        *,
        operator: str,
    ) -> dict[str, Any]:
        wechat_status = str(response.get("status") or response.get("refund_status") or "PROCESSING").upper()
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            current_order = self.public_order(row)
            current_refund = dict(current_order.get("refund") or {})
            if str(current_refund.get("out_refund_no") or "") != out_refund_no:
                raise OrderConflictError("退款单号已变化，请人工核对")
            if (
                current_order["status"] == "refunded"
                and current_order["payment_status"] == "refunded"
                and str(current_order.get("refund_status") or current_refund.get("status") or "").lower() == "success"
            ):
                return current_order
            if current_order["status"] != "refund_requested" or current_order["payment_status"] != "paid":
                raise OrderConflictError("退款返回期间订单状态已变化，请人工核对")
            current_refund.update(
                {
                    "status": {
                        "SUCCESS": "success",
                        "PROCESSING": "processing",
                        "ABNORMAL": "abnormal",
                        "CLOSED": "closed",
                    }.get(wechat_status, "unknown"),
                    "wechat_status": wechat_status,
                    "wechat_response": response,
                    "submission_finished_at": now_iso(),
                }
            )
            amount = response.get("amount") or {
                "refund": current_refund.get("refund_fee") or 0,
                "total": current_refund.get("total_fee") or current_order.get("total_fee") or 0,
            }
            current_order = {
                **current_order,
                "refund": current_refund,
                "refund_status": current_refund["status"],
            }
            self.apply_wechat_refund_result(
                current_order,
                {
                    **response,
                    "status": wechat_status,
                    "out_refund_no": out_refund_no,
                    "amount": amount,
                },
                "后台提交微信退款",
                connection=connection,
            )
        return self.get_order(order_id)

    def retry_refund_submission(
        self,
        order_id: str,
        operator: str = "",
        note: str = "",
        expected_after_sale_case_id: str = "",
    ) -> dict[str, Any]:
        order = self.get_order(order_id)
        if order.get("status") != "refund_requested" or order.get("payment_status") != "paid":
            raise ValueError("当前订单不能恢复退款提交")
        refund = dict(order.get("refund") or {})
        current_refund_status = str(order.get("refund_status") or refund.get("status") or "").lower()
        if current_refund_status not in {"submitting", "processing", "abnormal", "closed", "success"}:
            raise ValueError("退款尚未提交微信，不能同步退款状态")
        out_refund_no = str(refund.get("out_refund_no") or "").strip()
        if not out_refund_no or len(out_refund_no) > 64:
            raise ValueError("退款单号缺失或非法，不能恢复退款提交")
        linked_case_id = str(refund.get("after_sale_case_id") or "").strip()
        if linked_case_id and not expected_after_sale_case_id:
            raise ValueError("该退款来自售后工单，请在售后审核页恢复退款")
        if expected_after_sale_case_id and linked_case_id != expected_after_sale_case_id:
            raise ValueError("订单退款记录与售后工单不一致")

        query_not_found = False
        try:
            synced = self.sync_wechat_refund(order_id, operator=operator)
        except WechatPayRequestError as exc:
            if not exc.resource_not_found:
                raise
            query_not_found = True
        else:
            synced_status = str(synced.get("refund_status") or (synced.get("refund") or {}).get("status") or "").lower()
            if synced_status not in {"abnormal", "closed"}:
                return synced

        config = WechatPayConfig()
        if not config.ready:
            raise ValueError(f"微信支付未配置：缺少 {', '.join(config.missing)}")

        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            current_order = self.public_order(row)
            if current_order["status"] != "refund_requested" or current_order["payment_status"] != "paid":
                raise OrderConflictError("退款状态已更新，请刷新后重试")
            current_refund = dict(current_order.get("refund") or {})
            if str(current_refund.get("out_refund_no") or "") != out_refund_no:
                raise OrderConflictError("退款单号已变化，请人工核对")
            current_status = str(current_order.get("refund_status") or current_refund.get("status") or "").lower()
            if query_not_found:
                if current_status != "submitting":
                    raise OrderConflictError("退款状态已更新，请先同步微信结果")
                started_at = self.parse_utc_datetime(current_refund.get("submission_started_at"))
                if started_at is None:
                    raise ValueError("退款提交时间缺失，请人工核对")
                elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
                if elapsed < REFUND_SUBMISSION_RETRY_DELAY_SECONDS:
                    remaining = max(1, int(REFUND_SUBMISSION_RETRY_DELAY_SECONDS - elapsed))
                    raise OrderConflictError(f"退款指令仍在保护期，请 {remaining} 秒后再次核对")
            elif current_status not in {"abnormal", "closed"}:
                raise OrderConflictError("退款状态已更新，请先同步微信结果")

            total_fee = int(current_refund.get("total_fee") or current_order.get("total_fee") or 0)
            refund_fee = int(current_refund.get("refund_fee") or 0)
            if total_fee <= 0 or refund_fee <= 0 or refund_fee > total_fee:
                raise ValueError("退款金额异常，不能恢复退款提交")

            if linked_case_id:
                case_row = self.after_sale_case_row_for_update(connection, linked_case_id)
                if not case_row or case_row["order_id"] != order_id:
                    raise ValueError("订单退款记录与售后工单不一致")
                allowed_case_statuses = {"refund_submitting"} if query_not_found else {"refund_pending"}
                if case_row["status"] not in allowed_case_statuses:
                    raise OrderConflictError("售后退款状态已更新，请刷新后重试")

            timestamp = now_iso()
            current_refund.update(
                {
                    "status": "submitting",
                    "submission_started_at": timestamp,
                    "submission_attempt_id": secrets.token_hex(12),
                    "submission_attempts": int(current_refund.get("submission_attempts") or 0) + 1,
                    "last_recovery_query": "not_found" if query_not_found else current_status,
                    "recovery_note": str(note or "核对微信退款结果后恢复提交")[:500],
                    "recovered_by": str(operator or "admin")[:100],
                }
            )
            self.append_order_event(
                current_order,
                status=current_order["status"],
                label="微信退款未生效，使用原退款单号恢复提交",
                connection=connection,
                refund_status="submitting",
                refund=current_refund,
            )
            claimed_order = {
                **current_order,
                "refund_status": "submitting",
                "refund": current_refund,
            }
            self.resolve_linked_after_sale_case(
                connection,
                claimed_order,
                operator=operator or "admin",
            )

        response = self.create_wechat_refund(
            claimed_order,
            out_refund_no,
            refund_fee,
            total_fee,
            note or current_refund.get("reason") or "用户申请退款",
            config,
        )
        return self.finalize_wechat_refund_submission(
            order_id,
            out_refund_no,
            response,
            operator=operator or "admin",
        )

    def reject_refund(self, order_id: str, operator: str = "", note: str = "") -> dict[str, Any]:
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            order = self.public_order(row)
            if order["status"] != "refund_requested":
                raise ValueError("仅退款申请中的订单可以拒绝退款")
            refund = dict(order.get("refund") or {})
            if refund.get("after_sale_case_id"):
                raise ValueError("该退款来自售后工单，请在售后审核页处理")
            if refund.get("source_order_status") != "pending_ship":
                raise ValueError("退款申请缺少可信的原始履约状态，请人工核对")
            timestamp = now_iso()
            refund.update(
                {
                    "status": "rejected",
                    "rejected_at": timestamp,
                    "rejected_by": operator,
                    "reject_note": note,
                }
            )
            self.transition_order(
                order,
                "pending_ship",
                event_label=note or "退款申请未通过，订单恢复待发货",
                connection=connection,
                refund_status="rejected",
                refund=refund,
            )
        return self.get_order(order_id)

    def create_wechat_refund(
        self,
        order: dict[str, Any],
        out_refund_no: str,
        refund_fee: int,
        total_fee: int,
        reason: str,
        config: WechatPayConfig,
    ) -> dict[str, Any]:
        payment = order.get("payment") or {}
        body: dict[str, Any] = {
            "out_refund_no": out_refund_no,
            "reason": str(reason or "用户申请退款")[:80],
            "amount": {
                "refund": refund_fee,
                "total": total_fee,
                "currency": order.get("currency") or "CNY",
            },
        }
        if payment.get("transaction_id"):
            body["transaction_id"] = payment["transaction_id"]
        else:
            body["out_trade_no"] = order["out_trade_no"]
        if config.refund_notify_url:
            body["notify_url"] = config.refund_notify_url
        return self.wechat_request("POST", "/v3/refund/domestic/refunds", body, config, error_label="微信退款申请失败")

    def get_logistics(self, order_id: str, user_id: str) -> dict[str, Any]:
        order = self.get_order(order_id)
        self.ensure_order_owner(order, user_id)
        return self.refresh_order_logistics(order_id, force=False)

    def transition_order(
        self,
        order: dict[str, Any],
        target_status: str,
        event_label: str = "",
        connection=None,
        **updates,
    ) -> None:
        if connection is None:
            with self.connect() as owned_connection:
                self.begin_order_transaction(owned_connection)
                self.transition_order(
                    order,
                    target_status,
                    event_label=event_label,
                    connection=owned_connection,
                    **updates,
                )
            return

        row = self.order_row_for_update(connection, order["order_id"])
        if not row:
            raise ValueError("订单不存在")
        fresh_order = self.public_order(row)
        current_status = fresh_order["status"]
        if current_status != order["status"]:
            raise OrderConflictError("订单状态已更新，请刷新后重试")
        allowed = ORDER_STATE_TRANSITIONS.get(current_status, set())
        if target_status != current_status and target_status not in allowed:
            current = ORDER_STATUS_TEXT.get(current_status, current_status)
            target = ORDER_STATUS_TEXT.get(target_status, target_status)
            raise ValueError(f"订单状态不能从 {current} 变更为 {target}")

        timestamp = now_iso()
        payment_status = updates.get("payment_status", fresh_order.get("payment_status"))
        self.validate_order_state(target_status, str(payment_status or ""))

        history = list(fresh_order.get("status_history") or [])
        if target_status != current_status:
            history.append({
                "status": target_status,
                "label": event_label or ORDER_STATUS_TEXT.get(target_status, target_status),
                "time": timestamp,
            })

        set_parts = ["status = ?", "updated_at = ?", "status_history_json = ?"]
        values: list[Any] = [target_status, timestamp, json.dumps(history, ensure_ascii=False)]
        field_map = {
            "payment_status": "payment_status",
            "paid_at": "paid_at",
            "remark": "remark",
            "after_sale_status": "after_sale_status",
            "refund_status": "refund_status",
        }
        for key, column in field_map.items():
            if key in updates:
                set_parts.append(f"{column} = ?")
                values.append(updates[key])
        if "logistics" in updates:
            set_parts.append("logistics_json = ?")
            values.append(json.dumps(updates["logistics"], ensure_ascii=False))
        if "refund" in updates:
            set_parts.append("refund_json = ?")
            values.append(json.dumps(updates["refund"], ensure_ascii=False))
        values.extend([order["order_id"], current_status])
        cursor = connection.execute(
            f"UPDATE orders SET {', '.join(set_parts)} WHERE order_id = ? AND status = ?",
            values,
        )
        if cursor.rowcount == 0:
            current = self.order_row_for_update(connection, order["order_id"])
            if not current or current["status"] != current_status:
                raise OrderConflictError("订单状态已更新，请刷新后重试")

    @staticmethod
    def validate_order_state(status: str, payment_status: str) -> None:
        allowed_payment_states = {
            "pending_payment": {"unpaid", "processing"},
            "pending_ship": {"paid"},
            "shipped": {"paid"},
            "completed": {"paid"},
            "refund_requested": {"paid"},
            "refunded": {"refunded"},
            "closed": {"cancelled", "expired", "failed"},
        }
        if status not in allowed_payment_states:
            raise ValueError("不支持的订单状态")
        if payment_status not in allowed_payment_states[status]:
            raise ValueError("订单履约状态与支付状态不一致")

    def append_order_event(
        self,
        order: dict[str, Any],
        status: str,
        label: str,
        connection=None,
        **updates,
    ) -> None:
        if connection is None:
            with self.connect() as owned_connection:
                self.begin_order_transaction(owned_connection)
                self.append_order_event(
                    order,
                    status=status,
                    label=label,
                    connection=owned_connection,
                    **updates,
                )
            return

        row = self.order_row_for_update(connection, order["order_id"])
        if not row:
            raise ValueError("订单不存在")
        fresh_order = self.public_order(row)
        if fresh_order["status"] != order["status"] or status != fresh_order["status"]:
            raise OrderConflictError("订单状态已更新，请刷新后重试")
        payment_status = updates.get("payment_status", fresh_order.get("payment_status"))
        self.validate_order_state(fresh_order["status"], str(payment_status or ""))
        timestamp = now_iso()
        history = list(fresh_order.get("status_history") or [])
        history.append({"status": status, "label": label, "time": timestamp})
        set_parts = ["updated_at = ?", "status_history_json = ?"]
        values: list[Any] = [timestamp, json.dumps(history, ensure_ascii=False)]
        field_map = {
            "payment_status": "payment_status",
            "paid_at": "paid_at",
            "remark": "remark",
            "after_sale_status": "after_sale_status",
            "refund_status": "refund_status",
        }
        for key, column in field_map.items():
            if key in updates:
                set_parts.append(f"{column} = ?")
                values.append(updates[key])
        if "logistics" in updates:
            set_parts.append("logistics_json = ?")
            values.append(json.dumps(updates["logistics"], ensure_ascii=False))
        if "refund" in updates:
            set_parts.append("refund_json = ?")
            values.append(json.dumps(updates["refund"], ensure_ascii=False))
        values.extend([order["order_id"], fresh_order["status"]])
        cursor = connection.execute(
            f"UPDATE orders SET {', '.join(set_parts)} WHERE order_id = ? AND status = ?",
            values,
        )
        if cursor.rowcount == 0:
            current = self.order_row_for_update(connection, order["order_id"])
            if not current or current["status"] != fresh_order["status"]:
                raise OrderConflictError("订单状态已更新，请刷新后重试")

    def build_logistics(
        self,
        carrier: str,
        tracking_no: str | None = None,
        carrier_code: str = "shunfeng",
        phone_tail: str | None = None,
        source: str = "local",
    ) -> dict[str, Any]:
        timestamp = now_iso()
        tracking = tracking_no or f"YJ{int(time.time())}{secrets.token_hex(3).upper()}"
        return {
            "carrier": carrier or "顺丰速运",
            "carrier_code": carrier_code or "shunfeng",
            "tracking_no": tracking,
            "phone_tail": phone_tail or "",
            "status": "awaiting_pickup",
            "status_text": "已发货待揽收",
            "updated_at": timestamp,
            "shipped_at": timestamp,
            "source": source or "local",
            "traces": [
                {"time": timestamp, "location": "宇涧水晶工作室", "desc": "商家已打包并发货，等待快递揽收"},
            ],
        }

    @staticmethod
    def parse_logistics_time(value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone(timedelta(hours=8)))
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(text, pattern).replace(
                    tzinfo=timezone(timedelta(hours=8))
                ).astimezone(timezone.utc)
            except ValueError:
                continue
        return None

    @classmethod
    def latest_trace_time(cls, traces: list[dict[str, Any]]) -> str:
        best_text = ""
        best_time: datetime | None = None
        for trace in traces:
            text = str(trace.get("time") or "").strip()
            parsed = cls.parse_logistics_time(text)
            if parsed is not None and (best_time is None or parsed > best_time):
                best_time = parsed
                best_text = text
            elif not best_text and text:
                best_text = text
        return best_text

    @classmethod
    def with_signed_completion_deadline(
        cls,
        existing: dict[str, Any],
        incoming: dict[str, Any],
        merged: dict[str, Any],
    ) -> dict[str, Any]:
        if merged.get("status") != "signed":
            return merged
        signed_at_value = (
            existing.get("signed_at")
            or incoming.get("signed_at")
            or (existing.get("latest_event_time") if existing.get("status") == "signed" else "")
            or incoming.get("latest_event_time")
            or cls.latest_trace_time(list(incoming.get("traces") or []))
            or incoming.get("updated_at")
            or existing.get("updated_at")
            or now_iso()
        )
        signed_at = cls.parse_logistics_time(signed_at_value) or datetime.now(timezone.utc)
        signed_at = signed_at.astimezone(timezone.utc).replace(microsecond=0)
        merged["signed_at"] = signed_at.isoformat()
        merged["auto_complete_at"] = (
            signed_at + timedelta(days=SIGNED_AUTO_COMPLETE_DAYS)
        ).isoformat()
        return merged

    @staticmethod
    def logistics_completion_fields(logistics: dict[str, Any]) -> tuple[str | None, str | None]:
        if logistics.get("status") != "signed":
            return None, None
        return (
            str(logistics.get("signed_at") or "") or None,
            str(logistics.get("auto_complete_at") or "") or None,
        )

    @classmethod
    def merge_logistics(
        cls,
        existing: dict[str, Any] | None,
        incoming: dict[str, Any] | None,
    ) -> dict[str, Any]:
        current = dict(existing or {})
        update = dict(incoming or {})
        merged = {**current, **update}

        traces: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for raw_trace in list(update.get("traces") or []) + list(current.get("traces") or []):
            if not isinstance(raw_trace, dict):
                continue
            trace = {
                "time": str(raw_trace.get("time") or "").strip(),
                "location": str(raw_trace.get("location") or "").strip(),
                "desc": str(raw_trace.get("desc") or "").strip(),
            }
            key = (trace["time"], trace["location"], trace["desc"])
            if key in seen or not any(key):
                continue
            seen.add(key)
            traces.append(trace)
        traces.sort(
            key=lambda item: cls.parse_logistics_time(item.get("time")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        merged["traces"] = traces[:200]

        existing_event = cls.parse_logistics_time(current.get("latest_event_time"))
        incoming_event_text = str(update.get("latest_event_time") or cls.latest_trace_time(list(update.get("traces") or [])))
        incoming_event = cls.parse_logistics_time(incoming_event_text)
        existing_signed = current.get("status") == "signed"
        incoming_signed = update.get("status") == "signed"
        incoming_is_older = bool(existing_event and incoming_event and incoming_event < existing_event)
        if existing_signed or (incoming_is_older and not incoming_signed):
            for key in ("status", "status_text", "kuaidi100_state"):
                if key in current:
                    merged[key] = current[key]
        current_subscription = current.get("subscription_status")
        incoming_subscription = update.get("subscription_status")
        preserve_subscription = (
            current_subscription == "completed" and incoming_subscription != "completed"
        ) or (
            current_subscription == "aborted" and incoming_subscription not in {"completed", "aborted"}
        ) or (
            incoming_is_older and not incoming_signed and bool(current_subscription)
        )
        if preserve_subscription:
            merged["subscription_status"] = current["subscription_status"]
            if current.get("monitor_status"):
                merged["monitor_status"] = current["monitor_status"]
        if incoming_event and (existing_event is None or incoming_event >= existing_event):
            merged["latest_event_time"] = incoming_event_text
        elif current.get("latest_event_time"):
            merged["latest_event_time"] = current["latest_event_time"]

        if current.get("sync_mode") == "push" and not update.get("sync_mode"):
            merged["sync_mode"] = "push"
        if current.get("source") == "kuaidi100" and update.get("source") in {None, "", "local", "admin"}:
            merged["source"] = "kuaidi100"
        return cls.with_signed_completion_deadline(current, update, merged)

    @staticmethod
    def build_kuaidi100_callback_url(callback_url: str, order_id: str) -> str:
        parsed = urlsplit(str(callback_url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("快递100回调地址无效")
        query = parse_qs(parsed.query, keep_blank_values=True)
        query["order_id"] = [order_id]
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query, doseq=True), ""))

    def build_kuaidi100_subscription_payload(
        self,
        order_id: str,
        logistics: dict[str, Any],
        config: Kuaidi100Config,
    ) -> dict[str, Any]:
        carrier_code = str(logistics.get("carrier_code") or "").strip().lower()
        tracking_no = str(logistics.get("tracking_no") or "").strip()
        if not carrier_code or not tracking_no:
            raise ValueError("快递公司编码或快递单号缺失")
        if len(tracking_no) < 6 or len(tracking_no) > 32:
            raise ValueError("快递单号长度必须为 6 至 32 个字符")
        phone_tail = "".join(character for character in str(logistics.get("phone_tail") or "") if character.isdigit())[-4:]
        if carrier_code in KUAIDI100_PHONE_REQUIRED_COMPANIES and len(phone_tail) != 4:
            raise ValueError("该快递公司订阅需要收件手机号后四位")
        parameters = {
            "callbackurl": self.build_kuaidi100_callback_url(config.callback_url, order_id),
            "salt": config.callback_salt,
            "resultv2": config.resultv2,
        }
        if phone_tail:
            parameters["phone"] = phone_tail
        return {
            "company": carrier_code,
            "number": tracking_no,
            "key": config.key,
            "parameters": parameters,
        }

    def submit_kuaidi100_subscription(
        self,
        order_id: str,
        logistics: dict[str, Any],
        config: Kuaidi100Config,
    ) -> dict[str, Any]:
        payload = self.build_kuaidi100_subscription_payload(order_id, logistics, config)
        param_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        try:
            timeout = max(1.0, min(float(os.getenv("KUAIDI100_REQUEST_TIMEOUT_SECONDS", "10")), 30.0))
        except ValueError:
            timeout = 10.0
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    config.subscribe_url,
                    data={"schema": "json", "param": param_text},
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Request-ID": current_request_id(),
                    },
                )
        except httpx.RequestError as exc:
            raise ValueError("快递100订阅请求超时或网络不可用") from exc
        if response.status_code >= 400:
            raise ValueError(f"快递100订阅失败：HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ValueError("快递100订阅返回格式无效") from exc
        return_code = str(data.get("returnCode") or "")
        accepted = (
            return_code == "200" and str(data.get("result")).lower() == "true"
        ) or return_code == "501"
        if not accepted:
            raise ValueError(str(data.get("message") or "快递100订阅失败")[:200])
        return {
            "return_code": return_code or "200",
            "message": str(data.get("message") or "成功")[:200],
            "duplicate": return_code == "501",
        }

    def subscribe_order_logistics(self, order_id: str) -> dict[str, Any]:
        if not kuaidi100_subscribe_enabled():
            return {"enabled": False, "status": "disabled", "replayed": False}

        config = Kuaidi100Config()
        started_at = now_iso()
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            order = self.public_order(row)
            logistics = dict(order.get("logistics") or {})
            tracking_no = str(logistics.get("tracking_no") or "").strip()
            if order.get("status") != "shipped" or not tracking_no:
                return {"enabled": True, "status": "skipped", "replayed": False}
            same_tracking = logistics.get("subscription_tracking_no") == tracking_no
            subscription_status = str(logistics.get("subscription_status") or "")
            if same_tracking and subscription_status in {"active", "completed"}:
                return {"enabled": True, "status": subscription_status, "replayed": True}
            subscription_updated_at = self.parse_logistics_time(logistics.get("subscription_updated_at"))
            abort_in_cooldown = bool(
                same_tracking
                and subscription_status == "aborted"
                and subscription_updated_at
                and (datetime.now(timezone.utc) - subscription_updated_at).total_seconds() < 1800
            )
            if abort_in_cooldown:
                return {"enabled": True, "status": "cooldown", "replayed": True}
            requested_at = self.parse_logistics_time(logistics.get("subscription_requested_at"))
            request_is_fresh = bool(
                requested_at and (datetime.now(timezone.utc) - requested_at).total_seconds() < 60
            )
            if same_tracking and subscription_status == "subscribing" and request_is_fresh:
                return {"enabled": True, "status": "subscribing", "replayed": True}
            logistics.update(
                {
                    "subscription_status": "subscribing",
                    "subscription_tracking_no": tracking_no,
                    "subscription_requested_at": started_at,
                    "subscription_updated_at": started_at,
                    "subscription_attempts": int(logistics.get("subscription_attempts") or 0) + 1,
                    "subscription_return_code": "",
                    "subscription_message": "",
                }
            )
            connection.execute(
                "UPDATE orders SET logistics_json = ?, updated_at = ? WHERE order_id = ?",
                (json.dumps(logistics, ensure_ascii=False), started_at, order_id),
            )

        result: dict[str, Any] = {}
        error: Exception | None = None
        try:
            if not config.subscription_ready:
                raise ValueError("快递100主动订阅配置不完整")
            result = self.submit_kuaidi100_subscription(order_id, logistics, config)
        except Exception as exc:
            error = exc
            metrics.increment("external_service_failed_total", service="kuaidi100_subscribe", error_type=type(exc).__name__)
            log_event(
                logistics_logger,
                "logistics.subscription.failed",
                level=logging.WARNING,
                service="kuaidi100",
                error_type=type(exc).__name__,
                result="failed",
            )

        finished_at = now_iso()
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            latest = dict(self.public_order(row).get("logistics") or {})
            if str(latest.get("tracking_no") or "") != tracking_no:
                return {"enabled": True, "status": "stale", "replayed": False}
            existing_status = str(latest.get("subscription_status") or "")
            callback_already_accepted = bool(latest.get("last_callback_hash")) and existing_status in {
                "active", "completed", "aborted"
            }
            if callback_already_accepted:
                final_status = existing_status
            else:
                final_status = "active" if error is None else "failed"
            latest.update(
                {
                    "subscription_status": final_status,
                    "subscription_updated_at": finished_at,
                    "subscription_return_code": str(result.get("return_code") or ""),
                    "subscription_message": str(result.get("message") or (str(error) if error else ""))[:200],
                }
            )
            connection.execute(
                "UPDATE orders SET logistics_json = ?, updated_at = ? WHERE order_id = ?",
                (json.dumps(latest, ensure_ascii=False), finished_at, order_id),
            )
        if error is None:
            metrics.increment("logistics_subscription_total", service="kuaidi100", result="replayed" if result.get("duplicate") else "created")
            log_event(logistics_logger, "logistics.subscription.succeeded", service="kuaidi100", result="success")
        return {
            "enabled": True,
            "status": final_status,
            "replayed": bool(result.get("duplicate")),
            "return_code": str(result.get("return_code") or ""),
        }

    @staticmethod
    def parse_kuaidi100_callback_form(body_text: str) -> tuple[str, str]:
        try:
            fields = parse_qs(
                body_text,
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=10,
            )
        except ValueError as exc:
            raise ValueError("快递100回调表单格式无效") from exc
        param_values = fields.get("param") or []
        sign_values = fields.get("sign") or []
        if len(param_values) != 1 or len(sign_values) != 1 or not param_values[0] or not sign_values[0]:
            raise ValueError("快递100回调缺少必要字段")
        return param_values[0], sign_values[0]

    @staticmethod
    def verify_kuaidi100_callback(param_text: str, sign: str, config: Kuaidi100Config) -> None:
        if not config.callback_ready:
            raise RuntimeError("快递100回调验签配置不可用")
        expected = hashlib.md5(f"{param_text}{config.callback_salt}".encode("utf-8")).hexdigest().upper()
        if not hmac.compare_digest(expected, str(sign or "").strip().upper()):
            raise LogisticsCallbackSignatureError("快递100回调签名无效")

    def handle_kuaidi100_callback(self, order_id: str, param_text: str, sign: str) -> dict[str, Any]:
        config = Kuaidi100Config()
        self.verify_kuaidi100_callback(param_text, sign, config)
        try:
            payload = json.loads(param_text)
        except json.JSONDecodeError as exc:
            raise ValueError("快递100回调 JSON 无效") from exc
        if not isinstance(payload, dict):
            raise ValueError("快递100回调数据无效")
        last_result = payload.get("lastResult") or {}
        if isinstance(last_result, str):
            try:
                last_result = json.loads(last_result)
            except json.JSONDecodeError as exc:
                raise ValueError("快递100轨迹数据无效") from exc
        if not isinstance(last_result, dict):
            raise ValueError("快递100轨迹数据无效")

        raw_traces = last_result.get("data") or []
        if not isinstance(raw_traces, list) or len(raw_traces) > 500:
            raise ValueError("快递100轨迹数量异常")
        traces = [
            {
                "time": str(item.get("ftime") or item.get("time") or "")[:40],
                "location": str(item.get("areaName") or item.get("areaCode") or "")[:200],
                "desc": str(item.get("context") or "")[:1000],
            }
            for item in raw_traces
            if isinstance(item, dict)
        ]
        tracking_no = str(last_result.get("nu") or last_result.get("number") or "").strip()
        carrier_code = str(last_result.get("com") or "").strip()
        auto_check = str(payload.get("autoCheck") or "0").strip()
        original_carrier_code = str(payload.get("comOld") or "").strip()
        corrected_carrier_code = str(payload.get("comNew") or "").strip()
        state = str(last_result.get("state") or "").strip()
        monitor_status = str(payload.get("status") or "").strip().lower()
        signed = str(last_result.get("ischeck") or "").lower() in {"1", "true"} or state == "3"
        event_time = self.latest_trace_time(traces)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        received_at = now_iso()

        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            order = self.public_order(row)
            existing = dict(order.get("logistics") or {})
            if not tracking_no or tracking_no != str(existing.get("tracking_no") or ""):
                raise ValueError("快递100回调单号与订单不一致")
            existing_carrier_code = str(existing.get("carrier_code") or "")
            company_corrected = bool(
                carrier_code
                and existing_carrier_code
                and carrier_code != existing_carrier_code
                and auto_check == "1"
                and original_carrier_code == existing_carrier_code
                and corrected_carrier_code in {"", carrier_code}
            )
            if carrier_code and existing_carrier_code and carrier_code != existing_carrier_code and not company_corrected:
                raise ValueError("快递100回调快递公司与订单不一致")

            if monitor_status == "abort":
                subscription_status = "aborted"
            elif monitor_status == "shutdown":
                subscription_status = "completed" if signed else "stopped"
            else:
                subscription_status = "active"
            callback_hashes = [
                str(value)
                for value in list(existing.get("callback_event_hashes") or [])
                if str(value)
            ]
            duplicate = event_hash in callback_hashes
            if not duplicate:
                callback_hashes = ([event_hash] + callback_hashes)[:50]
            incoming = {
                "status": "signed" if signed else "in_transit",
                "status_text": self.kuaidi100_state_text(state) if state else existing.get("status_text") or "物流更新中",
                "updated_at": received_at,
                "source": "kuaidi100",
                "sync_mode": "push",
                "kuaidi100_state": state,
                "monitor_status": monitor_status,
                "subscription_status": subscription_status,
                "subscription_tracking_no": tracking_no,
                "subscription_updated_at": received_at,
                "last_callback_at": received_at,
                "last_callback_hash": event_hash,
                "callback_event_hashes": callback_hashes,
                "latest_event_time": event_time,
                "message": str(last_result.get("message") or payload.get("message") or "")[:200],
                "sync_error": monitor_status == "abort",
                "last_error_type": "provider_abort" if monitor_status == "abort" else "",
                "traces": traces,
            }
            if company_corrected:
                incoming.update(
                    {
                        "carrier_code": carrier_code,
                        "carrier_code_corrected_from": original_carrier_code,
                        "carrier_code_corrected_at": received_at,
                    }
                )
            if corrected_carrier_code:
                incoming["provider_suggested_carrier_code"] = corrected_carrier_code
            merged = self.merge_logistics(existing, incoming)
            if not duplicate:
                signed_at, auto_complete_at = self.logistics_completion_fields(merged)
                connection.execute(
                    """
                    UPDATE orders
                    SET logistics_json = ?, logistics_signed_at = ?, auto_complete_at = ?, updated_at = ?
                    WHERE order_id = ?
                    """,
                    (
                        json.dumps(merged, ensure_ascii=False),
                        signed_at,
                        auto_complete_at,
                        received_at,
                        order_id,
                    ),
                )

        metrics.increment("logistics_callback_total", service="kuaidi100", result="duplicate" if duplicate else "success")
        log_event(
            logistics_logger,
            "logistics.callback.succeeded",
            service="kuaidi100",
            result="duplicate" if duplicate else "success",
        )
        return {"duplicate": duplicate, "signed": signed, "monitor_status": monitor_status}

    def refresh_logistics_if_needed(self, order: dict[str, Any], logistics: dict[str, Any]) -> dict[str, Any]:
        if not logistics.get("tracking_no"):
            return logistics
        if logistics.get("status") == "signed":
            return logistics
        config = Kuaidi100Config()
        if not config.ready:
            return {**logistics, "source": logistics.get("source") or "local", "message": "快递100未配置，展示本地物流记录"}
        if self.is_logistics_cache_fresh(logistics):
            return logistics
        try:
            refreshed = self.query_kuaidi100(logistics, config)
        except Exception as exc:
            metrics.increment("external_service_failed_total", service="kuaidi100", error_type=type(exc).__name__)
            log_event(
                logistics_logger,
                "logistics.external.failed",
                level=logging.WARNING,
                service="kuaidi100",
                error_type=type(exc).__name__,
                result="failed",
            )
            return {
                **logistics,
                "source": logistics.get("source") or "local",
                "message": "物流服务暂时不可用，保留最近一次轨迹",
                "sync_error": True,
                "last_error_type": type(exc).__name__,
            }
        return self.update_logistics(order["order_id"], refreshed)

    def refresh_order_logistics(self, order_id: str, force: bool = True) -> dict[str, Any]:
        order = self.get_order(order_id)
        logistics = order.get("logistics") or {}
        if force:
            logistics = {**logistics, "updated_at": ""}
        refreshed = self.refresh_logistics_if_needed(order, logistics)
        if refreshed.get("status") == "signed":
            if not refreshed.get("auto_complete_at"):
                refreshed = self.update_logistics(order_id, refreshed)
            self.complete_signed_order_if_due(order_id)
            order = self.get_order(order_id)
            refreshed = order.get("logistics") or refreshed
        return {
            "order_id": order_id,
            "order_status": order.get("status"),
            "order_status_text": order.get("status_text"),
            "logistics": refreshed,
            "status_history": order.get("status_history") or [],
        }

    def complete_signed_order_if_due(
        self,
        order_id: str,
        now: datetime | None = None,
    ) -> bool:
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        current_time = current_time.astimezone(timezone.utc)
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                return False
            order = self.public_order(row)
            logistics = dict(order.get("logistics") or {})
            if order.get("status") != "shipped" or logistics.get("status") != "signed":
                return False
            deadline = self.parse_logistics_time(
                order.get("auto_complete_at") or logistics.get("auto_complete_at")
            )
            if deadline is None or deadline > current_time:
                return False
            self.transition_order(
                order,
                "completed",
                event_label="快递签收满7天，订单自动完成",
                connection=connection,
            )
            return True

    def complete_signed_orders_due(
        self,
        limit: int = 50,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        current_time = current_time.astimezone(timezone.utc).replace(microsecond=0)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT order_id, logistics_json FROM orders
                WHERE status = 'shipped'
                  AND auto_complete_at IS NOT NULL
                  AND auto_complete_at <= ?
                ORDER BY auto_complete_at ASC
                LIMIT ?
                """,
                (current_time.isoformat(), limit),
            ).fetchall()
        completed_order_ids: list[str] = []
        failed_order_ids: list[str] = []
        for row in rows:
            order_id = row["order_id"]
            try:
                if self.complete_signed_order_if_due(order_id, current_time):
                    completed_order_ids.append(order_id)
            except Exception:
                failed_order_ids.append(order_id)
        return {
            "checked": len(rows),
            "completed": len(completed_order_ids),
            "completed_order_ids": completed_order_ids,
            "failed": len(failed_order_ids),
            "failed_order_ids": failed_order_ids,
        }

    def refresh_active_shipments(self, limit: int = 50) -> dict[str, Any]:
        auto_completion = self.complete_signed_orders_due(limit=limit)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT order_id, logistics_json FROM orders
                WHERE status IN ('shipped', 'refund_requested', 'refunded')
                  AND logistics_json IS NOT NULL
                  AND logistics_json <> ''
                ORDER BY updated_at ASC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        rows = [
            row
            for row in rows
            if self.loads(dict(row).get("logistics_json") or "", {}).get("tracking_no")
        ]
        results = []
        for row in rows:
            try:
                results.append(self.refresh_order_logistics(row["order_id"], force=False))
            except Exception as exc:
                results.append({"order_id": row["order_id"], "error_type": type(exc).__name__})
        failed_order_ids = [
            item["order_id"]
            for item in results
            if item.get("error_type") or (item.get("logistics") or {}).get("sync_error")
        ]
        failed_order_ids = list(dict.fromkeys(
            list(auto_completion.get("failed_order_ids") or []) + failed_order_ids
        ))
        return {
            "checked": int(auto_completion.get("checked") or 0) + len(results),
            "completed": int(auto_completion.get("completed") or 0)
            + sum(1 for item in results if item.get("order_status") == "completed"),
            "failed": len(failed_order_ids),
            "failed_order_ids": failed_order_ids,
            "results": results,
        }

    def query_kuaidi100(self, logistics: dict[str, Any], config: Kuaidi100Config) -> dict[str, Any]:
        carrier_code = logistics.get("carrier_code") or "shunfeng"
        tracking_no = logistics.get("tracking_no") or ""
        if carrier_code == "shunfeng" and not logistics.get("phone_tail"):
            raise ValueError("顺丰物流查询需要收件手机号后四位")
        param = {
            "com": carrier_code,
            "num": tracking_no,
            "resultv2": "1",
        }
        if logistics.get("phone_tail"):
            param["phone"] = logistics["phone_tail"]
        param_text = json.dumps(param, ensure_ascii=False, separators=(",", ":"))
        sign = hashlib.md5(f"{param_text}{config.key}{config.customer}".encode("utf-8")).hexdigest().upper()
        try:
            with httpx.Client(timeout=10) as client:
                response = client.post(
                    config.query_url,
                    data={"customer": config.customer, "sign": sign, "param": param_text},
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Request-ID": current_request_id(),
                    },
                )
        except httpx.RequestError as exc:
            raise ValueError("快递100请求超时或网络不可用") from exc
        if response.status_code >= 400:
            raise ValueError(f"快递100查询失败：HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ValueError("快递100返回格式无效") from exc
        if data.get("returnCode") and str(data.get("returnCode")) != "200":
            raise ValueError(data.get("message") or "快递100查询失败")
        traces = [
            {
                "time": item.get("ftime") or item.get("time") or "",
                "location": item.get("areaName") or item.get("areaCode") or "",
                "desc": item.get("context") or "",
            }
            for item in data.get("data", [])
        ]
        state_text = self.kuaidi100_state_text(str(data.get("state", "")))
        return {
            **logistics,
            "status": "signed" if str(data.get("ischeck") or "") == "1" else "in_transit",
            "status_text": state_text,
            "updated_at": now_iso(),
            "source": "kuaidi100",
            "kuaidi100_state": str(data.get("state", "")),
            "message": data.get("message") or "",
            "sync_error": False,
            "last_error_type": "",
            "traces": traces or logistics.get("traces") or [],
        }

    def update_logistics(self, order_id: str, logistics: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            row = self.order_row_for_update(connection, order_id)
            if not row:
                raise ValueError("订单不存在")
            existing = self.loads(row.get("logistics_json") or "", {})
            merged = self.merge_logistics(existing, logistics)
            signed_at, auto_complete_at = self.logistics_completion_fields(merged)
            connection.execute(
                """
                UPDATE orders
                SET logistics_json = ?, logistics_signed_at = ?, auto_complete_at = ?, updated_at = ?
                WHERE order_id = ?
                """,
                (
                    json.dumps(merged, ensure_ascii=False),
                    signed_at,
                    auto_complete_at,
                    now_iso(),
                    order_id,
                ),
            )
        return merged

    def public_design(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "design_id": row["design_id"],
            "user_id": row["user_id"],
            "status": row["status"],
            "share_status": row.get("share_status") or "private",
            "design": self.loads(row.get("design_json") or "", {}),
            "sequence": self.loads(row.get("sequence_json") or "", []),
            "order_id": row.get("order_id") or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def public_shared_design(self, row: dict[str, Any]) -> dict[str, Any]:
        design = self.loads(row.get("design_json") or "", {})
        sequence = self.loads(row.get("sequence_json") or "", [])
        placement_keys = {
            "id", "materialId", "material_id", "sku", "skuId", "index", "angle",
            # These values are presentation-only.  Keeping the full placement snapshot
            # lets a shared workspace reproduce the sender's composition without
            # exposing the private design metadata filtered below.
            "x", "y", "dx", "dy", "looseX", "looseY", "rotation", "scale", "beadSize",
            "image_url", "name", "size", "size_mm", "bead_caps",
        }

        bead_cap_keys = {
            "id", "material_id", "sku", "skuId", "name", "category", "series",
            "size", "image_url", "image_urls", "material_params", "attachment_mode", "side",
        }

        def safe_bead_caps(value: Any) -> dict[str, Any]:
            if not isinstance(value, dict):
                return {}
            return {
                side: {key: item for key, item in cap.items() if key in bead_cap_keys}
                for side, cap in value.items()
                if side in {"left", "right"} and isinstance(cap, dict)
            }

        def safe_placement(value: Any) -> dict[str, Any]:
            if not isinstance(value, dict):
                return {}
            placement = {key: item for key, item in value.items() if key in placement_keys}
            if "bead_caps" in placement:
                placement["bead_caps"] = safe_bead_caps(placement["bead_caps"])
            return placement

        design_keys = {
            "name", "title", "selected", "placements", "wearStyle", "isLooseMode",
            "workspaceStageCenter", "workspace_stage_center",
            "preview_image", "previewImage", "image_url",
        }
        sequence_keys = {
            "id", "sku", "skuId", "name", "category", "series", "size", "size_mm",
            "color", "shine", "image_url", "placement", "top", "item_type",
            "material_params", "placement_mode", "attachment_mode", "attachment",
        }
        safe_design = {key: value for key, value in design.items() if key in design_keys}
        safe_design["placements"] = [
            safe_placement(item) for item in safe_design.get("placements", []) if isinstance(item, dict)
        ]
        safe_sequence = []
        for item in sequence:
            if not isinstance(item, dict):
                continue
            safe_item = {key: value for key, value in item.items() if key in sequence_keys}
            if "placement" in safe_item:
                safe_item["placement"] = safe_placement(safe_item["placement"])
            safe_sequence.append(safe_item)
        return {
            "share_status": "shared",
            "design": safe_design,
            "sequence": safe_sequence,
        }

    def public_cart_item(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "cart_item_id": row["cart_item_id"],
            "user_id": row["user_id"],
            "item_type": row.get("item_type") or "plan",
            "item_id": row.get("item_id") or "",
            "item": self.loads(row.get("item_json") or "", {}),
            "quantity": int(row.get("quantity") or 1),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def public_community_favorite(self, row: dict[str, Any]) -> dict[str, Any]:
        item = self.loads(row.get("item_json") or "", {})
        return {
            "user_id": row["user_id"],
            "post_id": row["post_id"],
            "item": item,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            **item,
            "id": item.get("id") or row["post_id"],
        }

    def public_address(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "address_id": row["address_id"],
            "user_id": row["user_id"],
            "name": row["name"],
            "phone": row["phone"],
            "region": self.loads(row.get("region_json") or "", []),
            "detail_address": row["detail_address"],
            "address": row["address"],
            "is_default": bool(row.get("is_default")),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def public_coupon(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "coupon_id": row["coupon_id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "coupon_type": row.get("coupon_type") or "amount",
            "value": float(row.get("value") or 0),
            "min_amount": float(row.get("min_amount") or 0),
            "status": row.get("status") or "unused",
            "expires_at": row.get("expires_at") or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def is_logistics_cache_fresh(logistics: dict[str, Any]) -> bool:
        updated_at = logistics.get("updated_at")
        if not updated_at:
            return False
        try:
            last = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        except ValueError:
            return False
        return (datetime.now(timezone.utc) - last).total_seconds() < 1800

    @staticmethod
    def kuaidi100_state_text(state: str) -> str:
        return {
            "0": "运输中",
            "1": "已揽收",
            "2": "疑难件",
            "3": "已签收",
            "4": "退签",
            "5": "派件中",
            "6": "退回中",
            "7": "转投中",
            "10": "待清关",
            "11": "清关中",
            "12": "已清关",
            "13": "清关异常",
            "14": "收件人拒签",
        }.get(state, "物流更新中")

    def wechat_request(
        self,
        method: str,
        url_path: str,
        body: dict[str, Any],
        config: WechatPayConfig,
        error_label: str = "微信支付请求失败",
    ) -> dict[str, Any]:
        url = f"https://api.mch.weixin.qq.com{url_path}"
        body_text = "" if method.upper() == "GET" else json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        signature = self.sign_message(f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body_text}\n", config)
        authorization = (
            'WECHATPAY2-SHA256-RSA2048 '
            f'mchid="{config.mch_id}",nonce_str="{nonce}",signature="{signature}",'
            f'timestamp="{timestamp}",serial_no="{config.serial_no}"'
        )
        try:
            with httpx.Client(timeout=12) as client:
                response = client.request(
                    method,
                    url,
                    content=body_text.encode("utf-8"),
                    headers={
                        "Authorization": authorization,
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "User-Agent": "yujian-fastapi/1.0",
                        "X-Request-ID": current_request_id(),
                    },
                )
        except httpx.RequestError as exc:
            metrics.increment("external_service_failed_total", service="wechat_pay", error_type=type(exc).__name__)
            log_event(
                external_logger,
                "external.wechat_pay.timeout",
                level=logging.WARNING,
                service="wechat_pay",
                error_type=type(exc).__name__,
                result="failed",
            )
            raise WechatPayRequestError(
                f"{error_label}：网络超时",
                retryable=True,
            ) from exc
        if response.status_code >= 400:
            provider_code = ""
            try:
                error_payload = response.json()
                if isinstance(error_payload, dict):
                    provider_code = str(error_payload.get("code") or "").strip().upper()
            except (ValueError, TypeError):
                provider_code = ""
            metrics.increment("external_service_failed_total", service="wechat_pay", status_code=response.status_code)
            log_event(
                external_logger,
                "external.wechat_pay.failed",
                level=logging.WARNING,
                service="wechat_pay",
                status_code=response.status_code,
                result="failed",
            )
            raise WechatPayRequestError(
                f"{error_label}：HTTP {response.status_code}",
                status_code=response.status_code,
                provider_code=provider_code,
                retryable=response.status_code == 429 or response.status_code >= 500,
            )
        return response.json()

    @staticmethod
    def webhook_payload_hash(body_text: str) -> str:
        return hashlib.sha256(body_text.encode("utf-8")).hexdigest()

    @staticmethod
    def provider_event_id(payload: dict[str, Any], event_type: str, payload_hash: str) -> str:
        explicit = str(payload.get("id") or "").strip()
        if explicit:
            if len(explicit) > 160:
                raise PaymentWebhookError("event_id_invalid", "微信支付事件标识过长")
            return explicit
        resource = payload.get("resource") or {}
        fingerprint = {
            "event_type": event_type,
            "create_time": payload.get("create_time") or "",
            "resource_type": payload.get("resource_type") or "",
            "algorithm": resource.get("algorithm") or "",
            "original_type": resource.get("original_type") or "",
            "ciphertext_hash": hashlib.sha256(
                str(resource.get("ciphertext") or payload_hash).encode("utf-8")
            ).hexdigest(),
        }
        canonical = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))
        return f"fallback_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"

    @staticmethod
    def strict_webhook_amount(value: Any, code: str, message: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise PaymentWebhookError(code, message)
        return value

    @staticmethod
    def masked_order_no(value: str) -> str:
        text = str(value or "")
        return f"***{text[-6:]}" if text else ""

    def audit_payment_event(
        self,
        provider_event_id: str,
        event_type: str,
        merchant_order_no: str,
        result: str,
    ) -> None:
        log_event(
            payment_logger,
            "payment.webhook.processed",
            provider_event_hash=hashlib.sha256(provider_event_id.encode("utf-8")).hexdigest()[:16],
            event_type=event_type[:80],
            order=self.masked_order_no(merchant_order_no),
            result=result[:40],
        )

    def claim_webhook_event(
        self,
        provider_event_id: str,
        event_type: str,
        payload_hash: str,
    ) -> dict[str, Any]:
        timestamp = now_iso()
        event_id = f"pe_{secrets.token_hex(16)}"
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO payment_webhook_events
                    (id, provider, provider_event_id, event_type, resource_id, transaction_id,
                     merchant_order_no, payload_hash, received_at, processed_at,
                     processing_status, failure_reason, conflict_count, security_alert_at,
                     created_at, updated_at)
                    VALUES (?, 'wechat_pay', ?, ?, '', '', '', ?, ?, NULL,
                            'received', '', 0, NULL, ?, ?)
                    """,
                    (event_id, provider_event_id, event_type, payload_hash, timestamp, timestamp, timestamp),
                )
            return {
                "id": event_id,
                "provider": "wechat_pay",
                "provider_event_id": provider_event_id,
                "event_type": event_type,
                "payload_hash": payload_hash,
                "processing_status": "received",
                "duplicate": False,
            }
        except (sqlite3.IntegrityError, *integrity_errors()):
            mismatch = False
            with self.connect() as connection:
                self.begin_order_transaction(connection)
                lock_clause = " FOR UPDATE" if self.mysql_transactions else ""
                row = connection.execute(
                    f"""
                    SELECT * FROM payment_webhook_events
                    WHERE provider = 'wechat_pay' AND provider_event_id = ?{lock_clause}
                    """,
                    (provider_event_id,),
                ).fetchone()
                if not row:
                    raise PaymentWebhookError("event_claim_conflict", "支付事件登记冲突")
                event = dict(row)
                if event["payload_hash"] != payload_hash:
                    mismatch = True
                    connection.execute(
                        """
                        UPDATE payment_webhook_events
                        SET conflict_count = conflict_count + 1,
                            security_alert_at = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (timestamp, timestamp, event["id"]),
                    )
                else:
                    event["duplicate"] = event["processing_status"] in WEBHOOK_TERMINAL_STATUSES
            if mismatch:
                self.audit_payment_event(provider_event_id, event_type, "", "payload_hash_mismatch")
                raise WebhookEventConflictError(
                    "payload_hash_mismatch",
                    "相同支付事件标识对应不同报文，已拒绝处理",
                )
            return event

    def locked_webhook_event(self, connection, event_id: str) -> dict[str, Any]:
        lock_clause = " FOR UPDATE" if self.mysql_transactions else ""
        row = connection.execute(
            f"SELECT * FROM payment_webhook_events WHERE id = ?{lock_clause}",
            (event_id,),
        ).fetchone()
        if not row:
            raise PaymentWebhookError("event_missing", "支付事件不存在")
        return dict(row)

    def finalize_webhook_event(
        self,
        connection,
        event_id: str,
        status: str,
        merchant_order_no: str = "",
        resource_id: str = "",
        transaction_id: str = "",
        failure_reason: str = "",
    ) -> None:
        timestamp = now_iso()
        connection.execute(
            """
            UPDATE payment_webhook_events
            SET merchant_order_no = ?, resource_id = ?, transaction_id = ?,
                processing_status = ?, failure_reason = ?, processed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                merchant_order_no,
                resource_id,
                transaction_id,
                status,
                failure_reason[:120],
                timestamp,
                timestamp,
                event_id,
            ),
        )

    def mark_webhook_event_failed(
        self,
        event_id: str,
        payload_hash: str,
        failure_reason: str,
    ) -> None:
        try:
            with self.connect() as connection:
                self.begin_order_transaction(connection)
                event = self.locked_webhook_event(connection, event_id)
                if event["payload_hash"] != payload_hash:
                    return
                if event["processing_status"] in WEBHOOK_TERMINAL_STATUSES:
                    return
                self.finalize_webhook_event(
                    connection,
                    event_id,
                    "failed",
                    event.get("merchant_order_no") or "",
                    event.get("resource_id") or "",
                    event.get("transaction_id") or "",
                    failure_reason,
                )
        except Exception as exc:
            log_event(
                payment_logger,
                "payment.webhook.failure_persist_failed",
                level=logging.ERROR,
                event_id_hash=hashlib.sha256(event_id.encode("utf-8")).hexdigest()[:16],
                error_type=type(exc).__name__,
                result="failed",
            )

    @staticmethod
    def webhook_error_code(error: Exception) -> str:
        return error.code if isinstance(error, PaymentWebhookError) else "processing_error"

    def decode_verified_webhook(
        self,
        headers: dict[str, str],
        body_text: str,
        config: WechatPayConfig,
        label: str,
    ) -> dict[str, Any]:
        if not config.api_v3_key:
            raise PaymentWebhookError("api_v3_key_missing", f"缺少 {label} APIv3 key")
        serial = headers.get("wechatpay-serial", "")
        timestamp = headers.get("wechatpay-timestamp", "")
        nonce = headers.get("wechatpay-nonce", "")
        signature = headers.get("wechatpay-signature", "")
        if not all([serial, timestamp, nonce, signature]):
            raise PaymentWebhookError("signature_headers_missing", f"{label}签名头不完整")
        self.verify_wechat_notify_signature(serial, timestamp, nonce, signature, body_text, config)
        payload = json.loads(body_text)
        if not isinstance(payload, dict):
            raise PaymentWebhookError("payload_invalid", f"{label}报文格式错误")
        return payload

    def handle_wechat_notify(self, headers: dict[str, str], body_text: str) -> dict[str, Any]:
        config = WechatPayConfig()
        payload = self.decode_verified_webhook(headers, body_text, config, "微信支付回调")
        event_type = str(payload.get("event_type") or "").upper()
        payload_hash = self.webhook_payload_hash(body_text)
        provider_event_id = self.provider_event_id(payload, event_type, payload_hash)
        event = self.claim_webhook_event(provider_event_id, event_type, payload_hash)
        if event.get("duplicate"):
            self.audit_payment_event(provider_event_id, event_type, event.get("merchant_order_no") or "", "duplicate")
            return {"duplicate": True, "processing_status": event["processing_status"]}
        try:
            if event_type not in PAYMENT_EVENT_STATES:
                raise PaymentWebhookError("event_type_unsupported", "不支持的微信支付回调事件类型")
            try:
                transaction = self.decrypt_wechat_resource(payload.get("resource") or {}, config.api_v3_key)
            except Exception as exc:
                raise PaymentWebhookError("decrypt_failed", "微信支付回调解密失败") from exc
            if not isinstance(transaction, dict):
                raise PaymentWebhookError("decrypt_payload_invalid", "微信支付回调资源格式错误")
            result = self.process_payment_webhook_event(event, payload_hash, event_type, transaction, config)
            self.audit_payment_event(
                provider_event_id,
                event_type,
                result.get("merchant_order_no") or "",
                result["processing_status"],
            )
            return result
        except Exception as exc:
            code = self.webhook_error_code(exc)
            self.mark_webhook_event_failed(event["id"], payload_hash, code)
            self.audit_payment_event(provider_event_id, event_type, "", code)
            raise

    def process_payment_webhook_event(
        self,
        event: dict[str, Any],
        payload_hash: str,
        event_type: str,
        transaction: dict[str, Any],
        config: WechatPayConfig,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            locked_event = self.locked_webhook_event(connection, event["id"])
            if locked_event["payload_hash"] != payload_hash:
                raise WebhookEventConflictError("payload_hash_mismatch", "支付事件报文摘要不一致")
            if locked_event["processing_status"] in WEBHOOK_TERMINAL_STATUSES:
                return {
                    "duplicate": True,
                    "processing_status": locked_event["processing_status"],
                    "merchant_order_no": locked_event.get("merchant_order_no") or "",
                }
            connection.execute(
                "UPDATE payment_webhook_events SET processing_status = 'processing', updated_at = ? WHERE id = ?",
                (now_iso(), event["id"]),
            )
            outcome = self.apply_payment_notification(connection, event_type, transaction, config)
            self.finalize_webhook_event(
                connection,
                event["id"],
                outcome["processing_status"],
                outcome["merchant_order_no"],
                outcome.get("resource_id") or "",
                outcome.get("transaction_id") or "",
                outcome.get("failure_reason") or "",
            )
            return {"duplicate": False, **outcome}

    def apply_payment_notification(
        self,
        connection,
        event_type: str,
        transaction: dict[str, Any],
        config: WechatPayConfig,
    ) -> dict[str, Any]:
        expected_trade_state = PAYMENT_EVENT_STATES[event_type]
        trade_state = str(transaction.get("trade_state") or "").upper()
        if trade_state != expected_trade_state:
            raise PaymentWebhookError("event_state_mismatch", "支付事件类型与交易状态不一致")
        appid = str(transaction.get("appid") or "")
        mchid = str(transaction.get("mchid") or "")
        if not config.app_id or appid != config.app_id:
            raise PaymentWebhookError("appid_mismatch", "微信支付回调 AppID 不匹配")
        if not config.mch_id or mchid != config.mch_id:
            raise PaymentWebhookError("mchid_mismatch", "微信支付回调商户号不匹配")
        merchant_order_no = str(transaction.get("out_trade_no") or "").strip()
        if not merchant_order_no:
            raise PaymentWebhookError("merchant_order_missing", "微信支付回调缺少商户订单号")
        amount = transaction.get("amount") or {}
        paid_total = self.strict_webhook_amount(
            amount.get("total"),
            "amount_invalid",
            "微信支付回调金额格式错误",
        )
        currency = str(amount.get("currency") or "").upper()
        lock_clause = " FOR UPDATE" if self.mysql_transactions else ""
        row = connection.execute(
            f"SELECT * FROM orders WHERE out_trade_no = ?{lock_clause}",
            (merchant_order_no,),
        ).fetchone()
        if not row:
            raise PaymentWebhookError("order_missing", "微信支付回调订单不存在")
        order_row = dict(row)
        order = self.public_order(order_row)
        if paid_total != int(order["total_fee"]):
            raise PaymentWebhookError("amount_mismatch", "微信支付回调金额与订单不一致")
        if not currency or currency != str(order["currency"] or "").upper():
            raise PaymentWebhookError("currency_mismatch", "微信支付回调币种与订单不一致")
        if order_row.get("payment_appid") and order_row["payment_appid"] != appid:
            raise PaymentWebhookError("order_appid_mismatch", "订单支付 AppID 归属不匹配")
        if order_row.get("payment_mchid") and order_row["payment_mchid"] != mchid:
            raise PaymentWebhookError("order_mchid_mismatch", "订单支付商户归属不匹配")
        if order_row.get("payment_currency") and order_row["payment_currency"] != currency:
            raise PaymentWebhookError("order_currency_mismatch", "订单支付币种归属不匹配")

        transaction_id = str(transaction.get("transaction_id") or "").strip()
        if trade_state == "SUCCESS" and not transaction_id:
            raise PaymentWebhookError("transaction_id_missing", "微信支付回调缺少交易号")
        existing_transaction = str(
            order_row.get("payment_transaction_id")
            or (order.get("payment") or {}).get("transaction_id")
            or ""
        )
        if existing_transaction and transaction_id and existing_transaction != transaction_id:
            raise PaymentWebhookError("transaction_id_mismatch", "微信支付交易号与订单不一致")
        if transaction_id:
            transaction_owner = connection.execute(
                """
                SELECT order_id FROM orders
                WHERE payment_provider = 'wechat_pay' AND payment_transaction_id = ? AND order_id <> ?
                """,
                (transaction_id, order["order_id"]),
            ).fetchone()
            if transaction_owner:
                raise PaymentWebhookError("transaction_id_reused", "微信支付交易号已属于其他订单")

        if order["payment_status"] in {"paid", "refunded"}:
            return {
                "processing_status": "ignored",
                "merchant_order_no": merchant_order_no,
                "resource_id": transaction_id,
                "transaction_id": transaction_id,
                "failure_reason": "already_paid",
            }

        if trade_state == "SUCCESS":
            if order["status"] == "closed" or order["payment_status"] in {"cancelled", "expired", "failed"}:
                return {
                    "processing_status": "compensation_required",
                    "merchant_order_no": merchant_order_no,
                    "resource_id": transaction_id,
                    "transaction_id": transaction_id,
                    "failure_reason": "closed_order_paid",
                }
            if order["status"] != "pending_payment" or order["payment_status"] not in {"unpaid", "processing"}:
                raise PaymentWebhookError("order_state_invalid", "订单当前状态不能确认支付")
            reservations = self.reservation_rows(connection, order["order_id"])
            if not reservations or any(item["status"] != "reserved" for item in reservations):
                raise PaymentWebhookError("reservation_state_invalid", "订单库存预占状态不能确认支付")
            self.confirm_reservations(connection, order["order_id"])
            success_time = str(transaction.get("success_time") or now_iso())
            payment = {
                **dict(order.get("payment") or {}),
                "provider": "wechat_pay",
                "transaction_id": transaction_id,
                "trade_state": trade_state,
                "success_time": success_time,
            }
            connection.execute(
                """
                UPDATE orders
                SET payment_json = ?, payment_provider = 'wechat_pay',
                    payment_transaction_id = ?, payment_appid = ?, payment_mchid = ?,
                    payment_currency = ?, payment_confirmed_at = ?, updated_at = ?
                WHERE order_id = ?
                """,
                (
                    json.dumps(payment, ensure_ascii=False),
                    transaction_id,
                    appid,
                    mchid,
                    currency,
                    success_time,
                    now_iso(),
                    order["order_id"],
                ),
            )
            self.transition_order(
                order,
                "pending_ship",
                event_label="微信支付成功，等待商家发货",
                connection=connection,
                payment_status="paid",
                paid_at=success_time,
            )
            return {
                "processing_status": "succeeded",
                "merchant_order_no": merchant_order_no,
                "resource_id": transaction_id,
                "transaction_id": transaction_id,
            }

        if order["status"] == "closed":
            return {
                "processing_status": "ignored",
                "merchant_order_no": merchant_order_no,
                "resource_id": transaction_id,
                "transaction_id": transaction_id,
                "failure_reason": "already_closed",
            }
        if order["status"] != "pending_payment" or order["payment_status"] not in {"unpaid", "processing"}:
            raise PaymentWebhookError("order_state_invalid", "支付状态事件与订单当前状态不兼容")
        if trade_state == "USERPAYING":
            self.transition_order(order, "pending_payment", connection=connection, payment_status="processing")
            status = "succeeded"
        elif trade_state == "NOTPAY":
            self.append_order_event(
                order,
                status=order["status"],
                label="微信支付未完成，可重新发起支付",
                connection=connection,
                payment_status="unpaid",
            )
            status = "succeeded"
        else:
            self.release_reservations(connection, order["order_id"], "released")
            self.transition_order(
                order,
                "closed",
                event_label="微信支付失败，库存预占已释放",
                connection=connection,
                payment_status="failed",
            )
            status = "succeeded"
        return {
            "processing_status": status,
            "merchant_order_no": merchant_order_no,
            "resource_id": transaction_id,
            "transaction_id": transaction_id,
        }

    def handle_wechat_refund_notify(self, headers: dict[str, str], body_text: str) -> dict[str, Any]:
        config = WechatPayConfig()
        payload = self.decode_verified_webhook(headers, body_text, config, "微信退款回调")
        event_type = str(payload.get("event_type") or "").upper()
        payload_hash = self.webhook_payload_hash(body_text)
        provider_event_id = self.provider_event_id(payload, event_type, payload_hash)
        event = self.claim_webhook_event(provider_event_id, event_type, payload_hash)
        if event.get("duplicate"):
            self.audit_payment_event(provider_event_id, event_type, event.get("merchant_order_no") or "", "duplicate")
            return {"duplicate": True, "processing_status": event["processing_status"]}
        try:
            if event_type not in REFUND_EVENT_STATES:
                raise PaymentWebhookError("event_type_unsupported", "不支持的微信退款回调事件类型")
            try:
                refund_result = self.decrypt_wechat_resource(payload.get("resource") or {}, config.api_v3_key)
            except Exception as exc:
                raise PaymentWebhookError("decrypt_failed", "微信退款回调解密失败") from exc
            if not isinstance(refund_result, dict):
                raise PaymentWebhookError("decrypt_payload_invalid", "微信退款回调资源格式错误")
            result = self.process_refund_webhook_event(event, payload_hash, event_type, refund_result, config)
            self.audit_payment_event(
                provider_event_id,
                event_type,
                result.get("merchant_order_no") or "",
                result["processing_status"],
            )
            return result
        except Exception as exc:
            code = self.webhook_error_code(exc)
            self.mark_webhook_event_failed(event["id"], payload_hash, code)
            self.audit_payment_event(provider_event_id, event_type, "", code)
            raise

    def process_refund_webhook_event(
        self,
        event: dict[str, Any],
        payload_hash: str,
        event_type: str,
        refund_result: dict[str, Any],
        config: WechatPayConfig,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            locked_event = self.locked_webhook_event(connection, event["id"])
            if locked_event["payload_hash"] != payload_hash:
                raise WebhookEventConflictError("payload_hash_mismatch", "退款事件报文摘要不一致")
            if locked_event["processing_status"] in WEBHOOK_TERMINAL_STATUSES:
                return {
                    "duplicate": True,
                    "processing_status": locked_event["processing_status"],
                    "merchant_order_no": locked_event.get("merchant_order_no") or "",
                }
            connection.execute(
                "UPDATE payment_webhook_events SET processing_status = 'processing', updated_at = ? WHERE id = ?",
                (now_iso(), event["id"]),
            )
            outcome = self.apply_refund_notification(connection, event_type, refund_result, config)
            self.finalize_webhook_event(
                connection,
                event["id"],
                outcome["processing_status"],
                outcome["merchant_order_no"],
                outcome.get("resource_id") or "",
                outcome.get("transaction_id") or "",
                outcome.get("failure_reason") or "",
            )
            return {"duplicate": False, **outcome}

    def apply_refund_notification(
        self,
        connection,
        event_type: str,
        refund_result: dict[str, Any],
        config: WechatPayConfig,
    ) -> dict[str, Any]:
        refund_status = str(refund_result.get("refund_status") or "").upper()
        if refund_status != REFUND_EVENT_STATES[event_type]:
            raise PaymentWebhookError("event_state_mismatch", "退款事件类型与退款状态不一致")
        if not config.mch_id or refund_result.get("mchid") != config.mch_id:
            raise PaymentWebhookError("mchid_mismatch", "微信退款回调商户号不匹配")
        merchant_order_no = str(refund_result.get("out_trade_no") or "").strip()
        if not merchant_order_no:
            raise PaymentWebhookError("merchant_order_missing", "微信退款回调缺少商户订单号")
        lock_clause = " FOR UPDATE" if self.mysql_transactions else ""
        row = connection.execute(
            f"SELECT * FROM orders WHERE out_trade_no = ?{lock_clause}",
            (merchant_order_no,),
        ).fetchone()
        if not row:
            raise PaymentWebhookError("order_missing", "微信退款回调订单不存在")
        order_row = dict(row)
        order = self.public_order(order_row)
        transaction_id = str(refund_result.get("transaction_id") or "").strip()
        expected_transaction = str(
            order_row.get("payment_transaction_id")
            or (order.get("payment") or {}).get("transaction_id")
            or ""
        )
        if not expected_transaction or transaction_id != expected_transaction:
            raise PaymentWebhookError("transaction_id_mismatch", "退款交易号与原支付订单不一致")
        refund = dict(order.get("refund") or {})
        expected_refund_no = str(refund.get("out_refund_no") or "").strip()
        actual_refund_no = str(refund_result.get("out_refund_no") or "").strip()
        if not expected_refund_no or actual_refund_no != expected_refund_no:
            raise PaymentWebhookError("out_refund_no_mismatch", "微信退款单号与本地退款申请不一致")
        amount = refund_result.get("amount") or {}
        total_fee = self.strict_webhook_amount(
            amount.get("total"),
            "refund_amount_invalid",
            "微信退款回调金额格式错误",
        )
        refund_fee = self.strict_webhook_amount(
            amount.get("refund"),
            "refund_amount_invalid",
            "微信退款回调金额格式错误",
        )
        if total_fee != int(order["total_fee"]):
            raise PaymentWebhookError("amount_mismatch", "退款原订单金额不一致")
        expected_refund = int(refund.get("refund_fee") or order["total_fee"])
        if refund_fee <= 0 or refund_fee != expected_refund or refund_fee > total_fee:
            raise PaymentWebhookError("refund_amount_mismatch", "微信退款金额与退款申请不一致")
        refund_id = str(refund_result.get("refund_id") or "").strip()
        resource_id = refund_id or str(refund_result.get("out_refund_no") or "")
        if order["status"] == "refunded" and order["payment_status"] == "refunded":
            self.resolve_linked_after_sale_case(connection, order, "wechat")
            return {
                "processing_status": "ignored",
                "merchant_order_no": merchant_order_no,
                "resource_id": resource_id,
                "transaction_id": transaction_id,
                "failure_reason": "already_refunded",
            }
        if order["payment_status"] != "paid" or order["status"] in {"pending_payment", "closed"}:
            raise PaymentWebhookError("refund_order_state_invalid", "订单当前状态不能处理退款通知")
        normalized_status = {
            "SUCCESS": "success",
            "ABNORMAL": "abnormal",
            "CLOSED": "closed",
            "PROCESSING": "processing",
        }[refund_status]
        refund = {
            **dict(order.get("refund") or {}),
            "status": normalized_status,
            "wechat_status": refund_status,
            "out_refund_no": actual_refund_no,
            "refund_id": refund_id,
            "transaction_id": transaction_id,
            "success_time": refund_result.get("success_time") or "",
            "refund_fee": refund_fee,
            "total_fee": total_fee,
            "notified_at": now_iso(),
        }
        if refund_status == "SUCCESS":
            if order["status"] != "refund_requested":
                raise PaymentWebhookError("refund_order_state_invalid", "退款成功通知与订单状态不一致")
            refund = self.apply_refund_inventory_disposition(connection, order, refund)
            self.transition_order(
                order,
                "refunded",
                event_label="微信退款成功，订单已退款",
                connection=connection,
                payment_status="refunded",
                refund_status="success",
                refund=refund,
            )
            self.resolve_linked_after_sale_case(
                connection,
                {**order, "status": "refunded", "payment_status": "refunded", "refund_status": "success", "refund": refund},
                "wechat",
            )
            status = "succeeded"
        else:
            connection.execute(
                "UPDATE orders SET refund_status = ?, refund_json = ?, updated_at = ? WHERE order_id = ?",
                (normalized_status, json.dumps(refund, ensure_ascii=False), now_iso(), order["order_id"]),
            )
            self.resolve_linked_after_sale_case(
                connection,
                {**order, "refund_status": normalized_status, "refund": refund},
                "wechat",
            )
            status = "succeeded"
        return {
            "processing_status": status,
            "merchant_order_no": merchant_order_no,
            "resource_id": resource_id,
            "transaction_id": transaction_id,
        }

    def query_wechat_refund(self, out_refund_no: str, config: WechatPayConfig) -> dict[str, Any]:
        return self.wechat_request(
            "GET",
            f"/v3/refund/domestic/refunds/{out_refund_no}",
            {},
            config,
            error_label="微信退款查询失败",
        )

    def sync_wechat_refund(self, order_id: str, operator: str = "") -> dict[str, Any]:
        order = self.get_order(order_id)
        if order.get("payment_status") not in {"paid", "refunded"}:
            raise ValueError("未支付订单不能同步退款状态")
        if order.get("status") not in {"refund_requested", "refunded"}:
            raise ValueError("订单未进入退款流程")
        refund = dict(order.get("refund") or {})
        out_refund_no = str(refund.get("out_refund_no") or "").strip()
        if not out_refund_no or len(out_refund_no) > 64:
            raise ValueError("退款单号缺失或非法，不能同步退款状态")
        config = WechatPayConfig()
        if not config.ready:
            raise ValueError(f"微信支付未配置：缺少 {', '.join(config.missing)}")
        refund_result = self.query_wechat_refund(out_refund_no, config)
        if str(refund_result.get("mchid") or "") != str(config.mch_id or ""):
            raise ValueError("微信退款查询结果商户号不匹配")
        if str(refund_result.get("out_refund_no") or "") != out_refund_no:
            raise ValueError("微信退款查询结果退款单号不匹配")
        if str(refund_result.get("out_trade_no") or "") != str(order.get("out_trade_no") or ""):
            raise ValueError("微信退款查询结果订单号不匹配")
        expected_transaction = str((order.get("payment") or {}).get("transaction_id") or "")
        if not expected_transaction or str(refund_result.get("transaction_id") or "") != expected_transaction:
            raise ValueError("微信退款查询结果交易号不匹配")
        query_status = str(refund_result.get("status") or refund_result.get("refund_status") or "").upper()
        if query_status not in {"SUCCESS", "PROCESSING", "ABNORMAL", "CLOSED"}:
            raise ValueError("微信退款查询结果状态非法")
        amount = refund_result.get("amount") or {}
        try:
            query_total_fee = int(amount.get("total"))
            query_refund_fee = int(amount.get("refund"))
        except (TypeError, ValueError):
            raise ValueError("微信退款查询结果金额字段非法") from None
        if query_total_fee != int(order.get("total_fee") or 0):
            raise ValueError("微信退款查询结果原订单金额不匹配")
        expected_refund = int(refund.get("refund_fee") or order.get("total_fee") or 0)
        if expected_refund <= 0 or query_refund_fee != expected_refund:
            raise ValueError("微信退款查询结果退款金额不匹配")
        if amount.get("currency") and amount.get("currency") != (order.get("currency") or "CNY"):
            raise ValueError("微信退款查询结果币种不匹配")
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            locked_row = self.order_row_for_update(connection, order_id)
            if not locked_row:
                raise ValueError("订单不存在")
            locked_order = self.public_order(locked_row)
            if locked_order.get("payment_status") not in {"paid", "refunded"}:
                raise ValueError("退款同步期间订单支付状态已变化")
            if locked_order.get("status") not in {"refund_requested", "refunded"}:
                raise ValueError("退款同步期间订单状态已变化")
            if int(locked_order.get("total_fee") or 0) != int(order.get("total_fee") or 0):
                raise ValueError("退款同步期间订单金额已变化")
            locked_transaction = str((locked_order.get("payment") or {}).get("transaction_id") or "")
            if locked_transaction != expected_transaction:
                raise ValueError("退款同步期间支付交易号已变化")
            locked_refund = dict(locked_order.get("refund") or {})
            if str(locked_refund.get("out_refund_no") or "") != out_refund_no:
                raise OrderConflictError("退款同步期间退款单号已变化")
            if int(locked_refund.get("refund_fee") or locked_order.get("total_fee") or 0) != expected_refund:
                raise OrderConflictError("退款同步期间退款金额已变化")
            self.apply_wechat_refund_result(
                locked_order,
                refund_result,
                f"后台同步微信退款状态：{operator}".rstrip("："),
                connection=connection,
            )
        return self.get_order(order_id)

    def apply_wechat_refund_result(
        self,
        order: dict[str, Any],
        refund_result: dict[str, Any],
        event_label_prefix: str = "微信退款结果通知",
        connection=None,
    ) -> dict[str, Any]:
        amount = refund_result.get("amount") or {}
        refund_status = str(refund_result.get("refund_status") or refund_result.get("status") or "").upper()
        normalized_status = {
            "SUCCESS": "success",
            "ABNORMAL": "abnormal",
            "CLOSED": "closed",
            "PROCESSING": "processing",
        }.get(refund_status, refund_status.lower() or "unknown")
        refund = dict(order.get("refund") or {})
        refund.update(
            {
                "status": normalized_status,
                "wechat_status": refund_status,
                "out_refund_no": refund_result.get("out_refund_no") or refund.get("out_refund_no") or "",
                "refund_id": refund_result.get("refund_id") or refund.get("refund_id") or "",
                "transaction_id": refund_result.get("transaction_id") or refund.get("transaction_id") or "",
                "success_time": refund_result.get("success_time") or refund.get("success_time") or "",
                "refund_fee": int(amount.get("refund") or refund.get("refund_fee") or 0),
                "total_fee": int(amount.get("total") or refund.get("total_fee") or order.get("total_fee") or 0),
                "payer_refund_fee": int(amount.get("payer_refund") or 0),
                "notified_at": now_iso(),
            }
        )
        if refund_status == "SUCCESS":
            if order.get("status") == "refunded" and order.get("payment_status") == "refunded":
                self.update_refund_snapshot(
                    order["order_id"],
                    refund,
                    refund_status="success",
                    payment_status="refunded",
                    connection=connection,
                )
            elif order.get("status") == "refund_requested" and order.get("payment_status") == "paid":
                if connection is None:
                    raise ValueError("退款成功结果必须在订单事务中应用")
                refund = self.apply_refund_inventory_disposition(connection, order, refund)
                self.transition_order(
                    order,
                    "refunded",
                    event_label="微信退款成功，订单已退款",
                    payment_status="refunded",
                    refund_status="success",
                    refund=refund,
                    connection=connection,
                )
            else:
                raise ValueError("订单当前状态不能应用退款成功结果")
            if connection is None:
                self.sync_linked_after_sale_case(
                    {**order, "status": "refunded", "payment_status": "refunded", "refund_status": "success", "refund": refund},
                    operator=event_label_prefix,
                )
            else:
                self.resolve_linked_after_sale_case(
                    connection,
                    {**order, "status": "refunded", "payment_status": "refunded", "refund_status": "success", "refund": refund},
                    operator=event_label_prefix,
                )
        else:
            if order.get("status") == "refunded" or order.get("payment_status") == "refunded":
                return refund
            self.append_order_event(
                order,
                status=order["status"],
                label=f"{event_label_prefix}：{refund_status or 'UNKNOWN'}",
                refund_status=normalized_status,
                refund=refund,
                connection=connection,
            )
            if normalized_status in {"processing", "abnormal", "closed"}:
                next_order = {
                    **order,
                    "refund_status": normalized_status,
                    "refund": refund,
                }
                if connection is None:
                    self.sync_linked_after_sale_case(next_order, operator=event_label_prefix)
                else:
                    self.resolve_linked_after_sale_case(
                        connection,
                        next_order,
                        operator=event_label_prefix,
                    )
        return refund

    def update_refund_snapshot(
        self,
        order_id: str,
        refund: dict[str, Any],
        refund_status: str | None = None,
        payment_status: str | None = None,
        connection=None,
    ) -> None:
        set_parts = ["updated_at = ?", "refund_json = ?"]
        values: list[Any] = [now_iso(), json.dumps(refund, ensure_ascii=False)]
        if refund_status is not None:
            set_parts.append("refund_status = ?")
            values.append(refund_status)
        if payment_status is not None:
            set_parts.append("payment_status = ?")
            values.append(payment_status)
        values.append(order_id)
        if connection is not None:
            connection.execute(f"UPDATE orders SET {', '.join(set_parts)} WHERE order_id = ?", values)
            return
        with self.connect() as owned_connection:
            owned_connection.execute(f"UPDATE orders SET {', '.join(set_parts)} WHERE order_id = ?", values)

    def verify_wechat_notify_signature(
        self,
        serial: str,
        timestamp: str,
        nonce: str,
        signature: str,
        body_text: str,
        config: WechatPayConfig,
    ) -> None:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        if serial.upper().startswith("PUB_KEY_ID_"):
            public_key_bytes = config.public_key_bytes()
            if not public_key_bytes:
                raise ValueError("缺少微信支付公钥")
            if config.public_key_id and config.public_key_id.upper() != serial.upper():
                raise ValueError("微信支付公钥 ID 不匹配")
            public_key = serialization.load_pem_public_key(public_key_bytes)
        else:
            from cryptography import x509

            cert_bytes = config.platform_cert_bytes() or self.fetch_wechat_platform_cert(serial, config)
            cert = x509.load_pem_x509_certificate(cert_bytes)
            if format(cert.serial_number, "X").upper() != serial.upper():
                raise ValueError("微信支付平台证书序列号不匹配")
            public_key = cert.public_key()
        message = f"{timestamp}\n{nonce}\n{body_text}\n".encode("utf-8")
        try:
            public_key.verify(
                base64.b64decode(signature),
                message,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except InvalidSignature as exc:
            raise ValueError("微信支付回调验签失败") from exc

    def fetch_wechat_platform_cert(self, serial: str, config: WechatPayConfig) -> bytes:
        payload = self.wechat_request("GET", "/v3/certificates", {}, config)
        for item in payload.get("data") or []:
            if str(item.get("serial_no") or "").upper() != serial.upper():
                continue
            plaintext = self.decrypt_wechat_resource(
                item.get("encrypt_certificate") or {},
                config.api_v3_key,
            )
            if not isinstance(plaintext, str):
                raise ValueError("微信支付平台证书格式错误")
            return plaintext.encode("utf-8")
        raise ValueError("未找到匹配的微信支付平台证书")

    @staticmethod
    def decrypt_wechat_resource(resource: dict[str, Any], api_v3_key: str) -> dict[str, Any] | str:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = str(resource.get("nonce") or "").encode("utf-8")
        associated_data = str(resource.get("associated_data") or "").encode("utf-8")
        ciphertext = base64.b64decode(str(resource.get("ciphertext") or ""))
        plaintext = AESGCM(api_v3_key.encode("utf-8")).decrypt(nonce, ciphertext, associated_data)
        text = plaintext.decode("utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def build_miniprogram_pay_params(self, prepay_id: str, config: WechatPayConfig) -> dict[str, str]:
        time_stamp = str(int(time.time()))
        nonce_str = secrets.token_hex(16)
        package_value = f"prepay_id={prepay_id}"
        pay_sign = self.sign_message(f"{config.app_id}\n{time_stamp}\n{nonce_str}\n{package_value}\n", config)
        return {
            "timeStamp": time_stamp,
            "nonceStr": nonce_str,
            "package": package_value,
            "signType": "RSA",
            "paySign": pay_sign,
        }

    def sign_message(self, message: str, config: WechatPayConfig) -> str:
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
        except ImportError as exc:
            raise ValueError("缺少 cryptography 依赖，无法生成微信支付签名") from exc

        private_key = serialization.load_pem_private_key(config.private_key_bytes(), password=None)
        signature = private_key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode("utf-8")

    def update_payment(
        self,
        order_id: str,
        payment: dict[str, Any],
        provider: str = "",
        appid: str = "",
        mchid: str = "",
        currency: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE orders
                SET payment_json = ?,
                    payment_provider = CASE WHEN ? <> '' THEN ? ELSE payment_provider END,
                    payment_appid = CASE WHEN ? <> '' THEN ? ELSE payment_appid END,
                    payment_mchid = CASE WHEN ? <> '' THEN ? ELSE payment_mchid END,
                    payment_currency = CASE WHEN ? <> '' THEN ? ELSE payment_currency END,
                    updated_at = ?
                WHERE order_id = ?
                """,
                (
                    json.dumps(payment, ensure_ascii=False),
                    provider,
                    provider,
                    appid,
                    appid,
                    mchid,
                    mchid,
                    currency,
                    currency,
                    now_iso(),
                    order_id,
                ),
            )

    def payment_confirmation(self, order_id: str, user_id: str) -> dict[str, Any]:
        order = self.get_order(order_id)
        self.ensure_order_owner(order, user_id)
        paid = order["payment_status"] == "paid"
        terminal = paid or order["status"] in {"closed", "refunded"}
        return {
            "order_id": order["order_id"],
            "status": order["status"],
            "payment_status": order["payment_status"],
            "paid": paid,
            "terminal": terminal,
            "updated_at": order["updated_at"],
        }

    def query_wechat_transaction(self, out_trade_no: str, config: WechatPayConfig) -> dict[str, Any]:
        merchant_order_no = str(out_trade_no or "").strip()
        if not merchant_order_no:
            raise ValueError("商户订单号不能为空")
        if not config.mch_id:
            raise ValueError("缺少微信支付商户号")
        return self.wechat_request(
            "GET",
            f"/v3/pay/transactions/out-trade-no/{merchant_order_no}?mchid={config.mch_id}",
            {},
            config,
            error_label="微信支付订单查询失败",
        )

    def reconcile_processing_payments(self, limit: int = 100) -> dict[str, Any]:
        config = WechatPayConfig()
        if not config.ready:
            return {
                "configured": False,
                "checked": 0,
                "updated": 0,
                "compensation_required": 0,
                "failed": 0,
                "results": [],
            }
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT order_id, out_trade_no FROM orders
                WHERE status = 'pending_payment' AND payment_status = 'processing'
                ORDER BY updated_at ASC LIMIT ?
                """,
                (max(1, min(int(limit), 1000)),),
            ).fetchall()
        event_types = {
            "SUCCESS": "TRANSACTION.SUCCESS",
            "CLOSED": "TRANSACTION.CLOSED",
            "PAYERROR": "TRANSACTION.PAYERROR",
            "USERPAYING": "TRANSACTION.USERPAYING",
            "NOTPAY": "TRANSACTION.NOTPAY",
        }
        results: list[dict[str, Any]] = []
        for row in rows:
            order_id = str(row["order_id"])
            try:
                transaction = self.query_wechat_transaction(str(row["out_trade_no"]), config)
                trade_state = str(transaction.get("trade_state") or "").upper()
                event_type = event_types.get(trade_state)
                if not event_type:
                    raise ValueError(f"不支持的微信支付状态：{trade_state or 'UNKNOWN'}")
                with self.connect() as connection:
                    self.begin_order_transaction(connection)
                    outcome = self.apply_payment_notification(
                        connection,
                        event_type,
                        transaction,
                        config,
                    )
                results.append({"order_id": order_id, "trade_state": trade_state, **outcome})
            except Exception as exc:
                results.append({"order_id": order_id, "error_type": type(exc).__name__})
        return {
            "configured": True,
            "checked": len(results),
            "updated": sum(
                1 for item in results if item.get("processing_status") in {"succeeded", "ignored"}
            ),
            "compensation_required": sum(
                1 for item in results if item.get("processing_status") == "compensation_required"
            ),
            "failed": sum(1 for item in results if item.get("error_type")),
            "results": results,
        }

    def list_payment_compensations(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT e.id, e.provider_event_id, e.merchant_order_no, e.transaction_id,
                       e.failure_reason, e.received_at, e.updated_at,
                       o.order_id, o.user_id, o.status AS order_status,
                       o.payment_status, o.total_fee, o.currency
                FROM payment_webhook_events e
                LEFT JOIN orders o ON o.out_trade_no = e.merchant_order_no
                WHERE e.processing_status = 'compensation_required'
                ORDER BY e.received_at ASC
                LIMIT ?
                """,
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def resolve_payment_compensation(
        self,
        event_id: str,
        action: str,
        operator: str,
        note: str,
    ) -> dict[str, Any]:
        normalized_action = str(action or "").strip()
        if normalized_action not in {"refund_verified", "manual_settlement_verified"}:
            raise ValueError("请选择有效的支付补偿处理结果")
        normalized_note = str(note or "").strip()
        if len(normalized_note) < 5:
            raise ValueError("请填写至少 5 个字的处理凭证说明")
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            event = self.locked_webhook_event(connection, event_id)
            if event["processing_status"] == "compensation_resolved":
                return event
            if event["processing_status"] != "compensation_required":
                raise ValueError("该支付事件不在人工补偿队列中")
            resolution = (
                f"resolved:{normalized_action}:{str(operator or 'admin')[:40]}:"
                f"{normalized_note}"
            )[:120]
            timestamp = now_iso()
            connection.execute(
                """
                UPDATE payment_webhook_events
                SET processing_status = 'compensation_resolved', failure_reason = ?,
                    processed_at = ?, updated_at = ?
                WHERE id = ? AND processing_status = 'compensation_required'
                """,
                (resolution, timestamp, timestamp, event_id),
            )
            updated = self.locked_webhook_event(connection, event_id)
        return updated

    def get_order(self, order_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if not row:
            raise ValueError("订单不存在")
        return self.public_order(dict(row))

    def list_user_orders(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [self.public_order(dict(row)) for row in rows]

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def public_order(self, row: dict[str, Any]) -> dict[str, Any]:
        status_history = self.loads(row.get("status_history_json") or "", [])
        if not status_history:
            status_history = [{
                "status": row["status"],
                "label": ORDER_STATUS_TEXT.get(row["status"], row["status"]),
                "time": row["updated_at"],
            }]
        return {
            "order_id": row["order_id"],
            "out_trade_no": row["out_trade_no"],
            "user_id": row["user_id"],
            "design_id": row.get("design_id") or "",
            "status": row["status"],
            "status_text": ORDER_STATUS_TEXT.get(row["status"], row["status"]),
            "payment_status": row["payment_status"],
            "total_amount": self.cents_text(int(row["total_fee"])),
            "total_fee": int(row["total_fee"]),
            "currency": row["currency"],
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
            "logistics_signed_at": row.get("logistics_signed_at") or "",
            "auto_complete_at": row.get("auto_complete_at") or "",
            "status_history": status_history,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "paid_at": row.get("paid_at"),
            "reservation_expires_at": row.get("reservation_expires_at") or "",
        }

    @staticmethod
    def ensure_order_owner(order: dict[str, Any], user_id: str) -> None:
        if order["user_id"] != user_id:
            raise ValueError("无权操作该订单")

    def validate_and_refresh_material_prices(self, sequence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self.connect() as connection:
            self.begin_order_transaction(connection)
            snapshots, _ = self.lock_validate_and_snapshot_items(connection, sequence)
            return snapshots

    @staticmethod
    def rebuild_bom_from_sequence(sequence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for item in sequence:
            key = str(item.get("sku") or item.get("skuId") or item.get("id") or item.get("name") or "")
            if not key:
                continue
            quantity = int(item.get("quantity") or 1)
            unit_cents = int(item.get("unit_price_cents") or 0)
            subtotal_cents = unit_cents * quantity
            row = grouped.setdefault(
                key,
                {
                    "id": item.get("id") or key,
                    "sku": item.get("sku") or item.get("skuId") or key,
                    "name": item.get("name") or "珠材",
                    "category": item.get("category") or "",
                    "size": item.get("size") or 0,
                    "price": OrderService.cents_text(unit_cents),
                    "unit_price_cents": unit_cents,
                    "qty": 0,
                    "total": "0.00",
                    "subtotal_cents": 0,
                    "price_version": item.get("price_version") or "",
                    "image_url": item.get("image_url") or "",
                },
            )
            row["qty"] += quantity
            row["subtotal_cents"] += subtotal_cents
            row["total"] = OrderService.cents_text(row["subtotal_cents"])
        return list(grouped.values())

    @staticmethod
    def calculate_sequence_total(sequence: list[dict[str, Any]]) -> Decimal:
        cents = sum(
            int(item.get("subtotal_cents") or 0)
            for item in sequence
        )
        return Decimal(cents) / Decimal("100")

    @staticmethod
    def calculate_total_amount(design: dict[str, Any], sequence: list[dict[str, Any]]) -> Decimal:
        return OrderService.calculate_sequence_total(sequence)

    @staticmethod
    def to_cents(amount: Decimal) -> int:
        return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @staticmethod
    def loads(text: str, default):
        if not text:
            return default
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return default
