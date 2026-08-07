from __future__ import annotations

import json

import pytest

from app.admin_service import AdminService, MaterialConflictError
from app.migrations.runner import upgrade
from app.order_service import OrderService
from app.material_catalog_v2 import validate_material_catalog_v2
from app.material_knowledge import upsert_material_knowledge


def _catalog_with_order_service(db_path):
    admin = AdminService(db_path)
    order = OrderService(db_path)
    category = admin.save_material_category({"top": "bead", "name": "水晶"})
    series = admin.save_material_series(
        {
            "category_id": category["id"],
            "name": "月光石",
            "material_code": "moonstone-v2-order",
            "primary_element": "water",
            "effects": ["平静"],
        }
    )
    saved = admin.save_material(
        {
            "id": "sku-v2-order-8",
            "top": "bead",
            "category": "水晶",
            "series": "月光石",
            "series_id": series["id"],
            "material_code": "moonstone-v2-order",
            "name": "月光石 8.25mm",
            "price": "67.89",
            "size": 8.25,
            "weight": 1.125,
            "stock": 10,
            "enabled": True,
        }
    )
    upgrade("sqlite", db_path)
    return admin, order, saved["sku"]["id"]


def test_order_catalog_v2_reads_snapshot_and_owns_inventory_transaction(tmp_path, monkeypatch):
    admin, order, sku_id = _catalog_with_order_service(tmp_path / "order-catalog-v2.db")
    series_id = admin.get_material(sku_id)["sku"]["series_id"]
    legacy_profile = admin.get_material_series(series_id)
    monkeypatch.setenv("MATERIAL_CATALOG_V2_ENABLED", "true")

    profile = admin.get_material_series(series_id)
    assert profile["name"] == legacy_profile["name"]
    assert profile["energy"] == legacy_profile["energy"]
    assert profile["rules"] == legacy_profile["rules"]
    assert profile["material_params"] == legacy_profile["material_params"]
    taxonomy = admin.list_material_taxonomy(top=profile["top"], include_disabled=True)
    assert any(
        item["id"] == series_id
        for category in taxonomy
        for item in category["series"]
    )
    assert any(item["code"] == profile["top"] for item in admin.list_material_types(True))

    with order.connect() as connection:
        rows = order.fetch_locked_material_rows(connection, {sku_id})
        assert len(rows) == 1
        assert rows[0]["id"] == sku_id
        assert rows[0]["price_cents"] == 6789
        assert float(rows[0]["size"]) == 8.25

        order.reserve_inventory(
            connection,
            "order-v2-1",
            {sku_id: {"quantity": 2, "name": "月光石 8.25mm", "sku_code": rows[0]["skuId"]}},
            "2026-08-08T00:00:00+00:00",
            "2026-08-07T00:00:00+00:00",
        )
        reserved = connection.execute(
            "SELECT stock, reserved_stock FROM material_inventory_v2 WHERE sku_id=?", (sku_id,)
        ).fetchone()
        assert dict(reserved) == {"stock": 10, "reserved_stock": 2}
        assert order.confirm_reservations(connection, "order-v2-1") == 1
        confirmed = connection.execute(
            "SELECT stock, reserved_stock FROM material_inventory_v2 WHERE sku_id=?", (sku_id,)
        ).fetchone()
        assert dict(confirmed) == {"stock": 8, "reserved_stock": 0}

        # The old table is deliberately untouched after cutover: it is rollback data,
        # never a second inventory ledger.
        legacy = connection.execute(
            "SELECT stock, reserved_stock FROM managed_materials WHERE id=?", (sku_id,)
        ).fetchone()
        assert dict(legacy) == {"stock": 10, "reserved_stock": 0}

    admin.disable_material_taxonomy_item(series_id)
    with order.connect() as connection:
        assert connection.execute(
            "SELECT stock FROM material_inventory_v2 WHERE sku_id=?", (sku_id,)
        ).fetchone()["stock"] == 8
        assert order.fetch_locked_material_rows(connection, {sku_id}) == []


def test_admin_writes_keep_shadow_catalog_ready_before_cutover(tmp_path):
    admin, _order, sku_id = _catalog_with_order_service(tmp_path / "shadow-sync.db")

    updated = admin.patch_material_sku(
        sku_id,
        {"price": "70.05", "size": 8.375, "weight": 1.25, "stock": 12},
    )
    assert updated["sku"]["price_per_bead"] == 70.05

    created = admin.save_material(
        {
            "id": "sku-v2-order-10",
            "top": "bead",
            "category": "水晶",
            "series": "月光石",
            "series_id": updated["sku"]["series_id"],
            "material_code": "moonstone-v2-order",
            "name": "月光石 10mm",
            "price": "88.08",
            "size": 10,
            "weight": 2,
            "stock": 6,
            "enabled": True,
        }
    )

    with admin.connect() as connection:
        report = validate_material_catalog_v2(connection)
        v2 = connection.execute(
            "SELECT price_cents, size_mm, weight_g FROM material_skus_v2 WHERE sku_id=?", (sku_id,)
        ).fetchone()
        assert report["ready"] is True
        assert dict(v2) == {"price_cents": 7005, "size_mm": 8.375, "weight_g": 1.25}

    admin.delete_material(created["sku"]["id"])
    with admin.connect() as connection:
        assert not connection.execute(
            "SELECT 1 FROM material_skus_v2 WHERE sku_id=?", (created["sku"]["id"],)
        ).fetchone()
        assert validate_material_catalog_v2(connection)["ready"] is True


