"""Schemas for background jobs and data exports."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.admin import (
    AccountStatus,
    CheckinSort,
    PaymentPurpose,
    PaymentSort,
    PaymentStatus,
    RevenuePeriod,
    Role,
    UserSort,
)
from app.schemas.profile import UtcDateTime
from app.schemas.shop import ActivityType, ProductSort, ProductStatus

ExportReport = Literal[
    "users", "payments", "checkins", "products", "revenue", "member_growth", "audit_logs"
]
ExportFormat = Literal["csv", "xlsx", "pdf"]


class ExportRequest(BaseModel):
    report: ExportReport
    format: ExportFormat = "xlsx"
    # Cùng bộ lọc với màn hình danh sách tương ứng, ví dụ {"status": "PAID"}.
    filters: dict[str, Any] = Field(default_factory=dict)


class UsersFilter(BaseModel):
    search: str | None = Field(default=None, max_length=150)
    role: Role | None = None
    status: AccountStatus | None = None
    sort: UserSort | None = None


class PaymentsFilter(BaseModel):
    search: str | None = Field(default=None, max_length=150)
    status: PaymentStatus | None = None
    purpose: PaymentPurpose | None = None
    date_from: date | None = None
    date_to: date | None = None
    sort: PaymentSort | None = None


class CheckinsFilter(BaseModel):
    search: str | None = Field(default=None, max_length=150)
    date_from: date | None = None
    date_to: date | None = None
    inside_only: bool = False
    sort: CheckinSort | None = None


class ProductsFilter(BaseModel):
    search: str | None = Field(default=None, max_length=150)
    activity_type: ActivityType | None = None
    status: ProductStatus | None = None
    sort: ProductSort | None = None


class PeriodFilter(BaseModel):
    period: RevenuePeriod = "MONTH"
    count: int | None = Field(default=None, ge=1, le=60)


class AuditFilter(BaseModel):
    entity_type: str | None = Field(default=None, max_length=80)
    action: str | None = Field(default=None, max_length=100)
    search: str | None = Field(default=None, max_length=150)
    date_from: date | None = None
    date_to: date | None = None


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: Literal["PENDING", "RUNNING", "SUCCESS", "FAILED"]
    progress: int
    error_message: str | None = None
    created_at: UtcDateTime
    started_at: UtcDateTime | None = None
    finished_at: UtcDateTime | None = None
    file_id: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    # Tải bằng GET kèm token (chỉ người yêu cầu tải được).
    download_url: str | None = None
