"""Data access for the admin area. All SQL lives in ``database/08_admin.sql``."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.procedures import ProcedureOutcome, call, outcome_from

BOOTSTRAP = "sp_admin_bootstrap"
OVERVIEW = "sp_admin_overview"
LIST_USERS = "sp_admin_user_list"
CREATE_USER = "sp_admin_user_create"
UPDATE_USER = "sp_admin_user_update"
SET_PASSWORD = "sp_admin_user_set_password"
DELETE_USER = "sp_admin_user_delete"
LIST_PLANS = "sp_admin_plan_list"
SAVE_PLAN = "sp_admin_plan_save"
DELETE_PLAN = "sp_admin_plan_delete"
LIST_CHECKINS = "sp_admin_checkin_list"
CREATE_CHECKIN = "sp_admin_checkin_create"
CHECKOUT = "sp_admin_checkout"
REVENUE = "sp_admin_revenue"
MEMBER_BASE = "sp_admin_member_base"
MEMBER_GROWTH = "sp_admin_member_growth"
LIST_PAYMENTS = "sp_admin_payment_list"
CONFIRM_PAYMENT_LOG = "sp_admin_payment_confirm_log"
VOID_PAYMENT = "sp_admin_payment_void"
LIST_AUDIT_LOGS = "sp_audit_log_list"


def _json_or_none(value: list[str] | None) -> str | None:
    return None if value is None else json.dumps(value)


def bootstrap(
    db: Session,
    *,
    user_id: str,
    username: str,
    email: str,
    password_hash: str,
    full_name: str,
) -> bool:
    rows = call(
        db,
        BOOTSTRAP,
        {
            "p_user_id": user_id,
            "p_username": username,
            "p_email": email,
            "p_password_hash": password_hash,
            "p_full_name": full_name,
        },
    )
    return bool(rows and rows[0].get("created"))


def overview(
    db: Session, *, day_start: datetime, month_start: datetime, prev_month_start: datetime
) -> dict[str, Any]:
    rows = call(
        db,
        OVERVIEW,
        {
            "p_day_start": day_start,
            "p_month_start": month_start,
            "p_prev_month_start": prev_month_start,
        },
    )
    return rows[0] if rows else {}


def list_users(
    db: Session,
    *,
    user_id: str | None = None,
    search: str | None,
    role: str | None,
    status: str | None,
    sort: str | None = None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    return call(
        db,
        LIST_USERS,
        {
            "p_user_id": user_id,
            "p_search": search,
            "p_role": role,
            "p_status": status,
            "p_sort": sort,
            "p_limit": limit,
            "p_offset": offset,
        },
    )


def create_user(
    db: Session,
    *,
    user_id: str,
    profile_id: str,
    email: str,
    username: str | None,
    phone: str | None,
    password_hash: str,
    full_name: str,
    role: str,
    hourly_rate: Decimal | None,
    bio: str | None,
    specialties: list[str],
    actor_id: str,
) -> ProcedureOutcome:
    rows = call(
        db,
        CREATE_USER,
        {
            "p_user_id": user_id,
            "p_profile_id": profile_id,
            "p_email": email,
            "p_username": username,
            "p_phone": phone,
            "p_password_hash": password_hash,
            "p_full_name": full_name,
            "p_role": role,
            "p_hourly_rate": hourly_rate,
            "p_bio": bio,
            "p_specialties": json.dumps(specialties),
            "p_actor_id": actor_id,
        },
    )
    return outcome_from(rows, "user_id")


def update_user(
    db: Session,
    *,
    user_id: str,
    email: str | None,
    username: str | None,
    phone: str | None,
    full_name: str | None,
    status: str | None,
    hourly_rate: Decimal | None,
    bio: str | None,
    specialties: list[str] | None,
    actor_id: str,
    utc_offset_minutes: int = 420,
) -> ProcedureOutcome:
    rows = call(
        db,
        UPDATE_USER,
        {
            "p_user_id": user_id,
            "p_email": email,
            "p_username": username,
            "p_phone": phone,
            "p_full_name": full_name,
            "p_status": status,
            "p_hourly_rate": hourly_rate,
            "p_bio": bio,
            "p_specialties": _json_or_none(specialties),
            "p_actor_id": actor_id,
            "p_utc_offset_minutes": utc_offset_minutes,
        },
    )
    return outcome_from(rows, "user_id", "cancelled_sessions")


def set_password(
    db: Session, *, user_id: str, password_hash: str, actor_id: str
) -> ProcedureOutcome:
    rows = call(
        db,
        SET_PASSWORD,
        {"p_user_id": user_id, "p_password_hash": password_hash, "p_actor_id": actor_id},
    )
    return outcome_from(rows)


def delete_user(db: Session, *, user_id: str, actor_id: str) -> ProcedureOutcome:
    rows = call(db, DELETE_USER, {"p_user_id": user_id, "p_actor_id": actor_id})
    return outcome_from(rows, "user_id")


def list_plans(db: Session) -> list[dict[str, Any]]:
    return call(db, LIST_PLANS, {})


def save_plan(
    db: Session,
    *,
    plan_id: str,
    is_new: bool,
    code: str,
    name: str,
    activity_type: str,
    description: str | None,
    duration_months: int | None,
    duration_days: int | None,
    price: Decimal,
    is_active: bool,
    expected_version: int | None = None,
    actor_id: str,
) -> ProcedureOutcome:
    rows = call(
        db,
        SAVE_PLAN,
        {
            "p_plan_id": plan_id,
            "p_is_new": is_new,
            "p_code": code,
            "p_name": name,
            "p_activity_type": activity_type,
            "p_description": description,
            "p_duration_months": duration_months,
            "p_duration_days": duration_days,
            "p_price": price,
            "p_is_active": is_active,
            "p_expected_version": expected_version,
            "p_actor_id": actor_id,
        },
    )
    return outcome_from(rows, "plan_id")


def delete_plan(db: Session, *, plan_id: str, actor_id: str) -> ProcedureOutcome:
    rows = call(db, DELETE_PLAN, {"p_plan_id": plan_id, "p_actor_id": actor_id})
    return outcome_from(rows)


def list_checkins(
    db: Session,
    *,
    start_from: datetime,
    start_to: datetime,
    search: str | None,
    inside_only: bool,
    sort: str | None = None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    return call(
        db,
        LIST_CHECKINS,
        {
            "p_from": start_from,
            "p_to": start_to,
            "p_search": search,
            "p_inside_only": inside_only,
            "p_sort": sort,
            "p_limit": limit,
            "p_offset": offset,
        },
    )


def create_checkin(
    db: Session, *, checkin_id: str, identifier: str, actor_id: str
) -> ProcedureOutcome:
    rows = call(
        db,
        CREATE_CHECKIN,
        {"p_checkin_id": checkin_id, "p_identifier": identifier, "p_actor_id": actor_id},
    )
    return outcome_from(rows, "checkin_id", "member_name")


def checkout(db: Session, *, checkin_id: str, actor_id: str) -> ProcedureOutcome:
    rows = call(db, CHECKOUT, {"p_checkin_id": checkin_id, "p_actor_id": actor_id})
    return outcome_from(rows)


def revenue(
    db: Session, *, start_from: datetime, start_to: datetime, period: str, offset_minutes: int
) -> list[dict[str, Any]]:
    return call(
        db,
        REVENUE,
        {
            "p_from": start_from,
            "p_to": start_to,
            "p_period": period,
            "p_offset_minutes": offset_minutes,
        },
    )


def member_base(db: Session, *, before: datetime) -> int:
    rows = call(db, MEMBER_BASE, {"p_before": before})
    return int(rows[0]["members"]) if rows else 0


def member_growth(
    db: Session, *, start_from: datetime, start_to: datetime, period: str, offset_minutes: int
) -> list[dict[str, Any]]:
    return call(
        db,
        MEMBER_GROWTH,
        {
            "p_from": start_from,
            "p_to": start_to,
            "p_period": period,
            "p_offset_minutes": offset_minutes,
        },
    )


def list_payments(
    db: Session,
    *,
    payment_id: str | None = None,
    search: str | None,
    status: str | None,
    purpose: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    sort: str | None = None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    return call(
        db,
        LIST_PAYMENTS,
        {
            "p_payment_id": payment_id,
            "p_search": search,
            "p_status": status,
            "p_purpose": purpose,
            "p_from": created_from,
            "p_to": created_to,
            "p_sort": sort,
            "p_limit": limit,
            "p_offset": offset,
        },
    )


def log_payment_confirm(
    db: Session, *, payment_id: str, method: str | None, actor_id: str
) -> ProcedureOutcome:
    rows = call(
        db,
        CONFIRM_PAYMENT_LOG,
        {"p_payment_id": payment_id, "p_method": method, "p_actor_id": actor_id},
    )
    return outcome_from(rows)


def void_payment(
    db: Session, *, payment_id: str, reason: str | None, actor_id: str
) -> ProcedureOutcome:
    rows = call(
        db,
        VOID_PAYMENT,
        {"p_payment_id": payment_id, "p_reason": reason, "p_actor_id": actor_id},
    )
    return outcome_from(rows)


def list_audit_logs(
    db: Session,
    *,
    entity_type: str | None,
    entity_id: str | None,
    action: str | None,
    search: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    return call(
        db,
        LIST_AUDIT_LOGS,
        {
            "p_entity_type": entity_type,
            "p_entity_id": entity_id,
            "p_action": action,
            "p_search": search,
            "p_from": created_from,
            "p_to": created_to,
            "p_limit": limit,
            "p_offset": offset,
        },
    )
