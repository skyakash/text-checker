from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from text_checker.config import Settings
from text_checker.providers import registry as registry_module
from text_checker.providers.registry import ProviderRegistry
from text_checker.rag import store as rag_store_module
from text_checker.rag.embeddings import EmbeddingsClient


def _mock_chat(content: str = "They're going home.") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "test-model",
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
        },
    )


def _seed_rag(tmp_path: Path) -> None:
    store = rag_store_module._store
    assert store is not None
    store.add(
        ids=["flowstate::editor.md::0"],
        texts=["The snapshot loader reads serialized editor state from disk."],
        embeddings=[[0.1, 0.2, 0.3, 0.4]],
        metadatas=[
            {"source": "flowstate", "section": "Snapshots", "chunk_index": 0}
        ],
    )


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> ProviderRegistry:
    reg = ProviderRegistry(Settings(ollama_base_url="http://ollama.test/v1"))
    monkeypatch.setattr(registry_module, "_registry", reg)
    return reg


@pytest.fixture
def fake_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_embed(self: EmbeddingsClient, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    monkeypatch.setattr(EmbeddingsClient, "embed", _fake_embed)


def test_rag_context_appears_in_response_when_store_has_docs(
    client: TestClient, tmp_path: Path, fake_embedder: None
) -> None:
    _seed_rag(tmp_path)
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=_mock_chat())
        r = client.post(
            "/v1/correct",
            json={"text": "their going home", "mode": "grammar"},
        )
    assert r.status_code == 200
    body = r.json()
    assert len(body["rag_context_used"]) == 1
    ctx = body["rag_context_used"][0]
    assert ctx["source"] == "flowstate"
    assert ctx["section"] == "Snapshots"
    assert "snapshot loader" in ctx["preview"]


def test_rag_context_block_is_injected_into_system_prompt(
    client: TestClient, tmp_path: Path, fake_embedder: None
) -> None:
    _seed_rag(tmp_path)
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        route = mock.post("/chat/completions").mock(return_value=_mock_chat())
        client.post("/v1/correct", json={"text": "their going home", "mode": "grammar"})

    sent_body = route.calls.last.request.content.decode()
    assert "flowstate" in sent_body
    assert "Snapshots" in sent_body
    assert "snapshot loader" in sent_body


def test_use_rag_false_skips_retrieval(
    client: TestClient, tmp_path: Path, fake_embedder: None
) -> None:
    _seed_rag(tmp_path)
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        route = mock.post("/chat/completions").mock(return_value=_mock_chat())
        r = client.post(
            "/v1/correct",
            json={"text": "their going home", "mode": "grammar", "use_rag": False},
        )
    body = r.json()
    assert body["rag_context_used"] == []
    sent_body = route.calls.last.request.content.decode()
    assert "snapshot loader" not in sent_body


def test_empty_rag_store_yields_empty_context(client: TestClient) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=_mock_chat())
        r = client.post("/v1/correct", json={"text": "their going home", "mode": "grammar"})
    assert r.json()["rag_context_used"] == []
