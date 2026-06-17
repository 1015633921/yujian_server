from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import httpx

from .repository import DB_PATH


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


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class WechatPayConfig:
    def __init__(self) -> None:
        self.app_id = os.getenv("WECHAT_PAY_APP_ID") or os.getenv("WECHAT_APP_ID") or os.getenv("WX_APPID")
        self.mch_id = os.getenv("WECHAT_PAY_MCH_ID") or os.getenv("WX_MCH_ID")
        self.serial_no = os.getenv("WECHAT_PAY_SERIAL_NO") or os.getenv("WX_PAY_SERIAL_NO")
        self.notify_url = os.getenv("WECHAT_PAY_NOTIFY_URL") or os.getenv("WX_PAY_NOTIFY_URL")
        self.private_key_path = os.getenv("WECHAT_PAY_PRIVATE_KEY_PATH") or os.getenv("WX_PAY_PRIVATE_KEY_PATH")
        self.private_key_text = os.getenv("WECHAT_PAY_PRIVATE_KEY") or os.getenv("WX_PAY_PRIVATE_KEY")

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


class Kuaidi100Config:
    def __init__(self) -> None:
        self.customer = os.getenv("KUAIDI100_CUSTOMER") or os.getenv("KUAIDI100_CUSTOMER_ID")
        self.key = os.getenv("KUAIDI100_KEY") or os.getenv("KUAIDI100_SECRET")
        self.query_url = os.getenv("KUAIDI100_QUERY_URL") or "https://poll.kuaidi100.com/poll/query.do"

    @property
    def ready(self) -> bool:
        return bool(self.customer and self.key)


