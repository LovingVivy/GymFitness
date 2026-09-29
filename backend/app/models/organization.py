from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.accounts import User
    from app.models.checkin import CheckIn
    from app.models.classes import Room
    from app.models.member import Member
    from app.models.operations import Equipment
    from app.models.pt import TrainerAvailability
    from app.models.trainer import TrainerProfile


class Branch(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "branches"

    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address_line: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="Asia/Bangkok")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    members: Mapped[list["Member"]] = relationship(back_populates="home_branch")
    trainers: Mapped[list["TrainerProfile"]] = relationship(back_populates="branch")
    rooms: Mapped[list["Room"]] = relationship(back_populates="branch")
    check_ins: Mapped[list["CheckIn"]] = relationship(back_populates="branch")
    equipment: Mapped[list["Equipment"]] = relationship(back_populates="branch")
    availabilities: Mapped[list["TrainerAvailability"]] = relationship(back_populates="branch")


class FileAsset(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "file_assets"

    owner_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    visibility: Mapped[str] = mapped_column(String(12), nullable=False, server_default="PRIVATE")
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    owner: Mapped[Optional["User"]] = relationship(back_populates="file_assets")
