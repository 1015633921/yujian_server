from __future__ import annotations

import sqlite3

from app.admin_service import AdminService
from app.migrations.runner import downgrade, upgrade
from app.order_service import OrderService


def columns(path, table: str) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def tables(path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_p0b_migration_is_additive_idempotent_and_independently_reversible(tmp_path):
    db_path = tmp_path / "p0b-migration.db"
    AdminService(db_path)
    OrderService(db_path)

    assert upgrade("sqlite", db_path) == [
        "20260712_01_p0a_security",
        "20260712_02_p0b_order_integrity",
        "20260712_03_p1a_payment_events",
        "20260712_04_p1b_report_snapshots",
        "20260712_05_p1c_runtime_tasks",
        "20260712_06_p1_material_price_cents",
        "20260713_07_order_receipt_completion",
        "20260717_08_web_login_pairing",
    ]
    assert upgrade("sqlite", db_path) == []
    assert {"idempotency_key", "request_hash", "reservation_expires_at"}.issubset(columns(db_path, "orders"))
    assert "reserved_stock" in columns(db_path, "managed_materials")
    assert {"order_requests", "inventory_reservations", "user_sessions"}.issubset(tables(db_path))

    assert downgrade("sqlite", db_path, steps=1) == ["20260717_08_web_login_pairing"]
    assert "order_requests" in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260713_07_order_receipt_completion"]
    assert "order_requests" in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260712_06_p1_material_price_cents"]
    assert "order_requests" in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260712_05_p1c_runtime_tasks"]
    assert "order_requests" in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260712_04_p1b_report_snapshots"]
    assert "order_requests" in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260712_03_p1a_payment_events"]
    assert "order_requests" in tables(db_path)
    assert downgrade("sqlite", db_path, steps=1) == ["20260712_02_p0b_order_integrity"]
    assert "user_sessions" in tables(db_path)
    assert "order_requests" not in tables(db_path)
    assert "reserved_stock" not in columns(db_path, "managed_materials")

    assert upgrade("sqlite", db_path) == [
        "20260712_02_p0b_order_integrity",
        "20260712_03_p1a_payment_events",
        "20260712_04_p1b_report_snapshots",
        "20260712_05_p1c_runtime_tasks",
        "20260712_06_p1_material_price_cents",
        "20260713_07_order_receipt_completion",
        "20260717_08_web_login_pairing",
    ]
