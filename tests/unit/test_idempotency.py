import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from text_checker.config import Settings
from text_checker.providers import registry as registry_module
from text_checker.providers.registry import ProviderRegistry


def _mock_ok(text: str = "They're going home.") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "test-model",
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> ProviderRegistry:
    reg = ProviderRegistry(Settings(ollama_base_url="http://ollama.test/v1"))
    monkeypatch.setattr(registry_module, "_registry", reg)
    return reg


def test_same_idempotency_key_replays_without_second_provider_call(
    client: TestClient, isolated_registry: ProviderRegistry
) -> None:
    payload = {"text": "their going home", "mode": "grammar"}
    headers = {"Idempotency-Key": "abc-123"}
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        route = mock.post("/chat/completions").mock(return_value=_mock_ok())
        r1 = client.post("/v1/correct", json=payload, headers=headers)
        r2 = client.post("/v1/correct", json=payload, headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["request_id"] == r2.json()["request_id"]
    assert route.call_count == 1


def test_different_idempotency_keys_each_call_the_provider(
    client: TestClient, isolated_registry: ProviderRegistry
) -> None:
    payload = {"text": "their going home", "mode": "grammar"}
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        route = mock.post("/chat/completions").mock(return_value=_mock_ok())
        client.post("/v1/correct", json=payload, headers={"Idempotency-Key": "one"})
        client.post("/v1/correct", json=payload, headers={"Idempotency-Key": "two"})
    assert route.call_count == 2


def test_no_idempotency_key_means_no_caching(
    client: TestClient, isolated_registry: ProviderRegistry
) -> None:
    payload = {"text": "their going home", "mode": "grammar"}
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        route = mock.post("/chat/completions").mock(return_value=_mock_ok())
        r1 = client.post("/v1/correct", json=payload)
        r2 = client.post("/v1/correct", json=payload)
    assert r1.json()["request_id"] != r2.json()["request_id"]
    assert route.call_count == 2
