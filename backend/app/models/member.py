from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, RowVersionMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.accounts import User
    from app.models.billing import Payment
    from app.models.checkin import CheckIn
    from app.models.classes import ClassBooking
    from app.models.commerce import Order
    from app.models.membership import MembershipSubscription
    from app.models.organization import Branch
    from app.models.pt import PtBooking, PtCreditAccount


class Member(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin):
    __tablename__ = "members"

    member_code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    home_branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id", ondelete="SET NULL")
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(30))
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ACTIVE")
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[Optional["User"]] = relationship(back_populates="member", uselist=False)
    home_branch: Mapped[Optional["Branch"]] = relationship(back_populates="members")
    subscriptions: Mapped[list["MembershipSubscription"]] = relationship(back_populates="member")
    pt_credit_account: Mapped[Optional["PtCreditAccount"]] = relationship(
        back_populates="member", uselist=False
    )
    check_ins: Mapped[list["CheckIn"]] = relationship(back_populates="member")
    pt_bookings: Mapped[list["PtBooking"]] = relationship(back_populates="member")
    class_bookings: Mapped[list["ClassBooking"]] = relationship(back_populates="member")
    payments: Mapped[list["Payment"]] = relationship(back_populates="member")
    orders: Mapped[list["Order"]] = relationship(back_populates="member")
