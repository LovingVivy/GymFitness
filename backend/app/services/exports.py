"""Data exports (CSV, Excel, PDF) built in the background job queue.

``start`` validates the request and the caller's permissions, then queues an
``export.report`` job; ``build`` runs inside the worker, renders the file and
stores it so only the requester can download it through ``/files/{id}``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import status
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core import exporters, storage
from app.core.exporters import Column
from app.core.gym_time import now_utc, to_local
from app.core.permissions import Permission, has_permission
from app.db.base import new_uuid
from app.repositories import jobs as jobs_repository
from app.schemas.jobs import (
    AuditFilter,
    CheckinsFilter,
    ExportRequest,
    JobResponse,
    PaymentsFilter,
    PeriodFilter,
    ProductsFilter,
    UsersFilter,
)
from app.services import admin as admin_service
from app.services import jobs as jobs_service
from app.services import shop as shop_service
from app.services.pt import error
from app.tasks import queue

# Một file xuất tối đa ngần này dòng; đủ cho mọi danh sách của một phòng tập.
EXPORT_LIMIT = 50_000

ROLE_LABELS = {
    "USER": "Hội viên",
    "PT": "Huấn luyện viên",
    "MANAGER": "Quản lý",
    "ADMIN": "Quản trị",
}
STATUS_LABELS = {
    "ACTIVE": "Hoạt động",
    "SUSPENDED": "Tạm khoá",
    "INACTIVE": "Ngưng",
    "PENDING": "Chờ",
    "PAID": "Đã thu",
    "VOID": "Đã huỷ",
    "FAILED": "Thất bại",
    "REFUNDED": "Đã hoàn",
    "DRAFT": "Nháp",
}
PURPOSE_LABELS = {"MEMBERSHIP": "Gói hội viên", "PT_CREDIT": "Buổi PT", "PRODUCT_ORDER": "Đơn hàng"}
METHOD_LABELS = {"QR": "QR", "CASH": "Tiền mặt", "BANK_TRANSFER": "Chuyển khoản", "CARD": "Thẻ"}


def _label(mapping: Mapping[str, str], key: str) -> Callable[[Mapping[str, Any]], str]:
    return lambda row: mapping.get(row.get(key) or "", row.get(key) or "")


@dataclass(frozen=True)
class Report:
    title: str
    permission: Permission
    filters: type[BaseModel]
    columns: tuple[Column, ...]
    rows: Callable[[Session, Any], list[dict[str, Any]]]


def _users(db: Session, f: UsersFilter) -> list[dict[str, Any]]:
    page = admin_service.list_users(
        db,
        search=f.search,
        role=f.role,
        account_status=f.status,
        sort=f.sort,
        page=1,
        page_size=EXPORT_LIMIT,
    )
    return [item.model_dump() for item in page.items]


def _payments(db: Session, f: PaymentsFilter) -> list[dict[str, Any]]:
    page = admin_service.list_payments(
        db,
        search=f.search,
        payment_status=f.status,
        purpose=f.purpose,
        date_from=f.date_from,
        date_to=f.date_to,
        sort=f.sort,
        page=1,
        page_size=EXPORT_LIMIT,
    )
    return [item.model_dump() for item in page.items]


def _checkins(db: Session, f: CheckinsFilter) -> list[dict[str, Any]]:
    page = admin_service.list_checkins(
        db,
        date_from=f.date_from,
        date_to=f.date_to,
        search=f.search,
        inside_only=f.inside_only,
        sort=f.sort,
        page=1,
        page_size=EXPORT_LIMIT,
    )
    return [item.model_dump() for item in page.items]


def _products(db: Session, f: ProductsFilter) -> list[dict[str, Any]]:
    page = shop_service.list_admin_products(
        db,
        search=f.search,
        activity_type=f.activity_type,
        product_status=f.status,
        sort=f.sort,
        page=1,
        page_size=EXPORT_LIMIT,
    )
    return [item.model_dump() for item in page.items]


def _revenue(db: Session, f: PeriodFilter) -> list[dict[str, Any]]:
    report = admin_service.revenue_report(db, f.period, f.count, use_cache=False)
    return [bucket.model_dump() for bucket in report.buckets]


def _growth(db: Session, f: PeriodFilter) -> list[dict[str, Any]]:
    report = admin_service.member_growth(db, f.period, f.count, use_cache=False)
    return [bucket.model_dump() for bucket in report.buckets]


def _audit(db: Session, f: AuditFilter) -> list[dict[str, Any]]:
    page = admin_service.list_audit_logs(
        db,
        entity_type=f.entity_type,
        entity_id=None,
        action=f.action,
        search=f.search,
        date_from=f.date_from,
        date_to=f.date_to,
        page=1,
        page_size=EXPORT_LIMIT,
    )
    return [item.model_dump() for item in page.items]


REPORTS: dict[str, Report] = {
    "users": Report(
        "Danh sách tài khoản",
        Permission.USERS_VIEW,
        UsersFilter,
        (
            Column("full_name", "Họ tên", width=1.6),
            Column("email", "Email", width=1.8),
            Column("phone", "Điện thoại"),
            Column("role", "Vai trò", value=_label(ROLE_LABELS, "role")),
            Column("status", "Trạng thái", value=_label(STATUS_LABELS, "status")),
            Column("code", "Mã", value=lambda r: r.get("member_code") or r.get("employee_code")),
            Column("active_plan_name", "Gói đang dùng", width=1.3),
            Column("active_plan_end_at", "Hết hạn", "datetime"),
            Column("created_at", "Ngày tạo", "datetime"),
            Column("last_login_at", "Đăng nhập gần nhất", "datetime"),
        ),
        _users,
    ),
    "payments": Report(
        "Danh sách giao dịch",
        Permission.PAYMENTS_VIEW,
        PaymentsFilter,
        (
            Column("payment_number", "Mã giao dịch", width=1.5),
            Column("created_at", "Tạo lúc", "datetime"),
            Column("member_name", "Hội viên", width=1.5),
            Column("member_code", "Mã hội viên"),
            Column("purpose", "Loại", value=_label(PURPOSE_LABELS, "purpose")),
            Column(
                "content",
                "Nội dung",
                width=1.6,
                value=lambda r: " + ".join(
                    part
                    for part in (
                        r.get("plan_name"),
                        f"{r['pt_quantity']} buổi PT" if r.get("pt_quantity") else None,
                    )
                    if part
                ),
            ),
            Column("amount", "Số tiền", "money"),
            Column("method", "Hình thức", value=_label(METHOD_LABELS, "method")),
            Column("status", "Trạng thái", value=_label(STATUS_LABELS, "status")),
            Column("paid_at", "Thu tiền lúc", "datetime"),
        ),
        _payments,
    ),
    "checkins": Report(
        "Lịch sử ra vào",
        Permission.CHECKINS_VIEW,
        CheckinsFilter,
        (
            Column("member_name", "Hội viên", width=1.6),
            Column("member_code", "Mã hội viên"),
            Column("member_phone", "Điện thoại"),
            Column("plan_name", "Gói tập", width=1.3),
            Column("check_in_at", "Vào lúc", "datetime"),
            Column("check_out_at", "Ra lúc", "datetime"),
            Column("duration_minutes", "Số phút", "int"),
            Column("method", "Cách check-in"),
        ),
        _checkins,
    ),
    "products": Report(
        "Danh sách sản phẩm",
        Permission.PRODUCTS_VIEW,
        ProductsFilter,
        (
            Column("sku", "SKU"),
            Column("name", "Tên sản phẩm", width=2),
            Column("category_name", "Danh mục"),
            Column("activity_type", "Nhóm"),
            Column("price", "Giá", "money"),
            Column("stock_quantity", "Tồn kho", "int"),
            Column("status", "Trạng thái", value=_label(STATUS_LABELS, "status")),
        ),
        _products,
    ),
    "revenue": Report(
        "Báo cáo doanh thu",
        Permission.REPORTS_VIEW,
        PeriodFilter,
        (
            Column("label", "Kỳ"),
            Column("total", "Tổng doanh thu", "money"),
            Column("membership_total", "Gói hội viên", "money"),
            Column("pt_total", "Buổi PT", "money"),
            Column("other_total", "Khác", "money"),
            Column("payment_count", "Số giao dịch", "int"),
        ),
        _revenue,
    ),
    "member_growth": Report(
        "Báo cáo tăng trưởng hội viên",
        Permission.REPORTS_VIEW,
        PeriodFilter,
        (
            Column("label", "Kỳ"),
            Column("new_members", "Hội viên mới", "int"),
            Column("total_members", "Tổng hội viên cuối kỳ", "int"),
        ),
        _growth,
    ),
    "audit_logs": Report(
        "Nhật ký thao tác",
        Permission.AUDIT_VIEW,
        AuditFilter,
        (
            Column("created_at", "Thời điểm", "datetime"),
            Column(
                "actor_name",
                "Người thực hiện",
                width=1.4,
                value=lambda r: r.get("actor_name") or r.get("actor_email") or "Hệ thống",
            ),
            Column("actor_role", "Vai trò", value=_label(ROLE_LABELS, "actor_role")),
            Column("action", "Hành động", width=1.3),
            Column("entity_type", "Đối tượng"),
            Column("entity_id", "Mã đối tượng", width=2),
        ),
        _audit,
    ),
}


def _validated_filters(report: Report, raw: Mapping[str, Any]) -> BaseModel:
    try:
        return report.filters.model_validate(raw)
    except ValidationError as exc:
        raise error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_FILTERS",
            "Bộ lọc xuất dữ liệu không hợp lệ.",
            {"errors": exc.errors(include_context=False, include_url=False)},
        ) from exc


def start(db: Session, user: Mapping[str, Any], payload: ExportRequest) -> JobResponse:
    report = REPORTS[payload.report]
    if not (
        has_permission(user["role"], Permission.REPORTS_EXPORT)
        and has_permission(user["role"], report.permission)
    ):
        raise error(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "Tài khoản của bạn không có quyền xuất dữ liệu này.",
        )
    filters = _validated_filters(report, payload.filters)
    job_id = queue.enqueue(
        db,
        "export.report",
        {
            "report": payload.report,
            "format": payload.format,
            "filters": filters.model_dump(mode="json", exclude_none=True),
        },
        requested_by=user["id"],
    )
    return jobs_service.get_job(db, user, job_id)


def _subtitle(filters: Mapping[str, Any], created: datetime) -> str:
    parts = [f"{key}: {value}" for key, value in filters.items() if value not in (None, "", False)]
    text = "Bộ lọc: " + (", ".join(parts) if parts else "tất cả")
    return f"{text} · Xuất lúc {to_local(created):%d/%m/%Y %H:%M} (GMT+7)"


def build(
    db: Session,
    parameters: Mapping[str, Any],
    requested_by: str | None,
    progress: Callable[[int], None] | None = None,
) -> str:
    """Render the export and store it; return the new file id."""
    report = REPORTS[parameters["report"]]
    fmt = parameters.get("format", "xlsx")
    filters = report.filters.model_validate(parameters.get("filters") or {})
    rows = report.rows(db, filters)
    if progress:
        progress(60)

    created = now_utc()
    content = exporters.render(
        fmt, report.title, _subtitle(parameters.get("filters") or {}, created), report.columns, rows
    )
    stored = storage.save_document(
        content, "exports", f".{fmt}", exporters.CONTENT_TYPES[fmt].split(";")[0]
    )
    file_id = new_uuid()
    jobs_repository.save_file(
        db,
        file_id=file_id,
        owner_user_id=requested_by,
        storage_key=stored.storage_key,
        original_name=f"{parameters['report']}-{to_local(created):%Y%m%d-%H%M}.{fmt}",
        content_type=exporters.CONTENT_TYPES[fmt],
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
    )
    return file_id
