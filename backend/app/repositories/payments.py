"""Data access for payment checkout, webhook events and confirmation.

All SQL lives in ``database/06_procedures_payment.sql``; the procedures that
actually grant benefits stay with their domain
(``sp_subscription_mark_paid``, ``sp_pt_credit_purchase_mark_paid``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.procedures import call

GET_FOR_USER = "sp_payment_get_for_user"
FIND_BY_NUMBER = "sp_payment_find_by_number"
RECORD_EVENT = "sp_payment_event_record"
FINISH_EVENT = "sp_payment_event_finish"
NOTIFY_PAID = "sp_payment_notify_paid"


@dataclass(frozen=True)
class RecordedEvent:
    event_id: str
    duplicate: bool
    already_processed: bool


def get_payment_for_user(db: Session, payment_id: str, user_id: str) -> dict[str, Any] | None:
    """The payment, only if it belongs to ``user_id``."""
    rows = call(db, GET_FOR_USER, {"p_payment_id": payment_id, "p_user_id": user_id})
    return rows[0] if rows else None


def find_by_number(db: Session, payment_number: str) -> dict[str, Any] | None:
    rows = call(db, FIND_BY_NUMBER, {"p_payment_number": payment_number})
    return rows[0] if rows else None


def record_event(
    db: Session,
    *,
    event_id: str,
    provider: str,
    provider_event_id: str,
    event_type: str,
    signature_valid: bool,
    payload: dict[str, Any],
) -> RecordedEvent:
    rows = call(
        db,
        RECORD_EVENT,
        {
            "p_event_id": event_id,
            "p_provider": provider,
            "p_provider_event_id": provider_event_id,
            "p_event_type": event_type,
            "p_signature_valid": signature_valid,
            "p_payload": json.dumps(payload, ensure_ascii=False, default=str),
        },
    )
    row = rows[0] if rows else {}
    return RecordedEvent(
        event_id=row.get("event_id") or event_id,
        duplicate=bool(row.get("duplicate")),
        already_processed=row.get("processed_at") is not None,
    )


def finish_event(
    db: Session,
    *,
    event_id: str,
    payment_id: str | None,
    error_message: str | None,
    provider: str,
    external_reference: str | None,
) -> None:
    call(
        db,
        FINISH_EVENT,
        {
            "p_event_id": event_id,
            "p_payment_id": payment_id,
            "p_error_message": error_message,
            "p_provider": provider,
            "p_external_reference": external_reference,
        },
    )


def notify_paid(db: Session, payment_id: str) -> None:
    call(db, NOTIFY_PAID, {"p_payment_id": payment_id})
