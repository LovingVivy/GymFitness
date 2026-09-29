"""Transfer codes printed in the bank-transfer description.

The code doubles as ``payments.payment_number``. It is letters and digits only
because Vietnamese banks strip or rewrite punctuation in the transfer
description, and the webhook has to find the code again in whatever text the
bank hands back (``"MBVCB.123.IRX260928A1B2C3D4.CT tu ..."``).
"""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime

from app.core.config import get_settings

_RANDOM_HEX_CHARS = 8


def _prefix() -> str:
    prefix = re.sub(r"[^A-Z0-9]", "", get_settings().payment_code_prefix.upper())
    return prefix or "IRX"


def new_payment_number(now: datetime | None = None) -> str:
    """``IRX`` + ``YYMMDD`` + 8 hex chars, e.g. ``IRX260928A1B2C3D4``."""
    moment = now or datetime.now(UTC)
    return f"{_prefix()}{moment:%y%m%d}{secrets.token_hex(_RANDOM_HEX_CHARS // 2).upper()}"


def extract_payment_number(*texts: str | None) -> str | None:
    """Find the first transfer code inside free-form bank descriptions."""
    pattern = re.compile(rf"{_prefix()}\d{{6}}[0-9A-F]{{{_RANDOM_HEX_CHARS}}}")
    for text in texts:
        if not text:
            continue
        normalized = re.sub(r"[^A-Z0-9]", "", text.upper())
        match = pattern.search(normalized)
        if match:
            return match.group(0)
    return None
