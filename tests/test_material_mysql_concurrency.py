from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import pytest


def mysql_test_configuration() -> dict[str, str]:
    database = os.getenv("MATERIAL_MYSQL_TEST_DATABASE", "")
    host = os.getenv("MATERIAL_MYSQL_TEST_HOST", "127.0.0.1")
    if os.getenv("RUN_MATERIAL_MYSQL_INTEGRATION") != "1":
        pytest.skip("set RUN_MATERIAL_MYSQL_INTEGRATION=1 to run the material MySQL concurrency test")
    shared_test_database = database.lower() == "yujian_test"
    if shared_test_database:
        if os.getenv("ALLOW_SHARED_MYSQL_TEST_DATABASE") != "1":
            pytest.fail("set ALLOW_SHARED_MYSQL_TEST_DATABASE=1 to use the backed-up yujian_test database")
        if not os.getenv("MYSQL_TEST_BACKUP_ID", "").strip():
            pytest.fail("MYSQL_TEST_BACKUP_ID is required before using yujian_test")
    elif "material_test" not in database.lower():
        pytest.fail("MATERIAL_MYSQL_TEST_DATABASE must be yujian_test or contain 'material_test'; production databases are forbidden")
    if host not in {"127.0.0.1", "localhost", "mysql"}:
        pytest.fail("material MySQL integration test only allows an isolated local/container host")
    return {
        "MYSQL_HOST": host,
        "MYSQL_PORT": os.getenv("MATERIAL_MYSQL_TEST_PORT", "3306"),
        "MYSQL_DATABASE": database,
        "MYSQL_USER": os.environ["MATERIAL_MYSQL_TEST_USER"],
        "MYSQL_PASSWORD": os.environ["MATERIAL_MYSQL_TEST_PASSWORD"],
    }


@pytest.mark.mysql_integration
def test_mysql_material_revision_rejects_stale_single_and_batch_edits(monkeypatch):
    """Exactly one competing editor can save a SKU revision; stale batches are all-or-nothing."""
    config = mysql_test_configuration()
    monkeypatch.setenv("DATABASE_BACKEND", "mysql")
    for key, value in config.items():
        monkeypatch.setenv(key, value)

    from app import database as database_module
    from app.admin_service import AdminService, MaterialConflictError
    from app.migrations.runner import upgrade

    service = AdminService()
    database_module._schema_ready.discard(config["MYSQL_DATABASE"])
    upgrade("mysql")
    sku_id = "material_mysql_revision_race"
    category = service.save_material_category({"top": "bead", "name": "material-mysql-test"})
    series = service.save_material_series(
        {"category_id": category["id"], "name": "Revision Race", "material_code": "material_mysql_revision_race"}
    )
    base = {
        "id": sku_id,
        "top": "bead",
        "category": "material-mysql-test",
        "series": "Revision Race",
        "series_id": series["id"],
        "material_code": "material_mysql_revision_race",
        "name": "Revision Race",
        "element": "水",
        "price": 10,
        "size": 8,
        "weight": 1,
        "stock": 12,
        "enabled": True,
    }
    with service.connect() as connection:
        connection.execute("DELETE FROM managed_materials WHERE id=?", (sku_id,))
    created = service.save_material(base)
    assert created["sku"]["revision"] == 1

    def concurrent_edit(_: int) -> bool:
        worker = AdminService()
        try:
            worker.patch_material_sku(sku_id, {"price": 11}, expected_revision=1)
            return True
        except MaterialConflictError:
            return False

    with ThreadPoolExecutor(max_workers=12) as executor:
        outcomes = list(executor.map(concurrent_edit, range(12)))

    current = service.get_material(sku_id)
    assert sum(outcomes) == 1
    assert current["sku"]["revision"] == 2
    assert current["sku"]["price_per_bead"] == 11

    # Simulate a second operator saving after a list was opened.  A selection
    # using the old revision must not partially apply inventory changes.
    service.patch_material_sku(sku_id, {"stock": 10}, expected_revision=2)
    with pytest.raises(MaterialConflictError):
        service.batch_update_materials(
            [sku_id],
            "stock",
            3,
            expected_revisions={sku_id: 2},
        )
    after_stale_batch = service.get_material(sku_id)
    assert after_stale_batch["sku"]["stock"] == 10
    assert after_stale_batch["sku"]["revision"] == 3
