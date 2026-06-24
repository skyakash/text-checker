from pathlib import Path

import pytest

from text_checker.rag.retriever import retrieve
from text_checker.rag.store import RagStore


class _FakeEmbedder:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector for _ in texts]


@pytest.fixture
def store(tmp_path: Path) -> RagStore:
    s = RagStore(tmp_path / "rag", collection_name="test_retr")
    s.add(
        ids=["docs::1::0"],
        texts=["the snapshot loader reads serialized editor state"],
        embeddings=[[0.1, 0.2, 0.3, 0.4]],
        metadatas=[{"source": "docs", "section": "Snapshots", "chunk_index": 0}],
    )
    return s


async def test_returns_top_k_chunks(store: RagStore) -> None:
    embedder = _FakeEmbedder([0.1, 0.2, 0.3, 0.4])
    out = await retrieve("anything", k=3, store=store, embedder=embedder)
    assert len(out) == 1
    assert out[0].source == "docs"


async def test_empty_store_returns_empty(tmp_path: Path) -> None:
    empty = RagStore(tmp_path / "empty", collection_name="empty")
    embedder = _FakeEmbedder([0.0] * 4)
    assert await retrieve("anything", k=3, store=empty, embedder=embedder) == []


async def test_blank_query_returns_empty(store: RagStore) -> None:
    embedder = _FakeEmbedder([0.1, 0.2, 0.3, 0.4])
    assert await retrieve("   ", k=3, store=store, embedder=embedder) == []


async def test_min_score_filters_out_low_matches(store: RagStore) -> None:
    embedder = _FakeEmbedder([0.1, 0.2, 0.3, 0.4])
    out = await retrieve("anything", k=3, store=store, embedder=embedder, min_score=2.0)
    assert out == []
