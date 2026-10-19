"""Periodic upkeep: expire subscriptions, send renewal reminders, close stale PT sessions.

Every step is an idempotent stored procedure, so running it from several
processes at once (API and worker) is harmless. The worker runs it on its
loop; the API runs it in a background thread when ``MAINTENANCE_IN_API`` is on
(the default, for setups without a worker).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from app.core import cache
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories import lifecycle as lifecycle_repository
from app.tasks import queue

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None


@dataclass
class MaintenanceResult:
    expired: int = 0
    reminders: int = 0
    closed_sessions: int = 0


def run_once() -> MaintenanceResult:
    settings = get_settings()
    result = MaintenanceResult()
    with SessionLocal() as db:
        expired = lifecycle_repository.expire_due(db)
        for row in expired:
            queue.enqueue(
                db,
                "email.membership_expired",
                {
                    "email": row["email"],
                    "full_name": row.get("full_name"),
                    "plan_name": row["plan_name"],
                    "end_at": row["end_at"].isoformat(),
                },
            )
        result.expired = len(expired)

        reminders = lifecycle_repository.reminders_due(db)
        for row in reminders:
            queue.enqueue(
                db,
                "email.membership_expiring",
                {
                    "email": row["email"],
                    "full_name": row.get("full_name"),
                    "plan_name": row["plan_name"],
                    "end_at": row["end_at"].isoformat(),
                    "days_left": int(row["days_left"]),
                },
            )
        result.reminders = len(reminders)

        result.closed_sessions = lifecycle_repository.autoclose_sessions(
            db,
            grace_minutes=settings.pt_autoclose_hours * 60,
            utc_offset_minutes=settings.gym_utc_offset_minutes,
        )

    if result.expired:
        # Số hội viên còn gói trên trang quản trị đổi theo.
        cache.invalidate(cache.REPORTS)
    if result.expired or result.reminders or result.closed_sessions:
        logger.info(
            "Bảo trì định kỳ",
            extra={
                "expired": result.expired,
                "reminders": result.reminders,
                "closed_sessions": result.closed_sessions,
            },
        )
    return result


def _loop(interval: int) -> None:
    while not _stop.wait(interval):
        try:
            run_once()
        except Exception:  # noqa: BLE001 - lần sau chạy lại, không làm sập API
            logger.exception("Bảo trì định kỳ thất bại.")


def start_background() -> None:
    """Start the API-side maintenance thread (first run after one interval)."""
    global _thread
    settings = get_settings()
    if not settings.maintenance_in_api or (_thread and _thread.is_alive()):
        return
    _stop.clear()
    _thread = threading.Thread(
        target=_loop,
        args=(settings.maintenance_interval_seconds,),
        name="gf-maintenance",
        daemon=True,
    )
    _thread.start()


def stop_background() -> None:
    _stop.set()
