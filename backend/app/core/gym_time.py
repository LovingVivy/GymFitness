"""Gym-local time helpers.

The database stores UTC, but a trainer's weekly schedule ("Mon 17:00-21:00")
is wall-clock time at the gym. Vietnam has no daylight saving, so a fixed
offset is exact and avoids depending on the ``tzdata`` package on Windows.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta, timezone

from app.core.config import get_settings

WEEKDAY_LABELS = {1: "T2", 2: "T3", 3: "T4", 4: "T5", 5: "T6", 6: "T7", 7: "CN"}


def gym_tz() -> timezone:
    return timezone(timedelta(minutes=get_settings().gym_utc_offset_minutes))


def now_utc() -> datetime:
    return datetime.now(UTC)


def to_local(value: datetime) -> datetime:
    """Aware or naive-UTC datetime → aware gym-local datetime."""
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return aware.astimezone(gym_tz())


def to_naive_utc(value: datetime) -> datetime:
    """Aware datetime → naive UTC, the shape stored in ``DATETIME`` columns."""
    return value.astimezone(UTC).replace(tzinfo=None)


def parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def minutes_of(value: time) -> int:
    return value.hour * 60 + value.minute


def local_label(value: datetime) -> str:
    """``17:00 30/09/2026`` in gym time, matching the stored-procedure format."""
    return to_local(value).strftime("%H:%M %d/%m/%Y")


def tz_label() -> str:
    offset = get_settings().gym_utc_offset_minutes
    sign = "+" if offset >= 0 else "-"
    hours, minutes = divmod(abs(offset), 60)
    return f"GMT{sign}{hours}" + (f":{minutes:02d}" if minutes else "")
