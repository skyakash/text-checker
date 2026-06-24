from __future__ import annotations

from .embeddings import EmbeddingsClient
from .store import RagStore, StoredChunk


async def retrieve(
    query: str,
    k: int,
    store: RagStore,
    embedder: EmbeddingsClient,
    min_score: float = 0.0,
) -> list[StoredChunk]:
    if not query.strip() or store.count() == 0:
        return []
    embeddings = await embedder.embed([query])
    results = store.query(embeddings[0], k=k)
    return [r for r in results if r.score >= min_score]
