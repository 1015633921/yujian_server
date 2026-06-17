from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import Request as FastAPIRequest

from .repository import AssessmentRepository
from .schemas import PhoneBindRequest, UserProfileUpdateRequest, WechatLoginRequest


class WechatAuthService:
    def __init__(self, repository: AssessmentRepository | None = None):
        self.repository = repository or AssessmentRepository()
        self.app_id = os.getenv("WECHAT_APP_ID") or os.getenv("WX_APPID")
        self.app_secret = os.getenv("WECHAT_APP_SECRET") or os.getenv("WX_APP_SECRET")
        self._access_token: dict[str, Any] | None = None

    def login(self, payload: WechatLoginRequest, request: FastAPIRequest) -> dict[str, Any]:
        identity = self.identity_from_headers(request)
        source = "cloudbase"
        if not identity.get("openid"):
            identity = self.identity_from_code(payload.code)
            source = identity.pop("source", "wechat")

        now = self.now()
        user_id = identity["user_id"]
        user = self.repository.upsert_user(
            {
                "user_id": user_id,
                "openid": identity.get("openid"),
                "unionid": identity.get("unionid"),
                "nickname": payload.nickname,
                "avatar_url": payload.avatar_url,
                "gender": payload.gender,
                "source": source,
                "updated_at": now,
            }
        )
        return self.public_user(user)

    def update_profile(self, payload: UserProfileUpdateRequest) -> dict[str, Any]:
        now = self.now()
        user = self.repository.upsert_user(
            {
                "user_id": payload.user_id,
                "nickname": payload.nickname or payload.name,
                "avatar_url": payload.avatar_url,
                "gender": payload.gender,
                "source": "wechat_profile",
                "updated_at": now,
            }
        )
        return self.public_user(user)

    def bind_phone(self, payload: PhoneBindRequest) -> dict[str, Any]:
        phone_number = payload.phone_number
        source = "manual"
        if payload.code and self.app_id and self.app_secret:
            phone_number = self.phone_from_code(payload.code)
            source = "wechat_phone"
        if not phone_number:
            raise ValueError("phone code cannot be exchanged without WECHAT_APP_ID and WECHAT_APP_SECRET")

        user = self.repository.upsert_user(
            {
                "user_id": payload.user_id,
                "phone_number": phone_number,
                "source": source,
                "updated_at": self.now(),
            }
        )
        return self.public_user(user)

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        user = self.repository.get_user(user_id)
        return self.public_user(user) if user else None

    def identity_from_headers(self, request: FastAPIRequest) -> dict[str, str]:
        openid = request.headers.get("x-wx-openid")
        appid = request.headers.get("x-wx-appid")
        unionid = request.headers.get("x-wx-unionid")
        if not openid:
            return {}
        return {
            "user_id": openid,
            "openid": openid,
            "unionid": unionid,
            "appid": appid or "",
        }

    def identity_from_code(self, code: str | None) -> dict[str, str]:
        if code and self.app_id and self.app_secret:
            params = urlencode(
                {
                    "appid": self.app_id,
                    "secret": self.app_secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                }
            )
            data = self.get_json(f"https://api.weixin.qq.com/sns/jscode2session?{params}")
            if data.get("errcode"):
                raise ValueError(data.get("errmsg", "wechat login failed"))
            openid = data["openid"]
            return {
                "user_id": openid,
                "openid": openid,
                "unionid": data.get("unionid"),
                "source": "wechat",
            }

        seed = code or f"anonymous:{time.time_ns()}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        return {
            "user_id": f"dev_{digest}",
            "openid": f"dev_{digest}",
            "source": "dev_mock",
        }

    def phone_from_code(self, code: str) -> str:
        token = self.access_token()
        data = self.get_json(
            f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={token}",
            method="POST",
            body={"code": code},
        )
        if data.get("errcode"):
            raise ValueError(data.get("errmsg", "wechat phone exchange failed"))
        phone_info = data.get("phone_info") or {}
        return phone_info.get("purePhoneNumber") or phone_info.get("phoneNumber")

    def access_token(self) -> str:
        if self._access_token and self._access_token["expires_at"] > time.time() + 60:
            return self._access_token["token"]
        params = urlencode(
            {
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
            }
        )
        data = self.get_json(f"https://api.weixin.qq.com/cgi-bin/token?{params}")
        if data.get("errcode"):
            raise ValueError(data.get("errmsg", "wechat access token failed"))
        self._access_token = {
            "token": data["access_token"],
            "expires_at": time.time() + int(data.get("expires_in", 7200)),
        }
        return self._access_token["token"]

    @staticmethod
    def get_json(url: str, method: str = "GET", body: dict | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def public_user(user: dict[str, Any]) -> dict[str, Any]:
        return {
            "user_id": user["user_id"],
            "nickname": user.get("nickname"),
            "avatar_url": user.get("avatar_url"),
            "gender": user.get("gender"),
            "phone_number": user.get("phone_number"),
            "has_profile": bool(user.get("nickname") or user.get("avatar_url")),
            "has_phone": bool(user.get("phone_number")),
            "source": user.get("source"),
        }

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()
