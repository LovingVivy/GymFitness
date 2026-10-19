"""Fixed-window rate limiting per client IP (Redis, else in-process).

Two rules apply to ``/api/v1``: a strict one for the sign-in endpoints
(brute-force protection) and a generous one for everything else. The bank
webhook is exempt because SePay retries and must never be throttled.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import redis
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.redis_client import get_redis, mark_unavailable

WINDOW_SECONDS = 60

_AUTH_PATHS = re.compile(
    r"^/api/v1/auth/(login|register|forgot-password|reset-password|2fa/verify)$"
)
_EXEMPT_PATHS = re.compile(r"^/api/v1/payments/webhooks/")


@dataclass(frozen=True)
class Rule:
    name: str
    limit: int


def rule_for(method: str, path: str) -> Rule | None:
    settings = get_settings()
    if not path.startswith("/api/v1/") or _EXEMPT_PATHS.match(path):
        return None
    if method == "POST" and _AUTH_PATHS.match(path):
        return Rule("auth", settings.rate_limit_auth_per_minute)
    return Rule("api", settings.rate_limit_api_per_minute)


class _MemoryCounter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, tuple[int, int]] = {}

    def hit(self, key: str, window: int) -> int:
        with self._lock:
            if len(self._counts) > 10_000:
                self._counts = {k: v for k, v in self._counts.items() if v[0] == window}
            stored_window, count = self._counts.get(key, (window, 0))
            count = count + 1 if stored_window == window else 1
            self._counts[key] = (window, count)
            return count

    def clear(self) -> None:
        with self._lock:
            self._counts.clear()


_memory = _MemoryCounter()


def hit(rule: Rule, client_id: str, now: float | None = None) -> tuple[int, int]:
    """Count one request; return ``(count_in_window, seconds_until_reset)``."""
    moment = time.time() if now is None else now
    window = int(moment // WINDOW_SECONDS)
    reset_in = WINDOW_SECONDS - int(moment % WINDOW_SECONDS)
    key = f"gf:rl:{rule.name}:{client_id}:{window}"

    client = get_redis()
    if client is not None:
        try:
            pipe = client.pipeline()
            pipe.incr(key)
            pipe.expire(key, WINDOW_SECONDS + 1)
            count, _ = pipe.execute()
            return int(count), reset_in
        except redis.RedisError as exc:
            mark_unavailable(exc)
    return _memory.hit(key, window), reset_in


def client_ip(request: Request) -> str:
    # Sau reverse proxy, uvicorn --proxy-headers đã đặt client.host từ X-Forwarded-For.
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    if not get_settings().rate_limit_enabled:
        return await call_next(request)

    rule = rule_for(request.method, request.url.path)
    if rule is None:
        return await call_next(request)

    count, reset_in = hit(rule, client_ip(request))
    remaining = max(rule.limit - count, 0)
    headers = {
        "X-RateLimit-Limit": str(rule.limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_in),
    }
    if count > rule.limit:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": f"Bạn thao tác quá nhanh, vui lòng thử lại sau {reset_in} giây.",
                    "details": {"retry_after_seconds": reset_in, "limit": rule.limit},
                }
            },
            headers={**headers, "Retry-After": str(reset_in)},
        )

    response = await call_next(request)
    for key, value in headers.items():
        response.headers.setdefault(key, value)
    return response


def reset_local() -> None:
    """Forget in-process counters (tests)."""
    _memory.clear()
