from __future__ import annotations

import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Protocol

from fastapi import Depends, HTTPException

from .auth import require_api_key

RATE_LIMIT_PER_MINUTE = 60

log = logging.getLogger(__name__)


class RateLimiter(Protocol):
    async def try_consume(self, key: str) -> bool: ...

    async def reset(self) -> None: ...


class TokenBucket:
    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self._capacity = float(capacity)
        self._refill = refill_per_second
        self._tokens = float(capacity)
        self._last = time.monotonic()
        self._lock = Lock()

    def try_consume(self) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill)
            self._last = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


class InMemoryRateLimiter:
    def __init__(self, per_minute: int = RATE_LIMIT_PER_MINUTE) -> None:
        self._per_minute = per_minute
        self._buckets: dict[str, TokenBucket] = defaultdict(self._new_bucket)

    def _new_bucket(self) -> TokenBucket:
        return TokenBucket(
            capacity=self._per_minute,
            refill_per_second=self._per_minute / 60.0,
        )

    async def try_consume(self, key: str) -> bool:
        return self._buckets[key].try_consume()

    async def reset(self) -> None:
        self._buckets.clear()


class RedisRateLimiter:
    """Sliding-window-per-minute counter via INCR + EXPIRE.

    Simpler than a full token bucket in Redis (which needs a Lua script for
    atomicity), and operationally equivalent for our purpose. The window
    resets on minute boundaries instead of refilling continuously.
    """

    def __init__(self, redis_client: object, per_minute: int = RATE_LIMIT_PER_MINUTE) -> None:
        self._client = redis_client
        self._per_minute = per_minute

    async def try_consume(self, key: str) -> bool:
        window = int(time.time()) // 60
        redis_key = f"rl:{key}:{window}"
        try:
            async with self._client.pipeline() as pipe:  # type: ignore[attr-defined]
                pipe.incr(redis_key)
                pipe.expire(redis_key, 70)
                count, _ = await pipe.execute()
        except Exception as e:
            log.warning("rate-limit backend error; failing open: %s", e)
            return True
        return int(count) <= self._per_minute

    async def reset(self) -> None:
        try:
            await self._client.flushdb()  # type: ignore[attr-defined]
        except Exception as e:
            log.warning("rate-limit reset failed: %s", e)


_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        from ..config import settings

        if settings.redis_url:
            import redis.asyncio as aioredis

            client = aioredis.from_url(settings.redis_url, decode_responses=True)
            _limiter = RedisRateLimiter(client, per_minute=RATE_LIMIT_PER_MINUTE)
        else:
            _limiter = InMemoryRateLimiter(per_minute=RATE_LIMIT_PER_MINUTE)
    return _limiter


def set_limiter(limiter: RateLimiter | None) -> None:
    global _limiter
    _limiter = limiter


def reset() -> None:
    """Drop the current limiter so the next request rebuilds from config."""
    global _limiter
    _limiter = None


async def enforce_rate_limit(key: str = Depends(require_api_key)) -> str:
    limiter = get_limiter()
    allowed = await limiter.try_consume(key)
    if not allowed:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    return key
