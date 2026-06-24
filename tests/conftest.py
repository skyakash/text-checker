import pytest
from fastapi.testclient import TestClient

from text_checker.api import idempotency, ratelimit
from text_checker.main import app


@pytest.fixture(autouse=True)
def reset_request_state() -> None:
    ratelimit.reset()
    idempotency.get_cache().reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
