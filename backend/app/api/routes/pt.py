"""PT credit wallet and PT sessions for members and trainers."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserDep, DbDep, TrainerDep
from app.core.config import get_settings
from app.schemas.pt import (
    PtBookingCancelRequest,
    PtBookingCreateRequest,
    PtBookingResponse,
    PtCancelResponse,
    PtCreditPurchaseRequest,
    PtCreditSummary,
    PtPrice,
)
from app.services import pt as pt_service
from app.services import pt_schedule as schedule_service

router = APIRouter(tags=["pt"])


# --------------------------------------------------------------------------
# Wallet
# --------------------------------------------------------------------------


@router.get("/pt-credits/price", response_model=PtPrice, summary="Giá một lượt PT")
def read_pt_price() -> PtPrice:
    """Công khai: trang chọn gói và trang đặt PT hiển thị đúng giá đang bán."""
    settings = get_settings()
    return PtPrice(
        unit_price=settings.pt_session_price, session_minutes=settings.pt_session_minutes
    )


@router.get("/pt-credits", response_model=PtCreditSummary, summary="Ví lượt PT của tôi")
def read_pt_credits(user: CurrentUserDep, db: DbDep) -> PtCreditSummary:
    return pt_service.get_pt_credit(db, user["id"])


@router.post(
    "/pt-credits/purchase",
    status_code=status.HTTP_201_CREATED,
    summary="Mua thêm buổi PT (payment PENDING)",
)
def purchase_pt_credits(
    payload: PtCreditPurchaseRequest,
    user: CurrentUserDep,
    db: DbDep,
) -> dict:
    """Tạo payment PENDING; lượt chỉ được cộng sau bước xác nhận ở backend."""
    return pt_service.purchase_pt_credit(db, user["id"], payload.quantity)


# --------------------------------------------------------------------------
# Sessions (ADR-015): đặt là xác nhận ngay, không còn bước PT duyệt.
# --------------------------------------------------------------------------


@router.get(
    "/pt-bookings/teaching",
    response_model=list[PtBookingResponse],
    summary="Buổi dạy của tôi (PT)",
)
def read_teaching_sessions(
    user: TrainerDep,
    db: DbDep,
    booking_status: str | None = Query(
        default=None, description="Lọc theo trạng thái, ví dụ ACCEPTED"
    ),
) -> list[PtBookingResponse]:
    """Buổi sắp tới trước (tăng dần theo giờ), sau đó là lịch sử."""
    return pt_service.list_trainer_bookings(db, user["id"], booking_status)


@router.get("/pt-bookings", response_model=list[PtBookingResponse], summary="Buổi PT của tôi")
def read_my_bookings(user: CurrentUserDep, db: DbDep) -> list[PtBookingResponse]:
    return pt_service.list_my_bookings(db, user["id"])


@router.post(
    "/pt-bookings",
    response_model=PtBookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đặt một ô trống của PT (xác nhận ngay)",
)
def create_booking(
    payload: PtBookingCreateRequest,
    user: CurrentUserDep,
    db: DbDep,
) -> PtBookingResponse:
    """Giữ 1 lượt PT, buổi ở trạng thái ACCEPTED và PT nhận thông báo."""
    return schedule_service.book_session(db, user["id"], payload)


@router.post(
    "/pt-bookings/{booking_id}/cancel",
    response_model=PtCancelResponse,
    summary="Huỷ buổi PT (hội viên hoặc PT phụ trách)",
)
def cancel_booking(
    booking_id: str,
    user: CurrentUserDep,
    db: DbDep,
    payload: PtBookingCancelRequest | None = None,
) -> PtCancelResponse:
    """PT huỷ phải có lý do và luôn hoàn lượt; hội viên huỷ sớm mới được hoàn lượt."""
    reason = payload.reason if payload else None
    return schedule_service.cancel_session(db, user["id"], booking_id, reason)


@router.post(
    "/pt-bookings/{booking_id}/complete",
    response_model=PtBookingResponse,
    summary="PT xác nhận buổi đã hoàn thành",
)
def complete_booking(booking_id: str, user: TrainerDep, db: DbDep) -> PtBookingResponse:
    return schedule_service.finish_session(db, user["id"], booking_id, "COMPLETED")


@router.post(
    "/pt-bookings/{booking_id}/no-show",
    response_model=PtBookingResponse,
    summary="PT ghi nhận hội viên vắng mặt",
)
def mark_no_show(booking_id: str, user: TrainerDep, db: DbDep) -> PtBookingResponse:
    return schedule_service.finish_session(db, user["id"], booking_id, "NO_SHOW")
