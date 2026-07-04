"""Unit tests for the MCP server tools and HTTP transport middleware.

The MCP server is a thin HTTP client of the text-checker service, so tests
mock the upstream API with respx and call the tool functions directly
(the same coroutines FastMCP registers).
"""
from __future__ import annotations

import httpx
import pytest
import respx

from text_checker import mcp_server


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEXT_CHECKER_URL", "http://svc.test")
    monkeypatch.setenv("TEXT_CHECKER_API_KEY", "svc-key")


# ----- tools -----


@pytest.mark.asyncio
async def test_correct_text_forwards_payload_and_returns_response() -> None:
    with respx.mock(base_url="http://svc.test") as mock:
        route = mock.post("/v1/correct").mock(
            return_value=httpx.Response(
                200,
                json={
                    "request_id": "r-1",
                    "corrected_text": "They're going home.",
                    "diff": [],
                    "model_used": "qwen2.5:7b-instruct",
                    "flagged": False,
                    "flag_reason": None,
                    "model_output": None,
                    "rag_context_used": [],
                    "metrics": {
                        "latency_ms": 300,
                        "tokens_in": 10,
                        "tokens_out": 5,
                        "edit_ratio": 0.2,
                    },
                },
            )
        )
        result = await mcp_server.correct_text(
            text="their going home", mode="grammar"
        )

    assert route.called
    body = route.calls.last.request.content
    assert b'"text":"their going home"' in body
    assert b'"mode":"grammar"' in body
    assert route.calls.last.request.headers["x-api-key"] == "svc-key"
    assert result["corrected_text"] == "They're going home."


@pytest.mark.asyncio
async def test_correct_text_forwards_model_override() -> None:
    with respx.mock(base_url="http://svc.test") as mock:
        route = mock.post("/v1/correct").mock(
            return_value=httpx.Response(
                200,
                json={
                    "request_id": "r-2",
                    "corrected_text": "ok",
                    "diff": [],
                    "model_used": "claude-haiku-4-5",
                    "flagged": False,
                    "flag_reason": None,
                    "model_output": None,
                    "rag_context_used": [],
                    "metrics": {"latency_ms": 0, "tokens_in": 0, "tokens_out": 0, "edit_ratio": 0.0},
                },
            )
        )
        await mcp_server.correct_text(
            text="x", mode="style", model="anthropic:claude-haiku-4-5"
        )
    assert route.called
    body = route.calls.last.request.content
    assert b'"model":"anthropic:claude-haiku-4-5"' in body


@pytest.mark.asyncio
async def test_list_modes_returns_service_response() -> None:
    with respx.mock(base_url="http://svc.test") as mock:
        mock.get("/v1/modes").mock(
            return_value=httpx.Response(
                200, json=["grammar", "style", "jira-story", "release-note"]
            )
        )
        result = await mcp_server.list_modes()
    assert set(result) == {"grammar", "style", "jira-story", "release-note"}


@pytest.mark.asyncio
async def test_list_models_returns_provider_model_entries() -> None:
    with respx.mock(base_url="http://svc.test") as mock:
        mock.get("/v1/models").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"provider": "ollama", "model": "qwen2.5:7b-instruct"},
                    {"provider": "anthropic", "model": "claude-haiku-4-5"},
                ],
            )
        )
        result = await mcp_server.list_models()
    assert result[0]["provider"] == "ollama"
    assert result[1]["provider"] == "anthropic"


@pytest.mark.asyncio
async def test_ingest_document_forwards_content_and_source() -> None:
    with respx.mock(base_url="http://svc.test") as mock:
        route = mock.post("/v1/rag/ingest").mock(
            return_value=httpx.Response(
                200, json={"source": "handbook", "chunks_indexed": 3}
            )
        )
        result = await mcp_server.ingest_document(
            content="product knowledge", source="handbook", section="intro"
        )

    assert route.called
    body = route.calls.last.request.content
    assert b'"content":"product knowledge"' in body
    assert b'"source":"handbook"' in body
    assert b'"section":"intro"' in body
    assert result == {"source": "handbook", "chunks_indexed": 3}


@pytest.mark.asyncio
async def test_correct_text_raises_on_upstream_error() -> None:
    with respx.mock(base_url="http://svc.test") as mock:
        mock.post("/v1/correct").mock(return_value=httpx.Response(502))
        with pytest.raises(httpx.HTTPStatusError):
            await mcp_server.correct_text(text="x", mode="grammar")


# ----- HTTP transport middleware -----


def test_http_transport_rejects_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from starlette.testclient import TestClient

    monkeypatch.setenv("MCP_API_KEY", "mcp-secret")
    app = mcp_server._build_http_app()
    c = TestClient(app)
    r = c.post("/mcp", json={})
    assert r.status_code == 401


def test_http_transport_rejects_wrong_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from starlette.testclient import TestClient

    monkeypatch.setenv("MCP_API_KEY", "mcp-secret")
    app = mcp_server._build_http_app()
    c = TestClient(app)
    r = c.post("/mcp", json={}, headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_http_transport_returns_500_when_no_key_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from starlette.testclient import TestClient

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("TEXT_CHECKER_API_KEY", raising=False)
    app = mcp_server._build_http_app()
    c = TestClient(app)
    r = c.post("/mcp", json={}, headers={"X-API-Key": "anything"})
    # Fail-closed: server refuses to serve any request until an operator
    # explicitly configures a key. This prevents accidental exposure.
    assert r.status_code == 500


def test_http_transport_healthz_exempt_from_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from starlette.testclient import TestClient

    monkeypatch.setenv("MCP_API_KEY", "mcp-secret")
    app = mcp_server._build_http_app()
    c = TestClient(app)
    r = c.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_stdio_transport_smoke() -> None:
    """The stdio path is exercised by FastMCP's own tests; here we just
    confirm the module imports and the tool decorators registered."""
    tool_names = {t.name for t in mcp_server.mcp._tool_manager.list_tools()}
    assert tool_names == {
        "correct_text",
        "list_modes",
        "list_models",
        "ingest_document",
    }
