"""Schemas for the shop catalogue: public listing and admin management."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.profile import MoneyOut, UtcDateTime

ActivityType = Literal["GYM", "YOGA"]
ProductStatus = Literal["DRAFT", "ACTIVE", "INACTIVE"]

_SKU = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,39}$")


class ShopProduct(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None = None
    category_name: str | None = None
    activity_type: str | None = None
    sku: str
    price: MoneyOut
    currency: str
    available_quantity: int
    badge: str | None = None
    art: str | None = None


class AdminProduct(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None = None
    status: str
    category_name: str | None = None
    activity_type: str | None = None
    sku: str
    price: MoneyOut
    currency: str
    stock_quantity: int
    reserved_quantity: int
    badge: str | None = None
    art: str | None = None
    created_at: UtcDateTime | None = None
    row_version: int = 1


class AdminProductPage(BaseModel):
    items: list[AdminProduct]
    total: int


class AdminProductSave(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    # Trống khi tạo mới = backend tự sinh SKU.
    sku: str | None = Field(default=None, max_length=40)
    category_name: str = Field(min_length=1, max_length=100)
    activity_type: ActivityType
    description: str | None = Field(default=None, max_length=2000)
    price: Decimal = Field(ge=0, le=1_000_000_000)
    stock_quantity: int = Field(ge=0, le=1_000_000)
    status: ProductStatus = "ACTIVE"
    badge: str | None = Field(default=None, max_length=40)
    art: str | None = Field(default=None, max_length=40)
    # row_version đang xem; khác bản hiện tại → 409 VERSION_CONFLICT. Bỏ trống = không kiểm tra.
    row_version: int | None = Field(default=None, ge=1)

    @field_validator("name", "category_name")
    @classmethod
    def _required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Không được để trống")
        return value

    @field_validator("description", "badge", "art")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("sku")
    @classmethod
    def _sku(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip().upper()
        if not _SKU.match(value):
            raise ValueError("SKU 2–40 ký tự, chỉ gồm chữ in hoa, số, gạch ngang, gạch dưới")
        return value


ProductSort = Literal[
    "name",
    "-name",
    "price",
    "-price",
    "stock_quantity",
    "-stock_quantity",
    "created_at",
    "-created_at",
]


class ImportRowError(BaseModel):
    row: int
    message: str


class ProductImportResult(BaseModel):
    created: int
    updated: int
    errors: list[ImportRowError]
