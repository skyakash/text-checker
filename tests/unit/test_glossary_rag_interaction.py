"""Regression tests for the glossary + RAG interaction bug.

Original failure (Jun 25, 2026): both qwen2.5:7b-instruct and hermes3:8b
returned `flagged: true` for the input "we improved the hallucination guard
in text-checker" in release-note mode with "Hallucination Guard" in the
glossary. RAG retrieved chunks containing the term verbatim; the model
inferred the placeholder's value from context and either substituted it in
the wrong case (qwen) or meta-described its own intent (hermes). Same input
with RAG off worked for both. Two fixes — chunk-masking and case-
canonicalizing — close the failure mode in the orchestrator.
"""

from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from text_checker.config import Settings
from text_checker.glossary import store as glossary_store_module
from text_checker.providers import registry as registry_module
from text_checker.providers.registry import ProviderRegistry
from text_checker.rag import store as rag_store_module
from text_checker.rag.embeddings import EmbeddingsClient


def _mock_chat(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "test-model",
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
        },
    )


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> ProviderRegistry:
    reg = ProviderRegistry(Settings(ollama_base_url="http://ollama.test/v1"))
    monkeypatch.setattr(registry_module, "_registry", reg)
    return reg


def _seed_term_and_chunk(term: str = "Hallucination Guard") -> None:
    glossary_store_module._store.add(term)
    store = rag_store_module._store
    assert store is not None
    store.add(
        ids=["docs::1::0"],
        texts=[f"The {term} verifies every masked token's original value."],
        embeddings=[[0.1, 0.2, 0.3, 0.4]],
        metadatas=[{"source": "docs", "section": "Guards", "chunk_index": 0}],
    )


@pytest.fixture
def fake_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _embed(self: EmbeddingsClient, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    monkeypatch.setattr(EmbeddingsClient, "embed", _embed)


def test_glossary_terms_are_masked_inside_rag_chunks(
    client: TestClient, tmp_path: Path, fake_embedder: None
) -> None:
    # Fix #1: chunk text containing the glossary term should reach the model
    # with the placeholder, not the term itself.
    _seed_term_and_chunk()
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        route = mock.post("/chat/completions").mock(return_value=_mock_chat("Improved <<MASK_5>>."))
        client.post(
            "/v1/correct",
            json={"text": "we improved the hallucination guard", "mode": "release-note"},
        )

    sent_body = route.calls.last.request.content.decode()
    # The chunk should have been rewritten — the canonical term must not be
    # visible to the model.
    assert "Hallucination Guard" not in sent_body
    # And a mask placeholder should be in the prompt (in both input and chunk).
    assert "<<MASK_" in sent_body


def test_lowercase_glossary_in_model_output_is_canonicalized_and_accepted(
    client: TestClient, tmp_path: Path
) -> None:
    # Fix #2: if the model writes the glossary term in any case other than
    # canonical, the guard accepts it and the response uses the canonical case.
    glossary_store_module._store.add("Hallucination Guard")
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(
            return_value=_mock_chat("Improved the hallucination guard in text-checker.")
        )
        r = client.post(
            "/v1/correct",
            json={"text": "we improved the hallucination guard in text-checker", "mode": "release-note"},
        )
    body = r.json()
    assert body["flagged"] is False
    assert "Hallucination Guard" in body["corrected_text"]
    assert "hallucination guard" not in body["corrected_text"]


def test_canonicalize_does_not_alter_non_glossary_masks(client: TestClient) -> None:
    # URLs and ticket IDs go through the masker but aren't glossary terms;
    # their canonical value is exactly what was extracted from the input.
    # Canonicalize should not touch them.
    with respx.mock(base_url="http://ollama.test/v1") as mock:
        mock.post("/chat/completions").mock(
            return_value=_mock_chat("See <<MASK_0>> for details.")
        )
        r = client.post(
            "/v1/correct",
            json={"text": "see https://example.com/foo for details", "mode": "release-note"},
        )
    assert r.status_code == 200
    assert "https://example.com/foo" in r.json()["corrected_text"]