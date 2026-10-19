"""Time-based one-time passwords (RFC 6238) for optional two-step sign-in.

Compatible with Google Authenticator, Microsoft Authenticator, Authy...:
SHA-1, 6 digits, 30-second steps. Secrets are stored encrypted with a key
derived from ``JWT_SECRET_KEY``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

STEP_SECONDS = 30
DIGITS = 6


def new_secret() -> str:
    """Random 160-bit secret in unpadded base32, as authenticator apps expect."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decode(secret: str) -> bytes:
    normalized = secret.strip().replace(" ", "").upper()
    return base64.b32decode(normalized + "=" * (-len(normalized) % 8))


def code_at(secret: str, moment: float | None = None) -> str:
    counter = int((time.time() if moment is None else moment) // STEP_SECONDS)
    digest = hmac.new(_decode(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def verify(secret: str, code: str, moment: float | None = None, window: int = 1) -> bool:
    """Accept the current code and ``window`` steps either side (clock drift)."""
    supplied = "".join(char for char in str(code) if char.isdigit())
    if len(supplied) != DIGITS:
        return False
    now = time.time() if moment is None else moment
    return any(
        hmac.compare_digest(code_at(secret, now + step * STEP_SECONDS), supplied)
        for step in range(-window, window + 1)
    )


def provisioning_uri(secret: str, account: str) -> str:
    issuer = get_settings().two_factor_issuer
    label = quote(f"{issuer}:{account}")
    query = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": DIGITS,
            "period": STEP_SECONDS,
        },
        quote_via=quote,
    )
    return f"otpauth://totp/{label}?{query}"


def _fernet() -> Fernet:
    key = hashlib.sha256(b"gymfitness-2fa:" + get_settings().jwt_secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_secret(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError):
        return None


def qr_svg(data: str) -> str:
    """The provisioning URI as an inline SVG QR code (no image library needed)."""
    from reportlab.graphics import renderSVG
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing

    widget = QrCodeWidget(data, barLevel="M")
    x0, y0, x1, y1 = widget.getBounds()
    size = 220
    drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    drawing.add(widget)
    svg = renderSVG.drawToString(drawing)
    # Bỏ khai báo XML/DOCTYPE để nhúng trực tiếp vào trang.
    return svg[svg.index("<svg") :]
