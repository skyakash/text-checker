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


class _EmbedderSpy:
    call_count: int = 0


@pytest.fixture
def fake_embedder(monkeypatch: pytest.MonkeyPatch) -> _EmbedderSpy:
    spy = _EmbedderSpy()

    async def _embed(self: EmbeddingsClient, texts: list[str]) -> list[list[float]]:
        spy.call_count += 1
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    monkeypatch.setattr(EmbeddingsClient, "embed", _embed)
    return spy


def test_rag_context_appears_in_response_when_store_has_docs(
    client: TestClient, tmp_path: Path, fake_embedder: _EmbedderSpy
) -> None:
    _seed_rag(tmp_path)
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=_mock_chat())
        r = client.post(
            "/v1/correct",
            json={"text": "we fixed the editor", "mode": "release-note"},
        )
    assert r.status_code == 200
    body = r.json()
    assert len(body["rag_context_used"]) == 1
    ctx = body["rag_context_used"][0]
    assert ctx["source"] == "flowstate"
    assert ctx["section"] == "Snapshots"


def test_rag_context_block_is_injected_into_system_prompt(
    client: TestClient, tmp_path: Path, fake_embedder: _EmbedderSpy
) -> None:
    _seed_rag(tmp_path)
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        route = mock.post("/chat/completions").mock(return_value=_mock_chat())
        client.post(
            "/v1/correct",
            json={"text": "we fixed the editor", "mode": "release-note"},
        )

    sent_body = route.calls.last.request.content.decode()
    assert "flowstate" in sent_body
    assert "Snapshots" in sent_body
    assert "snapshot loader" in sent_body


def test_use_rag_false_skips_retrieval(
    client: TestClient, tmp_path: Path, fake_embedder: _EmbedderSpy
) -> None:
    _seed_rag(tmp_path)
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        route = mock.post("/chat/completions").mock(return_value=_mock_chat())
        r = client.post(
            "/v1/correct",
            json={"text": "we fixed the editor", "mode": "release-note", "use_rag": False},
        )
    body = r.json()
    assert body["rag_context_used"] == []
    assert fake_embedder.call_count == 0
    sent_body = route.calls.last.request.content.decode()
    assert "snapshot loader" not in sent_body


def test_empty_rag_store_yields_empty_context(client: TestClient) -> None:
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=_mock_chat())
        r = client.post(
            "/v1/correct",
            json={"text": "we fixed the editor", "mode": "release-note"},
        )
    assert r.json()["rag_context_used"] == []


def test_grammar_mode_skips_rag_by_default(
    client: TestClient, tmp_path: Path, fake_embedder: _EmbedderSpy
) -> None:
    # Regression for the case where RAG context biased a grammar fix:
    # 'flowstate is going to be reased next quartar' got replaced with
    # 'Phase 1 is going to be released next quarter' because retrieved
    # roadmap chunks misled the model.
    _seed_rag(tmp_path)
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        route = mock.post("/chat/completions").mock(return_value=_mock_chat())
        r = client.post(
            "/v1/correct",
            json={"text": "their going home", "mode": "grammar"},
        )
    body = r.json()
    assert body["rag_context_used"] == []
    assert fake_embedder.call_count == 0
    sent_body = route.calls.last.request.content.decode()
    assert "snapshot loader" not in sent_body


def test_use_rag_true_overrides_grammar_skip(
    client: TestClient, tmp_path: Path, fake_embedder: _EmbedderSpy
) -> None:
    _seed_rag(tmp_path)
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=_mock_chat())
        r = client.post(
            "/v1/correct",
            json={"text": "we fixed the editor", "mode": "grammar", "use_rag": True},
        )
    assert len(r.json()["rag_context_used"]) == 1
    assert fake_embedder.call_count == 1


def test_min_score_floor_filters_weak_matches(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression for the live-testing case where score-0.55 chunks polluted
    # a grammar fix. Restore the production floor and seed orthogonal vectors
    # so the resulting score is well below the floor.
    from text_checker.config import settings as live_settings

    monkeypatch.setattr(live_settings, "rag_min_score", 0.5)

    store = rag_store_module._store
    assert store is not None
    store.add(
        ids=["unrelated::1::0"],
        texts=["completely unrelated content about something else"],
        embeddings=[[1.0, 0.0, 0.0, 0.0]],
        metadatas=[{"source": "unrelated", "section": "Other", "chunk_index": 0}],
    )

    async def _orthogonal(self: EmbeddingsClient, texts: list[str]) -> list[list[float]]:
        return [[0.0, 1.0, 0.0, 0.0] for _ in texts]

    monkeypatch.setattr(EmbeddingsClient, "embed", _orthogonal)

    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(return_value=_mock_chat())
        r = client.post(
            "/v1/correct",
            json={"text": "we fixed the editor", "mode": "release-note"},
        )
    assert r.json()["rag_context_used"] == []


def test_config_defaults_match_production_floor_and_skip() -> None:
    # Lock the production defaults so a careless config edit doesn't silently
    # widen the floor or remove the grammar skip.
    fresh = Settings()
    assert fresh.rag_min_score == 0.65
    assert "grammar" in fresh.rag_skip_modes_set
