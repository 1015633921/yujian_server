from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.web_login_pairing import BFF_TOKEN_HEADER


client = TestClient(app)
BFF_SECRET = "test-web-login-pairing-secret-at-least-32-bytes"


def enable_pairing(monkeypatch) -> None:
    monkeypatch.setenv("WEB_LOGIN_PAIRING_ENABLED", "true")
    monkeypatch.setenv("WEB_LOGIN_PAIRING_BFF_SECRET", BFF_SECRET)


def headers(value: str = BFF_SECRET) -> dict[str, str]:
    return {BFF_TOKEN_HEADER: value}


def login() -> tuple[dict, dict[str, str]]:
    response = client.post("/api/v1/auth/wechat-login", json={"code": f"pairing-{uuid4()}"})
    assert response.status_code == 200
    data = response.json()["data"]
    return data, {"Authorization": f"Bearer {data['access_token']}"}


def create_pairing() -> dict:
    response = client.post("/api/v1/auth/web-pairings", headers=headers())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def test_pairing_is_closed_by_default_and_bff_protected(monkeypatch):
    monkeypatch.delenv("WEB_LOGIN_PAIRING_ENABLED", raising=False)
    monkeypatch.delenv("WEB_LOGIN_PAIRING_BFF_SECRET", raising=False)
    assert client.post("/api/v1/auth/web-pairings").status_code == 503

    enable_pairing(monkeypatch)
    assert client.post("/api/v1/auth/web-pairings").status_code == 401
    assert client.post("/api/v1/auth/web-pairings", headers=headers("x" * 40)).status_code == 401


def test_confirmed_pairing_can_be_claimed_only_once_and_creates_a_usable_session(monkeypatch):
    enable_pairing(monkeypatch)
    pairing = create_pairing()
    confirmed_user, user_headers = login()
    confirm = client.post(
        f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/confirm",
        json={"verification_code": pairing["verification_code"]},
        headers=user_headers,
    )
    assert confirm.status_code == 200

    claim_url = f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/claim"
    payload = {"browser_secret": pairing["browser_secret"]}

    def claim(_index: int):
        with TestClient(app) as worker:
            return worker.post(claim_url, json=payload, headers=headers())

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(claim, range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    claimed = next(response.json()["data"] for response in responses if response.status_code == 200)
    assert claimed["user"]["user_id"] == confirmed_user["user"]["user_id"]
    assert pairing["browser_secret"] not in str(claimed)
    assert pairing["verification_code"] not in str(claimed)

    profile = client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {claimed['access_token']}"})
    assert profile.status_code == 200
    assert profile.json()["data"]["user_id"] == confirmed_user["user"]["user_id"]


def test_wrong_confirmation_codes_never_disclose_the_pairing(monkeypatch):
    enable_pairing(monkeypatch)
    pairing = create_pairing()
    _, user_headers = login()
    response = client.post(
        f"/api/v1/auth/web-pairings/{pairing['pairing_id']}/confirm",
        json={"verification_code": "22222222" if pairing["verification_code"] != "22222222" else "33333333"},
        headers=user_headers,
    )
    assert response.status_code == 404
