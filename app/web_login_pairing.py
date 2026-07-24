from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path as ApiPath
from pydantic import BaseModel, ConfigDict, Field

from .auth_service import WechatAuthService
from .database import DEFAULT_SQLITE_PATH, connect_database
from .feature_flags import web_login_pairing_enabled
from .user_sessions import UserPrincipal, UserSessionService, require_current_user, session_service


PAIRING_TTL_SECONDS = 5 * 60
VERIFICATION_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
BFF_TOKEN_HEADER = "X-Yustream-BFF-Token"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def bff_secret() -> str:
    value = os.getenv("WEB_LOGIN_PAIRING_BFF_SECRET", "")
    if len(value.encode("utf-8")) < 32:
        raise RuntimeError("WEB_LOGIN_PAIRING_BFF_SECRET must contain at least 32 bytes")
    return value


def verification_code_hash(value: str) -> str:
    return hmac.new(bff_secret().encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


class PairingNotFoundError(Exception):
    pass


class PairingExpiredError(Exception):
    pass


class PairingStateError(Exception):
    pass


class WebLoginPairingService:
    def __init__(self, db_path: Path | None = None, user_session_service: UserSessionService | None = None):
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_SQLITE_PATH
        self._force_sqlite = db_path is not None
        self.user_session_service = user_session_service or session_service

    def connect(self):
        return connect_database(self.db_path if self._force_sqlite else None)

    @staticmethod
    def expires_at() -> str:
        return (datetime.now(timezone.utc) + timedelta(seconds=PAIRING_TTL_SECONDS)).replace(microsecond=0).isoformat()

    @staticmethod
    def verification_code() -> str:
        return "".join(secrets.choice(VERIFICATION_ALPHABET) for _ in range(8))

    def create(self) -> dict[str, Any]:
        pairing_id = f"wp_{secrets.token_urlsafe(24)}"
        browser_secret = secrets.token_urlsafe(48)
        verification_code = self.verification_code()
        created_at = now_iso()
        expires_at = self.expires_at()
        with self.connect() as connection:
            connection.execute("UPDATE web_login_pairings SET status = 'expired' WHERE status IN ('pending', 'confirmed') AND expires_at <= ?", (created_at,))
            connection.execute(
                """INSERT INTO web_login_pairings
                (id, browser_secret_hash, verification_code_hash, status, confirmed_user_id, confirmed_session_id,
                 failed_confirm_attempts, created_at, expires_at, confirmed_at, consumed_at)
                VALUES (?, ?, ?, 'pending', NULL, NULL, 0, ?, ?, NULL, NULL)""",
                (pairing_id, secret_hash(browser_secret), verification_code_hash(verification_code), created_at, expires_at),
            )
        return {"pairing_id": pairing_id, "browser_secret": browser_secret, "verification_code": verification_code, "status": "pending", "expires_at": expires_at, "poll_after_seconds": 2}

    def confirm(self, pairing_id: str, verification_code: str, principal: UserPrincipal) -> dict[str, Any]:
        timestamp = now_iso()
        outcome = "conflict"
        expires_at = ""
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE web_login_pairings
                SET status = 'confirmed', confirmed_user_id = ?, confirmed_session_id = ?, confirmed_at = ?
                WHERE id = ? AND verification_code_hash = ? AND status = 'pending' AND confirmed_user_id IS NULL
                  AND failed_confirm_attempts < 5 AND expires_at > ?""",
                (principal.user_id, principal.session_id, timestamp, pairing_id, verification_code_hash(verification_code), timestamp),
            )
            if cursor.rowcount == 1:
                row = connection.execute("SELECT expires_at FROM web_login_pairings WHERE id = ?", (pairing_id,)).fetchone()
                expires_at, outcome = str(row["expires_at"]), "confirmed"
            else:
                row = connection.execute("SELECT verification_code_hash, status, expires_at, failed_confirm_attempts FROM web_login_pairings WHERE id = ?", (pairing_id,)).fetchone()
                if not row:
                    outcome = "not_found"
                elif not hmac.compare_digest(str(row["verification_code_hash"]), verification_code_hash(verification_code)):
                    if str(row["status"]) == "pending" and str(row["expires_at"]) > timestamp:
                        connection.execute("""UPDATE web_login_pairings SET failed_confirm_attempts = failed_confirm_attempts + 1,
                          status = CASE WHEN failed_confirm_attempts + 1 >= 5 THEN 'expired' ELSE status END
                          WHERE id = ? AND status = 'pending' AND expires_at > ?""", (pairing_id, timestamp))
                    outcome = "not_found"
                elif str(row["status"]) in {"pending", "confirmed"} and str(row["expires_at"]) <= timestamp:
                    connection.execute("UPDATE web_login_pairings SET status = 'expired' WHERE id = ? AND status IN ('pending', 'confirmed')", (pairing_id,))
                    outcome = "expired"
                elif str(row["status"]) == "expired":
                    outcome = "expired"
        if outcome == "not_found":
            raise PairingNotFoundError
        if outcome == "expired":
            raise PairingExpiredError
        if outcome != "confirmed":
            raise PairingStateError
        return {"pairing_id": pairing_id, "status": "confirmed", "expires_at": expires_at}

    def claim(self, pairing_id: str, browser_secret: str) -> dict[str, Any]:
        timestamp = now_iso()
        supplied_hash = secret_hash(browser_secret)
        outcome = "not_found"
        data: dict[str, Any] = {}
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE web_login_pairings SET status = 'consumed', consumed_at = ?
                WHERE id = ? AND browser_secret_hash = ? AND status = 'confirmed' AND confirmed_user_id IS NOT NULL AND expires_at > ?""",
                (timestamp, pairing_id, supplied_hash, timestamp),
            )
            if cursor.rowcount == 1:
                row = connection.execute("SELECT confirmed_user_id FROM web_login_pairings WHERE id = ? AND status = 'consumed'", (pairing_id,)).fetchone()
                if not row or not row["confirmed_user_id"]:
                    raise RuntimeError("confirmed pairing has no user")
                session = self.user_session_service.create_in_connection(connection, str(row["confirmed_user_id"]))
                outcome = "claimed"
                data = {"pairing_id": pairing_id, "status": "consumed", "user_id": str(row["confirmed_user_id"]), "session": session}
            else:
                row = connection.execute("SELECT browser_secret_hash, status, expires_at FROM web_login_pairings WHERE id = ?", (pairing_id,)).fetchone()
                if not row or not hmac.compare_digest(str(row["browser_secret_hash"]), supplied_hash):
                    outcome = "not_found"
                else:
                    status = str(row["status"])
                    if status in {"pending", "confirmed"} and str(row["expires_at"]) <= timestamp:
                        connection.execute("UPDATE web_login_pairings SET status = 'expired' WHERE id = ? AND status IN ('pending', 'confirmed')", (pairing_id,))
                        outcome = "expired"
                    elif status == "pending":
                        outcome = "pending"
                        data = {"pairing_id": pairing_id, "status": "pending", "expires_at": str(row["expires_at"]), "poll_after_seconds": 2}
                    elif status == "expired":
                        outcome = "expired"
                    else:
                        outcome = "conflict"
        if outcome == "not_found":
            raise PairingNotFoundError
        if outcome == "expired":
            raise PairingExpiredError
        if outcome == "conflict":
            raise PairingStateError
        return data


class PairingConfirmRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    verification_code: str = Field(min_length=8, max_length=16, pattern=r"^[A-Z0-9]+$")


class PairingClaimRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    browser_secret: str = Field(min_length=32, max_length=512)


def require_web_login_pairing_enabled() -> None:
    if not web_login_pairing_enabled():
        raise HTTPException(status_code=503, detail="网站登录配对当前未开放")
    try:
        bff_secret()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="网站登录配对配置不完整") from exc


def require_web_login_pairing_bff(supplied_token: str | None = Header(default=None, alias=BFF_TOKEN_HEADER)) -> None:
    require_web_login_pairing_enabled()
    expected = bff_secret()
    if not supplied_token or not hmac.compare_digest(supplied_token.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="未授权")


def success(data: Any, message: str = "ok") -> dict[str, Any]:
    return {"code": 0, "message": message, "data": data}


def pairing_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PairingNotFoundError):
        return HTTPException(status_code=404, detail="登录配对不存在")
    if isinstance(exc, PairingExpiredError):
        return HTTPException(status_code=410, detail="登录配对已过期")
    return HTTPException(status_code=409, detail="登录配对已被确认或领取")


pairing_service = WebLoginPairingService()
pairing_auth_service = WechatAuthService()
web_login_pairing_router = APIRouter(prefix="/api/v1/auth/web-pairings", tags=["网站登录配对"])


@web_login_pairing_router.post("", summary="创建网站登录配对")
def create_web_login_pairing(_authorized: None = Depends(require_web_login_pairing_bff)):
    return success(pairing_service.create(), "登录配对已创建")


@web_login_pairing_router.post("/{pairing_id}/confirm", summary="小程序确认网站登录")
def confirm_web_login_pairing(payload: PairingConfirmRequest, pairing_id: str = ApiPath(min_length=10, max_length=100), _enabled: None = Depends(require_web_login_pairing_enabled), principal: UserPrincipal = Depends(require_current_user)):
    try:
        return success(pairing_service.confirm(pairing_id, payload.verification_code, principal), "网站登录已确认")
    except (PairingNotFoundError, PairingExpiredError, PairingStateError) as exc:
        raise pairing_http_error(exc) from exc


@web_login_pairing_router.post("/{pairing_id}/claim", summary="轮询并领取网站登录会话")
def claim_web_login_pairing(payload: PairingClaimRequest, pairing_id: str = ApiPath(min_length=10, max_length=100), _authorized: None = Depends(require_web_login_pairing_bff)):
    try:
        result = pairing_service.claim(pairing_id, payload.browser_secret)
    except (PairingNotFoundError, PairingExpiredError, PairingStateError) as exc:
        raise pairing_http_error(exc) from exc
    if result["status"] == "pending":
        return success(result, "等待小程序确认")
    session = result["session"]
    user = pairing_auth_service.get_user(result["user_id"])
    return success({"pairing_id": pairing_id, "status": "consumed", "access_token": session["access_token"], "token_type": session["token_type"], "expires_at": session["expires_at"], "user": user or {"user_id": result["user_id"]}}, "网站登录成功")
