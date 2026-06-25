from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Protocol

from fastapi import Header

from .schemas import CorrectResponse

DEFAULT_TTL_SECONDS = 600

log = logging.getLogger(__name__)


class IdempotencyCache(Protocol):
    async def get(self, key: str) -> CorrectResponse | None: ...

    async def put(self, key: str, value: CorrectResponse) -> None: ...

    async def reset(self) -> None: ...


class InMemoryIdempotencyCache:
    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, CorrectResponse]] = {}
        self._lock = Lock()

    async def get(self, key: str) -> CorrectResponse | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    async def put(self, key: str, value: CorrectResponse) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + self._ttl, value)

    async def reset(self) -> None:
        with self._lock:
            self._store.clear()


class RedisIdempotencyCache:
    """JSON-serialized CorrectResponse stored under a prefixed key with TTL."""

    def __init__(self, redis_client: object, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._client = redis_client
        self._ttl = ttl_seconds

    async def get(self, key: str) -> CorrectResponse | None:
        try:
            raw = await self._client.get(f"idem:{key}")  # type: ignore[attr-defined]
        except Exception as e:
            log.warning("idempotency backend error on get; treating as miss: %s", e)
            return None
        if raw is None:
            return None
        return CorrectResponse.model_validate_json(raw)

    async def put(self, key: str, value: CorrectResponse) -> None:
        try:
            await self._client.set(  # type: ignore[attr-defined]
                f"idem:{key}", value.model_dump_json(), ex=self._ttl
            )
        except Exception as e:
            log.warning("idempotency backend error on put; skipping cache: %s", e)

    async def reset(self) -> None:
        try:
            await self._client.flushdb()  # type: ignore[attr-defined]
        except Exception as e:
            log.warning("idempotency reset failed: %s", e)


_cache: IdempotencyCache | None = None


def get_cache() -> IdempotencyCache:
    global _cache
    if _cache is None:
        from ..config import settings

        if settings.redis_url:
            import redis.asyncio as aioredis

            client = aioredis.from_url(settings.redis_url, decode_responses=True)
            _cache = RedisIdempotencyCache(client)
        else:
            _cache = InMemoryIdempotencyCache()
    return _cache


def set_cache(cache: IdempotencyCache | None) -> None:
    global _cache
    _cache = cache


def reset() -> None:
    """Drop the current cache so the next request rebuilds from config."""
    global _cache
    _cache = None


def idempotency_header(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str | None:
    return idempotency_key
