import json
from pathlib import Path

from text_corrector.eval.runner import load_dataset
from text_corrector.eval.scoring import edit_ratio_vs_expected, exact_match


def test_exact_match_ignores_surrounding_whitespace() -> None:
    assert exact_match("hello world", "  hello world  ")
    assert not exact_match("hello world", "Hello World")


def test_edit_ratio_zero_for_identical() -> None:
    assert edit_ratio_vs_expected("same", "same") == 0.0


def test_edit_ratio_grows_with_difference() -> None:
    small = edit_ratio_vs_expected("Hello world", "Hello world.")
    big = edit_ratio_vs_expected("Hello world", "Something totally different")
    assert 0 < small < big


def test_load_dataset_parses_golden_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "golden.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps({"id": "a1", "mode": "grammar", "input": "x", "expected": "y"}),
                json.dumps({"id": "b2", "mode": "style", "input": "p", "expected": "q"}),
            ]
        )
        + "\n"
    )
    rows = load_dataset(p)
    assert len(rows) == 2
    assert rows[0].id == "a1"
    assert rows[0].mode == "grammar"
    assert rows[1].input == "p"


def test_seed_dataset_is_valid() -> None:
    rows = load_dataset(Path("tests/eval/data/golden.jsonl"))
    assert len(rows) >= 5
    assert {r.mode for r in rows} == {"grammar", "style", "jira-story", "release-note"}
