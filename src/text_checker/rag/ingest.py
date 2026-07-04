from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import chunker, loaders
from .embeddings import EmbeddingsClient
from .store import RagStore


@dataclass
class IngestResult:
    source: str
    files: int
    chunks: int


async def ingest_content(
    content: str,
    source: str,
    store: RagStore,
    embedder: EmbeddingsClient,
    file_label: str = "inline",
    batch_size: int = 32,
) -> IngestResult:
    """Chunk, embed, and store an in-memory string.

    Same re-ingest semantics as ingest_path: existing chunks for `source`
    are removed before the new ones are added. Used by the HTTP API and
    for any caller that already has text in memory.
    """
    store.remove_source(source)

    chunks = chunker.chunk_text(content)
    if not chunks:
        return IngestResult(source=source, files=0, chunks=0)

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.text for c in batch]
        embeddings = await embedder.embed(texts)
        ids = [f"{source}::{file_label}::{c.index}" for c in batch]
        metadatas = [
            {
                "source": source,
                "file": file_label,
                "section": c.section or "",
                "chunk_index": c.index,
            }
            for c in batch
        ]
        store.add(ids=ids, texts=texts, embeddings=embeddings, metadatas=metadatas)

    return IngestResult(source=source, files=1, chunks=len(chunks))


async def ingest_path(
    path: Path,
    source: str,
    store: RagStore,
    embedder: EmbeddingsClient,
    recursive: bool = False,
    batch_size: int = 32,
) -> IngestResult:
    files = loaders.discover(path, recursive=recursive)
    if not files:
        return IngestResult(source=source, files=0, chunks=0)

    store.remove_source(source)

    total_chunks = 0
    for f in files:
        text = loaders.load(f)
        chunks = chunker.chunk_text(text)
        if not chunks:
            continue

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c.text for c in batch]
            embeddings = await embedder.embed(texts)
            ids = [f"{source}::{f.name}::{c.index}" for c in batch]
            metadatas = [
                {
                    "source": source,
                    "file": str(f),
                    "section": c.section or "",
                    "chunk_index": c.index,
                }
                for c in batch
            ]
            store.add(ids=ids, texts=texts, embeddings=embeddings, metadatas=metadatas)

        total_chunks += len(chunks)

    return IngestResult(source=source, files=len(files), chunks=total_chunks)
