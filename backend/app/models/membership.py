from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, RowVersionMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.checkin import CheckIn
    from app.models.classes import ClassBooking
    from app.models.member import Member
    from app.models.pt import PtBooking


class MembershipPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin):
    __tablename__ = "membership_plans"

    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(12), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    duration_months: Mapped[int | None] = mapped_column(SmallInteger)
    duration_days: Mapped[int | None] = mapped_column(SmallInteger)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="VND")
    max_visits: Mapped[int | None] = mapped_column(Integer)
    freeze_days_allowed: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    subscriptions: Mapped[list["MembershipSubscription"]] = relationship(back_populates="plan")


class MembershipSubscription(
    Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin
):
    __tablename__ = "membership_subscriptions"

    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="RESTRICT"), nullable=False
    )
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("membership_plans.id", ondelete="RESTRICT"), nullable=False
    )
    payment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="RESTRICT"), unique=True
    )
    renewed_from_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("membership_subscriptions.id", ondelete="SET NULL")
    )
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PENDING")
    remaining_visits: Mapped[int | None] = mapped_column(Integer)
    frozen_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    frozen_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )

    member: Mapped["Member"] = relationship(back_populates="subscriptions")
    plan: Mapped["MembershipPlan"] = relationship(back_populates="subscriptions")
    status_history: Mapped[list["SubscriptionStatusHistory"]] = relationship(
        back_populates="subscription"
    )
    freeze_history: Mapped[list["SubscriptionFreezeHistory"]] = relationship(
        back_populates="subscription"
    )
    workout_entries: Mapped[list["WorkoutScheduleEntry"]] = relationship(
        back_populates="subscription"
    )
    check_ins: Mapped[list["CheckIn"]] = relationship(back_populates="subscription")
    pt_bookings: Mapped[list["PtBooking"]] = relationship(back_populates="subscription")
    class_bookings: Mapped[list["ClassBooking"]] = relationship(back_populates="subscription")


class SubscriptionStatusHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "subscription_status_history"

    subscription_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("membership_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    subscription: Mapped["MembershipSubscription"] = relationship(back_populates="status_history")


class SubscriptionFreezeHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "subscription_freeze_history"

    subscription_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("membership_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    frozen_from: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    frozen_until: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    days_granted: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    subscription: Mapped["MembershipSubscription"] = relationship(back_populates="freeze_history")


class WorkoutScheduleEntry(
    Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin
):
    __tablename__ = "workout_schedule_entries"

    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="RESTRICT"), nullable=False
    )
    subscription_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("membership_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    activity_type: Mapped[str] = mapped_column(String(12), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PLANNED")
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="SYSTEM")

    subscription: Mapped["MembershipSubscription"] = relationship(back_populates="workout_entries")
