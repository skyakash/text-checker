"""MCP server exposing text-checker as tools for VS Code Copilot, Claude Code, and bots.

Design: this is a THIN HTTP client of the text-checker service (/v1/correct,
/v1/modes, /v1/models, /v1/rag/ingest). It never imports the pipeline or
opens the Chroma store. That keeps auth, rate limiting, idempotency,
guardrails, and metrics applying uniformly to every consumer, and avoids
concurrent access to the embedded vector store.

Transports:
- stdio (default): text-checker-mcp                — for VS Code / Claude Code
- HTTP:  text-checker-mcp --http                    — for bots / remote

HTTP transport requires the same X-API-Key the service does. This is
enforced by a Starlette middleware wrapping the MCP ASGI app so unauth'd
requests are rejected before they reach any tool handler.
"""
from __future__ import annotations

import argparse
import os
import sys

import httpx
from mcp.server.fastmcp import FastMCP

DEFAULT_API_URL = "http://localhost:8080"
MCP_HTTP_HOST = "0.0.0.0"
MCP_HTTP_PORT = 8081


def _service_url() -> str:
    return (os.environ.get("TEXT_CHECKER_URL") or DEFAULT_API_URL).rstrip("/")


def _service_key() -> str | None:
    return os.environ.get("TEXT_CHECKER_API_KEY")


def _headers() -> dict[str, str]:
    key = _service_key()
    return {"X-API-Key": key} if key else {}


def _mcp_expected_key() -> str | None:
    """The API key clients must send to the MCP HTTP endpoint.

    Defaults to the same key we use upstream (TEXT_CHECKER_API_KEY) so
    operators configure once. Override with MCP_API_KEY if the two need
    to differ (e.g. a public MCP endpoint using a distinct key).
    """
    return os.environ.get("MCP_API_KEY") or _service_key()


mcp = FastMCP(
    name="text-checker",
    instructions=(
        "Grammar, style, and release-note correction with product-context "
        "grounding. Use correct_text for text checks; use ingest_document "
        "to add product docs to the shared RAG store."
    ),
)


@mcp.tool()
async def correct_text(text: str, mode: str = "grammar", model: str | None = None) -> dict:
    """Correct text with the configured LLM pipeline.

    Args:
        text: Input text (max 5000 chars — service returns 413 above that).
        mode: One of "grammar", "style", "jira-story", "release-note".
              Grammar is language-universal; style and release-note pull in
              product-doc context via RAG.
        model: Optional "provider:model" override (e.g. "anthropic:claude-haiku-4-5",
              "custom:llama-3.3-70b", or "ollama:qwen2.5:14b-instruct"). Bare model
              names route to ollama.

    Returns dict with corrected_text, diff, model_used, flagged, flag_reason,
    rag_context_used, and metrics. When flagged=true, corrected_text falls
    back to the original input and model_output shows what the model produced.
    """
    payload: dict[str, object] = {"text": text, "mode": mode}
    if model:
        payload["model"] = model
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(
            f"{_service_url()}/v1/correct", json=payload, headers=_headers()
        )
        r.raise_for_status()
    return r.json()


@mcp.tool()
async def list_modes() -> list[str]:
    """List available correction modes."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{_service_url()}/v1/modes", headers=_headers())
        r.raise_for_status()
    return r.json()


@mcp.tool()
async def list_models() -> list[dict]:
    """List available models with their providers.

    Returns entries like {"provider": "ollama", "model": "qwen2.5:7b-instruct"}.
    Use "provider:model" as the model argument to correct_text to route.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{_service_url()}/v1/models", headers=_headers())
        r.raise_for_status()
    return r.json()


@mcp.tool()
async def ingest_document(content: str, source: str, label: str | None = None) -> dict:
    """Add a document to the shared RAG store so future corrections can use it.

    Args:
        content: The document text (max 200KB).
        source: Logical source name. Re-ingesting the same source replaces
                its prior chunks — use a stable name per document.
        label: Optional label stored as the chunk's file metadata (useful
                for provenance and debugging). Section metadata is derived
                from markdown headings automatically — this field is NOT
                a section override.

    Returns {"source": <source>, "chunks_indexed": <n>}.
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{_service_url()}/v1/rag/ingest",
            json={"content": content, "source": source, "label": label},
            headers=_headers(),
        )
        r.raise_for_status()
    return r.json()


# ----- HTTP transport auth middleware -----


def _build_http_app():  # pragma: no cover - thin ASGI wiring
    """Wrap the MCP streamable-HTTP ASGI app with X-API-Key enforcement.

    Rejects any request that doesn't carry a matching key. The health check
    at /healthz is exempt so orchestrators can probe without a key.
    """
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    inner = mcp.streamable_http_app()
    expected = _mcp_expected_key()

    class ApiKeyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path == "/healthz":
                return await call_next(request)
            if expected is None:
                # No key configured on the server side — reject rather than
                # silently allow. Fail-closed is the safe default for an
                # externally-reachable transport.
                return JSONResponse(
                    {"error": "MCP HTTP server has no API key configured; set MCP_API_KEY or TEXT_CHECKER_API_KEY"},
                    status_code=500,
                )
            provided = request.headers.get("X-API-Key")
            if provided != expected:
                return JSONResponse(
                    {"error": "invalid or missing X-API-Key"}, status_code=401
                )
            return await call_next(request)

    async def health(request):  # noqa: ANN001
        return JSONResponse({"status": "ok"})

    return Starlette(
        routes=[
            Route("/healthz", health),
            Mount("/", app=inner),
        ],
        middleware=[Middleware(ApiKeyMiddleware)],
    )


def _run_http() -> None:  # pragma: no cover
    import uvicorn

    app = _build_http_app()
    uvicorn.run(app, host=MCP_HTTP_HOST, port=MCP_HTTP_PORT, log_level="info")


def main() -> int:
    parser = argparse.ArgumentParser(prog="text-checker-mcp")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run as an HTTP MCP server on port 8081 instead of stdio. "
        "HTTP transport requires the same X-API-Key the text-checker service uses.",
    )
    args = parser.parse_args()
    if args.http:
        _run_http()
    else:
        mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
