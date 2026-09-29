from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, RowVersionMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.membership import MembershipSubscription
    from app.models.organization import Branch
    from app.models.trainer import TrainerProfile


class Room(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("branch_id", "code"),)

    branch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    branch: Mapped["Branch"] = relationship(back_populates="rooms")
    sessions: Mapped[list["ClassSession"]] = relationship(back_populates="room")


class ClassType(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "class_types"

    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(12), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    sessions: Mapped[list["ClassSession"]] = relationship(back_populates="class_type")


class ClassSession(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin):
    __tablename__ = "class_sessions"

    class_type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("class_types.id", ondelete="RESTRICT"), nullable=False
    )
    trainer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trainer_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    cancellation_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="SCHEDULED")

    class_type: Mapped["ClassType"] = relationship(back_populates="sessions")
    trainer: Mapped["TrainerProfile"] = relationship(back_populates="class_sessions")
    room: Mapped["Room"] = relationship(back_populates="sessions")
    bookings: Mapped[list["ClassBooking"]] = relationship(back_populates="session")


class ClassBooking(Base, UUIDPrimaryKeyMixin, TimestampMixin, RowVersionMixin):
    __tablename__ = "class_bookings"
    __table_args__ = (UniqueConstraint("session_id", "member_id"),)

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("class_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="RESTRICT"), nullable=False
    )
    subscription_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("membership_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="BOOKED")
    waitlist_position: Mapped[int | None] = mapped_column(Integer)
    booked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    session: Mapped["ClassSession"] = relationship(back_populates="bookings")
    member: Mapped["Member"] = relationship(back_populates="class_bookings")
    subscription: Mapped["MembershipSubscription"] = relationship(back_populates="class_bookings")
