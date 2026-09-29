from datetime import datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
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
    from app.models.member import Member
    from app.models.membership import MembershipSubscription
    from app.models.organization import Branch
    from app.models.trainer import TrainerProfile


class PtCreditAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin, RowVersionMixin):
    __tablename__ = "pt_credit_accounts"

    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    purchased_sessions: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    reserved_sessions: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    used_sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    member: Mapped["Member"] = relationship(back_populates="pt_credit_account")
    purchases: Mapped[list["PtCreditPurchase"]] = relationship(back_populates="credit_account")
    ledger: Mapped[list["PtCreditLedger"]] = relationship(back_populates="credit_account")


class PtCreditPurchase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pt_credit_purchases"

    credit_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pt_credit_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PENDING")
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    credit_account: Mapped["PtCreditAccount"] = relationship(back_populates="purchases")


class TrainerAvailability(
    Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin
):
    __tablename__ = "trainer_availability"

    trainer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trainer_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id", ondelete="SET NULL")
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    recurrence_rule: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)

    trainer: Mapped["TrainerProfile"] = relationship(back_populates="availabilities")
    branch: Mapped[Optional["Branch"]] = relationship(back_populates="availabilities")


class TrainerWeeklySchedule(Base, UUIDPrimaryKeyMixin):
    """Recurring working block in gym-local wall-clock time (ADR-015)."""

    __tablename__ = "trainer_weekly_schedule"

    trainer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trainer_profiles.id", ondelete="CASCADE"), nullable=False
    )
    # ISO 8601: 1 = Thứ 2 ... 7 = Chủ nhật.
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )


class TrainerTimeOff(Base, UUIDPrimaryKeyMixin, SoftDeleteMixin):
    __tablename__ = "trainer_time_off"

    trainer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trainer_profiles.id", ondelete="CASCADE"), nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )


class PtBooking(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin):
    __tablename__ = "pt_bookings"

    booking_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="RESTRICT"), nullable=False
    )
    trainer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trainer_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    subscription_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("membership_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    credit_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pt_credit_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    # Chỉ booking kiểu cũ (trước ADR-015) mới gắn với trainer_availability.
    availability_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("trainer_availability.id", ondelete="RESTRICT")
    )
    schedule_entry_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workout_schedule_entries.id", ondelete="SET NULL")
    )
    activity_type: Mapped[str] = mapped_column(String(12), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="REQUESTED")
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    cancelled_by: Mapped[str | None] = mapped_column(String(36))
    cancelled_by_role: Mapped[str | None] = mapped_column(String(12))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )
    response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    notes: Mapped[str | None] = mapped_column(Text)

    member: Mapped["Member"] = relationship(back_populates="pt_bookings")
    trainer: Mapped["TrainerProfile"] = relationship(back_populates="pt_bookings")
    subscription: Mapped["MembershipSubscription"] = relationship(back_populates="pt_bookings")


class PtCreditLedger(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "pt_credit_ledger"

    credit_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pt_credit_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    purchase_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pt_credit_purchases.id", ondelete="RESTRICT")
    )
    booking_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pt_bookings.id", ondelete="RESTRICT")
    )
    transaction_type: Mapped[str] = mapped_column(String(16), nullable=False)
    purchased_delta: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    reserved_delta: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    used_delta: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    purchased_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    used_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    credit_account: Mapped["PtCreditAccount"] = relationship(back_populates="ledger")
