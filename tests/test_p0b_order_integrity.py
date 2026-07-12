from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.admin_service import AdminService
from app.migrations.runner import upgrade
from app.order_service import (
    OrderConflictError,
    OrderPriceChangedError,
    OrderPricingError,
    OrderService,
)
from app.main import app
from app.money import money_to_cents
from app.user_sessions import session_service


client = TestClient(app)


def build_service(tmp_path) -> OrderService:
    db_path = tmp_path / f"p0b-{uuid4().hex}.db"
    AdminService(db_path)
    OrderService(db_path)
    upgrade("sqlite", db_path)
    service = OrderService(db_path)
    service.get_user = lambda _user_id: None
    return service


def add_sku(
    service: OrderService,
    sku_id: str,
    *,
    price="12.34",
    stock: int = 10,
    enabled: int = 1,
    updated_at: str = "2026-07-12T12:00:00+00:00",
) -> None:
    try:
        price_cents = money_to_cents(price, field_name="测试价格")
    except ValueError:
        price_cents = None if price in (None, "") else price
    with service.connect() as connection:
        connection.execute(
            """
            INSERT INTO managed_materials
            (id, skuId, top, category, series, material_code, grade, name, effect,
             element, price, price_cents, size, weight, cost_price, safety_stock, supplier_name,
             purchase_note, color, shine, image_path, image_url, image_urls_json,
             stock, reserved_stock, enabled, sort_order, created_at, updated_at)
            VALUES (?, ?, 'bead', 'test', 'P0B', ?, '', ?, '', '水', ?, ?, 8, 1,
                    0, 0, '', '', '#ffffff', '#ffffff', '', '', '[]', ?, 0, ?, 0, ?, ?)
            """,
            (
                sku_id,
                f"sku-{sku_id}",
                sku_id,
                f"测试 SKU {sku_id}",
                price,
                price_cents,
                stock,
                enabled,
                updated_at,
                updated_at,
            ),
        )


def order_payload(
    sku_id: str,
    *,
    key: str | None = None,
    user_id: str = "p0b-user",
    client_price="12.34",
    quantity=1,
    extra_sequence: list[dict] | None = None,
) -> dict:
    sequence = [{"id": sku_id, "price": client_price, "quantity": quantity}]
    sequence.extend(extra_sequence or [])
    return {
        "idempotency_key": key or f"checkout-{uuid4().hex}",
        "user_id": user_id,
        "receiver": {"name": "测试用户", "phone": "13800000000", "address": "测试地址"},
        "design": {"summary": {"price": "0.01"}},
        "sequence": sequence,
        "bom": [{"price": "0.01", "qty": 1}],
    }


def inventory(service: OrderService, sku_id: str) -> tuple[int, int]:
    with service.connect() as connection:
        row = connection.execute(
            "SELECT stock, reserved_stock FROM managed_materials WHERE id = ?", (sku_id,)
        ).fetchone()
    return int(row["stock"]), int(row["reserved_stock"])


def order_count(service: OrderService) -> int:
    with service.connect() as connection:
        return int(connection.execute("SELECT COUNT(*) AS total FROM orders").fetchone()["total"])


@pytest.mark.parametrize("forged_price", ["0.01", "0"])
def test_client_forged_prices_are_rejected_and_never_used(tmp_path, forged_price):
    service = build_service(tmp_path)
    add_sku(service, "price-guard", price="12.34")

    with pytest.raises(OrderPriceChangedError, match="价格已更新，请确认"):
        service.create_order(order_payload("price-guard", client_price=forged_price))

    assert order_count(service) == 0
    assert inventory(service, "price-guard") == (10, 0)


def test_server_price_builds_immutable_integer_cent_snapshot(tmp_path):
    service = build_service(tmp_path)
    add_sku(service, "snapshot", price="12.34", stock=5, updated_at="price-v7")

    result = service.create_order(order_payload("snapshot", quantity=2))
    order = result["order"]
    line = order["sequence"][0]

    assert order["total_fee"] == 2468
    assert order["total_amount"] == "24.68"
    assert line == {
        "id": "snapshot",
        "quantity": 2,
        "sku_id": "snapshot",
        "sku": "sku-snapshot",
        "skuId": "sku-snapshot",
        "name": "测试 SKU snapshot",
        "category": "test",
        "series": "P0B",
        "effect": "",
        "element": "水",
        "size": 8.0,
        "image_url": "",
        "image_urls": [],
        "unit_price_cents": 1234,
        "unit_price": "12.34",
        "price": "12.34",
        "subtotal_cents": 2468,
        "subtotal": "24.68",
        "price_version": "price-v7",
    }
    assert order["bom"][0]["qty"] == 2
    assert order["bom"][0]["subtotal_cents"] == 2468


