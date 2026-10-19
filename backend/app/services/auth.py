"""Authentication service: registration, login, password reset and 2FA.

Business rules live here. Every database statement is a call to a MySQL
stored procedure through :mod:`app.repositories.auth`, so no query text
appears in this file.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core import cache, totp
from app.core.config import get_settings
from app.core.permissions import sorted_permissions
from app.core.security import (
    create_access_token,
    create_purpose_token,
    decode_purpose_token,
    hash_password,
    utcnow,
    verify_password,
)
from app.db.base import new_uuid
from app.models.enums import UserStatus
from app.repositories import auth as auth_repository
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    TwoFactorChallenge,
    TwoFactorDisableRequest,
    TwoFactorEnableRequest,
    TwoFactorSetupResponse,
    TwoFactorVerifyRequest,
    UserResponse,
)
from app.tasks import queue

logger = logging.getLogger(__name__)

TWO_FACTOR_LOGIN = "2fa_login"
TWO_FACTOR_SETUP = "2fa_setup"
TWO_FACTOR_LOGIN_MINUTES = 5
TWO_FACTOR_SETUP_MINUTES = 10

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


def _to_user_response(row: Mapping[str, Any], two_factor_enabled: bool = False) -> UserResponse:
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
        permissions=sorted_permissions(row["role"]),
        two_factor_enabled=two_factor_enabled,
    )


def serialize_user(user: Mapping[str, Any]) -> UserResponse:
    """Public helper kept for callers that already hold a procedure row."""
    return _to_user_response(user)


def _token_response(user: Mapping[str, Any], two_factor_enabled: bool = False) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user["id"], user["role"]),
        user=_to_user_response(user, two_factor_enabled),
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

    # Báo cáo tăng trưởng hội viên phải thấy tài khoản mới ngay.
    cache.invalidate(cache.REPORTS)
    return _token_response(created)


def _record_failure(db: Session, user_id: str) -> None:
    settings = get_settings()
    auth_repository.mark_login_failed(
        db,
        user_id,
        max_attempts=settings.login_max_failed_attempts,
        lock_minutes=settings.login_lock_minutes,
    )


def _ensure_not_locked(user: Mapping[str, Any]) -> None:
    remaining = _lock_remaining_seconds(user.get("locked_until"))
    if remaining is not None:
        raise _error(
            429,
            "ACCOUNT_LOCKED",
            "Tài khoản tạm bị khoá do đăng nhập sai nhiều lần.",
            {"retry_after_seconds": remaining},
        )


def _two_factor_secret(db: Session, user_id: str) -> str | None:
    stored = auth_repository.get_two_factor_secret(db, user_id)
    if not stored:
        return None
    secret = totp.decrypt_secret(stored)
    if secret is None:
        # Khoá JWT đổi nên không giải mã được: coi như chưa bật, ghi log để admin biết.
        logger.error("Không giải mã được khoá 2FA của tài khoản", extra={"user_id": user_id})
    return secret


def login(db: Session, payload: LoginRequest) -> TokenResponse | TwoFactorChallenge:
    email = payload.email.strip().lower()

    user = auth_repository.find_user_by_email(db, email)
    if user is None:
        # Không tiết lộ email có tồn tại hay không.
        raise _error(401, "INVALID_CREDENTIALS", "Email hoặc mật khẩu chưa chính xác.")

    _ensure_not_locked(user)

    if not verify_password(payload.password, user["password_hash"]):
        _record_failure(db, user["id"])
        raise _error(401, "INVALID_CREDENTIALS", "Email hoặc mật khẩu chưa chính xác.")

    if user["status"] in (UserStatus.SUSPENDED.value, UserStatus.INACTIVE.value):
        raise _error(403, "ACCOUNT_DISABLED", "Tài khoản đã bị khoá hoặc ngưng hoạt động.")

    if _two_factor_secret(db, user["id"]):
        # Mật khẩu đúng nhưng còn bước 2: chưa ghi nhận đăng nhập, chưa cấp token.
        return TwoFactorChallenge(
            challenge_token=create_purpose_token(
                user["id"], TWO_FACTOR_LOGIN, TWO_FACTOR_LOGIN_MINUTES
            ),
            expires_in=TWO_FACTOR_LOGIN_MINUTES * 60,
        )

    auth_repository.mark_login_success(db, user["id"])
    refreshed = auth_repository.find_user_by_id(db, user["id"]) or user
    return _token_response(refreshed)


# --------------------------------------------------------------------------
# Two-step verification (TOTP)
# --------------------------------------------------------------------------


def _invalid_code() -> HTTPException:
    return _error(401, "INVALID_2FA_CODE", "Mã xác thực không đúng hoặc đã hết hạn.")


def verify_two_factor(db: Session, payload: TwoFactorVerifyRequest) -> TokenResponse:
    try:
        claims = decode_purpose_token(payload.challenge_token, TWO_FACTOR_LOGIN)
    except ValueError as exc:
        raise _error(
            401, "CHALLENGE_EXPIRED", "Phiên xác thực đã hết hạn, vui lòng đăng nhập lại."
        ) from exc

    user = auth_repository.find_user_by_id(db, str(claims.get("sub", "")))
    if user is None or user["status"] in (UserStatus.SUSPENDED.value, UserStatus.INACTIVE.value):
        raise _error(401, "CHALLENGE_EXPIRED", "Phiên xác thực đã hết hạn, vui lòng đăng nhập lại.")
    _ensure_not_locked(user)

    secret = _two_factor_secret(db, user["id"])
    if secret is None or not totp.verify(secret, payload.code):
        # Mã sai cũng tính vào bộ đếm khoá tài khoản để chặn dò mã.
        _record_failure(db, user["id"])
        raise _invalid_code()

    auth_repository.mark_login_success(db, user["id"])
    refreshed = auth_repository.find_user_by_id(db, user["id"]) or user
    return _token_response(refreshed, two_factor_enabled=True)


def two_factor_enabled(db: Session, user_id: str) -> bool:
    return bool(auth_repository.get_two_factor_secret(db, user_id))


def setup_two_factor(db: Session, user: Mapping[str, Any]) -> TwoFactorSetupResponse:
    if two_factor_enabled(db, user["id"]):
        raise _error(409, "TWO_FACTOR_ALREADY_ENABLED", "Xác thực 2 bước đã được bật.")
    secret = totp.new_secret()
    uri = totp.provisioning_uri(secret, user["email"])
    return TwoFactorSetupResponse(
        secret=secret,
        otpauth_uri=uri,
        qr_svg=totp.qr_svg(uri),
        # Khoá mới chỉ được lưu khi người dùng nhập đúng mã ở bước kích hoạt.
        setup_token=create_purpose_token(
            user["id"],
            TWO_FACTOR_SETUP,
            TWO_FACTOR_SETUP_MINUTES,
            secret=totp.encrypt_secret(secret),
        ),
    )


def enable_two_factor(
    db: Session, user: Mapping[str, Any], payload: TwoFactorEnableRequest
) -> MessageResponse:
    try:
        claims = decode_purpose_token(payload.setup_token, TWO_FACTOR_SETUP)
    except ValueError as exc:
        raise _error(
            400, "SETUP_EXPIRED", "Phiên cài đặt đã hết hạn, vui lòng bắt đầu lại."
        ) from exc
    encrypted = str(claims.get("secret", ""))
    secret = totp.decrypt_secret(encrypted) if encrypted else None
    if claims.get("sub") != user["id"] or secret is None:
        raise _error(400, "SETUP_EXPIRED", "Phiên cài đặt đã hết hạn, vui lòng bắt đầu lại.")
    if not totp.verify(secret, payload.code):
        raise _invalid_code()

    auth_repository.set_two_factor_secret(db, user["id"], totp.encrypt_secret(secret))
    return MessageResponse(message="Đã bật xác thực 2 bước.")


def disable_two_factor(
    db: Session, user: Mapping[str, Any], payload: TwoFactorDisableRequest
) -> MessageResponse:
    secret = _two_factor_secret(db, user["id"])
    if secret is None:
        raise _error(409, "TWO_FACTOR_NOT_ENABLED", "Xác thực 2 bước chưa được bật.")
    if not verify_password(payload.password, user["password_hash"]):
        raise _error(401, "INVALID_CREDENTIALS", "Mật khẩu chưa chính xác.")
    if not totp.verify(secret, payload.code):
        raise _invalid_code()

    auth_repository.set_two_factor_secret(db, user["id"], None)
    return MessageResponse(message="Đã tắt xác thực 2 bước.")


# --------------------------------------------------------------------------
# Password reset
# --------------------------------------------------------------------------

_FORGOT_MESSAGE = (
    "Nếu email đã đăng ký, chúng tôi đã gửi hướng dẫn đặt lại mật khẩu. Vui lòng kiểm tra hộp thư."
)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def forgot_password(db: Session, payload: ForgotPasswordRequest) -> MessageResponse:
    """Queue the reset email; the answer never reveals whether the email exists."""
    user = auth_repository.find_user_by_email(db, payload.email)
    if user is not None and user["status"] not in (
        UserStatus.SUSPENDED.value,
        UserStatus.INACTIVE.value,
    ):
        # Token được tạo trong tác vụ gửi mail: token gốc không bao giờ nằm trong database.
        queue.enqueue(db, "email.password_reset", {"user_id": user["id"]}, user["id"])
    return MessageResponse(message=_FORGOT_MESSAGE)


def reset_password(db: Session, payload: ResetPasswordRequest) -> MessageResponse:
    outcome = auth_repository.consume_password_reset(
        db,
        token_digest=token_digest(payload.token.strip()),
        password_hash=hash_password(payload.password),
    )
    if not outcome.succeeded:
        code = outcome.error_code or "INTERNAL_ERROR"
        status_code = 500 if code == "INTERNAL_ERROR" else 400
        raise _error(status_code, code, outcome.error_message or "Không thể đặt lại mật khẩu.")
    return MessageResponse(message="Đã đặt lại mật khẩu. Hãy đăng nhập bằng mật khẩu mới.")
