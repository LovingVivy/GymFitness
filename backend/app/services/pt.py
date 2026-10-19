"""Trainer catalogue, PT credit wallet, booking listings and notifications.

The weekly schedule and the session lifecycle live in :mod:`app.services.pt_schedule`.

Business rules live here; every database statement is a stored-procedure call
through :mod:`app.repositories.pt` and :mod:`app.repositories.profile`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import cache
from app.core.config import get_settings, pt_session_price
from app.core.gym_time import local_label
from app.core.payment_code import new_payment_number
from app.db.base import new_uuid
from app.repositories import pt as pt_repository
from app.repositories.procedures import ProcedureOutcome
from app.schemas.pt import (
    NotificationListResponse,
    NotificationResponse,
    PtBookingResponse,
    PtCreditSummary,
    TrainerProfileResponse,
    TrainerSummary,
)

_BOOKING_ERRORS: dict[str, tuple[int, str]] = {
    "MEMBER_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy hồ sơ hội viên."),
    "INVALID_QUANTITY": (status.HTTP_422_UNPROCESSABLE_CONTENT, "Số buổi PT phải từ 1 đến 100."),
    "INTERNAL_ERROR": (status.HTTP_500_INTERNAL_SERVER_ERROR, "Lỗi hệ thống."),
}


def error(status_code: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )


def raise_for_outcome(
    outcome: ProcedureOutcome, mapping: dict[str, tuple[int, str]], fallback: str
) -> None:
    code = outcome.error_code or "INTERNAL_ERROR"
    status_code, default_message = mapping.get(
        code, (status.HTTP_500_INTERNAL_SERVER_ERROR, fallback)
    )
    raise error(status_code, code, outcome.error_message or default_message)


def _split_specialties(value: Any) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _to_trainer_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "employee_code": row["employee_code"],
        "full_name": row.get("full_name"),
        "branch_name": row.get("branch_name"),
        "bio": row.get("bio"),
        "certifications": row.get("certifications"),
        "hourly_rate": row["hourly_rate"],
        "status": row["status"],
        "specialties": _split_specialties(row.get("specialties")),
        "schedule_weekdays": [int(day) for day in _split_specialties(row.get("schedule_weekdays"))],
    }


# --------------------------------------------------------------------------
# Trainers
# --------------------------------------------------------------------------


def get_my_trainer_profile(db: Session, user_id: str) -> TrainerProfileResponse:
    row = pt_repository.find_trainer_by_user(db, user_id)
    if row is None:
        raise error(
            status.HTTP_403_FORBIDDEN,
            "TRAINER_NOT_FOUND",
            "Tài khoản này không có hồ sơ huấn luyện viên.",
        )
    return TrainerProfileResponse(email=row["email"], **_to_trainer_summary(row))


def list_trainers(db: Session, activity_type: str | None = None) -> list[TrainerSummary]:
    normalised = activity_type.strip().upper() if activity_type else None
    if normalised not in (None, "GYM", "YOGA"):
        raise error(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "INVALID_ACTIVITY", "Loại hình không hợp lệ."
        )
    return cache.get_or_load(
        cache.CATALOG,
        f"trainers:{normalised or 'ALL'}",
        get_settings().cache_catalog_ttl_seconds,
        lambda: [
            TrainerSummary(**_to_trainer_summary(row))
            for row in pt_repository.list_trainers(db, normalised)
        ],
        list[TrainerSummary],
    )


def list_bookable_trainers(db: Session, user_id: str) -> list[TrainerSummary]:
    """Trainers this member may book: specialty matches an active plan (ADR-018)."""
    return [
        TrainerSummary(**_to_trainer_summary(row))
        for row in pt_repository.list_trainers(db, member_user_id=user_id)
    ]


def require_trainer_id(db: Session, user_id: str) -> str:
    row = pt_repository.find_trainer_by_user(db, user_id)
    if row is None:
        raise error(
            status.HTTP_403_FORBIDDEN,
            "TRAINER_NOT_FOUND",
            "Tài khoản này không có hồ sơ huấn luyện viên.",
        )
    return row["id"]


# --------------------------------------------------------------------------
# PT credits
# --------------------------------------------------------------------------


def get_pt_credit(db: Session, user_id: str) -> PtCreditSummary:
    row = pt_repository.get_pt_credit(db, user_id) or {}
    return PtCreditSummary(
        credit_account_id=row.get("credit_account_id"),
        purchased=int(row.get("purchased") or 0),
        reserved=int(row.get("reserved") or 0),
        used=int(row.get("used") or 0),
        available=int(row.get("available") or 0),
    )


def purchase_pt_credit(db: Session, user_id: str, quantity: int) -> dict[str, Any]:
    """Create a pending payment for a PT session bundle."""
    purchase_id = new_uuid()
    payment_id = new_uuid()
    payment_number = new_payment_number()

    unit_price = pt_session_price()
    outcome = pt_repository.create_pt_credit_purchase(
        db,
        purchase_id=purchase_id,
        payment_id=payment_id,
        payment_number=payment_number,
        idempotency_key=f"ptcredit-{purchase_id}",
        user_id=user_id,
        quantity=quantity,
        unit_price=unit_price,
    )
    if not outcome.succeeded:
        raise_for_outcome(outcome, _BOOKING_ERRORS, "Không thể tạo giao dịch mua lượt PT.")

    return {
        "payment_id": payment_id,
        "payment_number": payment_number,
        "purchase_id": purchase_id,
        "quantity": quantity,
        "unit_price": unit_price,
        "amount": outcome.data.get("amount"),
        "status": "PENDING",
    }


# --------------------------------------------------------------------------
# PT bookings
# --------------------------------------------------------------------------


def _to_booking(row: Mapping[str, Any]) -> PtBookingResponse:
    return PtBookingResponse(
        id=row["id"],
        booking_number=row["booking_number"],
        status=row["status"],
        activity_type=row["activity_type"],
        start_at=row["start_at"],
        end_at=row["end_at"],
        requested_at=row.get("requested_at"),
        responded_at=row.get("responded_at"),
        response_due_at=row.get("response_due_at"),
        rejection_reason=row.get("rejection_reason"),
        cancellation_reason=row.get("cancellation_reason"),
        cancelled_at=row.get("cancelled_at"),
        cancelled_by_role=row.get("cancelled_by_role"),
        completed_at=row.get("completed_at"),
        notes=row.get("notes"),
        local_label=local_label(row["start_at"]),
        refund_deadline=(
            row["start_at"] - timedelta(hours=get_settings().pt_cancel_refund_hours)
            if row["status"] in ("REQUESTED", "ACCEPTED")
            else None
        ),
        trainer_id=row["trainer_id"],
        trainer_name=row.get("trainer_name"),
        employee_code=row.get("employee_code"),
        hourly_rate=row.get("hourly_rate"),
        member_name=row.get("member_name"),
        member_phone=row.get("member_phone"),
        member_email=row.get("member_email"),
        member_code=row.get("member_code"),
    )


def list_my_bookings(db: Session, user_id: str) -> list[PtBookingResponse]:
    return [_to_booking(row) for row in pt_repository.list_bookings_for_member(db, user_id)]


def list_trainer_bookings(
    db: Session, user_id: str, booking_status: str | None = None
) -> list[PtBookingResponse]:
    rows = pt_repository.list_bookings_for_trainer(db, user_id, booking_status)
    return [_to_booking(row) for row in rows]


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------


def _parse_json_column(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def list_notifications(db: Session, user_id: str, limit: int = 30) -> NotificationListResponse:
    items = [
        NotificationResponse(
            id=row["id"],
            notification_type=row["notification_type"],
            title=row["title"],
            body=row["body"],
            data=_parse_json_column(row.get("data")),
            action_url=row.get("action_url"),
            read_at=row.get("read_at"),
            created_at=row["created_at"],
        )
        for row in pt_repository.list_notifications(db, user_id, limit)
    ]
    return NotificationListResponse(items=items, unread=pt_repository.unread_count(db, user_id))


def unread_notifications(db: Session, user_id: str) -> int:
    return pt_repository.unread_count(db, user_id)


def mark_notification_read(
    db: Session, user_id: str, notification_id: str
) -> NotificationListResponse:
    pt_repository.mark_notification_read(db, user_id=user_id, notification_id=notification_id)
    return list_notifications(db, user_id)


def mark_all_notifications_read(db: Session, user_id: str) -> NotificationListResponse:
    pt_repository.mark_all_notifications_read(db, user_id)
    return list_notifications(db, user_id)
