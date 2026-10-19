"""Shared Redis connection that degrades gracefully when Redis is not running.

Cache, rate limiting and the job queue all accept ``None`` from
:func:`get_redis` and fall back to in-process behaviour, so the API keeps
working on a laptop without Redis. A failed connection is retried at most
every ``_RETRY_SECONDS`` so a missing server does not slow every request.
"""

from __future__ import annotations

import logging
import threading
import time

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_RETRY_SECONDS = 30.0

_lock = threading.Lock()
_client: redis.Redis | None = None
_available: bool | None = None
_checked_at = 0.0
_override: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    """Connected client, or ``None`` when Redis is disabled or unreachable."""
    global _client, _available, _checked_at

    if _override is not None:
        return _override

    settings = get_settings()
    if not settings.redis_enabled or not settings.redis_url:
        return None

    now = time.monotonic()
    if _available is True and _client is not None:
        return _client
    if _available is False and now - _checked_at < _RETRY_SECONDS:
        return None

    with _lock:
        if _client is None:
            _client = redis.Redis.from_url(
                settings.redis_url,
                socket_connect_timeout=0.3,
                socket_timeout=1.0,
                decode_responses=True,
            )
        try:
            _client.ping()
        except redis.RedisError as exc:
            if _available is not False:
                logger.warning("Redis không khả dụng (%s), dùng chế độ dự phòng.", exc)
            _available = False
            _checked_at = now
            return None
        if _available is False:
            logger.info("Đã kết nối lại Redis.")
        _available = True
        _checked_at = now
        return _client


def mark_unavailable(exc: Exception) -> None:
    """Called by users of the client when a command fails mid-flight."""
    global _available, _checked_at
    if _override is not None:
        return
    if _available is not False:
        logger.warning("Mất kết nối Redis (%s), dùng chế độ dự phòng.", exc)
    _available = False
    _checked_at = time.monotonic()


def redis_status() -> str:
    """``"up"``, ``"down"`` or ``"disabled"``, for the readiness probe."""
    settings = get_settings()
    if _override is None and (not settings.redis_enabled or not settings.redis_url):
        return "disabled"
    return "up" if get_redis() is not None else "down"


def use_client_for_tests(client: redis.Redis | None) -> None:
    """Inject a client (e.g. fakeredis) or remove the injection with ``None``."""
    global _override
    _override = client
