"""Small signed-cookie session middleware for MaterialHub."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class SignedCookieSessionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        secret_key: str,
        cookie_name: str = "materialhub_session",
        max_age: int = 60 * 60 * 12,
        same_site: str = "lax",
        https_only: bool = False,
    ) -> None:
        self.app = app
        self.secret_key = secret_key.encode("utf-8")
        self.cookie_name = cookie_name
        self.max_age = max_age
        self.same_site = same_site
        self.https_only = https_only

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        scope["session"] = self._load_session(request.cookies.get(self.cookie_name))

        async def send_with_session(message) -> None:
            if message["type"] == "http.response.start":
                cookie_response = Response()
                session = scope.get("session") or {}
                if session:
                    cookie_response.set_cookie(
                        self.cookie_name,
                        self._dump_session(session),
                        max_age=self.max_age,
                        httponly=True,
                        samesite=self.same_site,
                        secure=self.https_only,
                    )
                else:
                    cookie_response.delete_cookie(self.cookie_name)
                set_cookie_headers = [
                    header for header in cookie_response.raw_headers
                    if header[0].lower() == b"set-cookie"
                ]
                message.setdefault("headers", []).extend(set_cookie_headers)
            await send(message)

        await self.app(scope, receive, send_with_session)

    def _load_session(self, cookie_value: str | None) -> dict[str, str]:
        if not cookie_value or "." not in cookie_value:
            return {}
        payload, signature = cookie_value.rsplit(".", 1)
        expected = self._signature(payload)
        if not hmac.compare_digest(signature, expected):
            return {}
        try:
            padded = payload + "=" * (-len(payload) % 4)
            data = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _dump_session(self, session: dict[str, str]) -> str:
        payload = base64.urlsafe_b64encode(
            json.dumps(session, separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")
        return f"{payload}.{self._signature(payload)}"

    def _signature(self, payload: str) -> str:
        digest = hmac.new(self.secret_key, payload.encode("ascii"), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
