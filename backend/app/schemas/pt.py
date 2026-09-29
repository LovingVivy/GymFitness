"""Request/response schemas for trainers, weekly schedules, PT sessions and notifications."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.profile import MoneyOut, UtcDateTime

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class TrainerSummary(BaseModel):
    """A trainer as shown in the booking picker."""

    id: str
    user_id: str
    employee_code: str
    full_name: str | None = None
    branch_name: str | None = None
    bio: str | None = None
    certifications: str | None = None
    hourly_rate: MoneyOut
    status: str
    specialties: list[str] = Field(default_factory=list)
    # Ngày làm việc trong tuần theo ISO (1 = Thứ 2 ... 7 = Chủ nhật).
    schedule_weekdays: list[int] = Field(default_factory=list)


class TrainerProfileResponse(TrainerSummary):
    """The signed-in trainer's own profile."""

    email: str


class WeeklyScheduleItem(BaseModel):
    """One working block, in gym-local wall-clock time."""

    weekday: int = Field(ge=1, le=7, description="1 = Thứ 2 ... 7 = Chủ nhật")
    start_time: str = Field(examples=["17:00"])
    end_time: str = Field(examples=["21:00"])

    @field_validator("start_time", "end_time")
    @classmethod
    def _hhmm(cls, value: str) -> str:
        value = value.strip()
        if not _HHMM.match(value):
            raise ValueError("Giờ phải có dạng HH:MM, ví dụ 17:00")
        return value

    @model_validator(mode="after")
    def _ordered(self) -> WeeklyScheduleItem:
        if self.end_time <= self.start_time:
            raise ValueError("Giờ kết thúc phải sau giờ bắt đầu")
        return self


class ScheduleUpdateRequest(BaseModel):
    weekly: list[WeeklyScheduleItem] = Field(max_length=50)

    @model_validator(mode="after")
    def _no_overlap(self) -> ScheduleUpdateRequest:
        by_day: dict[int, list[WeeklyScheduleItem]] = {}
        for item in self.weekly:
            by_day.setdefault(item.weekday, []).append(item)
        for items in by_day.values():
            items.sort(key=lambda item: item.start_time)
            for previous, current in zip(items, items[1:], strict=False):
                if current.start_time < previous.end_time:
                    raise ValueError("Các khung giờ trong cùng một ngày đang chồng lấn nhau")
        return self


class TimeOffCreateRequest(BaseModel):
    start_at: UtcDateTime
    end_at: UtcDateTime
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("reason")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class TimeOffItem(BaseModel):
    id: str
    start_at: UtcDateTime
    end_at: UtcDateTime
    reason: str | None = None


class BookableSlot(BaseModel):
    """A free session a member can book; local fields are gym wall-clock time."""

    start_at: UtcDateTime
    end_at: UtcDateTime
    local_date: str
    local_start: str
    local_end: str
    weekday: int


class PtCreditSummary(BaseModel):
    credit_account_id: str | None = None
    purchased: int = 0
    reserved: int = 0
    used: int = 0
    available: int = 0


class PtCreditPurchaseRequest(BaseModel):
    quantity: int = Field(ge=1, le=100, description="Số buổi PT muốn mua")


class PtBookingCreateRequest(BaseModel):
    trainer_id: str = Field(min_length=36, max_length=36)
    # Thời điểm bắt đầu của một ô trong GET /trainers/{id}/slots.
    start_at: UtcDateTime
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PtBookingCancelRequest(BaseModel):
    """PT bắt buộc ghi lý do; hội viên có thể để trống."""

    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class PtBookingResponse(BaseModel):
    id: str
    booking_number: str
    status: str
    activity_type: str
    start_at: UtcDateTime
    end_at: UtcDateTime
    requested_at: UtcDateTime | None = None
    responded_at: UtcDateTime | None = None
    response_due_at: UtcDateTime | None = None
    rejection_reason: str | None = None
    cancellation_reason: str | None = None
    cancelled_at: UtcDateTime | None = None
    cancelled_by_role: str | None = None
    completed_at: UtcDateTime | None = None
    notes: str | None = None
    # Giờ địa phương của phòng tập để hiển thị thống nhất.
    local_label: str | None = None
    # Hội viên huỷ trước mốc này thì được hoàn lượt.
    refund_deadline: UtcDateTime | None = None
    trainer_id: str
    trainer_name: str | None = None
    employee_code: str | None = None
    hourly_rate: MoneyOut | None = None
    member_name: str | None = None
    member_phone: str | None = None
    member_email: str | None = None
    member_code: str | None = None


class PtCancelResponse(BaseModel):
    booking: PtBookingResponse
    refunded: bool


class ScheduleResponse(BaseModel):
    """What the trainer's "Lịch của bạn" screen shows."""

    weekly: list[WeeklyScheduleItem]
    time_off: list[TimeOffItem]
    session_minutes: int
    timezone: str
    # Buổi đã đặt nhưng nằm ngoài lịch mới / trong lịch nghỉ: PT cần tự xử lý.
    conflicts: list[PtBookingResponse] = Field(default_factory=list)


class NotificationResponse(BaseModel):
    id: str
    notification_type: str
    title: str
    body: str
    data: dict[str, Any] = Field(default_factory=dict)
    action_url: str | None = None
    read_at: UtcDateTime | None = None
    created_at: UtcDateTime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread: int
