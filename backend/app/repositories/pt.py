"""Data access for trainers, weekly schedules, PT sessions, PT credits and notifications.

All SQL lives in ``database/05_procedures_pt.sql`` and ``database/07_pt_schedule.sql``;
this module only invokes it.
"""

from __future__ import annotations

import json
from datetime import datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.procedures import ProcedureOutcome, call, outcome_from

FIND_TRAINER_BY_USER = "sp_trainer_find_by_user"
LIST_TRAINERS = "sp_trainer_list"
GET_SCHEDULE = "sp_trainer_schedule_get"
REPLACE_SCHEDULE = "sp_trainer_schedule_replace"
LIST_TIME_OFF = "sp_trainer_time_off_list"
CREATE_TIME_OFF = "sp_trainer_time_off_create"
DELETE_TIME_OFF = "sp_trainer_time_off_delete"
LIST_BUSY = "sp_trainer_busy_list"

GET_PT_CREDIT = "sp_pt_credit_get"
CREATE_PT_CREDIT_PURCHASE = "sp_pt_credit_purchase_create"
MARK_PT_CREDIT_PAID = "sp_pt_credit_purchase_mark_paid"

GET_PAYMENT = "sp_payment_get"

BOOK_SESSION = "sp_pt_session_book"
CANCEL_SESSION = "sp_pt_session_cancel"
FINISH_SESSION = "sp_pt_session_finish"
LIST_BOOKINGS_FOR_TRAINER = "sp_pt_booking_list_for_trainer"
LIST_BOOKINGS_FOR_MEMBER = "sp_pt_booking_list_for_member"

LIST_NOTIFICATIONS = "sp_notification_list"
UNREAD_COUNT = "sp_notification_unread_count"
MARK_NOTIFICATION_READ = "sp_notification_mark_read"
MARK_ALL_NOTIFICATIONS_READ = "sp_notification_mark_all_read"


# --------------------------------------------------------------------------
# Trainers
# --------------------------------------------------------------------------


def find_trainer_by_user(db: Session, user_id: str) -> dict[str, Any] | None:
    rows = call(db, FIND_TRAINER_BY_USER, {"p_user_id": user_id})
    return rows[0] if rows else None


def list_trainers(
    db: Session, activity_type: str | None = None, member_user_id: str | None = None
) -> list[dict[str, Any]]:
    return call(
        db,
        LIST_TRAINERS,
        {"p_activity_type": activity_type, "p_member_user_id": member_user_id},
    )


# --------------------------------------------------------------------------
# Weekly schedule and time off
# --------------------------------------------------------------------------


def get_schedule(db: Session, trainer_id: str) -> list[dict[str, Any]]:
    """Weekly blocks with ``start_time``/``end_time`` already as ``HH:MM``."""
    return call(db, GET_SCHEDULE, {"p_trainer_id": trainer_id})


def replace_schedule(
    db: Session, *, user_id: str, weekly: list[dict[str, Any]]
) -> ProcedureOutcome:
    rows = call(
        db,
        REPLACE_SCHEDULE,
        {"p_user_id": user_id, "p_schedule": json.dumps(weekly)},
    )
    return outcome_from(rows, "trainer_id", "slot_count")


def list_time_off(
    db: Session, trainer_id: str, start_from: datetime, start_to: datetime | None = None
) -> list[dict[str, Any]]:
    return call(
        db, LIST_TIME_OFF, {"p_trainer_id": trainer_id, "p_from": start_from, "p_to": start_to}
    )


def create_time_off(
    db: Session,
    *,
    time_off_id: str,
    user_id: str,
    start_at: datetime,
    end_at: datetime,
    reason: str | None,
) -> ProcedureOutcome:
    rows = call(
        db,
        CREATE_TIME_OFF,
        {
            "p_time_off_id": time_off_id,
            "p_user_id": user_id,
            "p_start_at": start_at,
            "p_end_at": end_at,
            "p_reason": reason,
        },
    )
    return outcome_from(rows, "time_off_id", "trainer_id")


def delete_time_off(db: Session, *, time_off_id: str, user_id: str) -> ProcedureOutcome:
    rows = call(db, DELETE_TIME_OFF, {"p_time_off_id": time_off_id, "p_user_id": user_id})
    return outcome_from(rows)


def list_busy(
    db: Session, trainer_id: str, start_from: datetime, start_to: datetime
) -> list[dict[str, Any]]:
    """Start/end of the trainer's held sessions — no member details."""
    return call(db, LIST_BUSY, {"p_trainer_id": trainer_id, "p_from": start_from, "p_to": start_to})


# --------------------------------------------------------------------------
# PT credits
# --------------------------------------------------------------------------


def get_pt_credit(db: Session, user_id: str) -> dict[str, Any] | None:
    rows = call(db, GET_PT_CREDIT, {"p_user_id": user_id})
    return rows[0] if rows else None


