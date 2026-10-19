"""Email content. Every message has a plain-text body and a simple HTML body."""

from __future__ import annotations

from html import escape

from app.core.mailer import Attachment, Mail

_BRAND = "IRONIX Fitness"


def _html(title: str, paragraphs: list[str], button: tuple[str, str] | None = None) -> str:
    body = "".join(f"<p style='margin:0 0 14px'>{paragraph}</p>" for paragraph in paragraphs)
    action = ""
    if button:
        label, url = button
        action = (
            f"<p style='margin:24px 0'><a href='{escape(url)}' style='background:#c8102e;"
            "color:#fff;padding:12px 22px;border-radius:999px;text-decoration:none;"
            f"font-weight:600'>{escape(label)}</a></p>"
        )
    return (
        "<!doctype html><html><body style='margin:0;background:#f4f4f4;"
        "font-family:Arial,Helvetica,sans-serif;color:#111'>"
        "<div style='max-width:560px;margin:0 auto;padding:32px 24px'>"
        "<div style='font-size:22px;font-weight:800;letter-spacing:.5px'>IRONIX "
        "<span style='color:#c8102e'>FITNESS</span></div>"
        "<div style='background:#fff;border-radius:16px;padding:28px;margin-top:18px'>"
        f"<h1 style='font-size:20px;margin:0 0 16px'>{escape(title)}</h1>{body}{action}</div>"
        f"<p style='color:#888;font-size:12px;margin-top:18px'>{_BRAND} · Email tự động, "
        "vui lòng không trả lời.</p></div></body></html>"
    )


def password_reset(full_name: str | None, link: str, ttl_minutes: int) -> tuple[str, str, str]:
    """Subject, text and HTML of the reset email (recipient filled in by the caller)."""
    name = full_name or "bạn"
    subject = "Đặt lại mật khẩu IRONIX"
    text = (
        f"Xin chào {name},\n\n"
        "Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản IRONIX của bạn.\n"
        f"Mở liên kết sau trong {ttl_minutes} phút để tạo mật khẩu mới:\n\n{link}\n\n"
        "Nếu bạn không yêu cầu, hãy bỏ qua email này; mật khẩu hiện tại vẫn giữ nguyên.\n\n"
        f"{_BRAND}"
    )
    html = _html(
        "Đặt lại mật khẩu",
        [
            f"Xin chào <b>{escape(name)}</b>,",
            "Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản IRONIX của bạn.",
            f"Liên kết có hiệu lực trong <b>{ttl_minutes} phút</b> và chỉ dùng được một lần.",
            "Nếu bạn không yêu cầu, hãy bỏ qua email này; mật khẩu hiện tại vẫn giữ nguyên.",
        ],
        ("Tạo mật khẩu mới", link),
    )
    return subject, text, html


def payment_receipt(
    to: str,
    full_name: str | None,
    invoice_number: str,
    amount: str,
    description: str,
    pdf: bytes,
) -> Mail:
    name = full_name or "bạn"
    text = (
        f"Xin chào {name},\n\n"
        f"IRONIX đã nhận thanh toán {amount} cho: {description}.\n"
        f"Hoá đơn {invoice_number} được đính kèm trong email này.\n\n"
        f"Cảm ơn bạn đã tập luyện cùng {_BRAND}!"
    )
    html = _html(
        "Thanh toán thành công",
        [
            f"Xin chào <b>{escape(name)}</b>,",
            f"IRONIX đã nhận thanh toán <b>{escape(amount)}</b> cho: {escape(description)}.",
            f"Hoá đơn <b>{escape(invoice_number)}</b> được đính kèm dạng PDF.",
            f"Cảm ơn bạn đã tập luyện cùng {_BRAND}!",
        ],
    )
    return Mail(
        to=to,
        subject=f"Hoá đơn {invoice_number} · IRONIX",
        text=text,
        html=html,
        attachments=[Attachment(f"{invoice_number}.pdf", "application/pdf", pdf)],
    )


def pt_session_cancelled(
    to: str,
    recipient_name: str | None,
    cancelled_by: str,
    when: str,
    reason: str | None,
    refunded_note: str,
) -> Mail:
    name = recipient_name or "bạn"
    reason_text = reason or "không ghi lý do"
    text = (
        f"Xin chào {name},\n\n"
        f"Buổi PT lúc {when} đã được {cancelled_by} huỷ.\n"
        f"Lý do: {reason_text}.\n{refunded_note}\n\n{_BRAND}"
    )
    html = _html(
        "Buổi PT đã bị huỷ",
        [
            f"Xin chào <b>{escape(name)}</b>,",
            f"Buổi PT lúc <b>{escape(when)}</b> đã được {escape(cancelled_by)} huỷ.",
            f"Lý do: {escape(reason_text)}.",
            escape(refunded_note),
        ],
    )
    return Mail(to=to, subject=f"Buổi PT lúc {when} đã bị huỷ", text=text, html=html)


def membership_expiring(
    to: str, full_name: str | None, plan_name: str, end_label: str, days_left: int, link: str
) -> Mail:
    name = full_name or "bạn"
    when = "trong 24 giờ tới" if days_left <= 1 else f"trong vòng {days_left} ngày"
    text = (
        f"Xin chào {name},\n\n"
        f"Gói {plan_name} của bạn sẽ hết hạn {when} (lúc {end_label}).\n"
        "Gia hạn ngay để không bị gián đoạn: thời hạn của gói mới được cộng nối tiếp, "
        f"không mất ngày còn lại.\n\n{link}\n\n{_BRAND}"
    )
    html = _html(
        "Gói tập sắp hết hạn",
        [
            f"Xin chào <b>{escape(name)}</b>,",
            f"Gói <b>{escape(plan_name)}</b> sẽ hết hạn {escape(when)} "
            f"(lúc <b>{escape(end_label)}</b>).",
            "Gia hạn ngay để không bị gián đoạn: thời hạn gói mới được cộng nối tiếp, "
            "không mất ngày còn lại.",
        ],
        ("Gia hạn ngay", link),
    )
    return Mail(to=to, subject=f"Gói {plan_name} sắp hết hạn", text=text, html=html)


def membership_expired(
    to: str, full_name: str | None, plan_name: str, end_label: str, link: str
) -> Mail:
    name = full_name or "bạn"
    text = (
        f"Xin chào {name},\n\n"
        f"Gói {plan_name} của bạn đã hết hạn lúc {end_label}. Bạn tạm thời chưa check-in "
        f"và đặt PT được.\nGia hạn tại: {link}\n\n{_BRAND}"
    )
    html = _html(
        "Gói tập đã hết hạn",
        [
            f"Xin chào <b>{escape(name)}</b>,",
            f"Gói <b>{escape(plan_name)}</b> đã hết hạn lúc <b>{escape(end_label)}</b>.",
            "Bạn tạm thời chưa check-in và đặt PT được. Gia hạn để tiếp tục tập luyện.",
        ],
        ("Gia hạn ngay", link),
    )
    return Mail(to=to, subject=f"Gói {plan_name} đã hết hạn", text=text, html=html)
