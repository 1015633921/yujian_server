from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time

import pytest


def mysql_test_configuration() -> dict[str, str]:
    database = os.getenv("P1B_MYSQL_TEST_DATABASE", "")
    host = os.getenv("P1B_MYSQL_TEST_HOST", "127.0.0.1")
    if os.getenv("RUN_P1B_MYSQL_INTEGRATION") != "1":
        pytest.skip("set RUN_P1B_MYSQL_INTEGRATION=1 to run isolated MySQL report tests")
    if database.lower() == "yujian_test":
        if os.getenv("ALLOW_SHARED_MYSQL_TEST_DATABASE") != "1":
            pytest.fail("set ALLOW_SHARED_MYSQL_TEST_DATABASE=1 to use the backed-up yujian_test database")
        if not os.getenv("MYSQL_TEST_BACKUP_ID", "").strip():
            pytest.fail("MYSQL_TEST_BACKUP_ID is required before using yujian_test")
    elif "p1b_test" not in database.lower():
        pytest.fail("P1B_MYSQL_TEST_DATABASE must be yujian_test or contain 'p1b_test'; production databases are forbidden")
    if host not in {"127.0.0.1", "localhost", "mysql"}:
        pytest.fail("P1-B MySQL tests only allow an isolated local/container host")
    return {
        "MYSQL_HOST": host,
        "MYSQL_PORT": os.getenv("P1B_MYSQL_TEST_PORT", "3306"),
        "MYSQL_DATABASE": database,
        "MYSQL_USER": os.environ["P1B_MYSQL_TEST_USER"],
        "MYSQL_PASSWORD": os.environ["P1B_MYSQL_TEST_PASSWORD"],
    }


@pytest.mark.mysql_integration
def test_mysql_report_migration_and_concurrent_idempotency(monkeypatch):
    config = mysql_test_configuration()
    monkeypatch.setenv("DATABASE_BACKEND", "mysql")
    monkeypatch.setenv("REPORT_VERSIONING_V2_ENABLED", "false")
    for key, value in config.items():
        monkeypatch.setenv(key, value)

    from app import database as database_module
    from app.admin_service import AdminService
    from app.migrations.runner import downgrade, upgrade
    from app.order_service import OrderService
    from app.repository import AssessmentRepository
    from app.schemas import AssessmentRequest
    from app.service import AssessmentService

    database_module._schema_ready.discard(config["MYSQL_DATABASE"])
    AdminService()
    OrderService()
    AssessmentRepository()
    upgrade("mysql")
    assert downgrade("mysql", steps=1) == ["20260713_07_order_receipt_completion"]
    assert downgrade("mysql", steps=1) == ["20260712_06_p1_material_price_cents"]
    assert downgrade("mysql", steps=1) == ["20260712_05_p1c_runtime_tasks"]
    assert downgrade("mysql", steps=1) == ["20260712_04_p1b_report_snapshots"]
    assert upgrade("mysql") == [
        "20260712_04_p1b_report_snapshots",
        "20260712_05_p1c_runtime_tasks",
        "20260712_06_p1_material_price_cents",
        "20260713_07_order_receipt_completion",
    ]

    user_id = "p1b-mysql-idempotency-user"
    key = "p1b-mysql-shared-key"
    service = AssessmentService()
    with service.report_repository.connect() as connection:
        connection.execute("DELETE FROM assessment_recommendations WHERE report_id IN (SELECT report_id FROM report_snapshots WHERE user_id = ?)", (user_id,))
        connection.execute("DELETE FROM report_generation_requests WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM report_snapshots WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM report_version_counters WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM energy_assessments WHERE user_id = ?", (user_id,))

    request = AssessmentRequest(
        user_id=user_id,
        name="MySQL report test",
        birthday=date(1995, 8, 16),
        birth_time=time(9, 30),
        birth_place="成都市",
        core_wishes=["健康护身/保持专注"],
    )

    def attempt(_index: int):
        return AssessmentService().calculate_energy_v2(request, key)

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(attempt, range(10)))

    report_ids = {result[0]["report_id"] for result in results}
    versions = {int(result[0]["report_version"]) for result in results}
    with service.report_repository.connect() as connection:
        snapshot_count = connection.execute(
            "SELECT COUNT(*) AS total FROM report_snapshots WHERE user_id = ?", (user_id,)
        ).fetchone()["total"]
        request_count = connection.execute(
            "SELECT COUNT(*) AS total FROM report_generation_requests WHERE user_id = ?", (user_id,)
        ).fetchone()["total"]
    assert len(report_ids) == 1
    assert versions == {1}
    assert int(snapshot_count) == 1
    assert int(request_count) == 1
    assert sum(bool(result[1]) for result in results) == 9
