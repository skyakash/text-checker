from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb

DEFAULT_PATH = Path("./data/rag")
DEFAULT_COLLECTION = "products"


@dataclass
class StoredChunk:
    id: str
    text: str
    source: str
    section: str | None
    score: float


@dataclass
class SourceInfo:
    source: str
    chunks: int


class RagStore:
    def __init__(
        self,
        persist_path: Path | None = None,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self._persist_path = persist_path or DEFAULT_PATH
        self._collection_name = collection_name
        self._persist_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._persist_path))
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return self._collection.count()

    def add(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not ids:
            return
        self._collection.add(
            ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas
        )

    def query(self, embedding: list[float], k: int = 3) -> list[StoredChunk]:
        n = self._collection.count()
        if n == 0:
            return []
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(k, n),
        )
        chunks: list[StoredChunk] = []
        for i, doc in enumerate(result["documents"][0]):
            meta = result["metadatas"][0][i]
            section_raw = meta.get("section")
            section = section_raw if section_raw else None
            chunks.append(
                StoredChunk(
                    id=result["ids"][0][i],
                    text=doc,
                    source=str(meta.get("source", "unknown")),
                    section=str(section) if section else None,
                    score=1.0 - float(result["distances"][0][i]),
                )
            )
        return chunks

    def list_sources(self) -> list[SourceInfo]:
        if self._collection.count() == 0:
            return []
        all_data = self._collection.get()
        counts: dict[str, int] = {}
        for meta in all_data["metadatas"]:
            src = str(meta.get("source", "unknown"))
            counts[src] = counts.get(src, 0) + 1
        return [SourceInfo(source=s, chunks=c) for s, c in sorted(counts.items())]

    def remove_source(self, source: str) -> int:
        existing = self._collection.get(where={"source": source})
        n = len(existing["ids"])
        if n:
            self._collection.delete(where={"source": source})
        return n

    def reset(self) -> None:
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )


_store: RagStore | None = None


def get_store() -> RagStore:
    global _store
    if _store is None:
        from ..config import settings

        _store = RagStore(
            Path(settings.rag_store_path),
            collection_name=settings.rag_collection_name,
        )
    return _store


def reset_store() -> None:
    global _store
    _store = None
