"""Job handlers. Each one receives a :class:`JobContext` and may return a file id."""

from __future__ import annotations

import secrets
from decimal import Decimal

from app.core import mailer, pdf
from app.core.config import get_settings
from app.core.gym_time import local_label
from app.db.base import new_uuid
from app.repositories import auth as auth_repository
from app.repositories import pt as pt_repository
from app.services import emails, exports, invoices
from app.services.auth import token_digest
from app.tasks.queue import JobContext, handler


@handler("export.report")
def export_report(job: JobContext) -> str:
    return exports.build(job.db, job.parameters, job.requested_by, job.progress)


@handler("email.password_reset")
def send_password_reset(job: JobContext) -> None:
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    recipient = auth_repository.create_password_reset(
        job.db,
        token_id=new_uuid(),
        user_id=job.parameters["user_id"],
        token_digest=token_digest(token),
        ttl_minutes=settings.password_reset_ttl_minutes,
    )
    if recipient is None:
        return None
    link = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={token}"
    subject, text, html = emails.password_reset(
        recipient.get("full_name"), link, settings.password_reset_ttl_minutes
    )
    mailer.send(mailer.Mail(to=recipient["email"], subject=subject, text=text, html=html))
    return None


@handler("email.payment_receipt")
def send_payment_receipt(job: JobContext) -> None:
    row, content = invoices.render(job.db, job.parameters["payment_id"])
    if not row.get("member_email"):
        return None
    mailer.send(
        emails.payment_receipt(
            to=row["member_email"],
            full_name=row.get("member_name"),
            invoice_number=row["invoice_number"],
            amount=pdf.money(Decimal(row["amount"])),
            description=invoices.describe(row),
            pdf=content,
        )
    )
    return None


@handler("email.pt_session_cancelled")
def send_pt_cancellation(job: JobContext) -> None:
    booking = pt_repository.booking_contact(job.db, job.parameters["booking_id"])
    if booking is None:
        return None
    by_trainer = booking.get("cancelled_by_role") == "TRAINER"
    refunded = bool(job.parameters.get("refunded"))
    to = booking["member_email"] if by_trainer else booking["trainer_email"]
    recipient = booking.get("member_name") if by_trainer else booking.get("trainer_name")
    who = (
        f"huấn luyện viên {booking.get('trainer_name') or ''}".strip()
        if by_trainer
        else f"hội viên {booking.get('member_name') or ''}".strip()
    )
    note = (
        "Lượt PT của buổi này đã được hoàn lại vào ví."
        if refunded
        else "Buổi huỷ sát giờ nên lượt PT của buổi này đã được tính."
    )
    if not by_trainer:
        note = "Ô giờ này đã trống lại trong lịch của bạn."
    mailer.send(
        emails.pt_session_cancelled(
            to=to,
            recipient_name=recipient,
            cancelled_by=who,
            when=local_label(booking["start_at"]),
            reason=booking.get("cancellation_reason"),
            refunded_note=note,
        )
    )
    return None
