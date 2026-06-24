from pathlib import Path

import pytest

from text_checker.rag.store import RagStore


@pytest.fixture
def store(tmp_path: Path) -> RagStore:
    return RagStore(tmp_path / "rag", collection_name="test_store")


def _vec(seed: int, dim: int = 8) -> list[float]:
    return [(seed + i) * 0.01 for i in range(dim)]


def test_empty_store_count_zero(store: RagStore) -> None:
    assert store.count() == 0
    assert store.list_sources() == []
    assert store.query(_vec(0), k=3) == []


def test_add_and_count(store: RagStore) -> None:
    store.add(
        ids=["s::a::0", "s::a::1"],
        texts=["one", "two"],
        embeddings=[_vec(1), _vec(2)],
        metadatas=[
            {"source": "s", "file": "a.md", "section": "Intro", "chunk_index": 0},
            {"source": "s", "file": "a.md", "section": "Intro", "chunk_index": 1},
        ],
    )
    assert store.count() == 2


def test_query_returns_scored_chunks(store: RagStore) -> None:
    store.add(
        ids=["x::1::0"],
        texts=["the snapshot loader reads serialized state"],
        embeddings=[_vec(5)],
        metadatas=[{"source": "x", "file": "1.md", "section": "Snapshots", "chunk_index": 0}],
    )
    results = store.query(_vec(5), k=3)
    assert len(results) == 1
    assert results[0].source == "x"
    assert results[0].section == "Snapshots"
    assert 0.0 <= results[0].score <= 1.0


def test_list_sources_groups_by_source(store: RagStore) -> None:
    store.add(
        ids=["a::1::0", "a::2::0", "b::1::0"],
        texts=["a1", "a2", "b1"],
        embeddings=[_vec(1), _vec(2), _vec(3)],
        metadatas=[
            {"source": "a", "section": "", "chunk_index": 0},
            {"source": "a", "section": "", "chunk_index": 0},
            {"source": "b", "section": "", "chunk_index": 0},
        ],
    )
    sources = store.list_sources()
    by_name = {s.source: s.chunks for s in sources}
    assert by_name == {"a": 2, "b": 1}


def test_remove_source_drops_only_matching_chunks(store: RagStore) -> None:
    store.add(
        ids=["a::1::0", "b::1::0"],
        texts=["a1", "b1"],
        embeddings=[_vec(1), _vec(2)],
        metadatas=[
            {"source": "a", "section": "", "chunk_index": 0},
            {"source": "b", "section": "", "chunk_index": 0},
        ],
    )
    removed = store.remove_source("a")
    assert removed == 1
    assert store.count() == 1
    assert [s.source for s in store.list_sources()] == ["b"]


def test_remove_unknown_source_is_zero(store: RagStore) -> None:
    assert store.remove_source("missing") == 0


def test_reset_clears_everything(store: RagStore) -> None:
    store.add(
        ids=["a::1::0"],
        texts=["x"],
        embeddings=[_vec(1)],
        metadatas=[{"source": "a", "section": "", "chunk_index": 0}],
    )
    store.reset()
    assert store.count() == 0
