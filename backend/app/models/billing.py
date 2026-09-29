from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, RowVersionMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.member import Member


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin, RowVersionMixin):
    __tablename__ = "payments"

    payment_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL")
    )
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="VND")
    method: Mapped[str] = mapped_column(String(20), nullable=False, server_default="QR")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PENDING")
    provider: Mapped[str | None] = mapped_column(String(50))
    external_reference: Mapped[str | None] = mapped_column(String(150))
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    qr_payload: Mapped[str | None] = mapped_column(Text)
    qr_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )

    member: Mapped[Optional["Member"]] = relationship(back_populates="payments")
    events: Mapped[list["PaymentEvent"]] = relationship(back_populates="payment")
    invoice: Mapped[Optional["Invoice"]] = relationship(back_populates="payment", uselist=False)


class PaymentEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "payment_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id"),)

    payment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(150), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    signature_valid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    payment: Mapped[Optional["Payment"]] = relationship(back_populates="events")


class Invoice(Base, UUIDPrimaryKeyMixin, TimestampMixin, RowVersionMixin):
    __tablename__ = "invoices"

    invoice_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL")
    )
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default=text("0"))
    discount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), Computed("(subtotal + tax - discount)", persisted=True)
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="VND")
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="DRAFT")
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    pdf_file_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("file_assets.id", ondelete="SET NULL")
    )

    payment: Mapped["Payment"] = relationship(back_populates="invoice")
