from __future__ import annotations

import json
import sqlite3

from app.migrations.versions import v20260807_25_material_catalog_v2
from app.material_catalog_v2 import validate_material_catalog_v2


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def _legacy_database(path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        CREATE TABLE material_types (
            type_code TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO material_types VALUES
            ('bead', '珠子', '', 10, 1, '2026-08-07', '2026-08-07'),
            ('accessory', '配饰', '', 20, 1, '2026-08-07', '2026-08-07');

        CREATE TABLE material_taxonomy (
            item_id TEXT PRIMARY KEY, parent_id TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL,
            top TEXT NOT NULL, name TEXT NOT NULL, material_code TEXT NOT NULL DEFAULT '',
            color TEXT NOT NULL DEFAULT '', shine TEXT NOT NULL DEFAULT '', image_path TEXT,
            image_url TEXT, image_urls_json TEXT, asset_version INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO material_taxonomy VALUES
            ('cat-quartz', '', 'category', 'bead', '水晶', '', '', '', NULL, NULL, NULL, 1, 10, 1, '2026-08-07', '2026-08-07'),
            ('series-moonstone', 'cat-quartz', 'series', 'bead', '月光石', 'moonstone', '#ddd', '#fff', '',
             'https://cdn.example/cover.webp', '["https://cdn.example/side.webp"]', 3, 20, 1, '2026-08-07', '2026-08-07');

        CREATE TABLE material_knowledge (
            code TEXT PRIMARY KEY, name TEXT NOT NULL, primary_element TEXT NOT NULL DEFAULT '',
            effects_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO material_knowledge VALUES
            ('moonstone', '月光石', 'water', '["平静"]', '2026-08-07', '2026-08-07');

        CREATE TABLE managed_materials (
            id TEXT PRIMARY KEY, skuId TEXT NOT NULL, top TEXT NOT NULL, category TEXT NOT NULL,
            series TEXT NOT NULL, series_id TEXT NOT NULL, material_code TEXT NOT NULL,
            grade TEXT NOT NULL, name TEXT NOT NULL, price NUMERIC NOT NULL, price_cents INTEGER,
            size NUMERIC NOT NULL, weight NUMERIC NOT NULL, cost_price NUMERIC NOT NULL,
            safety_stock INTEGER NOT NULL, supplier_name TEXT NOT NULL, purchase_note TEXT,
            color TEXT NOT NULL, shine TEXT NOT NULL, physical_specs_json TEXT,
            stock INTEGER NOT NULL, reserved_stock INTEGER NOT NULL, enabled INTEGER NOT NULL,
            sort_order INTEGER NOT NULL, revision INTEGER NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO managed_materials VALUES
            ('sku-moonstone-8', '1000010080', 'bead', '水晶', '月光石', 'series-moonstone', 'moonstone',
             '5A', '月光石 8.25mm', 67.89, 6789, 8.25, 1.125, 12.34, 5, '供应商', '', '#ddd', '#fff',
             '{"body_width_mm":8.25}', 20, 3, 1, 10, 4, '2026-08-07', '2026-08-07');
        """
    )
    return connection


def test_material_catalog_v2_backfills_normalized_hierarchy_without_losing_precision(tmp_path):
    connection = _legacy_database(tmp_path / "catalog-v2.db")

    v20260807_25_material_catalog_v2.upgrade(connection, "sqlite")
    v20260807_25_material_catalog_v2.upgrade(connection, "sqlite")

    series = dict(connection.execute("SELECT * FROM material_series_v2").fetchone())
    sku = dict(connection.execute("SELECT * FROM material_skus_v2").fetchone())
    inventory = dict(connection.execute("SELECT * FROM material_inventory_v2").fetchone())
    assets = [dict(row) for row in connection.execute(
        "SELECT asset_role, image_url, sort_order FROM material_series_assets_v2 ORDER BY sort_order"
    ).fetchall()]
    profile = json.loads(connection.execute(
        "SELECT profile_json FROM material_series_profiles_v2 WHERE series_id='series-moonstone'"
    ).fetchone()[0])

    assert series["category_id"] == "cat-quartz"
    assert series["material_code"] == "moonstone"
    assert sku["series_id"] == "series-moonstone"
    assert sku["price_cents"] == 6789
    assert float(sku["size_mm"]) == 8.25
    assert float(sku["weight_g"]) == 1.125
    assert sku["cost_cents"] == 1234
    assert json.loads(sku["physical_specs_json"])["body_width_mm"] == 8.25
    assert inventory == {
        "sku_id": "sku-moonstone-8",
        "stock": 20,
        "reserved_stock": 3,
        "safety_stock": 5,
        "revision": 1,
        "updated_at": "2026-08-07",
    }
    assert assets == [
        {"asset_role": "cover", "image_url": "https://cdn.example/cover.webp", "sort_order": 0},
        {"asset_role": "gallery", "image_url": "https://cdn.example/side.webp", "sort_order": 1},
    ]
    assert profile["primary_element"] == "water"
    assert validate_material_catalog_v2(connection) == {
        "ready": True,
        "counts": {
            "legacy_skus": 1,
            "v2_categories": 1,
            "v2_series": 1,
            "v2_skus": 1,
            "v2_inventory": 1,
        },
        "issues": [],
    }

    connection.execute(
        "UPDATE material_inventory_v2 SET stock=19 WHERE sku_id='sku-moonstone-8'"
    )
    invalid = validate_material_catalog_v2(connection)
    assert invalid["ready"] is False
    assert invalid["issues"] == [{
        "code": "inventory_field_mismatch",
        "entity_id": "sku-moonstone-8",
        "field": "stock",
        "legacy": 20,
        "v2": 19,
    }]

    v20260807_25_material_catalog_v2.downgrade(connection, "sqlite")
    assert not {name for name in _tables(connection) if name.endswith("_v2")}
    assert connection.execute("SELECT stock FROM managed_materials").fetchone()[0] == 20
    connection.close()


def test_material_catalog_v2_rejects_invalid_legacy_inventory(tmp_path):
    connection = _legacy_database(tmp_path / "invalid-inventory.db")
    connection.execute(
        "UPDATE managed_materials SET stock=1, reserved_stock=2 WHERE id='sku-moonstone-8'"
    )

    try:
        v20260807_25_material_catalog_v2.upgrade(connection, "sqlite")
    except ValueError as exc:
        assert "reserved_stock exceeds stock" in str(exc)
    else:
        raise AssertionError("invalid inventory must block the migration")
    connection.close()


def test_material_catalog_v2_disambiguates_duplicate_legacy_sku_codes(tmp_path):
    connection = _legacy_database(tmp_path / "duplicate-sku-code.db")
    connection.execute(
        """
        INSERT INTO managed_materials VALUES
            ('sku-moonstone-10', '1000010080', 'bead', '水晶', '月光石', 'series-moonstone', 'moonstone',
             '5A', '月光石 10mm', 88, 8800, 10, 2, 15, 5, '', '', '#ddd', '#fff', '{}',
             10, 0, 1, 9, 1, '2026-08-07', '2026-08-07')
        """
    )

    v20260807_25_material_catalog_v2.upgrade(connection, "sqlite")

    rows = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT sku_id, sku_code FROM material_skus_v2"
        ).fetchall()
    }
    assert rows["sku-moonstone-8"] == "1000010080"
    assert rows["sku-moonstone-10"].startswith("1000010080-")
    assert len(set(rows.values())) == 2
    connection.close()


def test_material_catalog_v2_merges_duplicate_named_legacy_hierarchy(tmp_path):
    connection = _legacy_database(tmp_path / "duplicate-hierarchy.db")
    connection.execute(
        "INSERT INTO material_taxonomy VALUES "
        "('cat-quartz-copy', '', 'category', 'bead', '水晶', '', '', '', NULL, NULL, NULL, "
        "1, 11, 1, '2026-08-07', '2026-08-07')"
    )
    connection.execute(
        "INSERT INTO material_taxonomy VALUES "
        "('series-moonstone-copy', 'cat-quartz-copy', 'series', 'bead', '月光石', "
        "'moonstone-copy', '', '', NULL, NULL, NULL, 1, 21, 1, '2026-08-07', '2026-08-07')"
    )
    connection.execute(
        """
        INSERT INTO managed_materials VALUES
            ('sku-moonstone-copy-10', '1000010100', 'bead', '水晶', '月光石',
             'series-moonstone-copy', 'moonstone-copy', '5A', '月光石 10mm',
             88, 8800, 10, 2, 15, 5, '', '', '', '', '{}',
             10, 0, 1, 9, 1, '2026-08-07', '2026-08-07')
        """
    )

    v20260807_25_material_catalog_v2.upgrade(connection, "sqlite")

    assert connection.execute(
        "SELECT COUNT(*) FROM material_categories_v2 WHERE type_code='bead' AND name='水晶'"
    ).fetchone()[0] == 1
    assert connection.execute(
        "SELECT COUNT(*) FROM material_series_v2 WHERE name='月光石'"
    ).fetchone()[0] == 1
    assert connection.execute(
        "SELECT COUNT(DISTINCT series_id) FROM material_skus_v2 "
        "WHERE sku_id IN ('sku-moonstone-8', 'sku-moonstone-copy-10')"
    ).fetchone()[0] == 1
    assert validate_material_catalog_v2(connection)["ready"] is True
    connection.close()
