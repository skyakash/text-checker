from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from text_checker import readiness
from text_checker.api import idempotency, ratelimit
from text_checker.config import settings
from text_checker.glossary import store as glossary_store
from text_checker.main import app
from text_checker.rag import store as rag_store


@pytest.fixture(autouse=True)
def reset_request_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ratelimit.reset()
    idempotency.reset()
    readiness.reset()
    glossary_store._store = glossary_store.GlossaryStore(tmp_path / "glossary.json")
    rag_store._store = rag_store.RagStore(
        tmp_path / "rag", collection_name=f"test_{tmp_path.name}"
    )
    # Tests verify pipeline behavior, not Chroma's cosine math, so relax the
    # production min_score floor. Tests that specifically exercise the filter
    # override this themselves.
    monkeypatch.setattr(settings, "rag_min_score", 0.0)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
