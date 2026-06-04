"""
auth.py - Lightweight local registration/login endpoints.
"""

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from models.database import (
    create_auth_session,
    create_user,
    delete_auth_session,
    get_user_by_email,
    get_user_by_session_token,
)

router = APIRouter()

SESSION_COOKIE = "ai_path_session"
SESSION_DAYS = 7
PBKDF2_ITERATIONS = 180_000


class AuthUser(BaseModel):
    user_id: str
    name: str
    email: str


class AuthResponse(BaseModel):
    authenticated: bool
    user: AuthUser


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Email không hợp lệ.")
        return email


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Email không hợp lệ.")
        return email


def _public_user(user: dict) -> AuthUser:
    return AuthUser(user_id=user["user_id"], name=user["name"], email=user["email"])


def require_auth_user(ai_path_session: Optional[str]) -> dict:
    if not ai_path_session:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    user = get_user_by_session_token(ai_path_session)
    if not user:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã hết hạn.")
    return user


def _hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Mật khẩu cần ít nhất 8 ký tự.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="Mật khẩu cần có cả chữ và số.")


def _set_session_cookie(response: Response, user_id: str) -> None:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=SESSION_DAYS)
    create_auth_session(token=token, user_id=user_id, expires_at=expires_at.isoformat())
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


@router.post("/auth/register", response_model=AuthResponse)
async def register(payload: RegisterRequest, response: Response):
    _validate_password_strength(payload.password)

    email = payload.email.lower()
    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail="Email này đã được đăng ký.")

    user = create_user(
        user_id=f"user_{uuid4().hex[:12]}",
        name=payload.name.strip(),
        email=email,
        password_hash=_hash_password(payload.password),
    )
    _set_session_cookie(response, user["user_id"])
    return AuthResponse(authenticated=True, user=_public_user(user))


@router.post("/auth/login", response_model=AuthResponse)
async def login(payload: LoginRequest, response: Response):
    user = get_user_by_email(payload.email.lower())
    if not user or not _verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng.")

    _set_session_cookie(response, user["user_id"])
    return AuthResponse(authenticated=True, user=_public_user(user))


@router.post("/auth/logout")
async def logout(response: Response, ai_path_session: Optional[str] = Cookie(default=None)):
    if ai_path_session:
        delete_auth_session(ai_path_session)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"success": True}


@router.get("/auth/me", response_model=AuthResponse)
async def me(ai_path_session: Optional[str] = Cookie(default=None)):
    user = require_auth_user(ai_path_session)
    return AuthResponse(authenticated=True, user=_public_user(user))
