"""Data access for authentication.

Every SQL statement used by register/login lives inside MySQL stored
procedures (see ``database/03_procedures.sql``). This module contains no
``SELECT``/``INSERT``/``UPDATE`` of its own — it only invokes the procedures
and hands their result sets back to the service layer as plain dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.procedures import call

REGISTER = "sp_auth_register"
FIND_USER_BY_EMAIL = "sp_auth_find_user_by_email"
FIND_USER_BY_ID = "sp_auth_find_user_by_id"
MARK_LOGIN_SUCCESS = "sp_auth_mark_login_success"
MARK_LOGIN_FAILED = "sp_auth_mark_login_failed"

INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class RegisterOutcome:
    """Result set returned by ``sp_auth_register``."""

    error_code: str | None
    error_message: str | None
    user_id: str | None

    @property
    def succeeded(self) -> bool:
        return self.error_code is None and self.user_id is not None


def register_user(
    db: Session,
    *,
    user_id: str,
    member_id: str,
    email: str,
    phone: str | None,
    password_hash: str,
    full_name: str,
) -> RegisterOutcome:
    """Create the ``users``, ``user_profiles`` and ``members`` rows atomically."""
    rows = call(
        db,
        REGISTER,
        {
            "p_user_id": user_id,
            "p_member_id": member_id,
            "p_email": email,
            "p_phone": phone,
            "p_password_hash": password_hash,
            "p_full_name": full_name,
        },
    )
    if not rows:
        return RegisterOutcome(INTERNAL_ERROR, "Không thể tạo tài khoản do lỗi hệ thống.", None)

    row = rows[0]
    return RegisterOutcome(
        error_code=row.get("error_code"),
        error_message=row.get("error_message"),
        user_id=row.get("user_id"),
    )


def find_user_by_email(db: Session, email: str) -> dict[str, Any] | None:
    """Load the account (with its profile) used to verify a login attempt."""
    rows = call(db, FIND_USER_BY_EMAIL, {"p_email": email})
    return rows[0] if rows else None


def find_user_by_id(db: Session, user_id: str) -> dict[str, Any] | None:
    """Load the account (with its profile) by primary key."""
    rows = call(db, FIND_USER_BY_ID, {"p_user_id": user_id})
    return rows[0] if rows else None


def mark_login_success(db: Session, user_id: str) -> None:
    """Record ``last_login_at`` and clear the failed-attempt counter."""
    call(db, MARK_LOGIN_SUCCESS, {"p_user_id": user_id})


def mark_login_failed(
    db: Session,
    user_id: str,
    *,
    max_attempts: int,
    lock_minutes: int,
) -> None:
    """Increment the failure counter and lock the account past the threshold."""
    call(
        db,
        MARK_LOGIN_FAILED,
        {
            "p_user_id": user_id,
            "p_max_attempts": max_attempts,
            "p_lock_minutes": lock_minutes,
        },
    )
