from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, RowVersionMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.accounts import User
    from app.models.member import Member


class ProductCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "product_categories"

    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("product_categories.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    activity_type: Mapped[str | None] = mapped_column(String(12))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin):
    __tablename__ = "products"

    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("product_categories.id", ondelete="SET NULL")
    )
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ACTIVE")

    variants: Mapped[list["ProductVariant"]] = relationship(back_populates="product")
    images: Mapped[list["ProductImage"]] = relationship(back_populates="product")


class ProductVariant(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, RowVersionMixin):
    __tablename__ = "product_variants"

    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(120))
    attributes: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default=text("(JSON_OBJECT())")
    )
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="VND")
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    reserved_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    product: Mapped["Product"] = relationship(back_populates="variants")


class ProductImage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "product_images"
    __table_args__ = (UniqueConstraint("product_id", "file_asset_id"),)

    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    file_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("file_assets.id", ondelete="RESTRICT"), nullable=False
    )
    alt_text: Mapped[str | None] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    product: Mapped["Product"] = relationship(back_populates="images")


class Cart(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "carts"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    user: Mapped["User"] = relationship(back_populates="cart")
    items: Mapped[list["CartItem"]] = relationship(back_populates="cart")


class CartItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "variant_id"),)

    cart_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    cart: Mapped["Cart"] = relationship(back_populates="items")


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin, RowVersionMixin):
    __tablename__ = "orders"

    order_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL")
    )
    payment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="RESTRICT"), unique=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="PENDING_PAYMENT"
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )
    shipping_fee: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="VND")
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="orders")
    member: Mapped[Optional["Member"]] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    address: Mapped[Optional["OrderAddress"]] = relationship(back_populates="order", uselist=False)


class OrderAddress(Base):
    __tablename__ = "order_addresses"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="RESTRICT"), primary_key=True
    )
    source_address_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user_addresses.id", ondelete="SET NULL")
    )
    recipient_name: Mapped[str] = mapped_column(String(150), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    province: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    ward: Mapped[str] = mapped_column(String(100), nullable=False)
    address_line: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    order: Mapped["Order"] = relationship(back_populates="address")


class OrderItem(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    variant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("product_variants.id", ondelete="SET NULL")
    )
    sku_snapshot: Mapped[str] = mapped_column(String(60), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    variant_snapshot: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default=text("(JSON_OBJECT())")
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), Computed("(unit_price * quantity)", persisted=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    order: Mapped["Order"] = relationship(back_populates="items")


class InventoryMovement(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "inventory_movements"

    variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="SET NULL")
    )
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )
