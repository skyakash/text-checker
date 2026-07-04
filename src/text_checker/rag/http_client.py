"""Remote RAG API client used by the CLI's --server mode.

Thin httpx wrapper around POST /v1/rag/ingest, GET /v1/rag/sources,
DELETE /v1/rag/sources/{source}. The CLI reads files locally and
sends the raw text to the server so Chroma stays isolated to the
service process (single owner, no concurrent access).
"""
from __future__ import annotations

import httpx


class RagHttpClient:
    def __init__(self, base_url: str, api_key: str | None, timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["X-API-Key"] = api_key
        self._timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def ingest(self, content: str, source: str, section: str | None = None) -> int:
        r = httpx.post(
            self._url("/v1/rag/ingest"),
            json={"content": content, "source": source, "section": section},
            headers=self._headers,
            timeout=self._timeout,
        )
        r.raise_for_status()
        return int(r.json()["chunks_indexed"])

    def list_sources(self) -> list[dict]:
        r = httpx.get(
            self._url("/v1/rag/sources"),
            headers=self._headers,
            timeout=self._timeout,
        )
        r.raise_for_status()
        return r.json()

    def delete_source(self, source: str) -> int:
        r = httpx.request(
            "DELETE",
            self._url(f"/v1/rag/sources/{source}"),
            headers=self._headers,
            timeout=self._timeout,
        )
        r.raise_for_status()
        return int(r.json()["chunks_removed"])
