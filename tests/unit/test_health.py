import httpx
import respx
from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readyz_returns_ready_when_upstreams_are_ok(client: TestClient) -> None:
    # /readyz now actively probes the configured Ollama base URL; mock it so the
    # test doesn't depend on a real Ollama on the host.
    with respx.mock(base_url="http://localhost:11434/v1") as mock:
        mock.get("/models").mock(return_value=httpx.Response(200, json={"data": []}))
        r = client.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert "components" in body


def test_modes_lists_all_four(client: TestClient) -> None:
    r = client.get("/v1/modes")
    assert r.status_code == 200
    assert set(r.json()) == {"grammar", "style", "jira-story", "release-note"}


def test_models_returns_at_least_the_default(client: TestClient) -> None:
    r = client.get("/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert all(isinstance(m, str) for m in body)
