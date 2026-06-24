from pathlib import Path

import httpx
import pytest

from text_checker.rag.embeddings import EmbeddingsClient
from text_checker.rag.ingest import ingest_path
from text_checker.rag.retriever import retrieve
from text_checker.rag.store import RagStore

pytestmark = pytest.mark.integration

OLLAMA_URL = "http://localhost:11434/v1"
EMBEDDING_MODEL = "nomic-embed-text"


def _model_available() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
    except httpx.HTTPError:
        return False
    if r.status_code != 200:
        return False
    return any(EMBEDDING_MODEL in m.get("name", "") for m in r.json().get("models", []))


@pytest.fixture(autouse=True)
def _skip_if_no_ollama() -> None:
    if not _model_available():
        pytest.skip(f"Ollama with {EMBEDDING_MODEL} not running on localhost:11434")


async def test_real_embeddings_and_retrieval_round_trip(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "editor.md").write_text(
        "# Editor\n\n"
        "## Snapshots\n\n"
        "The snapshot loader reads serialized editor state from disk.\n\n"
        "## Permissions\n\n"
        "The permissions module controls which roles can edit which documents."
    )

    store = RagStore(tmp_path / "rag", collection_name="integration")
    embedder = EmbeddingsClient(base_url=OLLAMA_URL, model=EMBEDDING_MODEL)

    result = await ingest_path(docs, source="flowstate", store=store, embedder=embedder)
    assert result.files == 1
    assert result.chunks >= 1
    assert store.count() >= 1

    results = await retrieve(
        "we fixed the snapshot loader",
        k=3,
        store=store,
        embedder=embedder,
    )
    assert results
    top = results[0]
    assert "snapshot" in top.text.lower()
