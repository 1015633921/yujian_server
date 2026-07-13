from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app.avatar_storage import AvatarStorage, AvatarUploadResult, MAX_AVATAR_BYTES
from app.main import app
from app.order_service import now_iso
from app.user_sessions import session_service


client = TestClient(app)


def login(code: str | None = None) -> tuple[dict, dict[str, str]]:
    response = client.post("/api/v1/auth/wechat-login", json={"code": code or f"p0a-{uuid4()}"})
    assert response.status_code == 200
    session = response.json()["data"]
    assert len(session["access_token"]) >= 32
    assert session["expires_at"]
    assert "openid" not in session["user"]
    return session, {"Authorization": f"Bearer {session['access_token']}"}


def assessment_payload(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "name": "安全测试",
        "birthday": "1995-08-16",
        "birth_time": "09:30",
        "birth_place": "四川省成都市",
        "mbti": "INFJ",
        "core_wishes": ["健康护身/保持专注"],
        "wrist_size_cm": 15.5,
        "bead_size_mm": 8,
        "force_recalculate": True,
    }


def test_private_endpoint_rejects_missing_and_forged_tokens():
    assert client.get("/api/v1/auth/profile").status_code == 401
    forged = client.get(
        "/api/v1/auth/profile",
        headers={"Authorization": "Bearer " + "x" * 64},
    )
    assert forged.status_code == 401
    assert "x" * 32 not in forged.text


def test_login_rejects_dev_identity_and_untrusted_gateway_headers_by_default(monkeypatch):
    monkeypatch.setenv("ALLOW_DEV_WECHAT_LOGIN", "false")
    monkeypatch.setenv("TRUST_CLOUDBASE_IDENTITY_HEADERS", "false")
    monkeypatch.setattr(api_module.auth_service, "app_id", None)
    monkeypatch.setattr(api_module.auth_service, "app_secret", None)

    dev_fallback = client.post("/api/v1/auth/wechat-login", json={"code": "forged-code"})
    forged_header = client.post(
        "/api/v1/auth/wechat-login",
        json={},
        headers={"X-WX-OPENID": "forged-openid"},
    )

    assert dev_fallback.status_code == 400
    assert forged_header.status_code == 400
    assert "access_token" not in dev_fallback.text
    assert "access_token" not in forged_header.text


def test_expired_revoked_and_logged_out_sessions_are_rejected():
    expired = session_service.create("expired-user")
    with session_service.connect() as connection:
        connection.execute(
            "UPDATE user_sessions SET expires_at = ? WHERE id = ?",
            ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), expired["session_id"]),
        )
    expired_headers = {"Authorization": f"Bearer {expired['access_token']}"}
    assert client.get("/api/v1/auth/profile", headers=expired_headers).status_code == 401

    revoked = session_service.create("revoked-user")
    session_service.revoke(revoked["session_id"])
    revoked_headers = {"Authorization": f"Bearer {revoked['access_token']}"}
    assert client.get("/api/v1/auth/profile", headers=revoked_headers).status_code == 401

    _, headers = login()
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/profile", headers=headers).status_code == 401


def test_body_and_query_user_id_cannot_override_authenticated_principal():
    user_a, headers_a = login()
    user_b, _ = login()
    user_a_id = user_a["user"]["user_id"]
    user_b_id = user_b["user"]["user_id"]

    own_profile = client.get("/api/v1/auth/profile", headers=headers_a)
    assert own_profile.status_code == 200
    assert own_profile.headers["cache-control"] == "no-store"
    assert client.get(f"/api/v1/auth/profile?user_id={user_b_id}", headers=headers_a).status_code == 403
    profile = client.post(
        "/api/v1/auth/profile",
        headers=headers_a,
        json={"user_id": user_b_id, "nickname": "伪造用户"},
    )
    assert profile.status_code == 403
    assert api_module.auth_service.get_user(user_a_id)["nickname"] != "伪造用户"


