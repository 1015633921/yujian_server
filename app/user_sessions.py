from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import DEFAULT_SQLITE_PATH, connect_database
from .observability import bind_user_id


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class UserPrincipal:
    user_id: str
    session_id: str


class UserSessionService:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_SQLITE_PATH
        self._force_sqlite = db_path is not None

    def connect(self):
        return connect_database(self.db_path if self._force_sqlite else None)

    @staticmethod
    def ttl_seconds() -> int:
        configured = int(os.getenv("USER_SESSION_TTL_SECONDS", str(7 * 24 * 60 * 60)))
        return max(300, min(configured, 30 * 24 * 60 * 60))

    def create(self, user_id: str) -> dict[str, Any]:
        token = secrets.token_urlsafe(48)
        session_id = f"us_{secrets.token_hex(16)}"
        created_at = now_iso()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds())
        ).replace(microsecond=0).isoformat()
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO user_sessions
                    (id, user_id, token_hash, created_at, expires_at, revoked_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, NULL, ?)
                    """,
                    (session_id, user_id, token_hash(token), created_at, expires_at, created_at),
                )
        except (sqlite3.OperationalError, KeyError) as exc:
            raise RuntimeError("P0-A security migration has not been applied") from exc
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "session_id": session_id,
        }

    def authenticate(self, token: str) -> UserPrincipal | None:
        if not token or len(token) < 32 or len(token) > 512:
            return None
        timestamp = now_iso()
        try:
            with self.connect() as connection:
                row = connection.execute(
                    """
                    SELECT id, user_id FROM user_sessions
                    WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?
                    LIMIT 1
                    """,
                    (token_hash(token), timestamp),
                ).fetchone()
                if not row:
                    return None
                connection.execute(
                    "UPDATE user_sessions SET last_seen_at = ? WHERE id = ?",
                    (timestamp, row["id"]),
                )
        except sqlite3.OperationalError as exc:
            raise RuntimeError("P0-A security migration has not been applied") from exc
        return UserPrincipal(user_id=str(row["user_id"]), session_id=str(row["id"]))

    def revoke(self, session_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE user_sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (now_iso(), session_id),
            )

    def revoke_user(self, user_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (now_iso(), user_id),
            )


session_service = UserSessionService()
bearer_scheme = HTTPBearer(auto_error=False)


def require_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserPrincipal:
    token = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else ""
    principal = session_service.authenticate(token)
    if not principal:
        raise HTTPException(
            status_code=401,
            detail="登录已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    bind_user_id(principal.user_id)
    return principal


def require_owner(principal: UserPrincipal, supplied_user_id: str | None) -> str:
    if supplied_user_id and str(supplied_user_id) != principal.user_id:
        raise HTTPException(status_code=403, detail="无权访问该用户资源")
    return principal.user_id


def private_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="资源不存在")
