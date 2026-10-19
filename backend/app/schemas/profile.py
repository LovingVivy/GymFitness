"""Request/response schemas for the member profile and membership."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
)

from app.models.enums import ExperienceLevel, FitnessGoal, Gender

# Money is Decimal on the wire-safe side and a JSON number for display only.
MoneyOut = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


def _mark_as_utc(value: datetime) -> datetime:
    """Stored datetimes are naive UTC; tag them so clients convert correctly.

    Without the marker a browser would read ``2026-09-28T03:16:46`` as local
    time and show a shifted clock.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


UtcDateTime = Annotated[datetime, AfterValidator(_mark_as_utc)]

_EXPERIENCE_VALUES = {level.value for level in ExperienceLevel}
_GOAL_VALUES = {goal.value for goal in FitnessGoal}
_GENDER_VALUES = {gender.value for gender in Gender}


class MembershipSummary(BaseModel):
    """The subscription currently backing the member, if any."""

    subscription_id: str
    status: str
    plan_id: str
    plan_code: str
    plan_name: str
    activity_type: str
    duration_months: int | None = None
    duration_days: int | None = None
    price: MoneyOut
    currency: str
    start_at: UtcDateTime | None = None
    end_at: UtcDateTime | None = None
    days_remaining: int | None = None
    total_days: int | None = None


class PtCreditsSummary(BaseModel):
    """Wallet of paid personal-training sessions."""

    purchased: int = 0
    reserved: int = 0
    used: int = 0
    remaining: int = 0


class ProfileResponse(BaseModel):
    """Everything the profile page needs in a single call."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    phone: str | None = None
    role: str
    status: str
    full_name: str | None = None
    avatar_url: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    experience_level: str | None = None
    fitness_goal: str | None = None
    weekly_training_sessions: int | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    member_code: str | None = None
    member_joined_at: UtcDateTime | None = None
    home_branch_name: str | None = None
    membership: MembershipSummary | None = None
    # Mọi gói còn hiệu lực (tối đa một Gym và một Yoga), mới hết hạn sau cùng trước.
    memberships: list[MembershipSummary] = Field(default_factory=list)
    pt_credits: PtCreditsSummary = PtCreditsSummary()
    created_at: UtcDateTime | None = None
    last_login_at: UtcDateTime | None = None
    permissions: list[str] = Field(default_factory=list)
    two_factor_enabled: bool = False


class ProfileUpdateRequest(BaseModel):
    """Partial update; omitted fields keep their current value."""

    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    date_of_birth: date | None = None
    gender: str | None = None
    height_cm: float | None = Field(default=None, ge=50, le=300)
    weight_kg: float | None = Field(default=None, ge=15, le=500)
    experience_level: str | None = None
    fitness_goal: str | None = None
    weekly_training_sessions: int | None = Field(default=None, ge=1, le=14)
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_phone: str | None = Field(default=None, max_length=30)

    @field_validator("full_name", "phone", "emergency_contact_name", "emergency_contact_phone")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("gender")
    @classmethod
    def _validate_gender(cls, value: str | None) -> str | None:
        if value is None:
            return None
        upper = value.strip().upper()
        if upper not in _GENDER_VALUES:
            raise ValueError("Giới tính không hợp lệ")
        return upper

    @field_validator("experience_level")
    @classmethod
    def _validate_experience(cls, value: str | None) -> str | None:
        if value is None:
            return None
        upper = value.strip().upper()
        if upper not in _EXPERIENCE_VALUES:
            raise ValueError("Kinh nghiệm không hợp lệ")
        return upper

    @field_validator("fitness_goal")
    @classmethod
    def _validate_goal(cls, value: str | None) -> str | None:
        if value is None:
            return None
        upper = value.strip().upper()
        if upper not in _GOAL_VALUES:
            raise ValueError("Mục tiêu không hợp lệ")
        return upper


class AvatarUploadRequest(BaseModel):
    """Avatar sent as a base64 data URL.

    ``python-multipart`` is not installable in this environment, so the image
    travels inside JSON instead of a multipart form. The browser already reads
    the picked file as a data URL, so no extra client work is needed.
    """

    image: str = Field(min_length=32, max_length=4_000_000)


class PlanResponse(BaseModel):
    id: str
    code: str
    name: str
    activity_type: str
    description: str | None = None
    duration_months: int | None = None
    duration_days: int | None = None
    price: MoneyOut
    currency: str
    max_visits: int | None = None
    freeze_days_allowed: int = 0


class SubscriptionCreateRequest(BaseModel):
    """Create a pending subscription together with its pending payment."""

    plan_id: str = Field(min_length=36, max_length=36)
    # Mua kèm lượt PT trong cùng một payment (ADR-014), 0 = không mua.
    pt_sessions: int = Field(default=0, ge=0, le=100)


class PaymentSummary(BaseModel):
    id: str
    payment_number: str
    status: str
    amount: MoneyOut
    currency: str
    method: str
    qr_payload: str | None = None


class SubscriptionCreateResponse(BaseModel):
    subscription_id: str
    status: str
    payment: PaymentSummary
    pt_sessions: int = 0
