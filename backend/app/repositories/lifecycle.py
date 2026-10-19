"""Periodic lifecycle procedures (``database/12_lifecycle.sql``)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.repositories.procedures import call

EXPIRE_DUE = "sp_subscription_expire_due"
REMINDERS_DUE = "sp_subscription_reminders_due"
AUTOCLOSE = "sp_pt_session_autoclose"
MEMBERSHIPS = "sp_profile_memberships"


def expire_due(db: Session) -> list[dict[str, Any]]:
    """Mark overdue subscriptions EXPIRED; return those not renewed (for email)."""
    return call(db, EXPIRE_DUE, {})


def reminders_due(db: Session) -> list[dict[str, Any]]:
    """Create the 7/3/1-day renewal reminders that are due; return the new ones."""
    return [row for row in call(db, REMINDERS_DUE, {}) if row.get("subscription_id")]


def autoclose_sessions(db: Session, *, grace_minutes: int, utc_offset_minutes: int) -> int:
    rows = call(
        db,
        AUTOCLOSE,
        {"p_grace_minutes": grace_minutes, "p_utc_offset_minutes": utc_offset_minutes},
    )
    return int(rows[0]["closed"]) if rows else 0


def memberships(db: Session, user_id: str) -> list[dict[str, Any]]:
    """Every subscription still running, one row per activity (end of the renewal chain)."""
    return call(db, MEMBERSHIPS, {"p_user_id": user_id})
