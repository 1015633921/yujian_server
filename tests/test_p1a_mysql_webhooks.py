from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest


def mysql_test_configuration() -> dict[str, str]:
    database = os.getenv("P1A_MYSQL_TEST_DATABASE", "")
    host = os.getenv("P1A_MYSQL_TEST_HOST", "127.0.0.1")
    if os.getenv("RUN_P1A_MYSQL_INTEGRATION") != "1":
        pytest.skip("set RUN_P1A_MYSQL_INTEGRATION=1 to run isolated MySQL payment tests")
    shared_test_database = database.lower() == "yujian_test"
    if shared_test_database:
        if os.getenv("ALLOW_SHARED_MYSQL_TEST_DATABASE") != "1":
            pytest.fail("set ALLOW_SHARED_MYSQL_TEST_DATABASE=1 to use the backed-up yujian_test database")
        if not os.getenv("MYSQL_TEST_BACKUP_ID", "").strip():
            pytest.fail("MYSQL_TEST_BACKUP_ID is required before using yujian_test")
    elif "p1a_test" not in database.lower():
        pytest.fail("P1A_MYSQL_TEST_DATABASE must be yujian_test or contain 'p1a_test'; production databases are forbidden")
    if host not in {"127.0.0.1", "localhost", "mysql"}:
        pytest.fail("P1-A MySQL tests only allow an isolated local/container host")
    return {
        "MYSQL_HOST": host,
        "MYSQL_PORT": os.getenv("P1A_MYSQL_TEST_PORT", "3306"),
        "MYSQL_DATABASE": database,
        "MYSQL_USER": os.environ["P1A_MYSQL_TEST_USER"],
        "MYSQL_PASSWORD": os.environ["P1A_MYSQL_TEST_PASSWORD"],
    }


@pytest.mark.mysql_integration
def test_mysql_payment_event_migration_and_concurrent_deduplication(monkeypatch):
    config = mysql_test_configuration()
    monkeypatch.setenv("DATABASE_BACKEND", "mysql")
    monkeypatch.setenv("WECHAT_PAYMENT_ENABLED", "false")
    for key, value in config.items():
        monkeypatch.setenv(key, value)

    from app import database as database_module
    from app.admin_service import AdminService
    from app.migrations.runner import downgrade, upgrade
    from app.order_service import OrderService

    class FakeConfig:
        app_id = "wx-p1a-mysql"
        mch_id = "p1a-mysql-mch"
        api_v3_key = "0" * 32

    monkeypatch.setattr("app.order_service.WechatPayConfig", FakeConfig)

    database_module._schema_ready.discard(config["MYSQL_DATABASE"])
    AdminService()
    OrderService()
    upgrade("mysql")
    assert downgrade("mysql", steps=1) == ["20260712_06_p1_material_price_cents"]
    assert downgrade("mysql", steps=1) == ["20260712_05_p1c_runtime_tasks"]
    assert downgrade("mysql", steps=1) == ["20260712_04_p1b_report_snapshots"]
    assert downgrade("mysql", steps=1) == ["20260712_03_p1a_payment_events"]
    assert upgrade("mysql") == [
        "20260712_03_p1a_payment_events",
        "20260712_04_p1b_report_snapshots",
        "20260712_05_p1c_runtime_tasks",
        "20260712_06_p1_material_price_cents",
    ]

    service = OrderService()
    sku_id = "p1a_mysql_webhook_sku"
    user_id = "p1a-mysql-webhook-user"
    with service.connect() as connection:
        connection.execute("DELETE FROM payment_webhook_events WHERE provider_event_id = ?", ("p1a-mysql-event",))
        connection.execute("DELETE FROM inventory_reservations WHERE sku_id = ?", (sku_id,))
        connection.execute("DELETE FROM order_requests WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM orders WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM managed_materials WHERE id = ?", (sku_id,))
        connection.execute(
            """
            INSERT INTO managed_materials
            (id, skuId, top, category, series, material_code, grade, name, effect,
             element, price, price_cents, size, weight, cost_price, safety_stock, supplier_name,
             purchase_note, color, shine, image_path, image_url, image_urls_json,
             stock, reserved_stock, enabled, sort_order, created_at, updated_at)
            VALUES (?, ?, 'bead', 'test', 'P1A', 'p1a_mysql', '', 'P1A MySQL SKU',
                    '', '水', 10.00, 1000, 8, 1, 0, 0, '', '', '#fff', '#fff', '', '', '[]',
                    2, 0, 1, 0, '2026-07-12T00:00:00+00:00', '2026-07-12T00:00:00+00:00')
            """,
            (sku_id, sku_id),
        )
    order = service.create_order(
        {
            "idempotency_key": "p1a-mysql-order-key",
            "user_id": user_id,
            "receiver": {"name": "Test", "phone": "13800000000", "address": "Test"},
            "design": {},
            "sequence": [{"id": sku_id, "price": "10.00", "quantity": 1}],
            "bom": [],
        }
    )["order"]
    resource = {
        "appid": FakeConfig.app_id,
        "mchid": FakeConfig.mch_id,
        "out_trade_no": order["out_trade_no"],
        "transaction_id": "p1a-mysql-transaction",
        "trade_state": "SUCCESS",
        "success_time": "2026-07-12T12:01:00+08:00",
        "amount": {"total": order["total_fee"], "currency": "CNY"},
    }
    body = json.dumps(
        {
            "id": "p1a-mysql-event",
            "event_type": "TRANSACTION.SUCCESS",
            "resource": {"ciphertext": "fixture"},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    headers = {
        "wechatpay-serial": "PUB_KEY_ID_TEST",
        "wechatpay-timestamp": "1790000000",
        "wechatpay-nonce": "nonce",
        "wechatpay-signature": "signature",
    }

    def attempt(_index: int):
        worker = OrderService()
        worker.verify_wechat_notify_signature = lambda *_args, **_kwargs: None
        worker.decrypt_wechat_resource = lambda *_args, **_kwargs: resource
        return worker.handle_wechat_notify(headers, body)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))

    with service.connect() as connection:
        event_count = connection.execute(
            "SELECT COUNT(*) AS total FROM payment_webhook_events WHERE provider_event_id = ?",
            ("p1a-mysql-event",),
        ).fetchone()["total"]
        material = connection.execute(
            "SELECT stock, reserved_stock FROM managed_materials WHERE id = ?", (sku_id,)
        ).fetchone()
    assert int(event_count) == 1
    assert sum(not result.get("duplicate") for result in results) == 1
    assert int(material["stock"]) == 1 and int(material["reserved_stock"]) == 0
