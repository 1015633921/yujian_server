from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

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
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()


EXPRESS_COMPANY_CODES = {
    "shunfeng": "SF",
    "sf": "SF",
    "顺丰": "SF",
    "顺丰速运": "SF",
    "zhongtong": "ZTO",
    "zto": "ZTO",
    "中通": "ZTO",
    "yuantong": "YTO",
    "yto": "YTO",
    "圆通": "YTO",
    "shentong": "STO",
    "sto": "STO",
    "申通": "STO",
    "yunda": "YUNDA",
    "韵达": "YUNDA",
    "jd": "JD",
    "京东": "JD",
    "ems": "EMS",
    "邮政": "EMS",
    "youzhengguonei": "EMS",
    "中国邮政": "EMS",
    "jitu": "JTSD",
    "jtexpress": "JTSD",
    "极兔": "JTSD",
    "debangwuliu": "DBL",
    "debang": "DBL",
    "德邦": "DBL",
    "德邦快递": "DBL",
}


class WechatTradeService:
    def __init__(self) -> None:
        self.app_id = os.getenv("WECHAT_APP_ID") or os.getenv("WX_APPID") or os.getenv("WECHAT_PAY_APP_ID")
        self.app_secret = os.getenv("WECHAT_APP_SECRET") or os.getenv("WX_APP_SECRET")
        self.mch_id = os.getenv("WECHAT_PAY_MCH_ID") or os.getenv("WX_MCH_ID")
        self.sync_enabled = str(os.getenv("WECHAT_TRADE_SYNC_ENABLED", "true")).lower() in {
            "1", "true", "yes", "on",
        }
        self.order_detail_path = os.getenv(
            "WECHAT_ORDER_DETAIL_PATH",
            "/pages/order-detail/order-detail?id=${商品订单号}",
        )
        self._access_token: dict[str, Any] | None = None

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_secret and self.mch_id)

    def access_token(self) -> str:
        import time

        if self._access_token and self._access_token["expires_at"] > time.time() + 60:
            return self._access_token["token"]
        if not self.app_id or not self.app_secret:
            raise ValueError("缺少 WECHAT_APP_ID 或 WECHAT_APP_SECRET，无法调用微信交易管理接口")
        data = self.request_json(
            "GET",
            (
                "https://api.weixin.qq.com/cgi-bin/token"
                f"?grant_type=client_credential&appid={quote(self.app_id)}&secret={quote(self.app_secret)}"
            ),
        )
        self.ensure_success(data, "获取微信 access_token 失败")
        self._access_token = {
            "token": data["access_token"],
            "expires_at": time.time() + int(data.get("expires_in", 7200)),
        }
        return self._access_token["token"]

    def status(self) -> dict[str, Any]:
        if not self.configured:
            return {
                "configured": False,
                "sync_enabled": self.sync_enabled,
                "missing": [
                    name
                    for name, value in {
                        "WECHAT_APP_ID": self.app_id,
                        "WECHAT_APP_SECRET": self.app_secret,
                        "WECHAT_PAY_MCH_ID": self.mch_id,
                    }.items()
                    if not value
                ],
            }
        managed = self.call("/wxa/sec/order/is_trade_managed", {"appid": self.app_id})
        confirmation = self.call(
            "/wxa/sec/order/is_trade_management_confirmation_completed",
            {"appid": self.app_id},
        )
        path = self.call("/wxa/sec/order/get_order_detail_path", {})
        return {
            "configured": True,
            "sync_enabled": self.sync_enabled,
            "appid": self.app_id,
            "mchid": self.mch_id,
            "is_trade_managed": bool(managed.get("is_trade_managed")),
            "confirmation_completed": bool(
                confirmation.get("completed")
                or confirmation.get("is_trade_management_confirmation_completed")
                or confirmation.get("is_completed")
            ),
            "order_detail_path": path.get("path") or "",
            "raw": {
                "trade_managed": managed,
                "confirmation": confirmation,
                "order_detail_path": path,
            },
        }

    def configure_order_detail_path(self, path: str | None = None) -> dict[str, Any]:
        target = (path or self.order_detail_path).strip()
        if "${商品订单号}" not in target:
            raise ValueError("微信订单详情路径必须包含 ${商品订单号}")
        result = self.call("/wxa/sec/order/update_order_detail_path", {"path": target})
        return {"path": target, "wechat": result}

    def upload_shipping(self, order: dict[str, Any], logistics: dict[str, Any]) -> dict[str, Any]:
        if not self.sync_enabled:
            return {"skipped": True, "reason": "WECHAT_TRADE_SYNC_ENABLED=false"}
        if not self.configured:
            return {"skipped": True, "reason": "微信交易管理配置不完整"}
        openid = str(order.get("openid") or "")
        if not openid or openid.startswith("dev_"):
            return {"skipped": True, "reason": "非真实微信订单"}
        payment = order.get("payment") or {}
        if not payment.get("transaction_id"):
            return {"skipped": True, "reason": "订单缺少微信支付流水号，通常是模拟支付或非微信真实支付订单"}
        tracking_no = str(logistics.get("tracking_no") or "").strip()
        if not tracking_no:
            raise ValueError("同步微信发货信息需要快递单号")
        company = self.express_company(
            str(logistics.get("carrier_code") or ""),
            str(logistics.get("carrier") or ""),
        )
        shipping_item: dict[str, Any] = {
            "tracking_no": tracking_no,
            "express_company": company,
            "item_desc": self.item_description(order),
        }
        if company == "SF":
            receiver_phone = str((order.get("receiver") or {}).get("phone") or "")
            contact = self.mask_phone(receiver_phone)
            if not contact:
                raise ValueError("顺丰发货同步微信时需要有效的收件手机号")
            shipping_item["contact"] = {"receiver_contact": contact}
        payload_base = {
            "logistics_type": 1,
            "delivery_mode": 1,
            "shipping_list": [shipping_item],
            "upload_time": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
            "payer": {"openid": openid},
        }
        attempts = []
        last_error: ValueError | None = None
        for order_key in self.order_key_candidates(order):
            payload = {**payload_base, "order_key": order_key}
            attempts.append(order_key)
            try:
                result = self.call("/wxa/sec/order/upload_shipping_info", payload)
                break
            except ValueError as exc:
                last_error = exc
                if "10060001" not in str(exc) and "支付单不存在" not in str(exc):
                    raise
        else:
            if last_error:
                raise last_error
            raise ValueError("无法生成微信交易管理发货单号")
        return {
            "synced": True,
            "express_company": company,
            "tracking_no": tracking_no,
            "uploaded_at": payload["upload_time"],
            "order_key": payload["order_key"],
            "attempted_order_keys": attempts,
            "wechat": result,
        }

    def order_key_candidates(self, order: dict[str, Any]) -> list[dict[str, Any]]:
        payment = order.get("payment") or {}
        transaction_id = str(payment.get("transaction_id") or "").strip()
        out_trade_no = str(order.get("out_trade_no") or "").strip()
        candidates: list[dict[str, Any]] = []
        if transaction_id:
            candidates.append({"order_number_type": 1, "transaction_id": transaction_id})
        if out_trade_no:
            candidates.append({"order_number_type": 2, "mchid": self.mch_id, "out_trade_no": out_trade_no})
        if transaction_id:
            candidates.append({"order_number_type": 2, "transaction_id": transaction_id})
        if out_trade_no:
            candidates.append({"order_number_type": 1, "mchid": self.mch_id, "out_trade_no": out_trade_no})
        unique: list[dict[str, Any]] = []
        seen = set()
        for item in candidates:
            marker = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if marker not in seen:
                seen.add(marker)
                unique.append(item)
        return unique

    def call(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        token = self.access_token()
        data = self.request_json(
            "POST",
            f"https://api.weixin.qq.com{path}?access_token={quote(token)}",
            body,
        )
        self.ensure_success(data, f"微信交易管理接口调用失败：{path}")
        return data

    @staticmethod
    def request_json(method: str, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=data, method=method, headers={"Content-Type": "application/json; charset=utf-8"})
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def ensure_success(data: dict[str, Any], prefix: str) -> None:
        errcode = int(data.get("errcode") or 0)
        if errcode:
            raise ValueError(f"{prefix}（{errcode}）：{data.get('errmsg') or 'unknown error'}")

    @staticmethod
    def express_company(carrier_code: str, carrier: str) -> str:
        for value in (carrier_code, carrier):
            key = value.strip()
            mapped = EXPRESS_COMPANY_CODES.get(key) or EXPRESS_COMPANY_CODES.get(key.lower())
            if mapped:
                return mapped
            if key.isupper() and 2 <= len(key) <= 20:
                return key
        raise ValueError(f"暂不识别快递公司编码：{carrier_code or carrier}")

    @staticmethod
    def mask_phone(phone: str) -> str:
        digits = "".join(char for char in phone if char.isdigit())
        if len(digits) == 11:
            return f"{digits[:3]}****{digits[-4:]}"
        if len(digits) >= 4:
            return f"****{digits[-4:]}"
        return ""

    @staticmethod
    def item_description(order: dict[str, Any]) -> str:
        bom = order.get("bom") or []
        descriptions = []
        for item in bom[:6]:
            name = str(item.get("name") or item.get("sku") or "水晶珠").strip()
            qty = int(item.get("qty") or 1)
            descriptions.append(f"{name}×{qty}")
        text = "、".join(descriptions) or "天然水晶DIY手串×1"
        return text[:120]
