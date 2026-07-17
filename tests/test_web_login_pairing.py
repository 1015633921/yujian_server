from __future__ import annotations

import hashlib
import hmac
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.admin_service import AdminService
from app.main import app
from app.migrations.runner import downgrade, upgrade
from app.migrations.versions import v20260717_08_web_login_pairing as pairing_migration
from app.order_service import OrderService
from app.repository import AssessmentRepository
from app.runtime_health import required_config_errors
from app.web_login_pairing import BFF_TOKEN_HEADER, pairing_service


client = TestClient(app)
BFF_SECRET = "web-login-test-bff-secret-32-bytes-minimum"


def enable_pairing(monkeypatch) -> None:
    monkeypatch.setenv("WEB_LOGIN_PAIRING_ENABLED", "true")
    monkeypatch.setenv("WEB_LOGIN_PAIRING_BFF_SECRET", BFF_SECRET)


def bff_headers(token: str = BFF_SECRET) -> dict[str, str]:
    return {BFF_TOKEN_HEADER: token}


def login() -> tuple[dict, dict[str, str]]:
    response = client.post(
        "/api/v1/auth/wechat-login",
        json={"code": f"web-pairing-{uuid4()}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    return data, {"Authorization": f"Bearer {data['access_token']}"}


def create_pairing() -> dict:
    response = client.post("/api/v1/auth/web-pairings", headers=bff_headers())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def wrong_code(code: str) -> str:
    return ("2" if code[0] != "2" else "3") + code[1:]


def test_feature_is_closed_by_default_and_requires_strong_bff_configuration(monkeypatch):
    monkeypatch.delenv("WEB_LOGIN_PAIRING_ENABLED", raising=False)
    monkeypatch.delenv("WEB_LOGIN_PAIRING_BFF_SECRET", raising=False)
    assert client.post("/api/v1/auth/web-pairings").status_code == 503

    monkeypatch.setenv("WEB_LOGIN_PAIRING_ENABLED", "true")
    assert "WEB_LOGIN_PAIRING_BFF_SECRET_MISSING" in required_config_errors()
    assert client.post("/api/v1/auth/web-pairings").status_code == 503

    monkeypatch.setenv("WEB_LOGIN_PAIRING_BFF_SECRET", "too-short")
    assert "WEB_LOGIN_PAIRING_BFF_SECRET_TOO_SHORT" in required_config_errors()
    assert client.post("/api/v1/auth/web-pairings").status_code == 503


def test_create_and_claim_are_bff_only_but_confirm_uses_user_bearer(monkeypatch):
    enable_pairing(monkeypatch)
    assert client.post("/api/v1/auth/web-pairings").status_code == 401
    assert client.post(
        "/api/v1/auth/web-pairings",
        headers=bff_headers("x" * 40),
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/web-pairings",
        headers=[(BFF_TOKEN_HEADER.encode("ascii"), "错误密钥".encode("utf-8"))],
    ).status_code == 401

    pairing = create_pairing()
    claim_url = f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/claim"
    claim_body = {"browser_secret": pairing["browser_secret"]}
    assert client.post(claim_url, json=claim_body).status_code == 401
    assert client.post(claim_url, json=claim_body, headers=bff_headers("x" * 40)).status_code == 401

    _, user_headers = login()
    confirm = client.post(
        f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/confirm",
        json={"verification_code": pairing["verification_code"]},
        headers=user_headers,
    )
    assert confirm.status_code == 200
    assert confirm.json()["data"]["status"] == "confirmed"


def test_pairing_stores_only_hashes_and_pending_poll_rejects_fake_secret(monkeypatch):
    enable_pairing(monkeypatch)
    pairing = create_pairing()
    with pairing_service.connect() as connection:
        row = connection.execute(
            "SELECT * FROM web_login_pairings WHERE id = ?",
            (pairing["pairing_id"],),
        ).fetchone()

    assert row["browser_secret_hash"] == hashlib.sha256(
        pairing["browser_secret"].encode("utf-8")
    ).hexdigest()
    assert row["verification_code_hash"] == hmac.new(
        BFF_SECRET.encode("utf-8"),
        pairing["verification_code"].encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    stored_values = {str(value) for value in tuple(row)}
    assert pairing["browser_secret"] not in stored_values
    assert pairing["verification_code"] not in stored_values
    assert BFF_SECRET not in stored_values

    url = f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/claim"
    fake = client.post(
        url,
        json={"browser_secret": "forged-browser-secret-" + "x" * 48},
        headers=bff_headers(),
    )
    assert fake.status_code == 404
    pending = client.post(
        url,
        json={"browser_secret": pairing["browser_secret"]},
        headers=bff_headers(),
    )
    assert pending.status_code == 200
    assert pending.headers["cache-control"] == "no-store"
    assert pending.json()["data"]["status"] == "pending"
    assert "access_token" not in pending.text


def test_confirmation_is_one_time_and_cannot_be_overwritten_by_another_user(monkeypatch):
    enable_pairing(monkeypatch)
    pairing = create_pairing()
    first, first_headers = login()
    _, second_headers = login()
    url = f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/confirm"
    payload = {"verification_code": pairing["verification_code"]}

    assert client.post(url, json=payload).status_code == 401
    assert client.post(url, json=payload, headers=first_headers).status_code == 200
    assert client.post(url, json=payload, headers=first_headers).status_code == 409
    assert client.post(url, json=payload, headers=second_headers).status_code == 409

    with pairing_service.connect() as connection:
        row = connection.execute(
            "SELECT status, confirmed_user_id FROM web_login_pairings WHERE id = ?",
            (pairing["pairing_id"],),
        ).fetchone()
    assert row["status"] == "confirmed"
    assert row["confirmed_user_id"] == first["user"]["user_id"]


def test_five_wrong_codes_lock_pairing_without_exposing_code_hash(monkeypatch):
    enable_pairing(monkeypatch)
    pairing = create_pairing()
    _, user_headers = login()
    url = f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/confirm"
    for _ in range(5):
        response = client.post(
            url,
            json={"verification_code": wrong_code(pairing["verification_code"])},
            headers=user_headers,
        )
        assert response.status_code == 404

    assert client.post(
        url,
        json={"verification_code": pairing["verification_code"]},
        headers=user_headers,
    ).status_code == 410
    with pairing_service.connect() as connection:
        row = connection.execute(
            "SELECT status, failed_confirm_attempts FROM web_login_pairings WHERE id = ?",
            (pairing["pairing_id"],),
        ).fetchone()
    assert row["status"] == "expired"
    assert row["failed_confirm_attempts"] == 5


def test_expired_pairing_cannot_be_confirmed_or_claimed(monkeypatch):
    enable_pairing(monkeypatch)
    pairing = create_pairing()
    expired_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with pairing_service.connect() as connection:
        connection.execute(
            "UPDATE web_login_pairings SET expires_at = ? WHERE id = ?",
            (expired_at, pairing["pairing_id"]),
        )

    _, user_headers = login()
    assert client.post(
        f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/confirm",
        json={"verification_code": pairing["verification_code"]},
        headers=user_headers,
    ).status_code == 410
    assert client.post(
        f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/claim",
        json={"browser_secret": pairing["browser_secret"]},
        headers=bff_headers(),
    ).status_code == 410
    with pairing_service.connect() as connection:
        status = connection.execute(
            "SELECT status FROM web_login_pairings WHERE id = ?",
            (pairing["pairing_id"],),
        ).fetchone()["status"]
    assert status == "expired"


def test_confirmed_pairing_has_exactly_one_concurrent_claim_and_session_is_usable(monkeypatch):
    enable_pairing(monkeypatch)
    pairing = create_pairing()
    confirmed_user, user_headers = login()
    assert client.post(
        f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/confirm",
        json={"verification_code": pairing["verification_code"]},
        headers=user_headers,
    ).status_code == 200
    claim_url = f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/claim"

    def claim(_index: int):
        with TestClient(app) as worker:
            return worker.post(
                claim_url,
                json={"browser_secret": pairing["browser_secret"]},
                headers=bff_headers(),
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(claim, range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    claimed = next(response.json()["data"] for response in responses if response.status_code == 200)
    claimed_response = next(response for response in responses if response.status_code == 200)
    assert claimed_response.headers["cache-control"] == "no-store"
    assert claimed["status"] == "consumed"
    assert claimed["user"]["user_id"] == confirmed_user["user"]["user_id"]

    access_token = claimed["access_token"]
    profile = client.get(
        "/api/v1/auth/profile",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert profile.status_code == 200
    assert profile.json()["data"]["user_id"] == confirmed_user["user"]["user_id"]

    with pairing_service.connect() as connection:
        pairing_row = connection.execute(
            "SELECT * FROM web_login_pairings WHERE id = ?",
            (pairing["pairing_id"],),
        ).fetchone()
        session_row = connection.execute(
            "SELECT token_hash FROM user_sessions WHERE token_hash = ?",
            (hashlib.sha256(access_token.encode("utf-8")).hexdigest(),),
        ).fetchone()
    assert pairing_row["status"] == "consumed"
    assert access_token not in {str(value) for value in tuple(pairing_row)}
    assert session_row["token_hash"] == hashlib.sha256(access_token.encode("utf-8")).hexdigest()


def test_session_insert_failure_rolls_back_consumption_and_can_be_retried(monkeypatch):
    enable_pairing(monkeypatch)
    pairing = create_pairing()
    confirmed_user, user_headers = login()
    user_id = confirmed_user["user"]["user_id"]
    assert client.post(
        f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/confirm",
        json={"verification_code": pairing["verification_code"]},
        headers=user_headers,
    ).status_code == 200

    with pairing_service.connect() as connection:
        before_sessions = connection.execute(
            "SELECT COUNT(*) AS total FROM user_sessions WHERE user_id = ?",
            (user_id,),
        ).fetchone()["total"]

    original_create = pairing_service.user_session_service.create_in_connection

    def fail_session_insert(_connection, _user_id):
        raise RuntimeError("injected session insert failure")

    monkeypatch.setattr(
        pairing_service.user_session_service,
        "create_in_connection",
        fail_session_insert,
    )
    claim_url = f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/claim"
    with TestClient(app, raise_server_exceptions=False) as worker:
        failed = worker.post(
            claim_url,
            json={"browser_secret": pairing["browser_secret"]},
            headers=bff_headers(),
        )
    assert failed.status_code == 500
    assert "access_token" not in failed.text

    with pairing_service.connect() as connection:
        pairing_row = connection.execute(
            "SELECT status, consumed_at FROM web_login_pairings WHERE id = ?",
            (pairing["pairing_id"],),
        ).fetchone()
        after_sessions = connection.execute(
            "SELECT COUNT(*) AS total FROM user_sessions WHERE user_id = ?",
            (user_id,),
        ).fetchone()["total"]
    assert pairing_row["status"] == "confirmed"
    assert pairing_row["consumed_at"] is None
    assert after_sessions == before_sessions

    monkeypatch.setattr(
        pairing_service.user_session_service,
        "create_in_connection",
        original_create,
    )
    recovered = client.post(
        claim_url,
        json={"browser_secret": pairing["browser_secret"]},
        headers=bff_headers(),
    )
    assert recovered.status_code == 200
    assert recovered.json()["data"]["status"] == "consumed"


def test_sqlite_migration_is_explicit_idempotent_and_reversible(tmp_path):
    db_path = tmp_path / "web-login-pairing.db"
    AssessmentRepository(db_path)
    OrderService(db_path)
    AdminService(db_path)
    upgrade("sqlite", db_path)

    with sqlite3.connect(db_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(web_login_pairings)")}
    assert "web_login_pairings" in tables
    assert {
        "idx_web_login_pairings_status_expiry",
        "idx_web_login_pairings_confirmed_user",
    }.issubset(indexes)
    assert upgrade("sqlite", db_path) == []
    assert downgrade("sqlite", db_path, steps=1) == [pairing_migration.VERSION]
    with sqlite3.connect(db_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "web_login_pairings" not in tables
    assert upgrade("sqlite", db_path) == [pairing_migration.VERSION]


class RecordingConnection:
    def __init__(self):
        self.statements: list[str] = []

    def execute(self, statement: str, _params=()):
        self.statements.append(statement)


def test_mysql_migration_has_explicit_create_and_rollback():
    connection = RecordingConnection()
    pairing_migration.upgrade(connection, "mysql", "isolated_test")
    pairing_migration.downgrade(connection, "mysql", "isolated_test")
    statements = "\n".join(connection.statements)
    assert "CREATE TABLE IF NOT EXISTS web_login_pairings" in statements
    assert "ENGINE=InnoDB" in statements
    assert "DROP TABLE IF EXISTS web_login_pairings" in statements
