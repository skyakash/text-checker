from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from text_checker.api import idempotency, ratelimit
from text_checker.glossary import store as glossary_store
from text_checker.main import app
from text_checker.rag import store as rag_store


@pytest.fixture(autouse=True)
def reset_request_state(tmp_path: Path) -> None:
    ratelimit.reset()
    idempotency.get_cache().reset()
    glossary_store._store = glossary_store.GlossaryStore(tmp_path / "glossary.json")
    rag_store._store = rag_store.RagStore(
        tmp_path / "rag", collection_name=f"test_{tmp_path.name}"
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
