import time
from threading import Lock
from typing import Any

from fastapi import Header

DEFAULT_TTL_SECONDS = 600


class IdempotencyCache:
    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + self._ttl, value)

    def reset(self) -> None:
        with self._lock:
            self._store.clear()


_cache = IdempotencyCache()


def get_cache() -> IdempotencyCache:
    return _cache


def idempotency_header(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str | None:
    return idempotency_key