def test_missing_disabled_invalid_and_mixed_skus_fail_closed(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service, "valid", price="12.34")
    add_sku(service, "disabled", price="12.34", enabled=0)
    add_sku(service, "missing-price", price="")
    add_sku(service, "invalid-price", price="not-a-price")

    with pytest.raises(OrderPricingError, match="SKU 不存在"):
        service.create_order(order_payload("missing"))
    with pytest.raises(OrderPricingError, match="已下架"):
        service.create_order(order_payload("disabled"))
    with pytest.raises(OrderPricingError, match="缺少有效价格"):
        service.create_order(order_payload("missing-price", client_price=None))
    with pytest.raises(OrderPricingError, match="价格字段非法"):
        service.create_order(order_payload("invalid-price", client_price=None))
    with pytest.raises(OrderPricingError, match="SKU 不存在"):
        service.create_order(
            order_payload(
                "valid",
                extra_sequence=[{"id": "missing-second", "price": "12.34", "quantity": 1}],
            )
        )

    monkeypatch.setattr(
        service,
        "fetch_locked_material_rows",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db unavailable")),
    )
    with pytest.raises(OrderPricingError, match="SKU 数据查询失败"):
        service.create_order(order_payload("valid"))
    assert order_count(service) == 0


@pytest.mark.parametrize("quantity", [0, -1, "1.5"])
def test_zero_negative_and_fractional_quantity_are_rejected(tmp_path, quantity):
    service = build_service(tmp_path)
    add_sku(service, "quantity", stock=5)
    with pytest.raises(ValueError, match="正整数"):
        service.create_order(order_payload("quantity", quantity=quantity))
    assert inventory(service, "quantity") == (5, 0)


def test_quantity_is_checked_against_available_stock(tmp_path):
    service = build_service(tmp_path)
    add_sku(service, "limited", stock=2)
    with pytest.raises(OrderPricingError, match="库存不足"):
        service.create_order(order_payload("limited", quantity=3))
    assert inventory(service, "limited") == (2, 0)


def test_same_idempotency_key_replays_order_without_second_reservation(tmp_path):
    service = build_service(tmp_path)
    add_sku(service, "idem", stock=3)
    payload = order_payload("idem", key="same-key-123", quantity=2)

    first = service.create_order(payload)
    replay = service.create_order(payload)

    assert first["order"]["order_id"] == replay["order"]["order_id"]
    assert replay["idempotent_replay"] is True
    assert order_count(service) == 1
    assert inventory(service, "idem") == (3, 2)


def test_concurrent_same_idempotency_key_creates_one_order_and_one_reservation(tmp_path):
    service = build_service(tmp_path)
    add_sku(service, "idem-race", stock=3)
    payload = order_payload("idem-race", key="same-race-key-123", quantity=2)

    def attempt(_index: int) -> str:
        worker = OrderService(service.db_path)
        worker.get_user = lambda _user_id: None
        return worker.create_order(payload)["order"]["order_id"]

    with ThreadPoolExecutor(max_workers=10) as executor:
        order_ids = list(executor.map(attempt, range(10)))

    assert len(set(order_ids)) == 1
    assert order_count(service) == 1
    assert inventory(service, "idem-race") == (3, 2)


def test_same_idempotency_key_with_different_body_returns_conflict(tmp_path):
    service = build_service(tmp_path)
    add_sku(service, "idem-conflict", stock=3)
    service.create_order(order_payload("idem-conflict", key="conflict-key-123", quantity=1))

    with pytest.raises(OrderConflictError, match="不同的订单内容"):
        service.create_order(order_payload("idem-conflict", key="conflict-key-123", quantity=2))
    assert order_count(service) == 1
    assert inventory(service, "idem-conflict") == (3, 1)


def test_order_api_requires_header_replays_and_returns_409_for_conflicts(tmp_path, monkeypatch):
    from app import api as api_module

    service = build_service(tmp_path)
    add_sku(service, "api-idem", stock=3)
    monkeypatch.setattr(api_module, "order_service", service)
    monkeypatch.setenv("COMMERCE_CHECKOUT_ENABLED", "true")
    session = session_service.create("api-idem-user")
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    body = order_payload("api-idem", user_id="api-idem-user")
    body.pop("idempotency_key")

    missing = client.post("/api/v1/orders", headers=headers, json=body)
    first = client.post(
        "/api/v1/orders",
        headers={**headers, "Idempotency-Key": "api-idem-key-123"},
        json=body,
    )
    replay = client.post(
        "/api/v1/orders",
        headers={**headers, "Idempotency-Key": "api-idem-key-123"},
        json=body,
    )
    changed_body = {**body, "remark": "different"}
    conflict = client.post(
        "/api/v1/orders",
        headers={**headers, "Idempotency-Key": "api-idem-key-123"},
        json=changed_body,
    )
    price_changed_body = {
        **body,
        "sequence": [{"id": "api-idem", "price": "0.01", "quantity": 1}],
    }
    price_changed = client.post(
        "/api/v1/orders",
        headers={**headers, "Idempotency-Key": "api-price-key-123"},
        json=price_changed_body,
    )

    assert missing.status_code == 400
    assert first.status_code == 200
    assert replay.status_code == 200
    assert first.json()["data"]["order"]["order_id"] == replay.json()["data"]["order"]["order_id"]
    assert conflict.status_code == 409
    assert price_changed.status_code == 409
    assert "价格已更新，请确认" in price_changed.json()["detail"]


