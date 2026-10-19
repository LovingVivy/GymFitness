"""Outgoing email over SMTP, or into ``storage/outbox`` when SMTP is not configured.

Mail is always sent from the job queue (:mod:`app.tasks`), never inside an
HTTP request, so a slow or unreachable mail server cannot slow the API down.
"""

from __future__ import annotations

import logging
import re
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from app.core.config import get_settings
from app.core.storage import storage_root

logger = logging.getLogger(__name__)


@dataclass
class Attachment:
    filename: str
    content_type: str
    content: bytes


@dataclass
class Mail:
    to: str
    subject: str
    text: str
    html: str | None = None
    attachments: list[Attachment] = field(default_factory=list)


def build_message(mail: Mail) -> EmailMessage:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = mail.to
    message["Subject"] = mail.subject
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain="ironix.vn")
    message.set_content(mail.text)
    if mail.html:
        message.add_alternative(mail.html, subtype="html")
    for attachment in mail.attachments:
        maintype, _, subtype = attachment.content_type.partition("/")
        message.add_attachment(
            attachment.content, maintype=maintype, subtype=subtype, filename=attachment.filename
        )
    return message


def deliver(message: EmailMessage) -> str:
    """Send ``message``; return ``"smtp"`` or the outbox file name."""
    settings = get_settings()
    if settings.smtp_host:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return "smtp"

    outbox = storage_root() / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", str(message["To"]).lower()).strip("-")[:40]
    path = outbox / f"{datetime.now(UTC):%Y%m%d-%H%M%S-%f}-{slug}.eml"
    path.write_bytes(bytes(message))
    return path.name


def send(mail: Mail) -> str:
    target = deliver(build_message(mail))
    logger.info("Đã gửi email", extra={"mail_to": mail.to, "subject": mail.subject, "via": target})
    return target
