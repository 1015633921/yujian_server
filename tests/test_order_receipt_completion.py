from __future__ import annotations

import json
import sqlite3

from app.admin_service import AdminService
from app.migrations.runner import downgrade, upgrade
from app.order_service import OrderService, now_iso
from app.repository import AssessmentRepository


MIGRATION_VERSION = "20260713_07_order_receipt_completion"
AFTER_SALE_MIGRATION_VERSION = "20260713_08_after_sale_cases"
AFTER_SALE_RETURN_MIGRATION_VERSION = "20260714_09_after_sale_return_flow"
MATERIAL_PHYSICAL_SPECS_MIGRATION_VERSION = "20260714_10_material_physical_specs"
MATERIAL_TYPES_MIGRATION_VERSION = "20260715_11_material_types"


def columns(path, table: str) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def indexes(path, table: str) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA index_list({table})")}


def test_receipt_completion_migration_backfills_signed_order_and_round_trips(tmp_path):
    db_path = tmp_path / "receipt-completion.db"
    AdminService(db_path)
    OrderService(db_path)
    AssessmentRepository(db_path)
    upgrade("sqlite", db_path)
    assert downgrade("sqlite", db_path, steps=5) == [
        MATERIAL_TYPES_MIGRATION_VERSION,
        MATERIAL_PHYSICAL_SPECS_MIGRATION_VERSION,
        AFTER_SALE_RETURN_MIGRATION_VERSION,
        AFTER_SALE_MIGRATION_VERSION,
        MIGRATION_VERSION,
    ]
    assert "logistics_signed_at" not in columns(db_path, "orders")
    assert "auto_complete_at" not in columns(db_path, "orders")

    timestamp = now_iso()
    logistics = {
        "carrier": "顺丰速运",
        "tracking_no": "SF_LEGACY_SIGNED",
        "status": "signed",
        "status_text": "已签收",
        "updated_at": "2026-07-13T06:30:00+00:00",
        "latest_event_time": "2026-07-13 14:30:00",
        "traces": [{"time": "2026-07-13 14:30:00", "desc": "快件已签收"}],
    }
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO orders
            (order_id, out_trade_no, user_id, status, payment_status, total_amount, total_fee,
             currency, receiver_json, design_json, sequence_json, bom_json, remark, payment_json,
             created_at, updated_at, paid_at, refund_json, logistics_json, status_history_json)
            VALUES ('ORDER-LEGACY-SIGNED', 'OUT-LEGACY-SIGNED', 'user-legacy', 'shipped', 'paid',
                    1, 100, 'CNY', '{}', '{}', '[]', '[]', '', '{}', ?, ?, ?, '{}', ?, '[]')
            """,
            (timestamp, timestamp, timestamp, json.dumps(logistics, ensure_ascii=False)),
        )

    assert upgrade("sqlite", db_path) == [
        MIGRATION_VERSION,
        AFTER_SALE_MIGRATION_VERSION,
        AFTER_SALE_RETURN_MIGRATION_VERSION,
        MATERIAL_PHYSICAL_SPECS_MIGRATION_VERSION,
        MATERIAL_TYPES_MIGRATION_VERSION,
    ]
    assert {"logistics_signed_at", "auto_complete_at"} <= columns(db_path, "orders")
    assert "idx_orders_auto_complete" in indexes(db_path, "orders")
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT logistics_json, logistics_signed_at, auto_complete_at
            FROM orders WHERE order_id = 'ORDER-LEGACY-SIGNED'
            """
        ).fetchone()
    migrated = json.loads(row["logistics_json"])
    assert row["logistics_signed_at"] == "2026-07-13T06:30:00+00:00"
    assert row["auto_complete_at"] == "2026-07-20T06:30:00+00:00"
    assert migrated["signed_at"] == row["logistics_signed_at"]
    assert migrated["auto_complete_at"] == row["auto_complete_at"]
    assert upgrade("sqlite", db_path) == []

    assert downgrade("sqlite", db_path, steps=5) == [
        MATERIAL_TYPES_MIGRATION_VERSION,
        MATERIAL_PHYSICAL_SPECS_MIGRATION_VERSION,
        AFTER_SALE_RETURN_MIGRATION_VERSION,
        AFTER_SALE_MIGRATION_VERSION,
        MIGRATION_VERSION,
    ]
    assert "idx_orders_auto_complete" not in indexes(db_path, "orders")
    assert "auto_complete_at" not in columns(db_path, "orders")