def create_pt_credit_purchase(
    db: Session,
    *,
    purchase_id: str,
    payment_id: str,
    payment_number: str,
    idempotency_key: str,
    user_id: str,
    quantity: int,
    unit_price: Decimal,
) -> ProcedureOutcome:
    rows = call(
        db,
        CREATE_PT_CREDIT_PURCHASE,
        {
            "p_purchase_id": purchase_id,
            "p_payment_id": payment_id,
            "p_payment_number": payment_number,
            "p_idempotency_key": idempotency_key,
            "p_user_id": user_id,
            "p_quantity": quantity,
            "p_unit_price": unit_price,
        },
    )
    return outcome_from(rows, "payment_id", "purchase_id", "amount")


def mark_pt_credit_paid(
    db: Session, *, payment_id: str, changed_by: str | None
) -> ProcedureOutcome:
    rows = call(
        db,
        MARK_PT_CREDIT_PAID,
        {"p_payment_id": payment_id, "p_changed_by": changed_by},
    )
    return outcome_from(rows, "credit_account_id")


# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------


def get_payment(db: Session, payment_id: str) -> dict[str, Any] | None:
    rows = call(db, GET_PAYMENT, {"p_payment_id": payment_id})
    return rows[0] if rows else None


# --------------------------------------------------------------------------
# PT bookings
# --------------------------------------------------------------------------


def book_session(
    db: Session,
    *,
    booking_id: str,
    booking_number: str,
    user_id: str,
    trainer_id: str,
    start_at: datetime,
    end_at: datetime,
    local_weekday: int,
    local_start: time,
    local_end: time,
    local_label: str,
    notes: str | None,
) -> ProcedureOutcome:
    rows = call(
        db,
        BOOK_SESSION,
        {
            "p_booking_id": booking_id,
            "p_booking_number": booking_number,
            "p_user_id": user_id,
            "p_trainer_id": trainer_id,
            "p_start_at": start_at,
            "p_end_at": end_at,
            "p_local_weekday": local_weekday,
            "p_local_start": local_start,
            "p_local_end": local_end,
            "p_local_label": local_label,
            "p_notes": notes,
        },
    )
    return outcome_from(rows, "booking_id")


def cancel_session(
    db: Session,
    *,
    booking_id: str,
    user_id: str,
    reason: str | None,
    refund_minutes: int,
    utc_offset_minutes: int,
) -> ProcedureOutcome:
    rows = call(
        db,
        CANCEL_SESSION,
        {
            "p_booking_id": booking_id,
            "p_user_id": user_id,
            "p_reason": reason,
            "p_refund_minutes": refund_minutes,
            "p_utc_offset_minutes": utc_offset_minutes,
        },
    )
    return outcome_from(rows, "booking_id", "refunded", "cancelled_by_role")


def finish_session(
    db: Session, *, booking_id: str, user_id: str, outcome: str, utc_offset_minutes: int
) -> ProcedureOutcome:
    rows = call(
        db,
        FINISH_SESSION,
        {
            "p_booking_id": booking_id,
            "p_user_id": user_id,
            "p_outcome": outcome,
            "p_utc_offset_minutes": utc_offset_minutes,
        },
    )
    return outcome_from(rows, "booking_id")


def list_bookings_for_trainer(
    db: Session, user_id: str, status: str | None = None
) -> list[dict[str, Any]]:
    return call(db, LIST_BOOKINGS_FOR_TRAINER, {"p_user_id": user_id, "p_status": status})


def list_bookings_for_member(db: Session, user_id: str) -> list[dict[str, Any]]:
    return call(db, LIST_BOOKINGS_FOR_MEMBER, {"p_user_id": user_id})


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------


def list_notifications(db: Session, user_id: str, limit: int = 30) -> list[dict[str, Any]]:
    return call(db, LIST_NOTIFICATIONS, {"p_user_id": user_id, "p_limit": limit})


def unread_count(db: Session, user_id: str) -> int:
    rows = call(db, UNREAD_COUNT, {"p_user_id": user_id})
    if not rows:
        return 0
    return int(rows[0].get("unread") or 0)


def mark_notification_read(db: Session, *, user_id: str, notification_id: str) -> int:
    rows = call(
        db, MARK_NOTIFICATION_READ, {"p_user_id": user_id, "p_notification_id": notification_id}
    )
    return int(rows[0].get("updated") or 0) if rows else 0


def mark_all_notifications_read(db: Session, user_id: str) -> int:
    rows = call(db, MARK_ALL_NOTIFICATIONS_READ, {"p_user_id": user_id})
    return int(rows[0].get("updated") or 0) if rows else 0


def booking_contact(db: Session, booking_id: str) -> dict[str, Any] | None:
    """Member and trainer contact details of one booking, for emails."""
    rows = call(db, "sp_pt_booking_contact", {"p_booking_id": booking_id})
    return rows[0] if rows else None
