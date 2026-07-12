from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import pytest


def mysql_test_configuration() -> dict[str, str]:
    database = os.getenv("P0B_MYSQL_TEST_DATABASE", "")
    host = os.getenv("P0B_MYSQL_TEST_HOST", "127.0.0.1")
    if os.getenv("RUN_P0B_MYSQL_INTEGRATION") != "1":
        pytest.skip("set RUN_P0B_MYSQL_INTEGRATION=1 to run isolated MySQL concurrency test")
    shared_test_database = database.lower() == "yujian_test"
    if shared_test_database:
        if os.getenv("ALLOW_SHARED_MYSQL_TEST_DATABASE") != "1":
            pytest.fail("set ALLOW_SHARED_MYSQL_TEST_DATABASE=1 to use the backed-up yujian_test database")
        if not os.getenv("MYSQL_TEST_BACKUP_ID", "").strip():
            pytest.fail("MYSQL_TEST_BACKUP_ID is required before using yujian_test")
    elif "p0b_test" not in database.lower():
        pytest.fail("P0B_MYSQL_TEST_DATABASE must be yujian_test or contain 'p0b_test'; production databases are forbidden")
    if host not in {"127.0.0.1", "localhost", "mysql"}:
        pytest.fail("P0-B MySQL integration test only allows an isolated local/container host")
    return {
        "MYSQL_HOST": host,
        "MYSQL_PORT": os.getenv("P0B_MYSQL_TEST_PORT", "3306"),
        "MYSQL_DATABASE": database,
        "MYSQL_USER": os.environ["P0B_MYSQL_TEST_USER"],
        "MYSQL_PASSWORD": os.environ["P0B_MYSQL_TEST_PASSWORD"],
    }


@pytest.mark.mysql_integration
def test_mysql_fifty_concurrent_orders_cannot_oversell(monkeypatch):
    config = mysql_test_configuration()
    monkeypatch.setenv("DATABASE_BACKEND", "mysql")
    for key, value in config.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "false")

    from app import database as database_module
    from app.admin_service import AdminService
    from app.migrations.runner import upgrade
    from app.order_service import OrderPricingError, OrderService

    database_module._schema_ready.discard(config["MYSQL_DATABASE"])
    AdminService()
    OrderService()
    upgrade("mysql")
    service = OrderService()
    sku_id = "p0b_mysql_race_8"
    with service.connect() as connection:
        connection.execute("DELETE FROM inventory_reservations WHERE sku_id = ?", (sku_id,))
        connection.execute("DELETE FROM order_requests WHERE user_id LIKE 'p0b-mysql-user-%'")
        connection.execute("DELETE FROM orders WHERE user_id LIKE 'p0b-mysql-user-%'")
        connection.execute("DELETE FROM managed_materials WHERE id = ?", (sku_id,))
        connection.execute(
            """
            INSERT INTO managed_materials
            (id, skuId, top, category, series, material_code, grade, name, effect,
             element, price, price_cents, size, weight, cost_price, safety_stock, supplier_name,
             purchase_note, color, shine, image_path, image_url, image_urls_json,
             stock, reserved_stock, enabled, sort_order, created_at, updated_at)
            VALUES (?, ?, 'bead', 'test', 'P0B', 'p0b_mysql_race', '', 'MySQL Race SKU',
                    '', '水', 10.00, 1000, 8, 1, 0, 0, '', '', '#fff', '#fff', '', '', '[]',
                    10, 0, 1, 0, '2026-07-12T00:00:00+00:00', '2026-07-12T00:00:00+00:00')
            """,
            (sku_id, sku_id),
        )

    def attempt(index: int) -> bool:
        worker = OrderService()
        try:
            worker.create_order(
                {
                    "idempotency_key": f"p0b-mysql-key-{index:03d}",
                    "user_id": f"p0b-mysql-user-{index:03d}",
                    "receiver": {"name": "Test", "phone": "13800000000", "address": "Test"},
                    "design": {},
                    "sequence": [{"id": sku_id, "price": "10.00", "quantity": 1}],
                    "bom": [],
                }
            )
            return True
        except OrderPricingError:
            return False

    with ThreadPoolExecutor(max_workers=50) as executor:
        outcomes = list(executor.map(attempt, range(50)))

    with service.connect() as connection:
        material = connection.execute(
            "SELECT stock, reserved_stock FROM managed_materials WHERE id = ?", (sku_id,)
        ).fetchone()
        orders = connection.execute(
            "SELECT COUNT(*) AS total FROM orders WHERE user_id LIKE 'p0b-mysql-user-%'"
        ).fetchone()
        reservations = connection.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS total FROM inventory_reservations "
            "WHERE sku_id = ? AND status = 'reserved'",
            (sku_id,),
        ).fetchone()

    assert sum(outcomes) == 10
    assert int(orders["total"]) == 10
    assert int(reservations["total"]) == 10
    assert int(material["stock"]) == 10
    assert int(material["reserved_stock"]) == 10
    assert int(material["stock"]) - int(material["reserved_stock"]) == 0
