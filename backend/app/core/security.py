"""Password hashing (PBKDF2-SHA256) and HS256 JWT helpers.

Only the Python standard library is used so the backend stays installable
without network access. See docs/DECISIONS.md ADR-011 for the rationale.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings

_PBKDF2_ITERATIONS = 600_000
_PBKDF2_ALGO = "sha256"


def utcnow() -> datetime:
    """Naive UTC datetime matching the ``DATETIME`` (no tz) columns."""
    return datetime.now(UTC).replace(tzinfo=None)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return "$".join(
        [
            "pbkdf2_sha256",
            str(_PBKDF2_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iterations, salt_b64, digest_b64 = encoded.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        digest = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def create_access_token(subject: str, role: str) -> str:
    settings = get_settings()
    return _sign({"sub": subject, "role": role}, settings.jwt_access_token_expire_minutes)


def create_purpose_token(subject: str, purpose: str, minutes: int, **claims: str) -> str:
    """Short-lived token for one step of a flow (2FA challenge, 2FA setup).

    It carries a ``purpose`` claim, which :func:`decode_access_token` refuses,
    so it can never be used as a login session.
    """
    return _sign({"sub": subject, "purpose": purpose, **claims}, minutes)


def decode_purpose_token(token: str, purpose: str) -> dict:
    payload = _decode(token)
    if payload.get("purpose") != purpose:
        raise ValueError("invalid token purpose")
    return payload


def _sign(claims: dict, minutes: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=minutes)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        **claims,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": secrets.token_hex(16),
    }
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode()),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode()),
        ]
    )
    signature = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict:
    payload = _decode(token)
    if "purpose" in payload:
        raise ValueError("not an access token")
    return payload


def _decode(token: str) -> dict:
    settings = get_settings()
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}"
        expected = hmac.new(
            settings.jwt_secret_key.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64url_decode(signature_b64), expected):
            raise ValueError("invalid signature")
        payload = json.loads(_b64url_decode(payload_b64))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired token")
        return payload
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("invalid token") from exc
