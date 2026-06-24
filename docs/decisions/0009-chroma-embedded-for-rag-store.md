# 0009. Chroma embedded for the RAG vector store, with a planned swap to pgvector

Date: 2026-06-17
Status: Accepted

## Context

Stage 2 adds RAG over product docs to ground the model on the meaning of internal product terminology. The retrieval store needs to:

- Persist embeddings across service restarts
- Support metadata-filtered deletes (so re-ingesting one `--source` doesn't disturb others)
- Run with zero extra infrastructure on a developer laptop
- Scale to thousands of chunks per tenant without rearchitecture

Vector store candidates considered:

| Option | Persistence | Extra infra | Notes |
|---|---|---|---|
| **Chroma (embedded `PersistentClient`)** | SQLite-backed local dir | none | Works out of the box; bundles its own SQLite |
| **pgvector** | Postgres + extension | requires Postgres | Cleanest long-term — overlaps Phase 1 Postgres-for-request-log work |
| **Qdrant** | server | requires Qdrant container | Production-grade but another moving piece |
| **FAISS** | files | none | No metadata filtering, no easy delete-by-source |
| **sqlite-vec** | SQLite | none | Newer; less mature ecosystem |

## Decision

We will use Chroma's `PersistentClient` (embedded mode) for Stage 2 RAG, persisting under `./data/rag/`. Configuration: `RAG_STORE_PATH`, `RAG_COLLECTION_NAME`.

When Postgres lands in Phase 1 (for the request log), we will swap the implementation to pgvector. The `RagStore` interface (`count`, `add`, `query`, `list_sources`, `remove_source`, `reset`) is the contract that defines the swap surface.

## Consequences

- Developer experience: `pip install chromadb`, no extra service to run. Matches the Ollama-local pattern we already use for inference.
- Storage path is configurable but auto-creates the directory on first use. Listed in `.gitignore` so nobody commits embeddings.
- Chroma pulls in `onnxruntime` and `tokenizers` as transitive deps (~50 MB on disk). We don't use Chroma's built-in embedding — we use Ollama via HTTP — so this is unused weight. Acceptable for Stage 2; revisit if image size matters in production.
- The swap to pgvector is one class to rewrite. The `RagStore` interface is intentionally small (six methods) and uses primitive types only. Tests against `RagStore` exercise the contract, not Chroma internals, so the same tests will validate the pgvector implementation.
- Multi-replica deployment will need pgvector (or another shared store) for the same reason rate-limit and idempotency need Redis — embedded Chroma on each replica would maintain divergent stores. Documented in ADR-0007 and in the Phase 1 roadmap.
