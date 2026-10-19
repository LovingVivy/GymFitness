"""Invoices: one per paid payment, rendered as PDF on demand and emailed as a receipt."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.core import pdf
from app.core.gym_time import to_local
from app.core.permissions import Permission, has_permission
from app.db.base import new_uuid
from app.repositories import payments as payments_repository
from app.services.pt import error

METHOD_LABELS = {
    "QR": "QR chuyển khoản",
    "BANK_TRANSFER": "Chuyển khoản",
    "CASH": "Tiền mặt",
    "CARD": "Thẻ",
}
STATUS_LABELS = {"PAID": "Đã thanh toán"}
PURPOSE_LABELS = {
    "MEMBERSHIP": "Gói hội viên",
    "PT_CREDIT": "Buổi tập với huấn luyện viên (PT)",
    "PRODUCT_ORDER": "Đơn hàng",
}

_ERRORS = {
    "PAYMENT_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "Không tìm thấy giao dịch thanh toán."),
    "PAYMENT_NOT_PAID": (
        status.HTTP_409_CONFLICT,
        "Chỉ xuất hoá đơn cho giao dịch đã thanh toán.",
    ),
}


def _lines(row: Mapping[str, Any]) -> list[pdf.InvoiceLine]:
    amount = Decimal(row["amount"])
    pt_quantity = int(row.get("pt_quantity") or 0)
    pt_unit = Decimal(row.get("pt_unit_price") or 0)
    pt_total = pt_unit * pt_quantity
    lines: list[pdf.InvoiceLine] = []
    if row.get("plan_name"):
        lines.append(pdf.InvoiceLine(f"Gói hội viên: {row['plan_name']}", 1, amount - pt_total))
    if pt_quantity:
        lines.append(pdf.InvoiceLine("Buổi tập với huấn luyện viên (PT)", pt_quantity, pt_unit))
    if not lines:
        lines.append(pdf.InvoiceLine(PURPOSE_LABELS.get(row["purpose"], row["purpose"]), 1, amount))
    return lines


def describe(row: Mapping[str, Any]) -> str:
    return " + ".join(
        line.description if line.quantity == 1 else f"{line.quantity} {line.description}"
        for line in _lines(row)
    )


def issue(db: Session, payment_id: str) -> dict[str, Any]:
    """Issue (or re-read) the invoice of a paid payment."""
    row: dict[str, Any] = {}
    for _ in range(2):
        row = payments_repository.issue_invoice(db, invoice_id=new_uuid(), payment_id=payment_id)
        if row.get("error_code") != "RETRY":
            break
    code = row.get("error_code")
    if code:
        status_code, message = _ERRORS.get(
            code, (status.HTTP_500_INTERNAL_SERVER_ERROR, "Không thể lập hoá đơn.")
        )
        raise error(status_code, code, row.get("error_message") or message)
    return row


def to_invoice_data(row: Mapping[str, Any]) -> pdf.InvoiceData:
    lines = _lines(row)
    return pdf.InvoiceData(
        invoice_number=row["invoice_number"],
        issued_at=to_local(row["issued_at"]),
        payment_number=row["payment_number"],
        status=STATUS_LABELS.get(row["payment_status"], row["payment_status"]),
        method=METHOD_LABELS.get(row["method"], row["method"]),
        paid_at=to_local(row["paid_at"]) if row.get("paid_at") else None,
        customer_name=row.get("member_name") or "Khách lẻ",
        customer_code=row.get("member_code"),
        customer_email=row.get("member_email"),
        customer_phone=row.get("member_phone"),
        branch_name=row.get("branch_name") or "IRONIX Fitness",
        branch_address=row.get("branch_address") or "",
        lines=lines,
        total=Decimal(row["amount"]),
    )


def render(db: Session, payment_id: str) -> tuple[dict[str, Any], bytes]:
    row = issue(db, payment_id)
    return row, pdf.invoice_pdf(to_invoice_data(row))


def pdf_for(db: Session, user: Mapping[str, Any], payment_id: str) -> tuple[str, bytes]:
    """Invoice PDF for the payment's owner, or for staff who may view payments."""
    if not has_permission(user["role"], Permission.PAYMENTS_VIEW):
        # Hội viên chỉ thấy giao dịch của mình; của người khác trả 404 như không tồn tại.
        if payments_repository.get_payment_for_user(db, payment_id, user["id"]) is None:
            status_code, message = _ERRORS["PAYMENT_NOT_FOUND"]
            raise error(status_code, "PAYMENT_NOT_FOUND", message)
    row, content = render(db, payment_id)
    return f"{row['invoice_number']}.pdf", content
