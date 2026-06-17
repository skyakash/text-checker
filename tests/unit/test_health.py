from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readyz_returns_ready(client: TestClient) -> None:
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


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
