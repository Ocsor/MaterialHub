"""Environment-backed login and role checks."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from secrets import token_urlsafe
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 390000


@dataclass(frozen=True)
class AuthUser:
    username: str
    role: str


def hash_password(password: str, salt: str | None = None) -> str:
    """Return a portable PBKDF2 password hash for .env storage."""
    salt = salt or token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt}${encoded}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$", 3)
        if algorithm != PBKDF2_ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
    except (TypeError, ValueError):
        return False

    actual = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return hmac.compare_digest(actual, expected)


def _configured_users() -> tuple[dict[str, str], ...]:
    return (
        {
            "username": os.getenv("MATERIALHUB_ADMIN_USERNAME", ""),
            "password_hash": os.getenv("MATERIALHUB_ADMIN_PASSWORD_HASH", ""),
            "role": "admin",
        },
        {
            "username": os.getenv("MATERIALHUB_BASIC_USERNAME", ""),
            "password_hash": os.getenv("MATERIALHUB_BASIC_PASSWORD_HASH", ""),
            "role": "basic",
        },
    )


def authenticate_user(username: str, password: str) -> AuthUser | None:
    for user in _configured_users():
        if not user["username"] or not user["password_hash"]:
            continue
        if hmac.compare_digest(username, user["username"]) and verify_password(password, user["password_hash"]):
            return AuthUser(username=user["username"], role=user["role"])
    return None


def current_user(request: Request) -> AuthUser | None:
    username = request.session.get("user")
    role = request.session.get("role")
    if not isinstance(username, str) or role not in {"admin", "basic"}:
        return None
    return AuthUser(username=username, role=role)


def require_login(request: Request) -> AuthUser:
    user = current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": f"/login?next={request.url.path}"},
        )
    return user


def require_admin(user: Annotated[AuthUser, Depends(require_login)]) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
