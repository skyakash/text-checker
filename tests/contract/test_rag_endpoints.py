"""Contract tests for POST /v1/rag/ingest, GET /v1/rag/sources, DELETE /v1/rag/sources/{source}.

Uses the real (in-memory-backed) RagStore fixture from conftest — no need
to mock Chroma. The Ollama embeddings endpoint is mocked with respx so
tests don't require a running Ollama.
"""
from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from text_checker.api.schemas import RAG_INGEST_MAX_BYTES
from text_checker.config import settings


def _mock_embeddings(mock: respx.MockRouter) -> None:
    """Return one embedding per input string, matching the request length."""

    def _respond(request: httpx.Request) -> httpx.Response:
        import json as _json

        payload = _json.loads(request.content)
        inputs = payload["input"]
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2, 0.3, 0.4]} for _ in inputs]},
        )

    mock.post("/embeddings").mock(side_effect=_respond)


@pytest.fixture(autouse=True)
def _keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_keys", "test-key")


def test_ingest_stores_chunks_and_returns_count(client: TestClient) -> None:
    with respx.mock(base_url="http://localhost:11434/v1") as mock:
        _mock_embeddings(mock)
        r = client.post(
            "/v1/rag/ingest",
            headers={"X-API-Key": "test-key"},
            json={
                "content": "# Overview\nThis is a product doc.\n\n## Section\nAnother paragraph.",
                "source": "handbook",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "handbook"
    assert body["chunks_indexed"] >= 1


def test_ingest_requires_api_key(client: TestClient) -> None:
    r = client.post(
        "/v1/rag/ingest",
        json={"content": "hello", "source": "s"},
    )
    assert r.status_code == 401


def test_ingest_rejects_wrong_api_key(client: TestClient) -> None:
    r = client.post(
        "/v1/rag/ingest",
        headers={"X-API-Key": "wrong"},
        json={"content": "hello", "source": "s"},
    )
    assert r.status_code == 401


def test_ingest_rejects_oversized_content(client: TestClient) -> None:
    big = "a" * (RAG_INGEST_MAX_BYTES + 1)
    r = client.post(
        "/v1/rag/ingest",
        headers={"X-API-Key": "test-key"},
        json={"content": big, "source": "s"},
    )
    assert r.status_code == 413
    assert "exceeds" in r.json()["detail"]


def test_ingest_same_source_replaces_prior_chunks(client: TestClient) -> None:
    with respx.mock(base_url="http://localhost:11434/v1") as mock:
        _mock_embeddings(mock)
        client.post(
            "/v1/rag/ingest",
            headers={"X-API-Key": "test-key"},
            json={"content": "first pass content here", "source": "doc-a"},
        )
        # List should show only doc-a.
        listed = client.get(
            "/v1/rag/sources", headers={"X-API-Key": "test-key"}
        ).json()
        assert len(listed) == 1
        first_count = listed[0]["chunks"]

        # Re-ingest same source with different content.
        client.post(
            "/v1/rag/ingest",
            headers={"X-API-Key": "test-key"},
            json={"content": "totally new content replacing the old", "source": "doc-a"},
        )
        listed = client.get(
            "/v1/rag/sources", headers={"X-API-Key": "test-key"}
        ).json()
        assert len(listed) == 1  # still one source
        # It's the SAME source name — old chunks were dropped, new ones added.
        assert listed[0]["source"] == "doc-a"
        # We can't strictly assert count without knowing chunker output for
        # the specific fixture text, but we can assert non-zero and that no
        # extra source appeared.
        assert listed[0]["chunks"] >= 1


def test_list_sources_empty_by_default(client: TestClient) -> None:
    r = client.get("/v1/rag/sources", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    assert r.json() == []


def test_list_sources_requires_api_key(client: TestClient) -> None:
    r = client.get("/v1/rag/sources")
    assert r.status_code == 401


def test_delete_source_removes_chunks(client: TestClient) -> None:
    with respx.mock(base_url="http://localhost:11434/v1") as mock:
        _mock_embeddings(mock)
        client.post(
            "/v1/rag/ingest",
            headers={"X-API-Key": "test-key"},
            json={"content": "some content to be removed", "source": "doomed"},
        )
        r = client.delete(
            "/v1/rag/sources/doomed", headers={"X-API-Key": "test-key"}
        )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "doomed"
    assert body["chunks_removed"] >= 1

    # And it's gone from list.
    listed = client.get(
        "/v1/rag/sources", headers={"X-API-Key": "test-key"}
    ).json()
    assert listed == []


def test_delete_source_requires_api_key(client: TestClient) -> None:
    r = client.delete("/v1/rag/sources/anything")
    assert r.status_code == 401


def test_delete_source_with_slash_in_name(client: TestClient) -> None:
    # Remote directory ingest creates sources like "handbook/guide.md". The
    # DELETE route uses `{source:path}` so slashes reach the handler intact.
    with respx.mock(base_url="http://localhost:11434/v1") as mock:
        _mock_embeddings(mock)
        client.post(
            "/v1/rag/ingest",
            headers={"X-API-Key": "test-key"},
            json={"content": "guide content", "source": "handbook/guide.md"},
        )
        # Verify it's in the sources list.
        listed = client.get(
            "/v1/rag/sources", headers={"X-API-Key": "test-key"}
        ).json()
        assert any(s["source"] == "handbook/guide.md" for s in listed)

        r = client.delete(
            "/v1/rag/sources/handbook/guide.md",
            headers={"X-API-Key": "test-key"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "handbook/guide.md"
    assert body["chunks_removed"] >= 1

    # And it's gone from list.
    listed = client.get(
        "/v1/rag/sources", headers={"X-API-Key": "test-key"}
    ).json()
    assert listed == []


def test_ingest_rejects_oversized_content_length_early(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Middleware should reject on Content-Length before the endpoint is
    # entered — assert by spying on the ingest_content coroutine.
    called = {"n": 0}

    async def _fail(*args, **kwargs):  # type: ignore[no-untyped-def]
        called["n"] += 1
        return None

    monkeypatch.setattr("text_checker.api.rag_routes.ingest_content", _fail)

    # Send a request whose Content-Length exceeds the middleware cap.
    # The body itself doesn't need to actually be that large in a
    # TestClient — we spoof the header. Starlette respects the sent header.
    huge_body = b'{"content":"x","source":"s"}'
    r = client.post(
        "/v1/rag/ingest",
        content=huge_body,
        headers={
            "X-API-Key": "test-key",
            "Content-Type": "application/json",
            "Content-Length": str(RAG_INGEST_MAX_BYTES + 100_000),
        },
    )
    assert r.status_code == 413
    assert called["n"] == 0


def test_ingest_accepts_label_field(client: TestClient) -> None:
    # A3 rename: field is `label`, not `section`. Section metadata comes
    # from markdown headings via the chunker; `label` is stored as the
    # chunk's "file" metadata for provenance.
    with respx.mock(base_url="http://localhost:11434/v1") as mock:
        _mock_embeddings(mock)
        r = client.post(
            "/v1/rag/ingest",
            headers={"X-API-Key": "test-key"},
            json={
                "content": "some doc content",
                "source": "doc-a",
                "label": "guide.md",
            },
        )
    assert r.status_code == 200
