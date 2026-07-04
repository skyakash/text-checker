"""Unit tests for text-checker-check CLI."""
from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pytest
import respx

from text_checker.check import main as check_main


def _ok_response(corrected: str = "They're going home.") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "request_id": "r-1",
            "corrected_text": corrected,
            "diff": [{"op": "replace", "old": "their", "new": "They're"}],
            "model_used": "qwen2.5:7b-instruct",
            "flagged": False,
            "flag_reason": None,
            "model_output": None,
            "rag_context_used": [],
            "metrics": {
                "latency_ms": 100,
                "tokens_in": 10,
                "tokens_out": 5,
                "edit_ratio": 0.2,
            },
        },
    )


def _flagged_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "request_id": "r-2",
            "corrected_text": "their going home",
            "diff": [],
            "model_used": "qwen2.5:7b-instruct",
            "flagged": True,
            "flag_reason": "hallucination_guard",
            "model_output": "Completely different rewrite.",
            "rag_context_used": [],
            "metrics": {
                "latency_ms": 100,
                "tokens_in": 10,
                "tokens_out": 5,
                "edit_ratio": 0.9,
            },
        },
    )


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    f = tmp_path / "note.md"
    f.write_text("their going home tonigt")
    return f


def test_exit_0_on_clean_run(sample_file: Path) -> None:
    with respx.mock(base_url="http://localhost:8080") as mock:
        mock.post("/v1/correct").mock(return_value=_ok_response())
        code = check_main([str(sample_file), "--mode", "grammar"])
    assert code == 0


def test_exit_1_when_flagged_and_fail_on_flagged(sample_file: Path) -> None:
    with respx.mock(base_url="http://localhost:8080") as mock:
        mock.post("/v1/correct").mock(return_value=_flagged_response())
        code = check_main(
            [str(sample_file), "--mode", "grammar", "--fail-on-flagged"]
        )
    assert code == 1


def test_exit_0_when_flagged_without_fail_flag(sample_file: Path) -> None:
    with respx.mock(base_url="http://localhost:8080") as mock:
        mock.post("/v1/correct").mock(return_value=_flagged_response())
        code = check_main([str(sample_file), "--mode", "grammar"])
    assert code == 0


def test_exit_2_on_missing_file(tmp_path: Path) -> None:
    code = check_main([str(tmp_path / "nope.md"), "--mode", "grammar"])
    assert code == 2


def test_exit_2_on_connection_error(sample_file: Path) -> None:
    with respx.mock(base_url="http://localhost:8080") as mock:
        mock.post("/v1/correct").mock(side_effect=httpx.ConnectError("nope"))
        code = check_main([str(sample_file), "--mode", "grammar"])
    assert code == 2


def test_exit_2_on_upstream_http_error(sample_file: Path) -> None:
    with respx.mock(base_url="http://localhost:8080") as mock:
        mock.post("/v1/correct").mock(return_value=httpx.Response(502, text="bad gateway"))
        code = check_main([str(sample_file), "--mode", "grammar"])
    assert code == 2


def test_stdin_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("their going home"))
    with respx.mock(base_url="http://localhost:8080") as mock:
        mock.post("/v1/correct").mock(return_value=_ok_response())
        code = check_main(["-", "--mode", "grammar"])
    assert code == 0


def test_json_output_shape(
    sample_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with respx.mock(base_url="http://localhost:8080") as mock:
        mock.post("/v1/correct").mock(return_value=_ok_response())
        check_main([str(sample_file), "--mode", "grammar", "--json"])
    captured = capsys.readouterr().out
    parsed = json.loads(captured)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["target"] == str(sample_file)
    assert parsed[0]["response"]["corrected_text"] == "They're going home."


def test_multiple_files(tmp_path: Path) -> None:
    a = tmp_path / "a.md"
    a.write_text("a")
    b = tmp_path / "b.md"
    b.write_text("b")
    with respx.mock(base_url="http://localhost:8080") as mock:
        route = mock.post("/v1/correct").mock(return_value=_ok_response())
        code = check_main([str(a), str(b), "--mode", "grammar"])
    assert code == 0
    # Both files should trigger requests.
    assert route.call_count == 2


def test_sends_api_key_from_env(
    sample_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEXT_CHECKER_API_KEY", "env-key")
    with respx.mock(base_url="http://localhost:8080") as mock:
        route = mock.post("/v1/correct").mock(return_value=_ok_response())
        check_main([str(sample_file), "--mode", "grammar"])
    assert route.calls.last.request.headers["x-api-key"] == "env-key"


def test_server_flag_overrides_default(sample_file: Path) -> None:
    with respx.mock(base_url="http://other.svc") as mock:
        mock.post("/v1/correct").mock(return_value=_ok_response())
        code = check_main(
            [str(sample_file), "--mode", "grammar", "--server", "http://other.svc"]
        )
    assert code == 0


def test_model_override_forwarded(sample_file: Path) -> None:
    with respx.mock(base_url="http://localhost:8080") as mock:
        route = mock.post("/v1/correct").mock(return_value=_ok_response())
        check_main(
            [str(sample_file), "--mode", "grammar", "--model", "anthropic:claude-haiku-4-5"]
        )
    body = route.calls.last.request.content
    assert b'"model":"anthropic:claude-haiku-4-5"' in body


def test_multiple_stdin_targets_rejected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Stdin can only be read once — accepting multiple '-' would silently
    # lint empty strings after the first.
    code = check_main(["-", "-", "--mode", "grammar"])
    assert code == 2
    err = capsys.readouterr().err
    assert "stdin" in err.lower() or "'-'" in err


def test_flag_takes_precedence_over_env(
    sample_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEXT_CHECKER_URL", "http://env.svc")
    with respx.mock(base_url="http://flag.svc") as mock:
        mock.post("/v1/correct").mock(return_value=_ok_response())
        code = check_main(
            [str(sample_file), "--mode", "grammar", "--server", "http://flag.svc"]
        )
    assert code == 0