def test_admin_sku_edit_uses_v2_as_the_only_inventory_ledger_after_cutover(tmp_path, monkeypatch):
    admin, _order, sku_id = _catalog_with_order_service(tmp_path / "v2-admin-edit.db")
    with admin.connect() as connection:
        legacy_before = dict(connection.execute(
            "SELECT price_cents, size, stock FROM managed_materials WHERE id=?", (sku_id,)
        ).fetchone())
    monkeypatch.setenv("MATERIAL_CATALOG_V2_ENABLED", "true")
    revision = admin.get_material(sku_id)["sku"]["revision"]

    updated = admin.patch_material_sku(
        sku_id,
        {"price": "70.05", "size": 8.375, "stock": 12},
        expected_revision=revision,
    )

    assert updated["sku"]["price_per_bead"] == 70.05
    assert updated["sku"]["size_mm"] == 8.375
    assert updated["sku"]["stock"] == 12
    listed = admin.list_materials(keyword=sku_id)
    grouped = admin.list_material_spus(
        keyword=sku_id, compact=True, page=1, page_size=20
    )
    assert listed[0]["sku"]["price_per_bead"] == 70.05
    assert listed[0]["sku"]["size_mm"] == 8.375
    assert grouped["items"][0]["spu"]["size_values"] == [8.375]
    assert grouped["items"][0]["spu"]["sku_options"] == [
        {"id": sku_id, "size_mm": 8.375}
    ]
    with pytest.raises(MaterialConflictError):
        admin.patch_material_sku(sku_id, {"price": "71.00"}, expected_revision=revision)
    with admin.connect() as connection:
        legacy_after = dict(connection.execute(
            "SELECT price_cents, size, stock FROM managed_materials WHERE id=?", (sku_id,)
        ).fetchone())
        v2 = dict(connection.execute(
            """
            SELECT k.price_cents, k.size_mm, i.stock
            FROM material_skus_v2 k JOIN material_inventory_v2 i ON i.sku_id=k.sku_id
            WHERE k.sku_id=?
            """,
            (sku_id,),
        ).fetchone())
    assert legacy_after == legacy_before
    assert v2 == {"price_cents": 7005, "size_mm": 8.375, "stock": 12}
    status = admin.material_catalog_v2_status()
    assert status["ready"] is False  # legacy price/size are deliberately frozen too
    assert not any(issue["code"] == "inventory_field_mismatch" for issue in status["issues"])


def test_knowledge_writes_update_normalized_series_profile(tmp_path):
    admin, _order, _sku_id = _catalog_with_order_service(tmp_path / "v2-profile-sync.db")
    material = {"series": "Moonstone", "name": "Moonstone"}
    code = "moonstone"
    with admin.connect() as connection:
        upsert_material_knowledge(
            {
                "code": code,
                "name": material["series"],
                "primary_element": "water",
                "visual_tags": ["translucent"],
                "enabled": True,
            },
            material,
            connection=connection,
            force_update=True,
        )
        profile_json = connection.execute(
            "SELECT p.profile_json FROM material_series_profiles_v2 p "
            "JOIN material_series_v2 s ON s.series_id=p.series_id "
            "WHERE s.material_code=?",
            (code,),
        ).fetchone()["profile_json"]
    profile = json.loads(profile_json)
    assert profile["primary_element"] == "water"
    assert json.loads(profile["visual_tags_json"]) == ["translucent"]


def test_admin_batch_and_delete_mutations_stay_on_v2_after_cutover(tmp_path, monkeypatch):
    admin, _order, first_id = _catalog_with_order_service(tmp_path / "v2-admin-batch.db")
    first = admin.get_material(first_id)
    second = admin.save_material(
        {
            "id": "sku-v2-batch-10",
            "top": first["top"],
            "category": first["category"],
            "series": first["series"],
            "series_id": first["sku"]["series_id"],
            "material_code": first["sku"]["material_code"],
            "name": "V2 batch 10mm",
            "price": "80.00",
            "size": 10,
            "weight": 2,
            "stock": 5,
            "enabled": True,
        }
    )
    second_id = second["sku"]["id"]
    monkeypatch.setenv("MATERIAL_CATALOG_V2_ENABLED", "true")
    revisions = {
        item_id: admin.get_material(item_id)["sku"]["revision"]
        for item_id in (first_id, second_id)
    }

    result = admin.batch_update_materials(
        [first_id, second_id], "price", "72.34", expected_revisions=revisions
    )
    assert result["affected"] == 2
    next_revisions = {
        item_id: admin.get_material(item_id)["sku"]["revision"]
        for item_id in (first_id, second_id)
    }
    admin.batch_update_materials(
        [first_id, second_id], "stock", 7, expected_revisions=next_revisions
    )
    delete_revision = admin.get_material(second_id)["sku"]["revision"]
    admin.delete_material(second_id, expected_revision=delete_revision)

    with admin.connect() as connection:
        first_v2 = dict(connection.execute(
            """
            SELECT k.price_cents, i.stock FROM material_skus_v2 k
            JOIN material_inventory_v2 i ON i.sku_id=k.sku_id WHERE k.sku_id=?
            """,
            (first_id,),
        ).fetchone())
        assert first_v2 == {"price_cents": 7234, "stock": 7}
        assert not connection.execute(
            "SELECT 1 FROM material_skus_v2 WHERE sku_id=?", (second_id,)
        ).fetchone()
        assert connection.execute(
            "SELECT 1 FROM managed_materials WHERE id=?", (second_id,)
        ).fetchone()
