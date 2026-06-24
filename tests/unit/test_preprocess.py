import pytest

from text_checker.pipeline.exceptions import InputTooLongError, NonEnglishInputError
from text_checker.pipeline.preprocess import (
    is_likely_english,
    mask,
    preprocess,
    unmask,
)


def test_mask_unmask_round_trips_url() -> None:
    masked = mask("see https://example.com/foo for details")
    assert "https://example.com/foo" not in masked.text
    assert unmask(masked.text, masked.masks) == "see https://example.com/foo for details"


def test_mask_unmask_round_trips_mention() -> None:
    masked = mask("hey @alice can you check this")
    assert "@alice" not in masked.text
    assert unmask(masked.text, masked.masks) == "hey @alice can you check this"


def test_mask_unmask_round_trips_ticket_id() -> None:
    masked = mask("blocked by PROJ-1234 today")
    assert "PROJ-1234" not in masked.text
    assert unmask(masked.text, masked.masks) == "blocked by PROJ-1234 today"


def test_mask_unmask_round_trips_inline_code() -> None:
    original = "call `do_thing(x, y)` first"
    masked = mask(original)
    assert "`do_thing(x, y)`" not in masked.text
    assert unmask(masked.text, masked.masks) == original


def test_mask_unmask_round_trips_code_fence() -> None:
    original = "before\n```python\nx = 1\n```\nafter"
    masked = mask(original)
    assert "x = 1" not in masked.text
    assert unmask(masked.text, masked.masks) == original


def test_mask_handles_multiple_patterns_in_one_input() -> None:
    original = "@alice please look at PROJ-7 and https://x.com/y"
    masked = mask(original)
    assert unmask(masked.text, masked.masks) == original
    assert len(masked.masks) == 3


def test_is_likely_english_accepts_plain_english() -> None:
    assert is_likely_english("This is a plain English sentence.")


def test_is_likely_english_accepts_empty_or_punct_only() -> None:
    assert is_likely_english("")
    assert is_likely_english("...!?")


def test_is_likely_english_rejects_cjk() -> None:
    assert not is_likely_english("これは日本語の文章です。")


def test_is_likely_english_rejects_cyrillic() -> None:
    assert not is_likely_english("Это русское предложение.")


def test_preprocess_raises_on_oversize_input() -> None:
    with pytest.raises(InputTooLongError):
        preprocess("a" * 6000)


def test_preprocess_raises_on_non_english() -> None:
    with pytest.raises(NonEnglishInputError):
        preprocess("これは日本語の文章です。")


def test_preprocess_returns_masked_for_valid_english() -> None:
    out = preprocess("hello @bob, see PROJ-1")
    assert "@bob" not in out.text
    assert "PROJ-1" not in out.text
