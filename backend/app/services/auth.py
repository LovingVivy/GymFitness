"""Authentication service: registration and login.

Business rules live here. Every database statement is a call to a MySQL
stored procedure through :mod:`app.repositories.auth`, so no query text
appears in this file.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, utcnow, verify_password
from app.db.base import new_uuid
from app.models.enums import UserStatus
from app.repositories import auth as auth_repository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

_REGISTER_ERRORS: dict[str, tuple[int, str]] = {
    "EMAIL_EXISTS": (409, "Email này đã được sử dụng."),
    "PHONE_EXISTS": (409, "Số điện thoại này đã được sử dụng."),
    "INTERNAL_ERROR": (500, "Không thể tạo tài khoản do lỗi hệ thống."),
}


def _error(status_code: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )


def _to_user_response(row: Mapping[str, Any]) -> UserResponse:
    height = row.get("height_cm")
    weight = row.get("weight_kg")
    return UserResponse(
        id=row["id"],
        email=row["email"],
        phone=row.get("phone"),
        role=row["role"],
        status=row["status"],
        full_name=row.get("full_name"),
        height_cm=float(height) if height is not None else None,
        weight_kg=float(weight) if weight is not None else None,
        experience_level=row.get("experience_level"),
        fitness_goal=row.get("fitness_goal"),
        weekly_training_sessions=row.get("weekly_training_sessions"),
    )


def serialize_user(user: Mapping[str, Any]) -> UserResponse:
    """Public helper kept for callers that already hold a procedure row."""
    return _to_user_response(user)


def _token_response(user: Mapping[str, Any]) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user["id"], user["role"]),
        user=_to_user_response(user),
    )


def _lock_remaining_seconds(locked_until: datetime | None) -> int | None:
    if locked_until is None:
        return None
    remaining = int((locked_until - utcnow()).total_seconds())
    return remaining if remaining > 0 else None


def register(db: Session, payload: RegisterRequest) -> TokenResponse:
    email = payload.email.strip().lower()
    phone = payload.phone.strip() if payload.phone and payload.phone.strip() else None

    user_id = new_uuid()
    outcome = auth_repository.register_user(
        db,
        user_id=user_id,
        member_id=new_uuid(),
        email=email,
        phone=phone,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
    )

    if not outcome.succeeded:
        code = outcome.error_code or auth_repository.INTERNAL_ERROR
        status_code, default_message = _REGISTER_ERRORS.get(code, (500, "Không thể tạo tài khoản."))
        raise _error(status_code, code, outcome.error_message or default_message)

    created = auth_repository.find_user_by_id(db, user_id)
    if created is None:
        raise _error(500, "INTERNAL_ERROR", "Không thể đọc lại tài khoản vừa tạo.")

    return _token_response(created)


def login(db: Session, payload: LoginRequest) -> TokenResponse:
    settings = get_settings()
    email = payload.email.strip().lower()

    user = auth_repository.find_user_by_email(db, email)
    if user is None:
        # Không tiết lộ email có tồn tại hay không.
        raise _error(401, "INVALID_CREDENTIALS", "Email hoặc mật khẩu chưa chính xác.")

    remaining = _lock_remaining_seconds(user.get("locked_until"))
    if remaining is not None:
        raise _error(
            429,
            "ACCOUNT_LOCKED",
            "Tài khoản tạm bị khoá do đăng nhập sai nhiều lần.",
            {"retry_after_seconds": remaining},
        )

    if not verify_password(payload.password, user["password_hash"]):
        auth_repository.mark_login_failed(
            db,
            user["id"],
            max_attempts=settings.login_max_failed_attempts,
            lock_minutes=settings.login_lock_minutes,
        )
        raise _error(401, "INVALID_CREDENTIALS", "Email hoặc mật khẩu chưa chính xác.")

    if user["status"] in (UserStatus.SUSPENDED.value, UserStatus.INACTIVE.value):
        raise _error(403, "ACCOUNT_DISABLED", "Tài khoản đã bị khoá hoặc ngưng hoạt động.")

    auth_repository.mark_login_success(db, user["id"])
    refreshed = auth_repository.find_user_by_id(db, user["id"]) or user
    return _token_response(refreshed)
