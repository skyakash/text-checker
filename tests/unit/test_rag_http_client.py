"""Unit tests for the CLI's remote (--server) mode: RagHttpClient."""
from __future__ import annotations

import httpx
import pytest
import respx

from text_checker.rag.http_client import RagHttpClient


def test_ingest_sends_content_and_returns_chunk_count() -> None:
    client = RagHttpClient(base_url="http://svc.test", api_key="test-key")
    with respx.mock(base_url="http://svc.test") as mock:
        route = mock.post("/v1/rag/ingest").mock(
            return_value=httpx.Response(
                200,
                json={"source": "doc-a", "chunks_indexed": 4},
            )
        )
        n = client.ingest(content="hello world", source="doc-a", section="intro")

    assert n == 4
    assert route.called
    body = route.calls.last.request.content
    assert b'"content":"hello world"' in body
    assert b'"source":"doc-a"' in body
    assert route.calls.last.request.headers["x-api-key"] == "test-key"


def test_ingest_without_api_key_omits_header() -> None:
    client = RagHttpClient(base_url="http://svc.test", api_key=None)
    with respx.mock(base_url="http://svc.test") as mock:
        mock.post("/v1/rag/ingest").mock(
            return_value=httpx.Response(200, json={"source": "s", "chunks_indexed": 1})
        )
        client.ingest(content="x", source="s")
        assert "x-api-key" not in mock.calls.last.request.headers


def test_ingest_raises_on_server_error() -> None:
    client = RagHttpClient(base_url="http://svc.test", api_key="test-key")
    with respx.mock(base_url="http://svc.test") as mock:
        mock.post("/v1/rag/ingest").mock(return_value=httpx.Response(413))
        with pytest.raises(httpx.HTTPStatusError):
            client.ingest(content="x", source="s")


def test_list_sources_returns_server_payload() -> None:
    client = RagHttpClient(base_url="http://svc.test", api_key="test-key")
    with respx.mock(base_url="http://svc.test") as mock:
        mock.get("/v1/rag/sources").mock(
            return_value=httpx.Response(
                200, json=[{"source": "a", "chunks": 3}, {"source": "b", "chunks": 5}]
            )
        )
        sources = client.list_sources()
    assert sources == [{"source": "a", "chunks": 3}, {"source": "b", "chunks": 5}]


def test_delete_source_returns_count() -> None:
    client = RagHttpClient(base_url="http://svc.test", api_key="test-key")
    with respx.mock(base_url="http://svc.test") as mock:
        mock.delete("/v1/rag/sources/doomed").mock(
            return_value=httpx.Response(
                200, json={"source": "doomed", "chunks_removed": 2}
            )
        )
        n = client.delete_source("doomed")
    assert n == 2
