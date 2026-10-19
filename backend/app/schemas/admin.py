"""Schemas for the admin area: accounts, plans, check-in logs and revenue."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.profile import MoneyOut, UtcDateTime

Role = Literal["USER", "PT", "MANAGER", "ADMIN"]
AccountStatus = Literal["ACTIVE", "SUSPENDED", "INACTIVE"]
Specialty = Literal["GYM", "YOGA", "WEIGHT_LOSS", "MUSCLE_GAIN", "REHABILITATION", "FLEXIBILITY"]
RevenuePeriod = Literal["WEEK", "MONTH", "QUARTER", "YEAR"]
PaymentStatus = Literal["PENDING", "PAID", "FAILED", "REFUNDED", "VOID"]
PaymentPurpose = Literal["MEMBERSHIP", "PT_CREDIT", "PRODUCT_ORDER"]

_USERNAME = re.compile(r"^[a-z0-9._]{3,50}$")


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValueError("Email không hợp lệ")
    return value


def _normalize_username(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().lower()
    if not value:
        return ""
    if not _USERNAME.match(value):
        raise ValueError("Tên đăng nhập 3–50 ký tự, chỉ gồm chữ thường, số, dấu chấm, gạch dưới")
    return value


# --------------------------------------------------------------------------
# Overview
# --------------------------------------------------------------------------


class AdminOverview(BaseModel):
    members: int
    new_members_this_month: int = 0
    new_members_last_month: int = 0
    # So với tháng trước, None nếu tháng trước bằng 0.
    member_growth_percent: float | None = None
    trainers: int
    active_members: int
    checkins_today: int
    inside_now: int
    revenue_this_month: MoneyOut
    revenue_last_month: MoneyOut = Decimal(0)
    revenue_growth_percent: float | None = None
    pending_payments: int
    products: int = 0


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------


class AdminUser(BaseModel):
    id: str
    email: str
    username: str | None = None
    phone: str | None = None
    role: str
    status: str
    full_name: str | None = None
    member_code: str | None = None
    employee_code: str | None = None
    hourly_rate: MoneyOut | None = None
    bio: str | None = None
    specialties: list[str] = Field(default_factory=list)
    # Chỉ có khi vừa khoá/ngưng tài khoản: số buổi PT sắp tới đã tự huỷ và hoàn lượt.
    cancelled_sessions: int = 0
    # PT chưa khai lịch làm việc thì hội viên chưa thấy để đặt.
    has_schedule: bool = False
    active_plan_name: str | None = None
    active_plan_end_at: UtcDateTime | None = None
    created_at: UtcDateTime | None = None
    last_login_at: UtcDateTime | None = None
    locked: bool = False


class AdminUserPage(BaseModel):
    items: list[AdminUser]
    total: int


class AdminUserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: str
    username: str | None = None
    phone: str | None = Field(default=None, max_length=30)
    password: str = Field(min_length=8, max_length=128)
    role: Role = "USER"
    hourly_rate: Decimal | None = Field(default=None, ge=0, le=100_000_000)
    bio: str | None = Field(default=None, max_length=2000)
    specialties: list[Specialty] = Field(default_factory=list)

    _strip = field_validator("full_name", "phone", "bio")(_blank_to_none)
    _email = field_validator("email")(_normalize_email)
    _username = field_validator("username")(_normalize_username)

    @model_validator(mode="after")
    def _trainer_needs_specialty(self) -> AdminUserCreate:
        if not self.full_name:
            raise ValueError("Họ và tên không được để trống")
        if self.role == "PT" and not self.specialties:
            raise ValueError("Huấn luyện viên cần ít nhất một chuyên môn")
        return self


class AdminUserUpdate(BaseModel):
    """Partial update; omitted fields are kept. ``phone``/``username`` = "" clears them."""

    full_name: str | None = Field(default=None, max_length=150)
    email: str | None = None
    username: str | None = None
    phone: str | None = Field(default=None, max_length=30)
    status: AccountStatus | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0, le=100_000_000)
    bio: str | None = Field(default=None, max_length=2000)
    specialties: list[Specialty] | None = None

    _email = field_validator("email")(
        lambda value: None if value is None else _normalize_email(value)
    )
    _username = field_validator("username")(_normalize_username)

    @field_validator("full_name")
    @classmethod
    def _full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Họ và tên không được để trống")
        return value

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()


class AdminPasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------


class AdminPlan(BaseModel):
    id: str
    code: str
    name: str
    activity_type: str
    description: str | None = None
    duration_months: int | None = None
    duration_days: int | None = None
    price: MoneyOut
    currency: str
    is_active: bool
    active_subscriptions: int = 0
    total_sold: int = 0
    created_at: UtcDateTime | None = None
    # Phiên bản bản ghi: gửi lại khi sửa để không ghi đè thay đổi của người khác.
    row_version: int = 1


class AdminPlanSave(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=1, max_length=150)
    activity_type: Literal["GYM", "YOGA"]
    description: str | None = Field(default=None, max_length=2000)
    duration_months: int | None = Field(default=None, ge=1, le=60)
    duration_days: int | None = Field(default=None, ge=1, le=3650)
    price: Decimal = Field(ge=0, le=1_000_000_000)
    is_active: bool = True
    # row_version đang xem; khác bản hiện tại → 409 VERSION_CONFLICT. Bỏ trống = không kiểm tra.
    row_version: int | None = Field(default=None, ge=1)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.match(r"^[A-Z0-9_]{2,40}$", value):
            raise ValueError("Mã gói chỉ gồm chữ in hoa, số và gạch dưới, ví dụ GYM_3_MONTHS")
        return value

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Tên gói không được để trống")
        return value

    @model_validator(mode="after")
    def _one_duration(self) -> AdminPlanSave:
        if (self.duration_months is None) == (self.duration_days is None):
            raise ValueError("Chọn đúng một loại thời hạn: theo tháng hoặc theo ngày")
        return self


# --------------------------------------------------------------------------
# Check-in logs
# --------------------------------------------------------------------------


class CheckinLog(BaseModel):
    id: str
    check_in_at: UtcDateTime
    check_out_at: UtcDateTime | None = None
    method: str
    member_id: str
    member_code: str
    member_name: str
    member_email: str | None = None
    member_phone: str | None = None
    plan_name: str | None = None
    created_by_name: str | None = None
    duration_minutes: int | None = None


class CheckinPage(BaseModel):
    items: list[CheckinLog]
    total: int


class CheckinCreate(BaseModel):
    identifier: str = Field(min_length=1, max_length=254, description="Mã hội viên, email hoặc sđt")

    @field_validator("identifier")
    @classmethod
    def _identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nhập mã hội viên, email hoặc số điện thoại")
        # Collation utf8mb4_0900_ai_ci so khớp không phân biệt hoa/thường.
        return value


class CheckinCreated(BaseModel):
    id: str
    member_name: str | None = None


# --------------------------------------------------------------------------
# Revenue
# --------------------------------------------------------------------------


class RevenueBucket(BaseModel):
    period_start: str
    label: str
    total: MoneyOut
    membership_total: MoneyOut
    pt_total: MoneyOut
    other_total: MoneyOut
    payment_count: int


class RevenueReport(BaseModel):
    period: RevenuePeriod
    buckets: list[RevenueBucket]
    total: MoneyOut
    membership_total: MoneyOut
    pt_total: MoneyOut
    payment_count: int
    # So sánh kỳ hiện tại (kỳ cuối) với kỳ ngay trước đó, None nếu kỳ trước bằng 0.
    change_percent: float | None = None


# --------------------------------------------------------------------------
# Member growth
# --------------------------------------------------------------------------


class MemberGrowthBucket(BaseModel):
    period_start: str
    label: str
    new_members: int
    # Tổng hội viên tính đến hết kỳ này.
    total_members: int


class MemberGrowthReport(BaseModel):
    period: RevenuePeriod
    buckets: list[MemberGrowthBucket]
    total_members: int
    new_members: int
    # Hội viên mới của kỳ hiện tại so với kỳ ngay trước, None nếu kỳ trước bằng 0.
    change_percent: float | None = None
    # Tổng hội viên cuối kỳ hiện tại so với cuối kỳ trước, None nếu kỳ trước bằng 0.
    total_growth_percent: float | None = None


# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------


class AdminPayment(BaseModel):
    id: str
    payment_number: str
    purpose: str
    amount: MoneyOut
    currency: str
    method: str
    status: str
    external_reference: str | None = None
    failure_reason: str | None = None
    bank_note: str | None = None
    created_at: UtcDateTime
    paid_at: UtcDateTime | None = None
    qr_expires_at: UtcDateTime | None = None
    member_id: str | None = None
    member_code: str | None = None
    member_name: str | None = None
    member_email: str | None = None
    member_phone: str | None = None
    plan_name: str | None = None
    pt_quantity: int | None = None


class AdminPaymentPage(BaseModel):
    items: list[AdminPayment]
    total: int
    # Tổng tiền đã thu của mọi giao dịch khớp bộ lọc (không chỉ trang hiện tại).
    paid_total: MoneyOut = Decimal(0)


class PaymentConfirm(BaseModel):
    method: Literal["QR", "CASH", "BANK_TRANSFER", "CARD"] | None = None


class PaymentVoid(BaseModel):
    reason: str | None = Field(default=None, max_length=255)

    _strip = field_validator("reason")(_blank_to_none)


# --------------------------------------------------------------------------
# Sorting
# --------------------------------------------------------------------------

UserSort = Literal[
    "full_name",
    "-full_name",
    "email",
    "-email",
    "created_at",
    "-created_at",
    "last_login_at",
    "-last_login_at",
]
CheckinSort = Literal["check_in_at", "-check_in_at", "member_name", "-member_name"]
PaymentSort = Literal["created_at", "-created_at", "paid_at", "-paid_at", "amount", "-amount"]


# --------------------------------------------------------------------------
# Audit log
# --------------------------------------------------------------------------


class AuditLogEntry(BaseModel):
    id: str
    action: str
    entity_type: str
    entity_id: str | None = None
    before_data: dict | None = None
    after_data: dict | None = None
    created_at: UtcDateTime
    actor_user_id: str | None = None
    actor_name: str | None = None
    actor_email: str | None = None
    actor_role: str | None = None


class AuditLogPage(BaseModel):
    items: list[AuditLogEntry]
    total: int
