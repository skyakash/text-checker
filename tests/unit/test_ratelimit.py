import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from text_corrector.api import ratelimit
from text_corrector.config import Settings
from text_corrector.providers import registry as registry_module
from text_corrector.providers.registry import ProviderRegistry


def _mock_ok() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "test-model",
            "choices": [{"message": {"content": "They're going home."}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


@pytest.fixture
def low_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ratelimit, "RATE_LIMIT_PER_MINUTE", 2)
    ratelimit.reset()


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> ProviderRegistry:
    reg = ProviderRegistry(Settings(ollama_base_url="http://ollama.test/v1"))
    monkeypatch.setattr(registry_module, "_registry", reg)
    return reg


def test_rate_limit_blocks_after_capacity(
    client: TestClient, low_limit: None, isolated_registry: ProviderRegistry
) -> None:
    payload = {"text": "their going home", "mode": "grammar"}
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=_mock_ok())
        r1 = client.post("/v1/correct", json=payload)
        r2 = client.post("/v1/correct", json=payload)
        r3 = client.post("/v1/correct", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


def test_rate_limit_is_per_api_key(
    client: TestClient,
    low_limit: None,
    isolated_registry: ProviderRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from text_corrector.config import settings

    monkeypatch.setattr(settings, "api_keys", "alpha,beta")
    payload = {"text": "their going home", "mode": "grammar"}
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=_mock_ok())
        for _ in range(2):
            assert client.post(
                "/v1/correct", headers={"X-API-Key": "alpha"}, json=payload
            ).status_code == 200
        assert (
            client.post("/v1/correct", headers={"X-API-Key": "alpha"}, json=payload).status_code
            == 429
        )
        assert (
            client.post("/v1/correct", headers={"X-API-Key": "beta"}, json=payload).status_code
            == 200
        )
