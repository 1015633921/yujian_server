from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest


def mysql_test_configuration() -> dict[str, str]:
    database = os.getenv("P1C_MYSQL_TEST_DATABASE", "")
    host = os.getenv("P1C_MYSQL_TEST_HOST", "127.0.0.1")
    if os.getenv("RUN_P1C_MYSQL_INTEGRATION") != "1":
        pytest.skip("set RUN_P1C_MYSQL_INTEGRATION=1 to run the MySQL runtime lease gate")
    if database.lower() == "yujian_test":
        if os.getenv("ALLOW_SHARED_MYSQL_TEST_DATABASE") != "1":
            pytest.fail("set ALLOW_SHARED_MYSQL_TEST_DATABASE=1 after backing up yujian_test")
        if not os.getenv("MYSQL_TEST_BACKUP_ID", "").strip():
            pytest.fail("MYSQL_TEST_BACKUP_ID is required before using yujian_test")
    elif "p1c_test" not in database.lower():
        pytest.fail("P1C_MYSQL_TEST_DATABASE must be yujian_test or contain 'p1c_test'")
    if host not in {"127.0.0.1", "localhost", "mysql"}:
        pytest.fail("P1-C MySQL tests only allow a local/container host")
    return {
        "MYSQL_HOST": host,
        "MYSQL_PORT": os.getenv("P1C_MYSQL_TEST_PORT", "3306"),
        "MYSQL_DATABASE": database,
        "MYSQL_USER": os.environ["P1C_MYSQL_TEST_USER"],
        "MYSQL_PASSWORD": os.environ["P1C_MYSQL_TEST_PASSWORD"],
    }


@pytest.mark.mysql_integration
def test_mysql_runtime_lease_allows_only_one_worker(monkeypatch):
    config = mysql_test_configuration()
    monkeypatch.setenv("DATABASE_BACKEND", "mysql")
    monkeypatch.setenv("LOGISTICS_SYNC_ENABLED", "true")
    for key, value in config.items():
        monkeypatch.setenv(key, value)

    from app import database as database_module
    from app.admin_service import AdminService
    from app.migrations.runner import downgrade, upgrade
    from app.order_service import OrderService
    from app.runtime_tasks import LogisticsTaskRunner, RuntimeTaskStore

    database_module._schema_ready.discard(config["MYSQL_DATABASE"])
    AdminService()
    OrderService()
    upgrade("mysql")
    assert downgrade("mysql", steps=2) == [
        "20260712_06_p1_material_price_cents",
        "20260712_05_p1c_runtime_tasks",
    ]
    assert upgrade("mysql") == [
        "20260712_05_p1c_runtime_tasks",
        "20260712_06_p1_material_price_cents",
    ]

    store = RuntimeTaskStore()
    with store.connect() as connection:
        connection.execute("DELETE FROM runtime_task_runs WHERE task_name = 'logistics_sync'")
        connection.execute("DELETE FROM runtime_task_leases WHERE task_name = 'logistics_sync'")

    calls = 0
    calls_lock = threading.Lock()

    class FakeOrders:
        def refresh_active_shipments(self, limit=50):
            nonlocal calls
            with calls_lock:
                calls += 1
            time.sleep(0.1)
            return {"checked": 1, "failed_order_ids": []}

    def attempt(owner_id: str):
        return LogisticsTaskRunner(
            order_service=FakeOrders(),
            sleep_fn=lambda _seconds: None,
            owner_id=owner_id,
        ).run_once()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ("mysql-worker-a", "mysql-worker-b")))

    with store.connect() as connection:
        run_count = connection.execute(
            "SELECT COUNT(*) AS total FROM runtime_task_runs WHERE task_name = 'logistics_sync'"
        ).fetchone()["total"]
    assert calls == 1
    assert int(run_count) == 1
    assert sum(result["executed"] for result in results) == 1
