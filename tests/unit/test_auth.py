import httpx
import pytest
import respx
from fastapi.testclient import TestClient

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
def authed_client(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> TestClient:
    from text_corrector.config import settings

    monkeypatch.setattr(settings, "api_keys", "key-good,other-good")
    reg = ProviderRegistry(Settings(ollama_base_url="http://ollama.test/v1"))
    monkeypatch.setattr(registry_module, "_registry", reg)
    return client


def test_missing_api_key_returns_401(authed_client: TestClient) -> None:
    r = authed_client.post(
        "/v1/correct",
        json={"text": "hi there", "mode": "grammar"},
    )
    assert r.status_code == 401


def test_wrong_api_key_returns_401(authed_client: TestClient) -> None:
    r = authed_client.post(
        "/v1/correct",
        headers={"X-API-Key": "key-bad"},
        json={"text": "hi there", "mode": "grammar"},
    )
    assert r.status_code == 401


def test_correct_api_key_passes_through(authed_client: TestClient) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=_mock_ok())
        r = authed_client.post(
            "/v1/correct",
            headers={"X-API-Key": "key-good"},
            json={"text": "their going home", "mode": "grammar"},
        )
    assert r.status_code == 200


def test_unauthenticated_when_no_keys_configured(client: TestClient) -> None:
    r = client.get("/v1/modes")
    assert r.status_code == 200