def test_cancel_timeout_and_repeated_release_are_idempotent(tmp_path):
    service = build_service(tmp_path)
    add_sku(service, "release", stock=4)
    first = service.create_order(order_payload("release", key="cancel-key-123", quantity=2))
    order_id = first["order"]["order_id"]
    assert inventory(service, "release") == (4, 2)

    service.cancel_order(order_id, "p0b-user", "取消")
    service.cancel_order(order_id, "p0b-user", "重复取消")
    assert inventory(service, "release") == (4, 0)

    second = service.create_order(order_payload("release", key="timeout-key-123", quantity=3))
    second_id = second["order"]["order_id"]
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with service.connect() as connection:
        connection.execute(
            "UPDATE inventory_reservations SET expires_at = ? WHERE order_id = ?",
            (past, second_id),
        )
    first_release = service.release_expired_reservations(timestamp=now_iso_for_test())
    repeated_release = service.release_expired_reservations(timestamp=now_iso_for_test())
    assert first_release["released_reservations"] == 1
    assert repeated_release["released_reservations"] == 0
    assert inventory(service, "release") == (4, 0)
    assert service.get_order(second_id)["status"] == "closed"


def test_admin_cannot_reduce_or_delete_stock_with_active_reservation(tmp_path):
    service = build_service(tmp_path)
    admin = AdminService(service.db_path)
    add_sku(service, "admin-guard", stock=4)
    result = service.create_order(order_payload("admin-guard", key="admin-guard-key", quantity=3))

    with pytest.raises(ValueError, match="库存不能低于已预占数量"):
        admin.batch_update_materials(["admin-guard"], "stock", 2)
    with pytest.raises(ValueError, match="未完成库存预占"):
        admin.delete_material("admin-guard")
    with pytest.raises(ValueError, match="未完成库存预占"):
        admin.batch_update_materials(["admin-guard"], "delete")

    assert inventory(service, "admin-guard") == (4, 3)
    service.cancel_order(result["order"]["order_id"], "p0b-user")
    admin.batch_update_materials(["admin-guard"], "stock", 2)
    assert inventory(service, "admin-guard") == (2, 0)


def now_iso_for_test() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def test_payment_confirmation_is_idempotent_and_stock_never_negative(tmp_path, monkeypatch):
    monkeypatch.setenv("WECHAT_PAY_TEST_MODE", "true")
    service = build_service(tmp_path)
    add_sku(service, "confirm", stock=2)
    result = service.create_order(order_payload("confirm", key="confirm-key-123", quantity=2))
    order_id = result["order"]["order_id"]

    first = service.mark_paid_for_dev(order_id, "p0b-user")
    second = service.mark_paid_for_dev(order_id, "p0b-user")

    assert first["payment_status"] == "paid"
    assert second["payment_status"] == "paid"
    assert inventory(service, "confirm") == (0, 0)
    with service.connect() as connection:
        status = connection.execute(
            "SELECT status FROM inventory_reservations WHERE order_id = ?", (order_id,)
        ).fetchone()["status"]
    assert status == "confirmed"


def test_mid_transaction_failure_rolls_back_order_claim_and_reservation(tmp_path, monkeypatch):
    service = build_service(tmp_path)
    add_sku(service, "rollback", stock=5)
    original = service.reserve_inventory

    def reserve_then_fail(connection, *args, **kwargs):
        original(connection, *args, **kwargs)
        raise RuntimeError("injected transaction failure")

    monkeypatch.setattr(service, "reserve_inventory", reserve_then_fail)
    with pytest.raises(RuntimeError, match="injected"):
        service.create_order(order_payload("rollback", key="rollback-key-123", quantity=2))

    assert order_count(service) == 0
    assert inventory(service, "rollback") == (5, 0)
    with service.connect() as connection:
        assert connection.execute("SELECT COUNT(*) AS total FROM order_requests").fetchone()["total"] == 0
        assert connection.execute("SELECT COUNT(*) AS total FROM inventory_reservations").fetchone()["total"] == 0


def test_sqlite_concurrency_never_over_reserves(tmp_path):
    service = build_service(tmp_path)
    add_sku(service, "sqlite-race", stock=5)

    def attempt(index: int) -> bool:
        worker = OrderService(service.db_path)
        worker.get_user = lambda _user_id: None
        try:
            worker.create_order(
                order_payload(
                    "sqlite-race",
                    key=f"sqlite-race-{index:03d}",
                    user_id=f"user-{index}",
                    quantity=1,
                )
            )
            return True
        except OrderPricingError:
            return False

    with ThreadPoolExecutor(max_workers=20) as executor:
        outcomes = list(executor.map(attempt, range(20)))

    assert sum(outcomes) == 5
    assert inventory(service, "sqlite-race") == (5, 5)