class OrderService:
    def __init__(self, db_path=DB_PATH) -> None:
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
                    logistics_json TEXT,
                    status_history_json TEXT
                )
                """
            )
            self.ensure_columns(connection)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id, created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, payment_status)")

    def ensure_columns(self, connection: sqlite3.Connection) -> None:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(orders)").fetchall()}
        migrations = {
            "after_sale_status": "ALTER TABLE orders ADD COLUMN after_sale_status TEXT",
            "refund_status": "ALTER TABLE orders ADD COLUMN refund_status TEXT",
            "logistics_json": "ALTER TABLE orders ADD COLUMN logistics_json TEXT",
            "status_history_json": "ALTER TABLE orders ADD COLUMN status_history_json TEXT",
        }
        for column, sql in migrations.items():
            if column not in columns:
                connection.execute(sql)

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            raise ValueError("user_id 不能为空")
        receiver = payload.get("receiver") or {}
        if not receiver.get("name"):
            raise ValueError("请填写收货人")
        if not receiver.get("phone"):
            raise ValueError("请填写手机号")
        if not receiver.get("address"):
            raise ValueError("请填写详细地址")

        design = payload.get("design") or {}
        sequence = payload.get("sequence") or []
        bom = payload.get("bom") or []
        if not sequence:
            raise ValueError("订单材料不能为空")

        user = self.get_user(user_id) or {}
        total_amount = self.calculate_total_amount(design, sequence)
        total_fee = self.to_cents(total_amount)
        timestamp = now_iso()
        order_id = f"ord_{secrets.token_hex(8)}"
        out_trade_no = f"YJ{int(time.time())}{secrets.token_hex(4).upper()}"
        history = [{"status": "pending_payment", "label": "订单已创建，等待支付", "time": timestamp}]

        row = {
            "order_id": order_id,
            "out_trade_no": out_trade_no,
            "user_id": user_id,
            "openid": user.get("openid"),
            "status": "pending_payment",
            "payment_status": "unpaid",
            "total_amount": float(total_amount),
            "total_fee": total_fee,
            "currency": "CNY",
            "receiver_json": json.dumps(receiver, ensure_ascii=False),
            "design_json": json.dumps(design, ensure_ascii=False),
            "sequence_json": json.dumps(sequence, ensure_ascii=False),
            "bom_json": json.dumps(bom, ensure_ascii=False),
            "remark": str(payload.get("remark") or "").strip(),
            "payment_json": "",
            "created_at": timestamp,
            "updated_at": timestamp,
            "paid_at": None,
            "after_sale_status": "",
            "refund_status": "",
            "logistics_json": "",
            "status_history_json": json.dumps(history, ensure_ascii=False),
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO orders
                (order_id, out_trade_no, user_id, openid, status, payment_status, total_amount, total_fee,
                 currency, receiver_json, design_json, sequence_json, bom_json, remark, payment_json,
                 created_at, updated_at, paid_at, after_sale_status, refund_status, logistics_json, status_history_json)
                VALUES
                (:order_id, :out_trade_no, :user_id, :openid, :status, :payment_status, :total_amount, :total_fee,
                 :currency, :receiver_json, :design_json, :sequence_json, :bom_json, :remark, :payment_json,
                 :created_at, :updated_at, :paid_at, :after_sale_status, :refund_status, :logistics_json, :status_history_json)
                """,
                row,
            )
        order = self.get_order(order_id)
        payment = self.create_wechat_payment(order)
        return {"order": order, "payment": payment}

    def create_wechat_payment(self, order: dict[str, Any]) -> dict[str, Any]:
        if order.get("payment_status") == "paid":
            return {"available": False, "state": "already_paid", "message": "订单已支付", "pay_params": None}
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
            "description": "遇见水晶 DIY 手串",
            "out_trade_no": order["out_trade_no"],
            "notify_url": config.notify_url,
            "amount": {"total": int(order["total_fee"]), "currency": order["currency"]},
            "payer": {"openid": order["openid"]},
        }
        url_path = "/v3/pay/transactions/jsapi"
        response = self.wechat_request("POST", url_path, body, config)
        prepay_id = response["prepay_id"]
        pay_params = self.build_miniprogram_pay_params(prepay_id, config)
        payment = {
            "available": True,
            "state": "prepay_ready",
            "message": "微信支付预下单成功",
            "prepay_id": prepay_id,
            "pay_params": pay_params,
        }
        self.update_payment(order["order_id"], payment)
        return payment

    def request_payment(self, order_id: str, user_id: str) -> dict[str, Any]:
        order = self.get_order(order_id)
        self.ensure_order_owner(order, user_id)
        return {"order": order, "payment": self.create_wechat_payment(order)}

    def mark_paid_for_dev(self, order_id: str, user_id: str) -> dict[str, Any]:
        order = self.get_order(order_id)
        self.ensure_order_owner(order, user_id)
        if order["payment_status"] == "paid":
            return order
        self.transition_order(
            order,
            "pending_ship",
            event_label="支付成功，等待商家发货",
            payment_status="paid",
            paid_at=now_iso(),
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
        order = self.get_order(order_id)
        self.ensure_order_owner(order, user_id)
        if order["status"] != "shipped":
            raise ValueError("订单尚未发货，不能确认收货")
        self.transition_order(order, "completed", event_label="用户确认收货")
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
        remark = f"{order.get('remark') or ''}\n退款原因：{reason}".strip()
        self.transition_order(
            order,
            "refund_requested",
            event_label="用户申请退款",
            remark=remark,
            refund_status="requested",
        )
        return self.get_order(order_id)

    def get_logistics(self, order_id: str, user_id: str) -> dict[str, Any]:
        order = self.get_order(order_id)
        self.ensure_order_owner(order, user_id)
        logistics = order.get("logistics") or {
            "carrier": "",
            "tracking_no": "",
            "status": "not_shipped",
            "status_text": "商家尚未发货",
            "traces": [],
        }
        logistics = self.refresh_logistics_if_needed(order, logistics)
        return {"order_id": order_id, "logistics": logistics, "status_history": order.get("status_history") or []}

    def transition_order(self, order: dict[str, Any], target_status: str, event_label: str = "", **updates) -> None:
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
        values.append(order["order_id"])
        with self.connect() as connection:
            connection.execute(f"UPDATE orders SET {', '.join(set_parts)} WHERE order_id = ?", values)

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
                {"time": timestamp, "location": "遇见水晶工作室", "desc": "商家已打包并交给快递"},
                {"time": timestamp, "location": "始发分拨中心", "desc": "快件已揽收，正在发往下一站"},
            ],
        }

    def refresh_logistics_if_needed(self, order: dict[str, Any], logistics: dict[str, Any]) -> dict[str, Any]:
        if not logistics.get("tracking_no"):
            return logistics
        config = Kuaidi100Config()
        if not config.ready:
            return {**logistics, "source": logistics.get("source") or "local", "message": "快递100未配置，展示本地物流记录"}
        if self.is_logistics_cache_fresh(logistics):
            return logistics
        try:
            refreshed = self.query_kuaidi100(logistics, config)
        except ValueError as exc:
            return {**logistics, "source": logistics.get("source") or "local", "message": str(exc)}
        self.update_logistics(order["order_id"], refreshed)
        return refreshed

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
        with httpx.Client(timeout=10) as client:
            response = client.post(
                config.query_url,
                data={"customer": config.customer, "sign": sign, "param": param_text},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if response.status_code >= 400:
            raise ValueError(f"快递100查询失败：HTTP {response.status_code}")
        data = response.json()
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
            "status": "signed" if data.get("ischeck") == "1" else "in_transit",
            "status_text": state_text,
            "updated_at": now_iso(),
            "source": "kuaidi100",
            "kuaidi100_state": str(data.get("state", "")),
            "message": data.get("message") or "",
            "traces": traces or logistics.get("traces") or [],
        }

    def update_logistics(self, order_id: str, logistics: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE orders SET logistics_json = ?, updated_at = ? WHERE order_id = ?",
                (json.dumps(logistics, ensure_ascii=False), now_iso(), order_id),
            )

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

    def wechat_request(self, method: str, url_path: str, body: dict[str, Any], config: WechatPayConfig) -> dict[str, Any]:
        url = f"https://api.mch.weixin.qq.com{url_path}"
        body_text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        signature = self.sign_message(f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body_text}\n", config)
        authorization = (
            'WECHATPAY2-SHA256-RSA2048 '
            f'mchid="{config.mch_id}",nonce_str="{nonce}",signature="{signature}",'
            f'timestamp="{timestamp}",serial_no="{config.serial_no}"'
        )
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
                },
            )
        if response.status_code >= 400:
            raise ValueError(f"微信支付预下单失败：{response.text}")
        return response.json()

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

    def update_payment(self, order_id: str, payment: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE orders
                SET payment_json = ?, updated_at = ?
                WHERE order_id = ?
                """,
                (json.dumps(payment, ensure_ascii=False), now_iso(), order_id),
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
            "status": row["status"],
            "status_text": ORDER_STATUS_TEXT.get(row["status"], row["status"]),
            "payment_status": row["payment_status"],
            "total_amount": row["total_amount"],
            "total_fee": row["total_fee"],
            "currency": row["currency"],
            "receiver": self.loads(row["receiver_json"], {}),
            "design": self.loads(row["design_json"], {}),
            "sequence": self.loads(row["sequence_json"], []),
            "bom": self.loads(row["bom_json"], []),
            "remark": row.get("remark") or "",
            "payment": self.loads(row.get("payment_json") or "", {}),
            "after_sale_status": row.get("after_sale_status") or "",
            "refund_status": row.get("refund_status") or "",
            "logistics": self.loads(row.get("logistics_json") or "", {}),
            "status_history": status_history,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "paid_at": row.get("paid_at"),
        }

    @staticmethod
    def ensure_order_owner(order: dict[str, Any], user_id: str) -> None:
        if order["user_id"] != user_id:
            raise ValueError("无权操作该订单")

    @staticmethod
    def calculate_total_amount(design: dict[str, Any], sequence: list[dict[str, Any]]) -> Decimal:
        summary = design.get("summary") or {}
        if summary.get("price") is not None:
            return Decimal(str(summary["price"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = sum(Decimal(str(item.get("price") or 0)) for item in sequence)
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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
