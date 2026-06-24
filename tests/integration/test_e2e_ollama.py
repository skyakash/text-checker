import httpx
import pytest
from fastapi.testclient import TestClient

from text_checker.config import Settings
from text_checker.providers import registry as registry_module
from text_checker.providers.registry import ProviderRegistry

pytestmark = pytest.mark.integration

OLLAMA_URL = "http://localhost:11434/v1"
SMALL_MODEL = "qwen2.5:0.5b"


def _ollama_available() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
    except httpx.HTTPError:
        return False
    if r.status_code != 200:
        return False
    tags = r.json().get("models", [])
    return any(SMALL_MODEL in m.get("name", "") for m in tags)


@pytest.fixture(autouse=True)
def real_ollama_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _ollama_available():
        pytest.skip(f"Ollama with {SMALL_MODEL} not running on localhost:11434")
    reg = ProviderRegistry(Settings(ollama_base_url=OLLAMA_URL))
    monkeypatch.setattr(registry_module, "_registry", reg)


def test_correct_grammar_against_real_ollama(client: TestClient) -> None:
    r = client.post(
        "/v1/correct",
        json={"text": "their going home tonigt", "mode": "grammar", "model": SMALL_MODEL},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["model_used"]
    assert body["corrected_text"]
    assert isinstance(body["metrics"]["latency_ms"], int)
    assert body["metrics"]["latency_ms"] > 0


def test_correct_jira_story_against_real_ollama(client: TestClient) -> None:
    r = client.post(
        "/v1/correct",
        json={
            "text": "as a user i want logout button so i can log out",
            "mode": "jira-story",
            "model": SMALL_MODEL,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["corrected_text"]
