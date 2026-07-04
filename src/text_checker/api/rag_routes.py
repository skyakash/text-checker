from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..rag.embeddings import EmbeddingsClient
from ..rag.ingest import ingest_content
from ..rag.store import get_store
from .ratelimit import enforce_rate_limit
from .schemas import (
    RAG_INGEST_MAX_BYTES,
    RagIngestRequest,
    RagIngestResponse,
    RagSourceInfo,
)

router = APIRouter()


def _embedder() -> EmbeddingsClient:
    base_url = settings.rag_embedding_base_url or settings.ollama_base_url
    return EmbeddingsClient(base_url=base_url, model=settings.rag_embedding_model)


@router.post("/ingest", response_model=RagIngestResponse)
async def ingest(
    req: RagIngestRequest,
    _key: str = Depends(enforce_rate_limit),
) -> RagIngestResponse:
    if len(req.content.encode("utf-8")) > RAG_INGEST_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"content exceeds {RAG_INGEST_MAX_BYTES} bytes; split the document "
                "or ingest via the local CLI"
            ),
        )
    store = get_store()
    embedder = _embedder()
    result = await ingest_content(
        content=req.content,
        source=req.source,
        store=store,
        embedder=embedder,
        file_label=req.label or "inline",
    )
    return RagIngestResponse(source=result.source, chunks_indexed=result.chunks)


@router.get("/sources", response_model=list[RagSourceInfo])
async def list_sources(
    _key: str = Depends(enforce_rate_limit),
) -> list[RagSourceInfo]:
    store = get_store()
    return [RagSourceInfo(source=s.source, chunks=s.chunks) for s in store.list_sources()]


# `{source:path}` allows slashes in the source name — remote directory ingest
# creates sources like "handbook/guide.md", and without the :path converter
# those cannot be deleted (FastAPI's default path param stops at '/').
@router.delete("/sources/{source:path}")
async def delete_source(
    source: str,
    _key: str = Depends(enforce_rate_limit),
) -> dict[str, int | str]:
    store = get_store()
    removed = store.remove_source(source)
    return {"source": source, "chunks_removed": removed}
