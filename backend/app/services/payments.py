"""QR bank-transfer checkout, automatic confirmation via webhook (ADR-004, ADR-012).

Flow:
1. ``POST /subscriptions`` or ``POST /pt-credits/purchase`` creates a PENDING
   payment whose ``payment_number`` is the transfer code.
2. The client shows the VietQR from :func:`get_checkout` and polls it.
3. SePay calls :func:`handle_sepay_webhook` when money lands; after checking the
   API key, the code and the amount, the benefit is granted by the same stored
   procedure the rest of the system uses.

Nothing the member's browser sends can mark a payment as paid, except the
explicit development-only simulation in :func:`simulate_payment`.
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from urllib.parse import quote, urlencode

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.payment_code import extract_payment_number
from app.core.security import utcnow
from app.db.base import new_uuid
from app.models.enums import UserRole
from app.repositories import payments as payments_repository
from app.repositories import profile as profile_repository
from app.repositories import pt as pt_repository
from app.repositories.procedures import INTERNAL_ERROR, ProcedureOutcome
from app.schemas.payments import (
    PaymentBankInfo,
    PaymentCheckoutResponse,
    SepayWebhookPayload,
    WebhookAck,
)
from app.schemas.profile import ProfileResponse
from app.services import profile as profile_service

logger = logging.getLogger(__name__)

SEPAY_PROVIDER = "SEPAY"

_CONFIRM_ERRORS: dict[str, tuple[int, str]] = {
    "PAYMENT_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy giao dịch thanh toán."),
    "PURCHASE_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy giao dịch mua lượt PT."),
    "PAYMENT_NOT_PENDING": (status.HTTP_409_CONFLICT, "Giao dịch đã được xử lý trước đó."),
    "PURPOSE_NOT_SUPPORTED": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Chưa hỗ trợ xác nhận loại thanh toán này.",
    ),
    INTERNAL_ERROR: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Không thể xác nhận thanh toán."),
}


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": {}}},
    )


def _payment_not_found() -> HTTPException:
    return _error(
        status.HTTP_404_NOT_FOUND, "PAYMENT_NOT_FOUND", "Không tìm thấy giao dịch thanh toán."
    )


# --------------------------------------------------------------------------
# Checkout
# --------------------------------------------------------------------------


def _bank_info() -> PaymentBankInfo | None:
    settings = get_settings()
    if not (settings.payment_bank_code and settings.payment_account_no):
        return None
    return PaymentBankInfo(
        bank_code=settings.payment_bank_code,
        account_no=settings.payment_account_no,
        account_name=settings.payment_account_name,
    )


def _vietqr_image_url(bank: PaymentBankInfo, amount: Decimal, content: str) -> str:
    """Quick-link image from vietqr.io, readable by every Vietnamese banking app."""
    query = urlencode(
        {"amount": int(amount), "addInfo": content, "accountName": bank.account_name},
        quote_via=quote,
    )
    return (
        f"https://img.vietqr.io/image/{quote(bank.bank_code)}-{quote(bank.account_no)}"
        f"-compact2.png?{query}"
    )


def _to_checkout(row: Mapping[str, Any]) -> PaymentCheckoutResponse:
    settings = get_settings()
    bank = _bank_info()
    amount = Decimal(row["amount"])
    expires_at = row.get("qr_expires_at")
    pending = row["status"] == "PENDING"
    return PaymentCheckoutResponse(
        id=row["id"],
        payment_number=row["payment_number"],
        purpose=row["purpose"],
        status=row["status"],
        amount=amount,
        currency=row["currency"],
        method=row["method"],
        transfer_content=row["payment_number"],
        qr_image_url=_vietqr_image_url(bank, amount, row["payment_number"]) if bank else None,
        bank=bank,
        expires_at=expires_at,
        expired=bool(pending and expires_at is not None and expires_at < utcnow()),
        paid_at=row.get("paid_at"),
        simulation_enabled=pending and settings.allow_payment_simulation,
    )


def get_checkout(db: Session, user_id: str, payment_id: str) -> PaymentCheckoutResponse:
    """Checkout details and live status; only the payment's owner may read it."""
    row = payments_repository.get_payment_for_user(db, payment_id, user_id)
    if row is None:
        raise _payment_not_found()
    return _to_checkout(row)


# --------------------------------------------------------------------------
# Confirmation
# --------------------------------------------------------------------------


def _grant(db: Session, payment: Mapping[str, Any], changed_by: str | None) -> ProcedureOutcome:
    """Mark the payment PAID and grant what it bought, atomically in MySQL."""
    purpose = payment["purpose"]
    if purpose == "MEMBERSHIP":
        return profile_repository.mark_subscription_paid(
            db, payment_id=payment["id"], changed_by=changed_by
        )
    if purpose == "PT_CREDIT":
        return pt_repository.mark_pt_credit_paid(
            db, payment_id=payment["id"], changed_by=changed_by
        )
    return ProcedureOutcome(
        "PURPOSE_NOT_SUPPORTED", f"Chưa hỗ trợ xác nhận thanh toán cho loại {purpose}.", {}
    )


def _raise_for_outcome(outcome: ProcedureOutcome) -> None:
    code = outcome.error_code or INTERNAL_ERROR
    status_code, message = _CONFIRM_ERRORS.get(code, _CONFIRM_ERRORS[INTERNAL_ERROR])
    raise _error(status_code, code, outcome.error_message or message)


