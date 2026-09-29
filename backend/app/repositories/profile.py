"""Data access for member profile, membership plans, subscriptions and files.

As with the auth repository, all SQL lives in stored procedures
(``database/03_procedures.sql``) and this module only invokes them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.procedures import INTERNAL_ERROR, ProcedureOutcome, call, outcome_from

GET_PROFILE = "sp_profile_get"
UPDATE_PROFILE = "sp_profile_update"
LIST_PLANS = "sp_plan_list_active"
FIND_PLAN = "sp_plan_find_by_id"
CREATE_SUBSCRIPTION = "sp_subscription_create"
MARK_SUBSCRIPTION_PAID = "sp_subscription_mark_paid"
SAVE_AVATAR = "sp_file_save_avatar"
GET_FILE = "sp_file_get"


def get_profile(db: Session, user_id: str) -> dict[str, Any] | None:
    """Full profile row: account, profile, avatar, member and active plan."""
    rows = call(db, GET_PROFILE, {"p_user_id": user_id})
    return rows[0] if rows else None


def update_profile(
    db: Session,
    *,
    user_id: str,
    full_name: str | None = None,
    phone: str | None = None,
    date_of_birth: date | None = None,
    gender: str | None = None,
    height_cm: Decimal | None = None,
    weight_kg: Decimal | None = None,
    experience_level: str | None = None,
    fitness_goal: str | None = None,
    weekly_training_sessions: int | None = None,
    emergency_contact_name: str | None = None,
    emergency_contact_phone: str | None = None,
) -> ProcedureOutcome:
    rows = call(
        db,
        UPDATE_PROFILE,
        {
            "p_user_id": user_id,
            "p_full_name": full_name,
            "p_phone": phone,
            "p_date_of_birth": date_of_birth,
            "p_gender": gender,
            "p_height_cm": height_cm,
            "p_weight_kg": weight_kg,
            "p_experience_level": experience_level,
            "p_fitness_goal": fitness_goal,
            "p_weekly_training_sessions": weekly_training_sessions,
            "p_emergency_contact_name": emergency_contact_name,
            "p_emergency_contact_phone": emergency_contact_phone,
        },
    )
    return outcome_from(rows)


def list_active_plans(db: Session) -> list[dict[str, Any]]:
    return call(db, LIST_PLANS, {})


def find_plan(db: Session, plan_id: str) -> dict[str, Any] | None:
    rows = call(db, FIND_PLAN, {"p_plan_id": plan_id})
    return rows[0] if rows else None


def create_subscription(
    db: Session,
    *,
    subscription_id: str,
    payment_id: str,
    payment_number: str,
    idempotency_key: str,
    member_id: str,
    plan_id: str,
    created_by: str | None,
    pt_purchase_id: str | None = None,
    pt_quantity: int = 0,
    pt_unit_price: Decimal | None = None,
) -> ProcedureOutcome:
    rows = call(
        db,
        CREATE_SUBSCRIPTION,
        {
            "p_subscription_id": subscription_id,
            "p_payment_id": payment_id,
            "p_payment_number": payment_number,
            "p_idempotency_key": idempotency_key,
            "p_member_id": member_id,
            "p_plan_id": plan_id,
            "p_created_by": created_by,
            "p_pt_purchase_id": pt_purchase_id,
            "p_pt_quantity": pt_quantity,
            "p_pt_unit_price": pt_unit_price,
        },
    )
    return outcome_from(rows, "subscription_id", "payment_id", "amount")


def mark_subscription_paid(
    db: Session, *, payment_id: str, changed_by: str | None
) -> ProcedureOutcome:
    rows = call(
        db,
        MARK_SUBSCRIPTION_PAID,
        {"p_payment_id": payment_id, "p_changed_by": changed_by},
    )
    return outcome_from(rows, "subscription_id", "end_at")


def save_avatar(
    db: Session,
    *,
    file_id: str,
    user_id: str,
    storage_key: str,
    original_name: str,
    content_type: str,
    size_bytes: int,
    checksum_sha256: str,
) -> ProcedureOutcome:
    rows = call(
        db,
        SAVE_AVATAR,
        {
            "p_file_id": file_id,
            "p_user_id": user_id,
            "p_storage_key": storage_key,
            "p_original_name": original_name,
            "p_content_type": content_type,
            "p_size_bytes": size_bytes,
            "p_checksum_sha256": checksum_sha256,
        },
    )
    return outcome_from(rows, "file_id", "old_storage_key")


def get_file(db: Session, file_id: str) -> dict[str, Any] | None:
    rows = call(db, GET_FILE, {"p_file_id": file_id})
    return rows[0] if rows else None


__all__ = [
    "INTERNAL_ERROR",
    "ProcedureOutcome",
    "create_subscription",
    "find_plan",
    "get_file",
    "get_profile",
    "list_active_plans",
    "mark_subscription_paid",
    "save_avatar",
    "update_profile",
]
