from text_corrector.api.schemas import Mode
from text_corrector.pipeline.postprocess import (
    edit_ratio,
    hallucination_guard,
    structured_diff,
)


def test_edit_ratio_is_zero_for_identical() -> None:
    assert edit_ratio("hello world", "hello world") == 0.0


def test_edit_ratio_grows_with_changes() -> None:
    small = edit_ratio("hello world", "hello world!")
    big = edit_ratio("hello world", "goodbye everyone")
    assert big > small > 0.0


def test_structured_diff_skips_equal_chunks() -> None:
    chunks = structured_diff("a b c", "a b c")
    assert chunks == []


def test_structured_diff_captures_replacements() -> None:
    chunks = structured_diff("their going home", "they're going home")
    assert chunks
    assert any(c["op"] == "replace" for c in chunks)


def test_guard_passes_on_small_grammar_fix() -> None:
    passed, reason = hallucination_guard(
        "their going home", "they're going home", Mode.GRAMMAR
    )
    assert passed
    assert reason is None


def test_guard_rejects_when_edit_ratio_exceeds_threshold_for_grammar() -> None:
    passed, reason = hallucination_guard(
        "hi", "Here is a much longer rewrite of your text.", Mode.GRAMMAR
    )
    assert not passed
    assert reason is not None
    assert "edit ratio" in reason


def test_guard_rejects_leftover_mask_placeholder_in_output() -> None:
    passed, reason = hallucination_guard(
        "see this please", "see <<MASK_99>> please", Mode.GRAMMAR
    )
    assert not passed
    assert reason is not None
    assert "placeholder" in reason


def test_guard_rejects_too_many_new_capitalized_tokens() -> None:
    passed, reason = hallucination_guard(
        "ship it tomorrow",
        "Ship It Tomorrow With Sparkles And Confetti",
        Mode.GRAMMAR,
    )
    assert not passed
    assert reason is not None


def test_guard_allows_larger_rewrite_for_jira_story_mode() -> None:
    passed, _ = hallucination_guard(
        "as a user i want logout",
        "as a user, I want a logout button so I can sign out",
        Mode.JIRA_STORY,
    )
    assert passed
