"""Trainer weekly schedule, bookable slots and the PT session lifecycle (ADR-015).

A trainer declares recurring working hours once ("Mon-Fri 17:00-21:00") plus
ad-hoc time off. Members pick a free fixed-length slot inside those hours and
the booking is confirmed immediately — there is no per-request approval step.

Session lifecycle::

    ACCEPTED ──► COMPLETED   (trainer, after start)      credit consumed
             ├─► NO_SHOW     (trainer, after start)      credit consumed
             ├─► CANCELLED   (trainer, before start)     credit refunded
             └─► CANCELLED   (member,  before start)     refunded if early enough
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.gym_time import (
    gym_tz,
    local_label,
    minutes_of,
    now_utc,
    parse_hhmm,
    to_local,
    to_naive_utc,
    tz_label,
)
from app.db.base import new_uuid
from app.repositories import pt as pt_repository
from app.schemas.pt import (
    BookableSlot,
    PtBookingCreateRequest,
    PtBookingResponse,
    PtCancelResponse,
    ScheduleResponse,
    ScheduleUpdateRequest,
    TimeOffCreateRequest,
    TimeOffItem,
    WeeklyScheduleItem,
)
from app.services.pt import (
    error,
    list_my_bookings,
    list_trainer_bookings,
    raise_for_outcome,
    require_trainer_id,
)

_SCHEDULE_ERRORS: dict[str, tuple[int, str]] = {
    "TRAINER_NOT_FOUND": (status.HTTP_403_FORBIDDEN, "Tài khoản này không phải huấn luyện viên."),
    "INVALID_SCHEDULE": (status.HTTP_422_UNPROCESSABLE_CONTENT, "Lịch làm việc không hợp lệ."),
    "SCHEDULE_OVERLAP": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Các khung giờ trong cùng một ngày đang chồng lấn nhau.",
    ),
    "INVALID_WINDOW": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Thời điểm kết thúc phải sau thời điểm bắt đầu.",
    ),
    "PAST_WINDOW": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Không thể đặt lịch nghỉ trong quá khứ.",
    ),
    "TIME_OFF_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy lịch nghỉ."),
    "INTERNAL_ERROR": (status.HTTP_500_INTERNAL_SERVER_ERROR, "Lỗi hệ thống."),
}

_SESSION_ERRORS: dict[str, tuple[int, str]] = {
    "MEMBER_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy hồ sơ hội viên."),
    "TRAINER_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Huấn luyện viên không khả dụng."),
    "NO_ACTIVE_SUBSCRIPTION": (
        status.HTTP_409_CONFLICT,
        "Cần có gói hội viên còn hiệu lực trong ngày tập để đặt PT.",
    ),
    "OUTSIDE_SCHEDULE": (
        status.HTTP_409_CONFLICT,
        "Giờ này nằm ngoài lịch làm việc của huấn luyện viên.",
    ),
    "TRAINER_OFF": (status.HTTP_409_CONFLICT, "Huấn luyện viên nghỉ vào thời gian này."),
    "SLOT_UNAVAILABLE": (
        status.HTTP_409_CONFLICT,
        "Khung giờ này vừa có người đặt, vui lòng chọn giờ khác.",
    ),
    "MEMBER_BUSY": (status.HTTP_409_CONFLICT, "Bạn đã có một buổi PT khác trùng giờ này."),
    "NO_PT_CREDIT": (status.HTTP_409_CONFLICT, "Bạn chưa có lượt PT khả dụng. Hãy mua thêm buổi."),
    "TOO_SOON": (status.HTTP_422_UNPROCESSABLE_CONTENT, "Buổi tập cần được đặt trước."),
    "TOO_FAR": (status.HTTP_422_UNPROCESSABLE_CONTENT, "Chưa mở đặt lịch cho ngày này."),
    "BOOKING_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy buổi PT."),
    "BOOKING_NOT_ACTIVE": (status.HTTP_409_CONFLICT, "Buổi này đã kết thúc hoặc đã bị huỷ."),
    "SESSION_STARTED": (status.HTTP_409_CONFLICT, "Buổi tập đã bắt đầu, không thể huỷ."),
    "SESSION_NOT_STARTED": (
        status.HTTP_409_CONFLICT,
        "Chỉ chốt được buổi tập khi đã tới giờ bắt đầu.",
    ),
    "REASON_REQUIRED": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Vui lòng nhập lý do huỷ để thông báo cho hội viên.",
    ),
    "INVALID_STATUS": (status.HTTP_422_UNPROCESSABLE_CONTENT, "Trạng thái không hợp lệ."),
    "INTERNAL_ERROR": (status.HTTP_500_INTERNAL_SERVER_ERROR, "Lỗi hệ thống."),
}


def _session_length() -> timedelta:
    return timedelta(minutes=get_settings().pt_session_minutes)


# --------------------------------------------------------------------------
# Schedule geometry (pure functions, gym-local time)
# --------------------------------------------------------------------------


def _blocks_for(schedule: Iterable[Mapping[str, Any]], weekday: int) -> list[tuple[int, int]]:
    """``[(start_minute, end_minute), ...]`` of one weekday, in local minutes."""
    return sorted(
        (minutes_of(parse_hhmm(row["start_time"])), minutes_of(parse_hhmm(row["end_time"])))
        for row in schedule
        if int(row["weekday"]) == weekday
    )


def _slot_starts(block: tuple[int, int], length: int) -> range:
    start, end = block
    return range(start, end - length + 1, length)


def _is_slot_start(schedule: Iterable[Mapping[str, Any]], start: datetime) -> bool:
    """True when ``start`` is exactly one of the generated slot boundaries."""
    local = to_local(start)
    length = get_settings().pt_session_minutes
    minute = local.hour * 60 + local.minute
    if local.second or local.microsecond:
        return False
    return any(
        minute in _slot_starts(block, length) for block in _blocks_for(schedule, local.isoweekday())
    )


def _within_schedule(schedule: Iterable[Mapping[str, Any]], start: datetime, end: datetime) -> bool:
    """Whether an existing session still fits the (possibly new) weekly schedule."""
    local_start, local_end = to_local(start), to_local(end)
    if local_start.date() != local_end.date():
        return False
    begin = local_start.hour * 60 + local_start.minute
    finish = local_end.hour * 60 + local_end.minute
    return any(
        s <= begin and finish <= e for s, e in _blocks_for(schedule, local_start.isoweekday())
    )


def _overlaps(start: datetime, end: datetime, ranges: Iterable[tuple[datetime, datetime]]) -> bool:
    return any(start < other_end and end > other_start for other_start, other_end in ranges)


def _as_aware(value: datetime) -> datetime:
    return to_local(value)


# --------------------------------------------------------------------------
# Trainer: "Lịch của bạn"
# --------------------------------------------------------------------------


def _conflicts(db: Session, user_id: str, trainer_id: str) -> list[PtBookingResponse]:
    """Upcoming held sessions that no longer fit the schedule or hit time off."""
    schedule = pt_repository.get_schedule(db, trainer_id)
    now = now_utc()
    time_off = [
        (_as_aware(row["start_at"]), _as_aware(row["end_at"]))
        for row in pt_repository.list_time_off(db, trainer_id, to_naive_utc(now))
    ]
    return [
        booking
        for booking in list_trainer_bookings(db, user_id)
        if booking.status in ("REQUESTED", "ACCEPTED")
        and booking.start_at > now
        and (
            not _within_schedule(schedule, booking.start_at, booking.end_at)
            or _overlaps(booking.start_at, booking.end_at, time_off)
        )
    ]


def get_my_schedule(db: Session, user_id: str) -> ScheduleResponse:
    trainer_id = require_trainer_id(db, user_id)
    settings = get_settings()
    weekly = [
        WeeklyScheduleItem(
            weekday=int(row["weekday"]), start_time=row["start_time"], end_time=row["end_time"]
        )
        for row in pt_repository.get_schedule(db, trainer_id)
    ]
    time_off = [
        TimeOffItem(
            id=row["id"], start_at=row["start_at"], end_at=row["end_at"], reason=row.get("reason")
        )
        for row in pt_repository.list_time_off(db, trainer_id, to_naive_utc(now_utc()))
    ]
    return ScheduleResponse(
        weekly=weekly,
        time_off=time_off,
        session_minutes=settings.pt_session_minutes,
        timezone=tz_label(),
        conflicts=_conflicts(db, user_id, trainer_id),
    )


def save_my_schedule(db: Session, user_id: str, payload: ScheduleUpdateRequest) -> ScheduleResponse:
    length = get_settings().pt_session_minutes
    for item in payload.weekly:
        span = minutes_of(parse_hhmm(item.end_time)) - minutes_of(parse_hhmm(item.start_time))
        if span < length:
            raise error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "SCHEDULE_TOO_SHORT",
                f"Mỗi khung giờ cần dài ít nhất {length} phút (một buổi tập).",
            )

    outcome = pt_repository.replace_schedule(
        db, user_id=user_id, weekly=[item.model_dump() for item in payload.weekly]
    )
    if not outcome.succeeded:
        raise_for_outcome(outcome, _SCHEDULE_ERRORS, "Không thể lưu lịch làm việc.")
    return get_my_schedule(db, user_id)


def add_time_off(db: Session, user_id: str, payload: TimeOffCreateRequest) -> ScheduleResponse:
    outcome = pt_repository.create_time_off(
        db,
        time_off_id=new_uuid(),
        user_id=user_id,
        start_at=to_naive_utc(payload.start_at),
        end_at=to_naive_utc(payload.end_at),
        reason=payload.reason,
    )
    if not outcome.succeeded:
        raise_for_outcome(outcome, _SCHEDULE_ERRORS, "Không thể lưu lịch nghỉ.")
    return get_my_schedule(db, user_id)


def remove_time_off(db: Session, user_id: str, time_off_id: str) -> ScheduleResponse:
    outcome = pt_repository.delete_time_off(db, time_off_id=time_off_id, user_id=user_id)
    if not outcome.succeeded:
        raise_for_outcome(outcome, _SCHEDULE_ERRORS, "Không thể xoá lịch nghỉ.")
    return get_my_schedule(db, user_id)


# --------------------------------------------------------------------------
# Member: free slots
# --------------------------------------------------------------------------


def _booking_window(now: datetime) -> tuple[datetime, datetime]:
    settings = get_settings()
    return (
        now + timedelta(minutes=settings.pt_booking_min_lead_minutes),
        now + timedelta(days=settings.pt_booking_horizon_days),
    )


def list_bookable_slots(db: Session, trainer_id: str) -> list[BookableSlot]:
    """Free fixed-length slots for the next ``pt_booking_horizon_days`` days."""
    schedule = pt_repository.get_schedule(db, trainer_id)
    if not schedule:
        return []

    now = now_utc()
    earliest, latest = _booking_window(now)
    taken = [
        (_as_aware(row["start_at"]), _as_aware(row["end_at"]))
        for row in pt_repository.list_time_off(
            db, trainer_id, to_naive_utc(now), to_naive_utc(latest)
        )
    ] + [
        (_as_aware(row["start_at"]), _as_aware(row["end_at"]))
        for row in pt_repository.list_busy(db, trainer_id, to_naive_utc(now), to_naive_utc(latest))
    ]

    tz = gym_tz()
    length = get_settings().pt_session_minutes
    first_day = earliest.astimezone(tz).date()
    last_day = latest.astimezone(tz).date()

    slots: list[BookableSlot] = []
    day = first_day
    while day <= last_day:
        midnight = datetime(day.year, day.month, day.day, tzinfo=tz)
        for block in _blocks_for(schedule, day.isoweekday()):
            for minute in _slot_starts(block, length):
                start = midnight + timedelta(minutes=minute)
                end = start + timedelta(minutes=length)
                if start < earliest or start > latest or _overlaps(start, end, taken):
                    continue
                slots.append(_to_slot(start, end, day))
        day += timedelta(days=1)
    return slots


def _to_slot(start: datetime, end: datetime, day: date) -> BookableSlot:
    return BookableSlot(
        start_at=start,
        end_at=end,
        local_date=day.isoformat(),
        local_start=start.strftime("%H:%M"),
        local_end=end.strftime("%H:%M"),
        weekday=day.isoweekday(),
    )


# --------------------------------------------------------------------------
# Member: book / cancel
# --------------------------------------------------------------------------


def book_session(db: Session, user_id: str, payload: PtBookingCreateRequest) -> PtBookingResponse:
    start = payload.start_at.astimezone(gym_tz())
    end = start + _session_length()

    earliest, latest = _booking_window(now_utc())
    if start < earliest:
        hours = get_settings().pt_booking_min_lead_minutes / 60
        raise error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "TOO_SOON",
            f"Buổi tập cần được đặt trước ít nhất {hours:g} giờ.",
        )
    if start > latest:
        raise error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "TOO_FAR",
            f"Chỉ đặt được trong {get_settings().pt_booking_horizon_days} ngày tới.",
        )

    # Chỉ nhận đúng mốc của các ô 60 phút để lịch PT không bị chia vụn.
    if not _is_slot_start(pt_repository.get_schedule(db, payload.trainer_id), start):
        code = "OUTSIDE_SCHEDULE"
        raise error(status.HTTP_409_CONFLICT, code, _SESSION_ERRORS[code][1])

    booking_id = new_uuid()
    outcome = pt_repository.book_session(
        db,
        booking_id=booking_id,
        booking_number=f"PTB-{now_utc():%Y%m%d}-{secrets.token_hex(3).upper()}",
        user_id=user_id,
        trainer_id=payload.trainer_id,
        start_at=to_naive_utc(start),
        end_at=to_naive_utc(end),
        local_weekday=start.isoweekday(),
        local_start=start.time().replace(tzinfo=None),
        local_end=end.time().replace(tzinfo=None),
        local_label=local_label(start),
        notes=payload.notes,
    )
    if not outcome.succeeded:
        raise_for_outcome(outcome, _SESSION_ERRORS, "Không thể đặt buổi PT.")

    return _find(list_my_bookings(db, user_id), booking_id)


def cancel_session(
    db: Session, user_id: str, booking_id: str, reason: str | None
) -> PtCancelResponse:
    settings = get_settings()
    outcome = pt_repository.cancel_session(
        db,
        booking_id=booking_id,
        user_id=user_id,
        reason=reason,
        refund_minutes=settings.pt_cancel_refund_hours * 60,
        utc_offset_minutes=settings.gym_utc_offset_minutes,
    )
    if not outcome.succeeded:
        raise_for_outcome(outcome, _SESSION_ERRORS, "Không thể huỷ buổi PT.")

    if outcome.data.get("cancelled_by_role") == "TRAINER":
        bookings = list_trainer_bookings(db, user_id)
    else:
        bookings = list_my_bookings(db, user_id)
    return PtCancelResponse(
        booking=_find(bookings, booking_id), refunded=bool(outcome.data.get("refunded"))
    )


# --------------------------------------------------------------------------
# Trainer: close out a session
# --------------------------------------------------------------------------


def finish_session(db: Session, user_id: str, booking_id: str, result: str) -> PtBookingResponse:
    outcome = pt_repository.finish_session(
        db,
        booking_id=booking_id,
        user_id=user_id,
        outcome=result,
        utc_offset_minutes=get_settings().gym_utc_offset_minutes,
    )
    if not outcome.succeeded:
        raise_for_outcome(outcome, _SESSION_ERRORS, "Không thể cập nhật buổi PT.")
    return _find(list_trainer_bookings(db, user_id), booking_id)


def _find(bookings: list[PtBookingResponse], booking_id: str) -> PtBookingResponse:
    booking = next((item for item in bookings if item.id == booking_id), None)
    if booking is None:
        raise error(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Không đọc lại được buổi PT."
        )
    return booking
