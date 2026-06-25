from __future__ import annotations

import httpx
import pytest
import respx
from fakeredis import aioredis as fake_aioredis
from fastapi.testclient import TestClient

from text_checker import readiness
from text_checker.config import Settings
from text_checker.providers import registry as registry_module
from text_checker.providers.registry import ProviderRegistry


@pytest.fixture(autouse=True)
def fresh_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    # Point the registry at a stable test URL we can mock with respx
    reg = ProviderRegistry(Settings(ollama_base_url="http://ollama.test/v1"))
    monkeypatch.setattr(registry_module, "_registry", reg)


def test_healthz_unchanged(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readyz_returns_200_when_provider_is_up(client: TestClient) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.get("/models").mock(return_value=httpx.Response(200, json={"data": []}))
        r = client.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["components"]["provider:ollama"] == "ok"


def test_readyz_returns_503_when_provider_is_down(client: TestClient) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.get("/models").mock(side_effect=httpx.ConnectError("nope"))
        r = client.get("/readyz")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not ready"
    assert body["components"]["provider:ollama"] == "unhealthy"


def test_readyz_returns_503_when_provider_returns_non_200(client: TestClient) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.get("/models").mock(return_value=httpx.Response(500))
        r = client.get("/readyz")
    assert r.status_code == 503
    assert r.json()["components"]["provider:ollama"] == "unhealthy"


def test_readyz_includes_redis_when_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = fake_aioredis.FakeRedis()
    monkeypatch.setattr(
        "redis.asyncio.from_url", lambda *args, **kwargs: fake
    )
    from text_checker.config import settings as live

    monkeypatch.setattr(live, "redis_url", "redis://test:6379/0")

    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.get("/models").mock(return_value=httpx.Response(200, json={"data": []}))
        r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["components"]["redis"] == "ok"


def test_readyz_returns_503_when_redis_is_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _BrokenRedis:
        async def ping(self) -> None:
            raise ConnectionError("redis offline")

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(
        "redis.asyncio.from_url", lambda *args, **kwargs: _BrokenRedis()
    )
    from text_checker.config import settings as live

    monkeypatch.setattr(live, "redis_url", "redis://test:6379/0")

    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.get("/models").mock(return_value=httpx.Response(200, json={"data": []}))
        r = client.get("/readyz")
    assert r.status_code == 503
    body = r.json()
    assert body["components"]["redis"].startswith("error")
    assert body["components"]["provider:ollama"] == "ok"


def test_readyz_caches_result_within_ttl(client: TestClient) -> None:
    # First call probes, sets cache. Second call within 5s should NOT re-probe.
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        route = mock.get("/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        r1 = client.get("/readyz")
        r2 = client.get("/readyz")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert route.call_count == 1


async def test_probe_function_is_directly_testable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Sanity: the underlying probe is usable from non-FastAPI contexts.
    reg = ProviderRegistry(Settings(ollama_base_url="http://ollama.test/v1"))
    monkeypatch.setattr(registry_module, "_registry", reg)
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.get("/models").mock(return_value=httpx.Response(200, json={}))
        report = await readiness.probe()
    assert report.ready is True
    assert report.components["provider:ollama"] == "ok"
