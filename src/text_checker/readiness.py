"""Active readiness probe for /readyz.

`/healthz` answers "process is alive" — useful for k8s liveness, restart-on-
crash, and ad-hoc curl. `/readyz` answers "can this replica serve traffic
right now" — needs to actually probe upstream dependencies (the LLM provider
and, if configured, Redis).

Result is cached for a short window so a k8s probe hitting /readyz every 10s
doesn't hammer Ollama every time.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .config import settings


@dataclass
class ReadinessReport:
    ready: bool
    components: dict[str, str] = field(default_factory=dict)


_CACHE_TTL_SECONDS = 5.0
_last_check_at: float = 0.0
_last_report: ReadinessReport = ReadinessReport(ready=False, components={})


def reset() -> None:
    """Drop the cached readiness state so the next call re-probes."""
    global _last_check_at, _last_report
    _last_check_at = 0.0
    _last_report = ReadinessReport(ready=False, components={})


async def _probe_provider() -> tuple[str, bool]:
    """Probe the default Ollama-shaped provider for /v1/models."""
    from .providers.registry import get_registry

    try:
        registry = get_registry()
        provider = registry.get("ollama")
        ok = await provider.health()
    except Exception as e:
        return f"error: {e.__class__.__name__}", False
    return ("ok" if ok else "unhealthy"), ok


async def _probe_redis() -> tuple[str, bool]:
    """Ping Redis if configured."""
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url, socket_timeout=2)
        try:
            pong = await client.ping()
        finally:
            await client.aclose()
    except Exception as e:
        return f"error: {e.__class__.__name__}", False
    return ("ok" if pong else "no_pong"), bool(pong)


async def probe() -> ReadinessReport:
    components: dict[str, str] = {}
    all_ok = True

    provider_status, provider_ok = await _probe_provider()
    components["provider:ollama"] = provider_status
    if not provider_ok:
        all_ok = False

    if settings.redis_url:
        redis_status, redis_ok = await _probe_redis()
        components["redis"] = redis_status
        if not redis_ok:
            all_ok = False

    return ReadinessReport(ready=all_ok, components=components)


async def check(cache_ttl_seconds: float = _CACHE_TTL_SECONDS) -> ReadinessReport:
    """Return a cached readiness report, refreshing if older than `cache_ttl_seconds`."""
    global _last_check_at, _last_report
    now = time.monotonic()
    if now - _last_check_at > cache_ttl_seconds:
        _last_report = await probe()
        _last_check_at = now
    return _last_report
