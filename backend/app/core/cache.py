"""Read-through cache for catalogue data and reports (Redis, else in-process).

Entries live under a *namespace* whose version number is part of every key.
Invalidating a namespace bumps the version, so all of its entries become
unreachable at once without scanning keys; Redis expires the stale ones.

    plans = cache.get_or_load("catalog", "plans", ttl, load_plans, list[PlanResponse])
    cache.invalidate("catalog")
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import redis
from pydantic import TypeAdapter

from app.core.config import get_settings
from app.core.redis_client import get_redis, mark_unavailable

logger = logging.getLogger(__name__)

CATALOG = "catalog"
REPORTS = "reports"

_PREFIX = "gf:cache"
_adapters: dict[Any, TypeAdapter] = {}


class _MemoryStore:
    """Per-process fallback with the same TTL semantics as Redis."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: dict[str, tuple[float, str]] = {}
        self._versions: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        with self._lock:
            item = self._values.get(key)
            if item is None:
                return None
            expires, value = item
            if expires < time.monotonic():
                del self._values[key]
                return None
            return value

    def set(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            if len(self._values) > 2_000:
                now = time.monotonic()
                self._values = {k: v for k, v in self._values.items() if v[0] >= now}
            self._values[key] = (time.monotonic() + ttl, value)

    def version(self, namespace: str) -> int:
        with self._lock:
            return self._versions.get(namespace, 0)

    def bump(self, namespace: str) -> None:
        with self._lock:
            self._versions[namespace] = self._versions.get(namespace, 0) + 1

    def clear(self) -> None:
        with self._lock:
            self._values.clear()
            self._versions.clear()


_memory = _MemoryStore()


def _adapter(type_: Any) -> TypeAdapter:
    adapter = _adapters.get(type_)
    if adapter is None:
        adapter = _adapters[type_] = TypeAdapter(type_)
    return adapter


def _version(client: redis.Redis | None, namespace: str) -> int:
    if client is None:
        return _memory.version(namespace)
    return int(client.get(f"{_PREFIX}:ver:{namespace}") or 0)


def get_or_load[T](namespace: str, key: str, ttl: int, loader: Callable[[], T], type_: Any) -> T:
    """Return the cached value of ``key`` or compute, store and return it."""
    if not get_settings().cache_enabled:
        return loader()

    adapter = _adapter(type_)
    client = get_redis()
    try:
        full_key = f"{_PREFIX}:{namespace}:{_version(client, namespace)}:{key}"
        raw = client.get(full_key) if client is not None else _memory.get(full_key)
        if raw is not None:
            return adapter.validate_json(raw)

        value = loader()
        encoded = adapter.dump_json(value).decode("utf-8")
        if client is not None:
            client.set(full_key, encoded, ex=ttl)
        else:
            _memory.set(full_key, encoded, ttl)
        return value
    except redis.RedisError as exc:
        mark_unavailable(exc)
        return loader()


def invalidate(*namespaces: str) -> None:
    """Drop every entry of the given namespaces (both Redis and the local fallback)."""
    for namespace in namespaces:
        _memory.bump(namespace)
        client = get_redis()
        if client is None:
            continue
        try:
            client.incr(f"{_PREFIX}:ver:{namespace}")
        except redis.RedisError as exc:
            mark_unavailable(exc)


def clear_local() -> None:
    """Forget the in-process fallback (tests)."""
    _memory.clear()