def simulate_payment(db: Session, user: Mapping[str, Any], payment_id: str) -> ProfileResponse:
    """Manual confirmation: an ADMIN at any time, the owner only in development.

    Stands in for the bank webhook while developing, so the whole flow can be
    exercised without transferring real money.
    """
    is_admin = user["role"] == UserRole.ADMIN.value
    if is_admin:
        payment = pt_repository.get_payment(db, payment_id)
    else:
        payment = payments_repository.get_payment_for_user(db, payment_id, user["id"])

    # Payment của người khác trả 404 như không tồn tại, không lộ thông tin.
    if payment is None:
        raise _payment_not_found()

    if not is_admin and not get_settings().allow_payment_simulation:
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "PAYMENT_SIMULATION_DISABLED",
            "Thanh toán chỉ được xác nhận tự động khi ngân hàng báo đã nhận tiền.",
        )

    if str(payment["status"]) != "PENDING":
        raise _error(
            status.HTTP_409_CONFLICT, "PAYMENT_NOT_PENDING", "Giao dịch đã được xử lý trước đó."
        )

    outcome = _grant(db, payment, changed_by=user["id"])
    if not outcome.succeeded:
        _raise_for_outcome(outcome)

    payments_repository.notify_paid(db, payment["id"])
    return profile_service.get_profile(db, user["id"])


# --------------------------------------------------------------------------
# SePay webhook
# --------------------------------------------------------------------------


def _authorized(authorization: str | None) -> bool:
    """SePay sends ``Authorization: Apikey <key>`` when API-key auth is chosen."""
    expected = get_settings().sepay_webhook_api_key
    if not authorization:
        return False
    scheme, _, supplied = authorization.strip().partition(" ")
    if scheme.lower() != "apikey" or not supplied:
        return False
    return hmac.compare_digest(supplied.strip().encode(), expected.encode())


def handle_sepay_webhook(
    db: Session, payload: SepayWebhookPayload, authorization: str | None
) -> WebhookAck:
    settings = get_settings()
    if not settings.sepay_webhook_api_key:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "WEBHOOK_NOT_CONFIGURED",
            "Chưa cấu hình SEPAY_WEBHOOK_API_KEY.",
        )
    if not _authorized(authorization):
        raise _error(status.HTTP_401_UNAUTHORIZED, "INVALID_SIGNATURE", "API key không hợp lệ.")

    recorded = payments_repository.record_event(
        db,
        event_id=new_uuid(),
        provider=SEPAY_PROVIDER,
        provider_event_id=str(payload.id),
        event_type=f"transfer.{(payload.transfer_type or 'unknown').lower()}",
        signature_valid=True,
        payload=payload.model_dump(mode="json", by_alias=True),
    )
    if recorded.already_processed:
        # SePay gửi lại một giao dịch đã xử lý: trả thành công để nó ngừng thử lại.
        return WebhookAck(message="duplicate")

    def finish(payment_id: str | None, error_message: str | None) -> WebhookAck:
        payments_repository.finish_event(
            db,
            event_id=recorded.event_id,
            payment_id=payment_id,
            error_message=error_message,
            provider=SEPAY_PROVIDER,
            external_reference=payload.reference_code,
        )
        if error_message:
            logger.info("SePay event %s không kích hoạt: %s", payload.id, error_message)
        return WebhookAck(message=error_message or "paid")

    if (payload.transfer_type or "").lower() != "in":
        return finish(None, "IGNORED_OUTGOING_TRANSFER")

    receiving_account = settings.payment_account_no.strip()
    if (
        receiving_account
        and payload.account_number
        and payload.account_number.strip() != receiving_account
    ):
        return finish(None, "ACCOUNT_MISMATCH")

    payment_number = extract_payment_number(payload.code, payload.content, payload.description)
    if payment_number is None:
        return finish(None, "NO_PAYMENT_CODE")

    payment = payments_repository.find_by_number(db, payment_number)
    if payment is None:
        return finish(None, "PAYMENT_NOT_FOUND")

    if payment["status"] != "PENDING":
        return finish(payment["id"], "PAYMENT_NOT_PENDING")

    if payment["currency"] != "VND":
        return finish(payment["id"], "CURRENCY_NOT_SUPPORTED")

    if payload.transfer_amount < Decimal(payment["amount"]):
        # Chuyển thiếu: giữ PENDING, nhân viên đối soát thủ công qua payment_events.
        return finish(
            payment["id"],
            f"AMOUNT_TOO_LOW: nhận {payload.transfer_amount}, cần {payment['amount']}",
        )

    outcome = _grant(db, payment, changed_by=None)
    if not outcome.succeeded:
        if outcome.error_code == "PAYMENT_NOT_PENDING":
            # Hai lần gửi đồng thời: lần kia đã kích hoạt xong.
            return finish(payment["id"], "PAYMENT_NOT_PENDING")
        # Để processed_at trống và trả lỗi 500 để SePay gửi lại sau.
        logger.error("Kích hoạt payment %s thất bại: %s", payment["id"], outcome.error_code)
        raise _error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            outcome.error_code or INTERNAL_ERROR,
            "Không thể kích hoạt quyền lợi, vui lòng gửi lại.",
        )

    ack = finish(payment["id"], None)
    payments_repository.notify_paid(db, payment["id"])
    return ack
