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
from .materials import clean_image_urls
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
    "after_sale": "售后中",
    "refund_requested": "退款中",
    "refunded": "已退款",
    "closed": "已关闭",
}

ORDER_STATE_TRANSITIONS = {
    "pending_payment": {"pending_ship", "closed"},
    "pending_ship": {"shipped", "refund_requested"},
    "shipped": {"completed", "after_sale", "refund_requested"},
    "completed": {"after_sale"},
    "after_sale": {"refund_requested", "completed"},
    "refund_requested": {"refunded", "after_sale"},
    "refunded": set(),
    "closed": set(),
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
WEBHOOK_TERMINAL_STATUSES = {"succeeded", "ignored", "compensation_required"}
KUAIDI100_PHONE_REQUIRED_COMPANIES = {"shunfeng", "shunfengkuaiyun", "zhongtong"}
KUAIDI100_CALLBACK_MAX_BYTES = 512 * 1024
SIGNED_AUTO_COMPLETE_DAYS = 7


class OrderConflictError(ValueError):
    pass


class OrderPricingError(ValueError):
    pass


class OrderPriceChangedError(OrderConflictError):
    pass


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

        by_reference: dict[str, dict[str, Any]] = {}
        for raw_row in rows:
            material = dict(raw_row)
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
        order = self.get_order(order_id)
        self.ensure_order_owner(order, user_id)
        if order["payment_status"] != "paid":
            raise ValueError("订单未支付，不能发货")
        self.transition_order(
            order,
            "shipped",
            event_label="商家已发货",
            logistics=self.build_logistics(carrier, tracking_no, carrier_code, phone_tail),
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
        order = self.get_order(order_id)
        self.ensure_order_owner(order, user_id)
        if order["status"] not in {"pending_payment", "pending_ship"}:
            raise ValueError("订单已发货，不能修改收货地址")

        clean_receiver = self.normalize_order_receiver(receiver)
        timestamp = now_iso()
        history = list(order.get("status_history") or [])
        history.append({
            "status": order["status"],
            "label": "用户修改收货地址",
            "time": timestamp,
        })
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE orders
                SET receiver_json = ?, updated_at = ?, status_history_json = ?
                WHERE order_id = ?
                """,
                (
                    json.dumps(clean_receiver, ensure_ascii=False),
                    timestamp,
                    json.dumps(history, ensure_ascii=False),
                    order_id,
                ),
            )
        return self.get_order(order_id)

    def request_after_sale(self, order_id: str, user_id: str, reason: str = "") -> dict[str, Any]:
        order = self.get_order(order_id)
        self.ensure_order_owner(order, user_id)
        if order["payment_status"] != "paid":
            raise ValueError("未支付订单不能申请售后")
        remark = f"{order.get('remark') or ''}\n售后原因：{reason}".strip()
        self.transition_order(
            order,
            "after_sale",
            event_label="用户申请售后",
            remark=remark,
            after_sale_status="requested",
        )
        return self.get_order(order_id)

    def request_refund(self, order_id: str, user_id: str, reason: str = "") -> dict[str, Any]:
        order = self.get_order(order_id)
        self.ensure_order_owner(order, user_id)
        if order["payment_status"] != "paid":
            raise ValueError("未支付订单不能申请退款")
        if order["status"] in {"refunded", "closed"}:
            raise ValueError("当前订单状态不能申请退款")
        if order["status"] == "refund_requested":
            raise ValueError("订单已提交退款申请，请等待商家处理")
        requested_at = now_iso()
        refund = {
            **(order.get("refund") or {}),
            "status": "requested",
            "reason": reason or "用户申请退款",
            "requested_at": requested_at,
            "refund_fee": int(order.get("total_fee") or self.to_cents(Decimal(str(order.get("total_amount") or 0)))),
            "total_fee": int(order.get("total_fee") or 0),
            "currency": order.get("currency") or "CNY",
        }
        remark = f"{order.get('remark') or ''}\n退款原因：{reason}".strip()
        self.transition_order(
            order,
            "refund_requested",
            event_label="用户申请退款",
            remark=remark,
            refund_status="requested",
            refund=refund,
        )
        return self.get_order(order_id)

    def approve_refund(self, order_id: str, operator: str = "", note: str = "") -> dict[str, Any]:
        order = self.get_order(order_id)
        if order["status"] != "refund_requested":
            raise ValueError("仅退款申请中的订单可以同意退款")
        if order["payment_status"] != "paid":
            raise ValueError("订单未处于已支付状态，不能发起原路退款")
        if order.get("refund_status") == "processing" or (order.get("refund") or {}).get("status") == "processing":
            raise ValueError("退款已提交微信处理，请不要重复发起")
        refund = dict(order.get("refund") or {})
        total_fee = int(order.get("total_fee") or self.to_cents(Decimal(str(order.get("total_amount") or 0))))
        if total_fee <= 0:
            raise ValueError("订单金额异常，不能退款")
        refund_fee = int(refund.get("refund_fee") or total_fee)
        if refund_fee <= 0 or refund_fee > total_fee:
            raise ValueError("退款金额异常，不能超过原订单金额")
        out_refund_no = str(refund.get("out_refund_no") or f"RF{order['order_id']}")[:64]
        config = WechatPayConfig()
        if not config.ready:
            raise ValueError(f"微信支付未配置：缺少 {', '.join(config.missing)}")
        response = self.create_wechat_refund(
            order,
            out_refund_no,
            refund_fee,
            total_fee,
            note or refund.get("reason") or "用户申请退款",
            config,
        )
        wechat_status = str(response.get("status") or "").upper()
        timestamp = now_iso()
        refund.update(
            {
                "status": "success" if wechat_status == "SUCCESS" else "processing",
                "out_refund_no": out_refund_no,
                "refund_fee": refund_fee,
                "total_fee": total_fee,
                "currency": order.get("currency") or "CNY",
                "approved_at": timestamp,
                "approved_by": operator,
                "approve_note": note,
                "wechat_status": wechat_status,
                "wechat_response": response,
            }
        )
        if wechat_status == "SUCCESS":
            self.transition_order(
                order,
                "refunded",
                event_label="后台已同意退款，微信原路退款成功",
                payment_status="refunded",
                refund_status="success",
                refund=refund,
            )
        else:
            self.append_order_event(
                order,
                status=order["status"],
                label=f"后台已同意退款，微信退款处理中：{wechat_status or 'PROCESSING'}",
                refund_status="processing",
                refund=refund,
            )
        return self.get_order(order_id)

    def reject_refund(self, order_id: str, operator: str = "", note: str = "") -> dict[str, Any]:
        order = self.get_order(order_id)
        if order["status"] != "refund_requested":
            raise ValueError("仅退款申请中的订单可以拒绝退款")
        refund = dict(order.get("refund") or {})
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
            "after_sale",
            event_label=note or "后台拒绝退款，转入售后处理",
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
        current_status = order["status"]
        allowed = ORDER_STATE_TRANSITIONS.get(current_status, set())
        if target_status != current_status and target_status not in allowed:
            current = ORDER_STATUS_TEXT.get(current_status, current_status)
            target = ORDER_STATUS_TEXT.get(target_status, target_status)
            raise ValueError(f"订单状态不能从 {current} 变更为 {target}")

        timestamp = now_iso()
        history = list(order.get("status_history") or [])
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
        values.append(order["order_id"])
        if connection is not None:
            connection.execute(f"UPDATE orders SET {', '.join(set_parts)} WHERE order_id = ?", values)
            return
        with self.connect() as owned_connection:
            owned_connection.execute(f"UPDATE orders SET {', '.join(set_parts)} WHERE order_id = ?", values)

    def append_order_event(
        self,
        order: dict[str, Any],
        status: str,
        label: str,
        connection=None,
        **updates,
    ) -> None:
        timestamp = now_iso()
        history = list(order.get("status_history") or [])
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
        values.append(order["order_id"])
        if connection is not None:
            connection.execute(f"UPDATE orders SET {', '.join(set_parts)} WHERE order_id = ?", values)
            return
        with self.connect() as owned_connection:
            owned_connection.execute(f"UPDATE orders SET {', '.join(set_parts)} WHERE order_id = ?", values)

    def build_logistics(
        self,
        carrier: str,
        tracking_no: str | None = None,
        carrier_code: str = "shunfeng",
        phone_tail: str | None = None,
    ) -> dict[str, Any]:
        timestamp = now_iso()
        tracking = tracking_no or f"YJ{int(time.time())}{secrets.token_hex(3).upper()}"
        return {
            "carrier": carrier or "顺丰速运",
            "carrier_code": carrier_code or "shunfeng",
            "tracking_no": tracking,
            "phone_tail": phone_tail or "",
            "status": "in_transit",
            "status_text": "运输中",
            "updated_at": timestamp,
            "source": "local",
            "traces": [
                {"time": timestamp, "location": "宇涧水晶工作室", "desc": "商家已打包，待快递揽收"},
                {"time": timestamp, "location": "宇涧水晶工作室", "desc": "商家已填写发货信息，等待物流公司更新轨迹"},
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
                SELECT order_id FROM orders
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
                SELECT order_id FROM orders
                WHERE status = 'shipped' AND auto_complete_at IS NULL
                ORDER BY updated_at ASC LIMIT ?
                """,
                (limit,),
            ).fetchall()
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
            "image_url", "name", "size", "size_mm",
        }

        def safe_placement(value: Any) -> dict[str, Any]:
            if not isinstance(value, dict):
                return {}
            return {key: item for key, item in value.items() if key in placement_keys}

        design_keys = {
            "name", "title", "selected", "placements", "wearStyle", "isLooseMode",
            "workspaceStageCenter", "workspace_stage_center",
            "preview_image", "previewImage", "image_url",
        }
        sequence_keys = {
            "id", "sku", "skuId", "name", "category", "series", "size", "size_mm",
            "color", "shine", "image_url", "placement",
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
            raise ValueError(f"{error_label}：网络超时") from exc
        if response.status_code >= 400:
            metrics.increment("external_service_failed_total", service="wechat_pay", status_code=response.status_code)
            log_event(
                external_logger,
                "external.wechat_pay.failed",
                level=logging.WARNING,
                service="wechat_pay",
                status_code=response.status_code,
                result="failed",
            )
            raise ValueError(f"{error_label}：HTTP {response.status_code}")
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
            status = "ignored"
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
        expected_refund = int((order.get("refund") or {}).get("refund_fee") or order["total_fee"])
        if refund_fee <= 0 or refund_fee != expected_refund or refund_fee > total_fee:
            raise PaymentWebhookError("refund_amount_mismatch", "微信退款金额与退款申请不一致")
        refund_id = str(refund_result.get("refund_id") or "").strip()
        resource_id = refund_id or str(refund_result.get("out_refund_no") or "")
        if order["status"] == "refunded" and order["payment_status"] == "refunded":
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
            "out_refund_no": refund_result.get("out_refund_no") or "",
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
            self.transition_order(
                order,
                "refunded",
                event_label="微信退款成功，订单已退款",
                connection=connection,
                payment_status="refunded",
                refund_status="success",
                refund=refund,
            )
            status = "succeeded"
        else:
            connection.execute(
                "UPDATE orders SET refund_status = ?, refund_json = ?, updated_at = ? WHERE order_id = ?",
                (normalized_status, json.dumps(refund, ensure_ascii=False), now_iso(), order["order_id"]),
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
        out_refund_no = str(refund.get("out_refund_no") or f"RF{order_id}")[:64]
        config = WechatPayConfig()
        if not config.ready:
            raise ValueError(f"微信支付未配置：缺少 {', '.join(config.missing)}")
        refund_result = self.query_wechat_refund(out_refund_no, config)
        if refund_result.get("mchid") and refund_result.get("mchid") != config.mch_id:
            raise ValueError("微信退款查询结果商户号不匹配")
        refund_result.setdefault("out_refund_no", out_refund_no)
        refund_result.setdefault("out_trade_no", order.get("out_trade_no") or order_id)
        if refund_result.get("out_trade_no") != order.get("out_trade_no"):
            raise ValueError("微信退款查询结果订单号不匹配")
        expected_transaction = str((order.get("payment") or {}).get("transaction_id") or "")
        if not expected_transaction or refund_result.get("transaction_id") != expected_transaction:
            raise ValueError("微信退款查询结果交易号不匹配")
        amount = refund_result.get("amount") or {}
        if int(amount.get("total") or 0) != int(order.get("total_fee") or 0):
            raise ValueError("微信退款查询结果原订单金额不匹配")
        expected_refund = int(refund.get("refund_fee") or order.get("total_fee") or 0)
        if int(amount.get("refund") or 0) != expected_refund:
            raise ValueError("微信退款查询结果退款金额不匹配")
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
