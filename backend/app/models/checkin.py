from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, RowVersionMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.membership import MembershipSubscription
    from app.models.organization import Branch


class QrNonce(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "qr_nonces"

    nonce_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="RESTRICT"), nullable=False
    )
    subscription_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("membership_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class CheckIn(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin):
    __tablename__ = "check_ins"

    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="RESTRICT"), nullable=False
    )
    subscription_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("membership_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id", ondelete="SET NULL")
    )
    qr_nonce_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("qr_nonces.id", ondelete="RESTRICT"), unique=True
    )
    check_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    location: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )

    member: Mapped["Member"] = relationship(back_populates="check_ins")
    subscription: Mapped["MembershipSubscription"] = relationship(back_populates="check_ins")
    branch: Mapped[Optional["Branch"]] = relationship(back_populates="check_ins")