def test_user_a_cannot_read_user_b_report_design_cart_address_order_or_after_sale():
    session_a, headers_a = login()
    session_b, headers_b = login()
    user_a = session_a["user"]["user_id"]
    user_b = session_b["user"]["user_id"]

    report = client.post(
        "/api/v1/assessment/energy",
        headers=headers_b,
        json=assessment_payload(user_b),
    ).json()["data"]
    assert client.get(f"/api/v1/assessment/{report['assessment_id']}", headers=headers_a).status_code == 404

    design = api_module.order_service.save_design(
        {"user_id": user_b, "design": {"selected": ["clearQuartz8"]}, "sequence": [{"id": "clearQuartz8"}]}
    )
    assert client.get(f"/api/v1/diy-designs/{design['design_id']}", headers=headers_a).status_code == 404
    assert client.delete(f"/api/v1/diy-designs/{design['design_id']}", headers=headers_a).status_code == 404

    api_module.order_service.save_cart_item(
        {"user_id": user_b, "item_type": "plan", "item_id": "private-plan", "item": {"name": "B"}}
    )
    assert client.get(f"/api/v1/cart?user_id={user_b}", headers=headers_a).status_code == 403
    assert client.get("/api/v1/cart", headers=headers_a).json()["data"] == []

    address = api_module.order_service.save_address(
        {
            "user_id": user_b,
            "name": "用户 B",
            "phone": "13800000000",
            "region": ["四川省", "成都市"],
            "detail_address": "仅用于测试",
        }
    )
    assert client.delete(
        f"/api/v1/user/addresses/{address['address_id']}?user_id={user_b}", headers=headers_a
    ).status_code == 403

    timestamp = now_iso()
    order_id = f"P0A-{uuid4().hex}"
    with api_module.order_service.connect() as connection:
        connection.execute(
            """
            INSERT INTO orders
            (order_id, out_trade_no, user_id, openid, status, payment_status, total_amount,
             total_fee, currency, receiver_json, design_json, sequence_json, bom_json, remark,
             payment_json, created_at, updated_at, paid_at, after_sale_status, refund_status,
             refund_json, logistics_json, status_history_json, design_id)
            VALUES (?, ?, ?, NULL, 'pending_payment', 'unpaid', 1, 100, 'CNY', ?, '{}', '[]',
                    '[]', NULL, '{}', ?, ?, NULL, NULL, NULL, NULL, NULL, '[]', NULL)
            """,
            (order_id, f"OUT-{uuid4().hex}", user_b, json.dumps({"name": "B"}), timestamp, timestamp),
        )
    assert client.get(f"/api/v1/orders/{order_id}", headers=headers_a).status_code == 404
    after_sale = client.post(
        f"/api/v1/orders/{order_id}/after-sale",
        headers=headers_a,
        json={"user_id": user_a, "reason": "越权测试"},
    )
    assert after_sale.status_code == 404


def test_risk_flags_default_to_closed(monkeypatch):
    for name in (
        "COMMERCE_CHECKOUT_ENABLED",
        "WECHAT_PAYMENT_ENABLED",
        "REPORT_VERSIONING_V2_ENABLED",
        "DIY_PUBLIC_SHARE_ENABLED",
        "REMOTE_AVATAR_FETCH_ENABLED",
        "LOGISTICS_SYNC_ENABLED",
        "KUAIDI100_SUBSCRIBE_ENABLED",
        "METRICS_ENDPOINT_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)
    session, headers = login()
    user_id = session["user"]["user_id"]
    checkout = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "user_id": user_id,
            "receiver": {"name": "测试", "phone": "13800000000", "address": "测试"},
            "sequence": [{"id": "clearQuartz8", "name": "白水晶"}],
        },
    )
    assert checkout.status_code == 503
    assert client.get("/api/v1/diy-designs/shared/not-a-token").status_code == 503
    assert client.get("/internal/metrics").status_code == 404
    with pytest.raises(ValueError, match="已关闭"):
        AvatarStorage().upload_url(user_id, "https://thirdwx.qlogo.cn/avatar.png")


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1", "::1", "fe80::1", "169.254.169.254"],
)
def test_remote_avatar_rejects_unsafe_resolved_addresses(monkeypatch, address):
    monkeypatch.setenv("REMOTE_AVATAR_FETCH_ENABLED", "true")
    monkeypatch.setenv("REMOTE_AVATAR_ALLOWED_HOSTS", "avatar.example.com")
    monkeypatch.setattr(AvatarStorage, "resolve_host_addresses", staticmethod(lambda _host: frozenset({address})))
    with pytest.raises(ValueError, match="不允许的网络"):
        AvatarStorage.validate_remote_avatar_url("https://avatar.example.com/avatar.png")


