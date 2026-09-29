"""Payment checkout status, bank webhook and development-only confirmation."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header

from app.api.deps import CurrentUserDep, DbDep
from app.schemas.payments import PaymentCheckoutResponse, SepayWebhookPayload, WebhookAck
from app.schemas.profile import ProfileResponse
from app.services import payments as payments_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get(
    "/{payment_id}",
    response_model=PaymentCheckoutResponse,
    summary="Thông tin chuyển khoản QR và trạng thái thanh toán",
)
def read_checkout(payment_id: str, user: CurrentUserDep, db: DbDep) -> PaymentCheckoutResponse:
    """Frontend gọi lặp lại endpoint này cho tới khi ``status`` chuyển sang ``PAID``."""
    return payments_service.get_checkout(db, user["id"], payment_id)


@router.post(
    "/webhooks/sepay",
    response_model=WebhookAck,
    summary="Webhook SePay báo có tiền vào tài khoản",
)
def sepay_webhook(
    payload: SepayWebhookPayload,
    db: DbDep,
    authorization: Annotated[str | None, Header()] = None,
) -> WebhookAck:
    """Xác thực API key, khớp mã chuyển khoản + số tiền rồi mới kích hoạt quyền lợi."""
    return payments_service.handle_sepay_webhook(db, payload, authorization)


@router.post(
    "/{payment_id}/mark-paid",
    response_model=ProfileResponse,
    summary="Giả lập đã nhận tiền (chỉ dev) hoặc Admin xác nhận thủ công",
)
def mark_payment_paid(payment_id: str, user: CurrentUserDep, db: DbDep) -> ProfileResponse:
    """Hội viên chỉ dùng được khi ``allow_payment_simulation`` bật và payment là của mình.

    Ở production quyền lợi chỉ được kích hoạt qua webhook ngân hàng hoặc Admin (ADR-004).
    """
    return payments_service.simulate_payment(db, user, payment_id)
