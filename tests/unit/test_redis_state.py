"""Tests for the Redis-backed rate-limit and idempotency implementations.

Uses fakeredis to avoid a real Redis dependency in CI; the async API surface
is exactly the same so this also exercises the real-Redis code path.
"""

from __future__ import annotations

import pytest
from fakeredis import aioredis as fake_aioredis

from text_checker.api.idempotency import (
    InMemoryIdempotencyCache,
    RedisIdempotencyCache,
)
from text_checker.api.ratelimit import (
    InMemoryRateLimiter,
    RedisRateLimiter,
)
from text_checker.api.schemas import CorrectMetrics, CorrectResponse


# ---------- rate limiter ----------


async def test_redis_rate_limiter_allows_under_limit() -> None:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    limiter = RedisRateLimiter(client, per_minute=3)
    for _ in range(3):
        assert await limiter.try_consume("alice") is True


async def test_redis_rate_limiter_rejects_over_limit() -> None:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    limiter = RedisRateLimiter(client, per_minute=2)
    assert await limiter.try_consume("alice") is True
    assert await limiter.try_consume("alice") is True
    assert await limiter.try_consume("alice") is False


async def test_redis_rate_limiter_isolates_keys() -> None:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    limiter = RedisRateLimiter(client, per_minute=1)
    assert await limiter.try_consume("alice") is True
    assert await limiter.try_consume("alice") is False
    # Beta has its own bucket
    assert await limiter.try_consume("beta") is True


async def test_redis_rate_limiter_fails_open_on_backend_error() -> None:
    # A broken client whose pipeline raises — operator gets no rate limiting
    # rather than a 503 spiral; documented behavior.
    class _Broken:
        def pipeline(self) -> object:
            raise RuntimeError("redis down")

    limiter = RedisRateLimiter(_Broken(), per_minute=1)
    assert await limiter.try_consume("alice") is True


# ---------- idempotency cache ----------


def _response(req_id: str = "req-1") -> CorrectResponse:
    return CorrectResponse(
        request_id=req_id,
        corrected_text="hello",
        diff=[],
        model_used="test-model",
        flagged=False,
        metrics=CorrectMetrics(latency_ms=42, tokens_in=1, tokens_out=1, edit_ratio=0.0),
    )


async def test_redis_idempotency_round_trip() -> None:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    cache = RedisIdempotencyCache(client)
    resp = _response("req-abc")
    assert await cache.get("key-1") is None
    await cache.put("key-1", resp)
    got = await cache.get("key-1")
    assert got is not None
    assert got.request_id == "req-abc"


async def test_redis_idempotency_returns_none_for_unknown_key() -> None:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    cache = RedisIdempotencyCache(client)
    assert await cache.get("missing") is None


async def test_redis_idempotency_fails_safe_on_backend_error() -> None:
    class _Broken:
        async def get(self, *a: object, **kw: object) -> None:
            raise RuntimeError("redis down")

        async def set(self, *a: object, **kw: object) -> None:
            raise RuntimeError("redis down")

    cache = RedisIdempotencyCache(_Broken())
    # get returns None (treat as miss) — service continues to call the LLM
    assert await cache.get("k") is None
    # put silently swallows — service keeps serving even if cache is down
    await cache.put("k", _response())


# ---------- factory dispatch ----------


async def test_in_memory_idempotency_works_unchanged() -> None:
    cache = InMemoryIdempotencyCache(ttl_seconds=60)
    resp = _response("req-mem")
    await cache.put("k", resp)
    got = await cache.get("k")
    assert got is not None
    assert got.request_id == "req-mem"


async def test_in_memory_rate_limiter_works_unchanged() -> None:
    limiter = InMemoryRateLimiter(per_minute=2)
    assert await limiter.try_consume("alice") is True
    assert await limiter.try_consume("alice") is True
    assert await limiter.try_consume("alice") is False


def test_factory_dispatches_to_in_memory_when_redis_url_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from text_checker.api import idempotency as idem_module
    from text_checker.api import ratelimit as rl_module
    from text_checker.config import settings

    monkeypatch.setattr(settings, "redis_url", None)
    idem_module.reset()
    rl_module.reset()

    assert isinstance(idem_module.get_cache(), InMemoryIdempotencyCache)
    assert isinstance(rl_module.get_limiter(), InMemoryRateLimiter)