class FakeResponse:
    def __init__(self, status=200, headers=None, chunks=None):
        self.status = status
        self.headers = headers or {}
        self._content = b"".join(chunks or [])
        self._offset = 0

    def getheader(self, name, default=None):
        for key, value in self.headers.items():
            if key.lower() == name.lower():
                return value
        return default

    def read(self, amount):
        chunk = self._content[self._offset:self._offset + amount]
        self._offset += len(chunk)
        return chunk


class FakeConnection:
    def __init__(self, response):
        self.response = response

    def request(self, *_args, **_kwargs):
        return None

    def getresponse(self):
        return self.response

    def close(self):
        return None


def remote_fetch_storage(monkeypatch, addresses=("8.8.8.8",)) -> AvatarStorage:
    monkeypatch.setenv("REMOTE_AVATAR_FETCH_ENABLED", "true")
    monkeypatch.setenv("REMOTE_AVATAR_ALLOWED_HOSTS", "avatar.example.com")
    monkeypatch.setattr(
        AvatarStorage,
        "resolve_host_addresses",
        staticmethod(lambda _host: frozenset(addresses)),
    )
    return AvatarStorage()


def test_remote_avatar_rejects_redirect_oversize_and_non_image(monkeypatch):
    storage = remote_fetch_storage(monkeypatch)
    monkeypatch.setattr(
        AvatarStorage,
        "pinned_https_connection",
        staticmethod(
            lambda *_args: FakeConnection(
                FakeResponse(status=302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})
            )
        ),
    )
    with pytest.raises(ValueError, match="不能跳转"):
        storage.upload_url("user", "https://avatar.example.com/avatar.png")

    monkeypatch.setattr(
        AvatarStorage,
        "pinned_https_connection",
        staticmethod(
            lambda *_args: FakeConnection(
                FakeResponse(headers={"content-type": "image/png"}, chunks=[b"x" * (MAX_AVATAR_BYTES + 1)])
            )
        ),
    )
    with pytest.raises(ValueError, match="不能超过"):
        storage.upload_url("user", "https://avatar.example.com/avatar.png")

    monkeypatch.setattr(
        AvatarStorage,
        "pinned_https_connection",
        staticmethod(
            lambda *_args: FakeConnection(
                FakeResponse(headers={"content-type": "text/plain"}, chunks=[b"not an image"])
            )
        ),
    )
    with pytest.raises(ValueError, match="不是受支持的图片"):
        storage.upload_url("user", "https://avatar.example.com/avatar.png")


def test_remote_avatar_pins_the_validated_address_against_dns_rebinding(monkeypatch):
    monkeypatch.setenv("REMOTE_AVATAR_FETCH_ENABLED", "true")
    monkeypatch.setenv("REMOTE_AVATAR_ALLOWED_HOSTS", "avatar.example.com")
    resolution_calls = []
    monkeypatch.setattr(
        AvatarStorage,
        "resolve_host_addresses",
        staticmethod(lambda host: resolution_calls.append(host) or frozenset({"8.8.8.8"})),
    )
    pinned_addresses = []
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 16
    monkeypatch.setattr(
        AvatarStorage,
        "pinned_https_connection",
        staticmethod(
            lambda _host, pinned_ip: pinned_addresses.append(pinned_ip)
            or FakeConnection(FakeResponse(headers={"content-type": "image/png"}, chunks=[png]))
        ),
    )
    storage = AvatarStorage()
    monkeypatch.setattr(
        storage,
        "upload",
        lambda **_kwargs: AvatarUploadResult(key="safe", avatar_url="https://cdn.example.com/safe.png"),
    )
    result = storage.upload_url("user", "https://avatar.example.com/avatar.png")
    assert result.key == "safe"
    assert resolution_calls == ["avatar.example.com"]
    assert pinned_addresses == ["8.8.8.8"]


def test_tokens_are_stored_only_as_hashes():
    session = session_service.create("hash-only-user")
    with session_service.connect() as connection:
        row = connection.execute(
            "SELECT token_hash FROM user_sessions WHERE id = ?", (session["session_id"],)
        ).fetchone()
    assert row["token_hash"] == hashlib.sha256(session["access_token"].encode()).hexdigest()
    assert session["access_token"] != row["token_hash"]
