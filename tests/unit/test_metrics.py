import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from text_corrector.config import Settings
from text_corrector.providers import registry as registry_module
from text_corrector.providers.registry import ProviderRegistry


def _mock_ok(text: str = "They're going home.") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "test-model",
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
        },
    )


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> ProviderRegistry:
    reg = ProviderRegistry(Settings(ollama_base_url="http://ollama.test/v1"))
    monkeypatch.setattr(registry_module, "_registry", reg)
    return reg


def test_metrics_endpoint_serves_prometheus_format(client: TestClient) -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "correct_requests_total" in r.text


def test_successful_correct_increments_ok_counter(
    client: TestClient, isolated_registry: ProviderRegistry
) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=_mock_ok())
        client.post("/v1/correct", json={"text": "their going home", "mode": "grammar"})
    metrics = client.get("/metrics").text
    assert 'correct_requests_total{mode="grammar",model="test-model",status="ok"}' in metrics
    assert "correct_latency_seconds_count" in metrics


def test_flagged_correct_increments_flagged_counter(
    client: TestClient, isolated_registry: ProviderRegistry
) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(
            return_value=_mock_ok("Totally Different Output With Many New Words Added Here")
        )
        client.post("/v1/correct", json={"text": "their going home", "mode": "grammar"})
    metrics = client.get("/metrics").text
    assert 'status="flagged"' in metrics


def test_rejected_non_english_increments_rejected_counter(client: TestClient) -> None:
    client.post("/v1/correct", json={"text": "これは日本語の文章です。", "mode": "grammar"})
    metrics = client.get("/metrics").text
    assert 'status="rejected_lang"' in metrics


def test_upstream_error_increments_error_counter(
    client: TestClient, isolated_registry: ProviderRegistry
) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=httpx.Response(503))
        client.post("/v1/correct", json={"text": "their going home", "mode": "grammar"})
    metrics = client.get("/metrics").text
    assert 'status="upstream_error"' in metrics
