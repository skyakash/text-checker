import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from text_corrector.config import Settings
from text_corrector.providers import registry as registry_module
from text_corrector.providers.registry import ProviderRegistry


def _mock_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "test-model",
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8},
        },
    )


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> ProviderRegistry:
    reg = ProviderRegistry(Settings(ollama_base_url="http://ollama.test/v1"))
    monkeypatch.setattr(registry_module, "_registry", reg)
    return reg


def test_correct_happy_path_returns_corrected_text(client: TestClient) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=_mock_response("They're going home."))
        r = client.post(
            "/v1/correct",
            json={"text": "their going home", "mode": "grammar"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["corrected_text"] == "They're going home."
    assert body["flagged"] is False
    assert body["model_used"] == "test-model"
    assert body["metrics"]["tokens_in"] == 10
    assert body["metrics"]["tokens_out"] == 8
    assert body["diff"]


def test_correct_flags_when_guard_rejects(client: TestClient) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(
            return_value=_mock_response("Here Is A Totally Different Rewrite With Many New Words")
        )
        r = client.post(
            "/v1/correct",
            json={"text": "their going home", "mode": "grammar"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["flagged"] is True
    assert body["flag_reason"]
    assert body["corrected_text"] == "their going home"
    assert body["diff"] == []
    assert body["model_output"] == "Here Is A Totally Different Rewrite With Many New Words"


def test_correct_flags_when_model_drops_a_masked_token(client: TestClient) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(
            return_value=_mock_response("see the link or message them")
        )
        r = client.post(
            "/v1/correct",
            json={
                "text": "see @alice or https://example.com/x",
                "mode": "release-note",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["flagged"] is True
    assert "dropped masked token" in body["flag_reason"]
    assert body["corrected_text"] == "see @alice or https://example.com/x"
    assert body["model_output"] == "see the link or message them"


def test_correct_unmasks_protected_tokens_in_output(client: TestClient) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(
            return_value=_mock_response("see <<MASK_0>> please")
        )
        r = client.post(
            "/v1/correct",
            json={"text": "see PROJ-9 plz", "mode": "grammar"},
        )
    assert r.status_code == 200
    assert "PROJ-9" in r.json()["corrected_text"]


def test_correct_rejects_non_english_with_422(client: TestClient) -> None:
    r = client.post(
        "/v1/correct",
        json={"text": "これは日本語の文章です。", "mode": "grammar"},
    )
    assert r.status_code == 422


def test_correct_rejects_oversized_with_413(client: TestClient) -> None:
    r = client.post(
        "/v1/correct",
        json={"text": "a " * 3000, "mode": "grammar"},
    )
    assert r.status_code == 413


def test_correct_returns_502_when_upstream_fails(client: TestClient) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=httpx.Response(503))
        r = client.post(
            "/v1/correct",
            json={"text": "their going home", "mode": "grammar"},
        )
    assert r.status_code == 502
