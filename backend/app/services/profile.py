"""Member profile service: profile read/update, plans, subscriptions and avatar.

Like the auth service, this module holds business rules only. Every database
statement is a stored-procedure call through :mod:`app.repositories.profile`.
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import cache, storage
from app.core.config import get_settings, pt_session_price
from app.core.gym_time import now_utc, to_local
from app.core.payment_code import new_payment_number
from app.core.permissions import sorted_permissions
from app.db.base import new_uuid
from app.repositories import auth as auth_repository
from app.repositories import lifecycle as lifecycle_repository
from app.repositories import profile as profile_repository
from app.schemas.profile import (
    MembershipSummary,
    PaymentSummary,
    PlanResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    PtCreditsSummary,
    SubscriptionCreateResponse,
)

FILES_PREFIX = "/api/v1/files/"

_UPDATE_ERRORS: dict[str, tuple[int, str]] = {
    "USER_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy tài khoản."),
    "PHONE_EXISTS": (status.HTTP_409_CONFLICT, "Số điện thoại này đã được sử dụng."),
    "INTERNAL_ERROR": (status.HTTP_500_INTERNAL_SERVER_ERROR, "Không thể cập nhật hồ sơ."),
}

_SUBSCRIPTION_ERRORS: dict[str, tuple[int, str]] = {
    "MEMBER_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy hồ sơ hội viên."),
    "PLAN_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Gói tập không tồn tại hoặc đã ngừng bán."),
    "INVALID_QUANTITY": (status.HTTP_422_UNPROCESSABLE_CONTENT, "Số buổi PT phải từ 0 đến 100."),
    "INTERNAL_ERROR": (status.HTTP_500_INTERNAL_SERVER_ERROR, "Không thể tạo đăng ký gói."),
}

_PAYMENT_ERRORS: dict[str, tuple[int, str]] = {
    "PAYMENT_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy giao dịch thanh toán."),
    "PAYMENT_NOT_PENDING": (
        status.HTTP_409_CONFLICT,
        "Giao dịch đã được xử lý trước đó.",
    ),
    "INTERNAL_ERROR": (
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Không thể xác nhận thanh toán.",
    ),
}

_AVATAR_ERRORS: dict[str, tuple[int, str]] = {
    "USER_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy hồ sơ người dùng."),
    "INTERNAL_ERROR": (status.HTTP_500_INTERNAL_SERVER_ERROR, "Không thể lưu ảnh đại diện."),
}


def _error(status_code: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )


def _raise_for_outcome(
    outcome: profile_repository.ProcedureOutcome,
    mapping: dict[str, tuple[int, str]],
    fallback_message: str,
) -> None:
    code = outcome.error_code or profile_repository.INTERNAL_ERROR
    status_code, default_message = mapping.get(
        code, (status.HTTP_500_INTERNAL_SERVER_ERROR, fallback_message)
    )
    raise _error(status_code, code, outcome.error_message or default_message)


def _local_days(start: datetime | None, end: datetime | None) -> int | None:
    """Whole gym-local calendar days between two instants (UTC+7, not UTC dates)."""
    if start is None or end is None:
        return None
    return (to_local(end).date() - to_local(start).date()).days


def _membership(
    *,
    subscription_id: str,
    status: str,
    start_at: datetime | None,
    end_at: datetime | None,
    coverage_start_at: datetime | None,
    plan: Mapping[str, Any],
) -> MembershipSummary:
    remaining = _local_days(now_utc(), end_at)
    return MembershipSummary(
        subscription_id=subscription_id,
        status=status,
        plan_id=plan["plan_id"],
        plan_code=plan["plan_code"],
        plan_name=plan["plan_name"],
        activity_type=plan["activity_type"],
        duration_months=plan.get("duration_months"),
        duration_days=plan.get("duration_days"),
        price=plan["price"],
        currency=plan["currency"],
        start_at=start_at,
        end_at=end_at,
        days_remaining=max(0, remaining) if remaining is not None else None,
        # Gia hạn sớm: tổng thời hạn tính từ đầu chuỗi gói nối tiếp.
        total_days=_local_days(coverage_start_at or start_at, end_at),
    )


def _membership_from_row(row: Mapping[str, Any]) -> MembershipSummary | None:
    if row.get("subscription_id") is None or row.get("plan_id") is None:
        return None
    return _membership(
        subscription_id=row["subscription_id"],
        status=row["subscription_status"],
        start_at=row.get("subscription_start_at"),
        end_at=row.get("subscription_end_at"),
        coverage_start_at=row.get("coverage_start_at"),
        plan={
            "plan_id": row["plan_id"],
            "plan_code": row["plan_code"],
            "plan_name": row["plan_name"],
            "activity_type": row["plan_activity_type"],
            "duration_months": row.get("plan_duration_months"),
            "duration_days": row.get("plan_duration_days"),
            "price": row["plan_price"],
            "currency": row["plan_currency"],
        },
    )


def _to_profile(row: Mapping[str, Any]) -> ProfileResponse:
    avatar_file_id = row.get("avatar_file_id")
    return ProfileResponse(
        id=row["id"],
        email=row["email"],
        phone=row.get("phone"),
        role=row["role"],
        status=row["status"],
        full_name=row.get("full_name"),
        avatar_url=f"{FILES_PREFIX}{avatar_file_id}" if avatar_file_id else None,
        date_of_birth=row.get("date_of_birth"),
        gender=row.get("gender"),
        height_cm=float(row["height_cm"]) if row.get("height_cm") is not None else None,
        weight_kg=float(row["weight_kg"]) if row.get("weight_kg") is not None else None,
        experience_level=row.get("experience_level"),
        fitness_goal=row.get("fitness_goal"),
        weekly_training_sessions=row.get("weekly_training_sessions"),
        emergency_contact_name=row.get("emergency_contact_name"),
        emergency_contact_phone=row.get("emergency_contact_phone"),
        member_code=row.get("member_code"),
        member_joined_at=row.get("member_joined_at"),
        home_branch_name=row.get("home_branch_name"),
        membership=_membership_from_row(row),
        pt_credits=PtCreditsSummary(
            purchased=row.get("pt_purchased") or 0,
            reserved=row.get("pt_reserved") or 0,
            used=row.get("pt_used") or 0,
            remaining=row.get("pt_remaining") or 0,
        ),
        created_at=row.get("user_created_at"),
        last_login_at=row.get("last_login_at"),
        permissions=sorted_permissions(row["role"]),
    )


def get_profile(db: Session, user_id: str) -> ProfileResponse:
    row = profile_repository.get_profile(db, user_id)
    if row is None:
        raise _error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "Không tìm thấy tài khoản.")
    profile = _to_profile(row)
    profile.two_factor_enabled = bool(auth_repository.get_two_factor_secret(db, user_id))
    profile.memberships = [
        _membership(
            subscription_id=item["subscription_id"],
            status=item["status"],
            start_at=item.get("start_at"),
            end_at=item.get("end_at"),
            coverage_start_at=item.get("coverage_start_at"),
            plan=item,
        )
        for item in lifecycle_repository.memberships(db, user_id)
    ]
    return profile


def update_profile(db: Session, user_id: str, payload: ProfileUpdateRequest) -> ProfileResponse:
    def as_decimal(value: float | None) -> Decimal | None:
        return None if value is None else Decimal(str(value))

    outcome = profile_repository.update_profile(
        db,
        user_id=user_id,
        full_name=payload.full_name,
        phone=payload.phone,
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        height_cm=as_decimal(payload.height_cm),
        weight_kg=as_decimal(payload.weight_kg),
        experience_level=payload.experience_level,
        fitness_goal=payload.fitness_goal,
        weekly_training_sessions=payload.weekly_training_sessions,
        emergency_contact_name=payload.emergency_contact_name,
        emergency_contact_phone=payload.emergency_contact_phone,
    )
    if not outcome.succeeded:
        _raise_for_outcome(outcome, _UPDATE_ERRORS, "Không thể cập nhật hồ sơ.")

    return get_profile(db, user_id)


_DATA_URL = re.compile(r"^data:(image/[A-Za-z0-9.+-]+);base64,(.+)$", re.DOTALL)


def _decode_data_url(data_url: str) -> tuple[bytes, str]:
    """Split ``data:image/png;base64,...`` into bytes plus content type."""
    match = _DATA_URL.match(data_url.strip())
    if match is None:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_FILE",
            "Ảnh phải ở dạng data URL base64, ví dụ: data:image/png;base64,...",
        )

    content_type = match.group(1).lower()
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_FILE",
            "Nội dung ảnh base64 không hợp lệ.",
        ) from exc

    return content, content_type


def save_avatar(db: Session, user_id: str, *, data_url: str) -> ProfileResponse:
    """Persist the uploaded avatar to local storage and link it to the profile."""
    content, content_type = _decode_data_url(data_url)

    try:
        stored = storage.save_avatar(content, content_type)
    except ValueError as exc:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "INVALID_FILE", str(exc)) from exc

    try:
        outcome = profile_repository.save_avatar(
            db,
            file_id=new_uuid(),
            user_id=user_id,
            storage_key=stored.storage_key,
            original_name=f"avatar{Path(stored.storage_key).suffix}",
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            checksum_sha256=stored.checksum_sha256,
        )
    except Exception:
        storage.delete_file(stored.storage_key)
        raise

    if not outcome.succeeded:
        # Database không nhận metadata thì bytes vừa ghi thành file mồ côi.
        storage.delete_file(stored.storage_key)
        _raise_for_outcome(outcome, _AVATAR_ERRORS, "Không thể lưu ảnh đại diện.")

    # Ảnh cũ đã được soft-delete trong cùng transaction; giờ mới xoá bytes.
    storage.delete_file(outcome.data.get("old_storage_key"))

    return get_profile(db, user_id)


def list_plans(db: Session) -> list[PlanResponse]:
    return cache.get_or_load(
        cache.CATALOG,
        "plans",
        get_settings().cache_catalog_ttl_seconds,
        lambda: [PlanResponse(**row) for row in profile_repository.list_active_plans(db)],
        list[PlanResponse],
    )


def create_subscription(
    db: Session, user: Mapping[str, Any], plan_id: str, pt_sessions: int = 0
) -> SubscriptionCreateResponse:
    """Create a PENDING payment and subscription for the chosen plan.

    ``pt_sessions`` bundles a PT credit purchase into the same payment, so the
    member scans a single QR (ADR-014). Nothing is activated here: per ADR-004
    only a verified backend step may mark a payment as paid.
    """
    row = profile_repository.get_profile(db, user["id"])
    member_id = row.get("member_id") if row else None
    if not member_id:
        raise _error(
            status.HTTP_404_NOT_FOUND, "MEMBER_NOT_FOUND", "Không tìm thấy hồ sơ hội viên."
        )

    plan = profile_repository.find_plan(db, plan_id)
    if plan is None:
        raise _error(
            status.HTTP_404_NOT_FOUND,
            "PLAN_NOT_FOUND",
            "Gói tập không tồn tại hoặc đã ngừng bán.",
        )

    subscription_id = new_uuid()
    payment_id = new_uuid()
    payment_number = new_payment_number()

    outcome = profile_repository.create_subscription(
        db,
        subscription_id=subscription_id,
        payment_id=payment_id,
        payment_number=payment_number,
        idempotency_key=f"sub-{subscription_id}",
        member_id=member_id,
        plan_id=plan["id"],
        created_by=user["id"],
        pt_purchase_id=new_uuid() if pt_sessions else None,
        pt_quantity=pt_sessions,
        pt_unit_price=pt_session_price() if pt_sessions else None,
    )
    if not outcome.succeeded:
        _raise_for_outcome(outcome, _SUBSCRIPTION_ERRORS, "Không thể tạo đăng ký gói.")

    return SubscriptionCreateResponse(
        subscription_id=subscription_id,
        status="PENDING",
        payment=PaymentSummary(
            id=payment_id,
            payment_number=payment_number,
            status="PENDING",
            amount=outcome.data.get("amount") or plan["price"],
            currency=plan["currency"],
            method="QR",
            qr_payload=f"IRONIX|{payment_number}",
        ),
        pt_sessions=pt_sessions,
    )
