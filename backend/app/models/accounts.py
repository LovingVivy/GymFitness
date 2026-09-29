from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, RowVersionMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.commerce import Cart, Order
    from app.models.member import Member
    from app.models.operations import AuditLog, Notification
    from app.models.organization import FileAsset
    from app.models.trainer import TrainerProfile


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(String(30), unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ACTIVE")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    two_factor_secret_encrypted: Mapped[str | None] = mapped_column(Text)

    profile: Mapped[Optional["UserProfile"]] = relationship(back_populates="user", uselist=False)
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(back_populates="user")
    addresses: Mapped[list["UserAddress"]] = relationship(back_populates="user")
    member: Mapped[Optional["Member"]] = relationship(back_populates="user", uselist=False)
    trainer_profile: Mapped[Optional["TrainerProfile"]] = relationship(
        back_populates="user", uselist=False
    )
    cart: Mapped[Optional["Cart"]] = relationship(back_populates="user", uselist=False)
    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user")
    file_assets: Mapped[list["FileAsset"]] = relationship(back_populates="owner")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="actor")


class UserProfile(Base, TimestampMixin, RowVersionMixin):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    avatar_file_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("file_assets.id", ondelete="SET NULL")
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(16))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    experience_level: Mapped[str | None] = mapped_column(String(20))
    fitness_goal: Mapped[str | None] = mapped_column(String(24))
    weekly_training_sessions: Mapped[int | None] = mapped_column(SmallInteger)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(150))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(30))

    user: Mapped["User"] = relationship(back_populates="profile")


class UserAddress(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin):
    __tablename__ = "user_addresses"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    label: Mapped[str | None] = mapped_column(String(60))
    recipient_name: Mapped[str] = mapped_column(String(150), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    province: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    ward: Mapped[str] = mapped_column(String(100), nullable=False)
    address_line: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_note: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))

    user: Mapped["User"] = relationship(back_populates="addresses")


class RefreshToken(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    jwt_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    replaced_by_token_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("refresh_tokens.id", ondelete="SET NULL")
    )
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class PasswordResetToken(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    user: Mapped["User"] = relationship(back_populates="password_reset_tokens")
