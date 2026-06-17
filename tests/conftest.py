import pytest
from fastapi.testclient import TestClient

from text_corrector.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
