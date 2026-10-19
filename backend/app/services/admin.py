"""Admin area: default admin, accounts, plans, check-ins, payments, reports (ADR-016/017)."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.core import cache
from app.core.config import get_settings
from app.core.gym_time import gym_tz, now_utc, to_local, to_naive_utc
from app.core.permissions import can_manage_account
from app.core.security import hash_password
from app.db.base import new_uuid
from app.repositories import admin as admin_repository
from app.schemas.admin import (
    AdminOverview,
    AdminPasswordReset,
    AdminPayment,
    AdminPaymentPage,
    AdminPlan,
    AdminPlanSave,
    AdminUser,
    AdminUserCreate,
    AdminUserPage,
    AdminUserUpdate,
    AuditLogEntry,
    AuditLogPage,
    CheckinCreate,
    CheckinCreated,
    CheckinLog,
    CheckinPage,
    MemberGrowthBucket,
    MemberGrowthReport,
    PaymentConfirm,
    PaymentVoid,
    RevenueBucket,
    RevenueReport,
)
from app.services import payments as payments_service
from app.services.pt import error, raise_for_outcome

logger = logging.getLogger(__name__)

_ERRORS: dict[str, tuple[int, str]] = {
    "USER_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy tài khoản."),
    "EMAIL_EXISTS": (status.HTTP_409_CONFLICT, "Email này đã được sử dụng."),
    "PHONE_EXISTS": (status.HTTP_409_CONFLICT, "Số điện thoại này đã được sử dụng."),
    "USERNAME_EXISTS": (status.HTTP_409_CONFLICT, "Tên đăng nhập này đã được sử dụng."),
    "DUPLICATE": (status.HTTP_409_CONFLICT, "Thông tin đăng nhập bị trùng."),
    "INVALID_ROLE": (status.HTTP_422_UNPROCESSABLE_CONTENT, "Vai trò không hợp lệ."),
    "CANNOT_DELETE_SELF": (
        status.HTTP_409_CONFLICT,
        "Không thể tự xoá tài khoản đang đăng nhập.",
    ),
    "LAST_ADMIN": (status.HTTP_409_CONFLICT, "Phải còn ít nhất một tài khoản quản trị."),
    "HAS_UPCOMING_SESSIONS": (status.HTTP_409_CONFLICT, "Tài khoản còn buổi PT sắp tới."),
    "PLAN_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy gói tập."),
    "PLAN_CODE_EXISTS": (status.HTTP_409_CONFLICT, "Mã gói này đã tồn tại."),
    "INVALID_PLAN": (status.HTTP_422_UNPROCESSABLE_CONTENT, "Thông tin gói tập không hợp lệ."),
    "MEMBER_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy hội viên."),
    "NO_ACTIVE_SUBSCRIPTION": (
        status.HTTP_409_CONFLICT,
        "Hội viên không có gói tập còn hiệu lực.",
    ),
    "ALREADY_INSIDE": (status.HTTP_409_CONFLICT, "Hội viên đang ở trong phòng tập."),
    "CHECKIN_NOT_OPEN": (status.HTTP_409_CONFLICT, "Lượt vào này đã check-out."),
    "PAYMENT_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy giao dịch thanh toán."),
    "PAYMENT_NOT_PENDING": (
        status.HTTP_409_CONFLICT,
        "Chỉ xử lý được giao dịch đang chờ thanh toán.",
    ),
    "VERSION_CONFLICT": (
        status.HTTP_409_CONFLICT,
        "Bản ghi vừa được người khác sửa. Tải lại để xem bản mới nhất.",
    ),
    "INTERNAL_ERROR": (status.HTTP_500_INTERNAL_SERVER_ERROR, "Lỗi hệ thống."),
}


def _forbidden_account() -> Exception:
    return error(
        status.HTTP_403_FORBIDDEN,
        "FORBIDDEN",
        "Tài khoản của bạn chỉ quản lý được tài khoản hội viên.",
    )


def _fail(outcome, fallback: str) -> None:
    raise_for_outcome(outcome, _ERRORS, fallback)


def _local_midnight_utc(day: date) -> datetime:
    """00:00 of a gym-local day, as naive UTC for ``DATETIME`` comparisons."""
    return to_naive_utc(datetime.combine(day, time(), tzinfo=gym_tz()))


def _today_local() -> date:
    return to_local(now_utc()).date()


# --------------------------------------------------------------------------
# Default admin
# --------------------------------------------------------------------------


def ensure_default_admin(db: Session) -> bool:
    """Create the configured admin account once; never overwrite an existing password."""
    settings = get_settings()
    if not settings.admin_default_password:
        logger.info("ADMIN_DEFAULT_PASSWORD trống — bỏ qua tạo admin mặc định.")
        return False

    created = admin_repository.bootstrap(
        db,
        user_id=new_uuid(),
        username=settings.admin_username.strip().lower(),
        email=settings.admin_email.strip().lower(),
        password_hash=hash_password(settings.admin_default_password),
        full_name=settings.admin_full_name,
    )
    if created:
        logger.warning("Đã tạo tài khoản admin mặc định '%s'.", settings.admin_username)
    return created


# --------------------------------------------------------------------------
# Overview
# --------------------------------------------------------------------------


def _percent_change(current: Decimal | int, previous: Decimal | int) -> float | None:
    """Growth of ``current`` over ``previous`` in percent; ``None`` without a baseline."""
    if previous <= 0:
        return None
    return round(float((Decimal(current) - Decimal(previous)) / Decimal(previous) * 100), 1)


def overview(db: Session) -> AdminOverview:
    today = _today_local()
    month_start = today.replace(day=1)
    row = admin_repository.overview(
        db,
        day_start=_local_midnight_utc(today),
        month_start=_local_midnight_utc(month_start),
        prev_month_start=_local_midnight_utc(_shift(month_start, "MONTH", -1)),
    )
    new_members = int(row.get("new_members_this_month") or 0)
    new_members_before = int(row.get("new_members_last_month") or 0)
    revenue = Decimal(row.get("revenue_this_month") or 0)
    revenue_before = Decimal(row.get("revenue_last_month") or 0)
    return AdminOverview(
        members=int(row.get("members") or 0),
        new_members_this_month=new_members,
        new_members_last_month=new_members_before,
        member_growth_percent=_percent_change(new_members, new_members_before),
        trainers=int(row.get("trainers") or 0),
        active_members=int(row.get("active_members") or 0),
        checkins_today=int(row.get("checkins_today") or 0),
        inside_now=int(row.get("inside_now") or 0),
        revenue_this_month=revenue,
        revenue_last_month=revenue_before,
        revenue_growth_percent=_percent_change(revenue, revenue_before),
        pending_payments=int(row.get("pending_payments") or 0),
        products=int(row.get("products") or 0),
    )


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------


def _to_user(row: Mapping[str, Any]) -> AdminUser:
    locked_until = row.get("locked_until")
    specialties = row.get("specialties")
    return AdminUser(
        id=row["id"],
        email=row["email"],
        username=row.get("username"),
        phone=row.get("phone"),
        role=row["role"],
        status=row["status"],
        full_name=row.get("full_name"),
        member_code=row.get("member_code"),
        employee_code=row.get("employee_code"),
        hourly_rate=row.get("hourly_rate"),
        bio=row.get("bio"),
        specialties=[item for item in (specialties or "").split(",") if item],
        has_schedule=bool(row.get("schedule_slots")),
        active_plan_name=row.get("active_plan_name"),
        active_plan_end_at=row.get("active_plan_end_at"),
        created_at=row.get("created_at"),
        last_login_at=row.get("last_login_at"),
        locked=bool(locked_until and locked_until > to_naive_utc(now_utc())),
    )


def list_users(
    db: Session,
    *,
    search: str | None,
    role: str | None,
    account_status: str | None,
    page: int,
    page_size: int,
    sort: str | None = None,
) -> AdminUserPage:
    rows = admin_repository.list_users(
        db,
        search=search,
        role=role,
        status=account_status,
        sort=sort,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    total = int(rows[0]["total_count"]) if rows else 0
    return AdminUserPage(items=[_to_user(row) for row in rows], total=total)


def _find_user(db: Session, user_id: str) -> AdminUser:
    rows = admin_repository.list_users(
        db, user_id=user_id, search=None, role=None, status=None, limit=1, offset=0
    )
    row = rows[0] if rows else None
    if row is None:
        raise error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "Không tìm thấy tài khoản.")
    return _to_user(row)


def create_user(
    db: Session, actor_id: str, payload: AdminUserCreate, actor_role: str = "ADMIN"
) -> AdminUser:
    if not can_manage_account(actor_role, payload.role):
        raise _forbidden_account()
    user_id = new_uuid()
    outcome = admin_repository.create_user(
        db,
        user_id=user_id,
        profile_id=new_uuid(),
        email=payload.email,
        username=payload.username or None,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        hourly_rate=None if payload.hourly_rate is None else Decimal(str(payload.hourly_rate)),
        bio=payload.bio,
        specialties=list(payload.specialties) if payload.role == "PT" else [],
        actor_id=actor_id,
    )
    if not outcome.succeeded:
        _fail(outcome, "Không thể tạo tài khoản.")
    cache.invalidate(cache.REPORTS, cache.CATALOG)
    return _find_user(db, user_id)


def update_user(
    db: Session,
    actor_id: str,
    user_id: str,
    payload: AdminUserUpdate,
    actor_role: str = "ADMIN",
) -> AdminUser:
    if not can_manage_account(actor_role, _find_user(db, user_id).role):
        raise _forbidden_account()
    if user_id == actor_id and payload.status not in (None, "ACTIVE"):
        raise error(
            status.HTTP_409_CONFLICT,
            "CANNOT_DISABLE_SELF",
            "Không thể tự khoá tài khoản đang đăng nhập.",
        )
    outcome = admin_repository.update_user(
        db,
        user_id=user_id,
        email=payload.email,
        username=payload.username,
        phone=payload.phone,
        full_name=payload.full_name,
        status=payload.status,
        hourly_rate=None if payload.hourly_rate is None else Decimal(str(payload.hourly_rate)),
        bio=payload.bio,
        specialties=None if payload.specialties is None else list(payload.specialties),
        actor_id=actor_id,
        utc_offset_minutes=get_settings().gym_utc_offset_minutes,
    )
    if not outcome.succeeded:
        _fail(outcome, "Không thể cập nhật tài khoản.")
    cache.invalidate(cache.CATALOG)
    user = _find_user(db, user_id)
    # Khoá/ngưng tài khoản: số buổi PT sắp tới đã được huỷ và hoàn lượt.
    user.cancelled_sessions = int(outcome.data.get("cancelled_sessions") or 0)
    return user


def reset_password(
    db: Session,
    actor_id: str,
    user_id: str,
    payload: AdminPasswordReset,
    actor_role: str = "ADMIN",
) -> None:
    if not can_manage_account(actor_role, _find_user(db, user_id).role):
        raise _forbidden_account()
    outcome = admin_repository.set_password(
        db, user_id=user_id, password_hash=hash_password(payload.password), actor_id=actor_id
    )
    if not outcome.succeeded:
        _fail(outcome, "Không thể đặt lại mật khẩu.")


def delete_user(db: Session, actor_id: str, user_id: str) -> None:
    outcome = admin_repository.delete_user(db, user_id=user_id, actor_id=actor_id)
    if not outcome.succeeded:
        _fail(outcome, "Không thể xoá tài khoản.")
    cache.invalidate(cache.REPORTS, cache.CATALOG)


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------


def list_plans(db: Session) -> list[AdminPlan]:
    return [
        AdminPlan(**{**row, "is_active": bool(row["is_active"])})
        for row in admin_repository.list_plans(db)
    ]


def save_plan(
    db: Session, actor_id: str, payload: AdminPlanSave, plan_id: str | None = None
) -> AdminPlan:
    target_id = plan_id or new_uuid()
    outcome = admin_repository.save_plan(
        db,
        plan_id=target_id,
        is_new=plan_id is None,
        code=payload.code,
        name=payload.name,
        activity_type=payload.activity_type,
        description=payload.description,
        duration_months=payload.duration_months,
        duration_days=payload.duration_days,
        price=Decimal(str(payload.price)),
        is_active=payload.is_active,
        expected_version=payload.row_version if plan_id else None,
        actor_id=actor_id,
    )
    if not outcome.succeeded:
        _fail(outcome, "Không thể lưu gói tập.")
    cache.invalidate(cache.CATALOG)
    plan = next((item for item in list_plans(db) if item.id == target_id), None)
    if plan is None:
        raise error(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Không đọc lại được gói."
        )
    return plan


def delete_plan(db: Session, actor_id: str, plan_id: str) -> None:
    outcome = admin_repository.delete_plan(db, plan_id=plan_id, actor_id=actor_id)
    if not outcome.succeeded:
        _fail(outcome, "Không thể xoá gói tập.")
    cache.invalidate(cache.CATALOG)


# --------------------------------------------------------------------------
# Check-in logs
# --------------------------------------------------------------------------


def list_checkins(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    search: str | None,
    inside_only: bool,
    page: int,
    page_size: int,
    sort: str | None = None,
) -> CheckinPage:
    today = _today_local()
    first = date_from or today - timedelta(days=6)
    last = date_to or today
    if last < first:
        first, last = last, first

    rows = admin_repository.list_checkins(
        db,
        start_from=_local_midnight_utc(first),
        start_to=_local_midnight_utc(last + timedelta(days=1)),
        search=search,
        inside_only=inside_only,
        sort=sort,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    items = []
    for row in rows:
        check_in, check_out = row["check_in_at"], row.get("check_out_at")
        minutes = int((check_out - check_in).total_seconds() // 60) if check_out else None
        items.append(
            CheckinLog(
                **{key: row.get(key) for key in CheckinLog.model_fields if key in row},
                duration_minutes=minutes,
            )
        )
    total = int(rows[0]["total_count"]) if rows else 0
    return CheckinPage(items=items, total=total)


def create_checkin(db: Session, actor_id: str, payload: CheckinCreate) -> CheckinCreated:
    checkin_id = new_uuid()
    outcome = admin_repository.create_checkin(
        db, checkin_id=checkin_id, identifier=payload.identifier, actor_id=actor_id
    )
    if not outcome.succeeded:
        _fail(outcome, "Không thể check-in.")
    return CheckinCreated(id=checkin_id, member_name=outcome.data.get("member_name"))


def checkout(db: Session, actor_id: str, checkin_id: str) -> None:
    outcome = admin_repository.checkout(db, checkin_id=checkin_id, actor_id=actor_id)
    if not outcome.succeeded:
        _fail(outcome, "Không thể check-out.")


# --------------------------------------------------------------------------
# Revenue
# --------------------------------------------------------------------------

DEFAULT_BUCKETS = {"WEEK": 12, "MONTH": 12, "QUARTER": 8, "YEAR": 5}


def _period_start(day: date, period: str) -> date:
    if period == "WEEK":
        return day - timedelta(days=day.weekday())
    if period == "MONTH":
        return day.replace(day=1)
    if period == "QUARTER":
        return date(day.year, (day.month - 1) // 3 * 3 + 1, 1)
    return date(day.year, 1, 1)


def _shift(start: date, period: str, steps: int) -> date:
    """Move a period start by ``steps`` whole periods (negative = back in time)."""
    if period == "WEEK":
        return start + timedelta(weeks=steps)
    months = {"MONTH": 1, "QUARTER": 3, "YEAR": 12}[period] * steps
    index = start.year * 12 + (start.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def _label(start: date, period: str) -> str:
    if period == "WEEK":
        return f"Tuần {start:%d/%m}"
    if period == "MONTH":
        return f"T{start.month}/{start.year}"
    if period == "QUARTER":
        return f"Q{(start.month - 1) // 3 + 1}/{start.year}"
    return str(start.year)


def revenue_report(
    db: Session, period: str, count: int | None = None, use_cache: bool = True
) -> RevenueReport:
    """Revenue of the last ``count`` periods (current one included), zero-filled."""
    if use_cache:
        return cache.get_or_load(
            cache.REPORTS,
            f"revenue:{period}:{count}:{_today_local().isoformat()}",
            get_settings().cache_report_ttl_seconds,
            lambda: revenue_report(db, period, count, use_cache=False),
            RevenueReport,
        )
    size = count or DEFAULT_BUCKETS[period]
    current = _period_start(_today_local(), period)
    starts = [_shift(current, period, offset) for offset in range(-(size - 1), 1)]
    end = _shift(current, period, 1)

    rows = admin_repository.revenue(
        db,
        start_from=_local_midnight_utc(starts[0]),
        start_to=_local_midnight_utc(end),
        period=period,
        offset_minutes=get_settings().gym_utc_offset_minutes,
    )
    by_start = {row["period_start"]: row for row in rows}

    buckets = []
    for start in starts:
        row = by_start.get(start.isoformat(), {})
        buckets.append(
            RevenueBucket(
                period_start=start.isoformat(),
                label=_label(start, period),
                total=Decimal(row.get("total") or 0),
                membership_total=Decimal(row.get("membership_total") or 0),
                pt_total=Decimal(row.get("pt_total") or 0),
                other_total=Decimal(row.get("other_total") or 0),
                payment_count=int(row.get("payment_count") or 0),
            )
        )

    change = _percent_change(buckets[-1].total, buckets[-2].total) if len(buckets) >= 2 else None

    return RevenueReport(
        period=period,
        buckets=buckets,
        total=sum((bucket.total for bucket in buckets), Decimal(0)),
        membership_total=sum((bucket.membership_total for bucket in buckets), Decimal(0)),
        pt_total=sum((bucket.pt_total for bucket in buckets), Decimal(0)),
        payment_count=sum(bucket.payment_count for bucket in buckets),
        change_percent=change,
    )


# --------------------------------------------------------------------------
# Member growth
# --------------------------------------------------------------------------


def member_growth(
    db: Session, period: str, count: int | None = None, use_cache: bool = True
) -> MemberGrowthReport:
    """New members of the last ``count`` periods and the running member total."""
    if use_cache:
        return cache.get_or_load(
            cache.REPORTS,
            f"growth:{period}:{count}:{_today_local().isoformat()}",
            get_settings().cache_report_ttl_seconds,
            lambda: member_growth(db, period, count, use_cache=False),
            MemberGrowthReport,
        )
    size = count or DEFAULT_BUCKETS[period]
    current = _period_start(_today_local(), period)
    starts = [_shift(current, period, offset) for offset in range(-(size - 1), 1)]
    range_start = _local_midnight_utc(starts[0])

    rows = admin_repository.member_growth(
        db,
        start_from=range_start,
        start_to=_local_midnight_utc(_shift(current, period, 1)),
        period=period,
        offset_minutes=get_settings().gym_utc_offset_minutes,
    )
    by_start = {row["period_start"]: int(row["new_members"]) for row in rows}
    base = admin_repository.member_base(db, before=range_start)

    buckets = []
    running = base
    for start in starts:
        new_members = by_start.get(start.isoformat(), 0)
        running += new_members
        buckets.append(
            MemberGrowthBucket(
                period_start=start.isoformat(),
                label=_label(start, period),
                new_members=new_members,
                total_members=running,
            )
        )

    previous = buckets[-2] if len(buckets) >= 2 else None
    return MemberGrowthReport(
        period=period,
        buckets=buckets,
        total_members=running,
        new_members=running - base,
        change_percent=(
            _percent_change(buckets[-1].new_members, previous.new_members) if previous else None
        ),
        total_growth_percent=(
            _percent_change(buckets[-1].total_members, previous.total_members) if previous else None
        ),
    )


# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------


def _to_payment(row: Mapping[str, Any]) -> AdminPayment:
    return AdminPayment(**{key: row.get(key) for key in AdminPayment.model_fields})


def list_payments(
    db: Session,
    *,
    search: str | None,
    payment_status: str | None,
    purpose: str | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
    sort: str | None = None,
) -> AdminPaymentPage:
    if date_from and date_to and date_to < date_from:
        date_from, date_to = date_to, date_from

    rows = admin_repository.list_payments(
        db,
        search=search,
        status=payment_status,
        purpose=purpose,
        created_from=_local_midnight_utc(date_from) if date_from else None,
        created_to=_local_midnight_utc(date_to + timedelta(days=1)) if date_to else None,
        sort=sort,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return AdminPaymentPage(
        items=[_to_payment(row) for row in rows],
        total=int(rows[0]["total_count"]) if rows else 0,
        paid_total=Decimal(rows[0]["paid_total"] or 0) if rows else Decimal(0),
    )


def _find_payment(db: Session, payment_id: str) -> AdminPayment:
    rows = admin_repository.list_payments(
        db,
        payment_id=payment_id,
        search=None,
        status=None,
        purpose=None,
        created_from=None,
        created_to=None,
        limit=1,
        offset=0,
    )
    if not rows:
        raise error(
            status.HTTP_404_NOT_FOUND, "PAYMENT_NOT_FOUND", "Không tìm thấy giao dịch thanh toán."
        )
    return _to_payment(rows[0])


def confirm_payment(
    db: Session, actor_id: str, payment_id: str, payload: PaymentConfirm
) -> AdminPayment:
    """Mark a pending payment as received and grant what it bought (ADR-004)."""
    payments_service.confirm_by_admin(db, actor_id, payment_id)
    admin_repository.log_payment_confirm(
        db, payment_id=payment_id, method=payload.method, actor_id=actor_id
    )
    return _find_payment(db, payment_id)


def void_payment(db: Session, actor_id: str, payment_id: str, payload: PaymentVoid) -> AdminPayment:
    outcome = admin_repository.void_payment(
        db, payment_id=payment_id, reason=payload.reason, actor_id=actor_id
    )
    if not outcome.succeeded:
        _fail(outcome, "Không thể huỷ giao dịch.")
    return _find_payment(db, payment_id)


# --------------------------------------------------------------------------
# Audit log
# --------------------------------------------------------------------------


def _json(value: Any) -> dict | None:
    if value is None or isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def list_audit_logs(
    db: Session,
    *,
    entity_type: str | None,
    entity_id: str | None,
    action: str | None,
    search: str | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
) -> AuditLogPage:
    """Who did what and when, newest first; before/after data is the record's history."""
    if date_from and date_to and date_to < date_from:
        date_from, date_to = date_to, date_from
    rows = admin_repository.list_audit_logs(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        search=search,
        created_from=_local_midnight_utc(date_from) if date_from else None,
        created_to=_local_midnight_utc(date_to + timedelta(days=1)) if date_to else None,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    items = [
        AuditLogEntry(
            **{
                **{key: row.get(key) for key in AuditLogEntry.model_fields},
                "before_data": _json(row.get("before_data")),
                "after_data": _json(row.get("after_data")),
            }
        )
        for row in rows
    ]
    return AuditLogPage(items=items, total=int(rows[0]["total_count"]) if rows else 0)
