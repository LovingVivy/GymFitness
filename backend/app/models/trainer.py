from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, RowVersionMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.accounts import User
    from app.models.classes import ClassSession
    from app.models.organization import Branch
    from app.models.pt import PtBooking, TrainerAvailability


class TrainerProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin):
    __tablename__ = "trainer_profiles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    employee_code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id", ondelete="SET NULL")
    )
    bio: Mapped[str | None] = mapped_column(Text)
    certifications: Mapped[str | None] = mapped_column(Text)
    hourly_rate: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("200000")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ACTIVE")

    user: Mapped["User"] = relationship(back_populates="trainer_profile")
    branch: Mapped[Optional["Branch"]] = relationship(back_populates="trainers")
    specialties: Mapped[list["TrainerSpecialty"]] = relationship(back_populates="trainer")
    availabilities: Mapped[list["TrainerAvailability"]] = relationship(back_populates="trainer")
    pt_bookings: Mapped[list["PtBooking"]] = relationship(back_populates="trainer")
    class_sessions: Mapped[list["ClassSession"]] = relationship(back_populates="trainer")


class TrainerSpecialty(Base):
    __tablename__ = "trainer_specialties"

    trainer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trainer_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    specialty: Mapped[str] = mapped_column(String(24), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    trainer: Mapped["TrainerProfile"] = relationship(back_populates="specialties")
