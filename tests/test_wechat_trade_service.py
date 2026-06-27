from __future__ import annotations

from app.wechat_trade_service import WechatTradeService


def configured_service(monkeypatch) -> WechatTradeService:
    monkeypatch.setenv("WECHAT_APP_ID", "wx-test")
    monkeypatch.setenv("WECHAT_APP_SECRET", "secret")
    monkeypatch.setenv("WECHAT_PAY_MCH_ID", "1746874094")
    return WechatTradeService()


def test_upload_shipping_builds_official_payload(monkeypatch):
    service = configured_service(monkeypatch)
    calls = []

    def fake_call(path, body):
        calls.append((path, body))
        return {"errcode": 0, "errmsg": "ok"}

    monkeypatch.setattr(service, "call", fake_call)
    order = {
        "out_trade_no": "202606220001",
        "openid": "o-real-openid",
        "receiver": {"phone": "13800138000"},
        "payment": {"transaction_id": "4200000000202606260000000001"},
        "bom": [{"name": "海蓝宝 8mm", "qty": 12}, {"name": "银隔片", "qty": 2}],
    }
    result = service.upload_shipping(
        order,
        {
            "carrier": "顺丰速运",
            "carrier_code": "shunfeng",
            "tracking_no": "SF123456789",
        },
    )

    assert result["synced"] is True
    path, payload = calls[0]
    assert path == "/wxa/sec/order/upload_shipping_info"
    assert payload["order_key"] == {
        "order_number_type": 1,
        "transaction_id": "4200000000202606260000000001",
    }
    assert payload["payer"]["openid"] == "o-real-openid"
    assert payload["shipping_list"][0]["express_company"] == "SF"
    assert payload["shipping_list"][0]["contact"]["receiver_contact"] == "138****8000"
    assert "海蓝宝 8mm×12" in payload["shipping_list"][0]["item_desc"]


def test_upload_shipping_skips_dev_order(monkeypatch):
    service = configured_service(monkeypatch)
    result = service.upload_shipping(
        {"out_trade_no": "1", "openid": "dev_test", "receiver": {}, "bom": []},
        {"tracking_no": "TEST", "carrier_code": "SF"},
    )
    assert result == {"skipped": True, "reason": "非真实微信订单"}


def test_upload_shipping_skips_order_without_wechat_transaction(monkeypatch):
    service = configured_service(monkeypatch)
    result = service.upload_shipping(
        {"out_trade_no": "202606220001", "openid": "o-real-openid", "receiver": {}, "bom": []},
        {"tracking_no": "TEST", "carrier_code": "SF"},
    )
    assert result["skipped"] is True
    assert "支付流水号" in result["reason"]


def test_upload_shipping_retries_out_trade_no_when_transaction_key_missing_in_wechat(monkeypatch):
    service = configured_service(monkeypatch)
    calls = []

    def fake_call(path, body):
        calls.append((path, body))
        if len(calls) == 1:
            raise ValueError("微信交易管理接口调用失败：/wxa/sec/order/upload_shipping_info（10060001）：支付单不存在")
        return {"errcode": 0, "errmsg": "ok"}

    monkeypatch.setattr(service, "call", fake_call)
    result = service.upload_shipping(
        {
            "out_trade_no": "202606220001",
            "openid": "o-real-openid",
            "receiver": {"phone": "13800138000"},
            "payment": {"transaction_id": "4200000000202606260000000001"},
            "bom": [],
        },
        {"tracking_no": "SF123456789", "carrier_code": "shunfeng"},
    )

    assert result["synced"] is True
    assert calls[0][1]["order_key"] == {
        "order_number_type": 1,
        "transaction_id": "4200000000202606260000000001",
    }
    assert calls[1][1]["order_key"] == {
        "order_number_type": 2,
        "mchid": "1746874094",
        "out_trade_no": "202606220001",
    }


def test_order_path_requires_placeholder(monkeypatch):
    service = configured_service(monkeypatch)
    try:
        service.configure_order_detail_path("pages/order-detail/order-detail?id=123")
    except ValueError as exc:
        assert "${商品订单号}" in str(exc)
    else:
        raise AssertionError("missing order placeholder should fail")


def test_default_order_path_starts_with_slash(monkeypatch):
    service = configured_service(monkeypatch)
    assert service.order_detail_path == "/pages/order-detail/order-detail?id=${商品订单号}"


def test_trade_status_uses_completed_field(monkeypatch):
    service = configured_service(monkeypatch)
    responses = iter(
        [
            {"errcode": 0, "is_trade_managed": True},
            {"errcode": 0, "completed": True},
            {"errcode": 0, "path": "pages/order-detail/order-detail?id=${商品订单号}"},
        ]
    )
    monkeypatch.setattr(service, "call", lambda path, body: next(responses))
    status = service.status()
    assert status["is_trade_managed"] is True
    assert status["confirmation_completed"] is True
