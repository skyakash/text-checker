from text_checker.pipeline.preprocess import mask, unmask


def test_glossary_term_is_masked() -> None:
    masked = mask("we shipped Flowstate today", glossary_terms={"Flowstate"})
    assert "Flowstate" not in masked.text
    assert unmask(masked.text, masked.masks) == "we shipped Flowstate today"


def test_glossary_match_is_case_insensitive() -> None:
    masked = mask("we shipped flowstate today", glossary_terms={"Flowstate"})
    assert "flowstate" not in masked.text.lower()


def test_unmask_restores_canonical_case_from_glossary() -> None:
    masked = mask("we shipped flowstate today", glossary_terms={"Flowstate"})
    restored = unmask(masked.text, masked.masks)
    assert "Flowstate" in restored
    assert "flowstate" not in restored


def test_longer_terms_match_before_shorter_substrings() -> None:
    masked = mask(
        "the Flowstate Editor is great",
        glossary_terms={"Flowstate", "Flowstate Editor"},
    )
    restored = unmask(masked.text, masked.masks)
    assert restored == "the Flowstate Editor is great"
    assert len(masked.masks) == 1


def test_word_boundaries_prevent_substring_match() -> None:
    masked = mask("the ratio is good", glossary_terms={"IO"})
    assert "ratio" in masked.text


def test_multi_word_glossary_terms_match() -> None:
    masked = mask(
        "see the API Reference for details",
        glossary_terms={"API Reference"},
    )
    assert "API Reference" not in masked.text
    assert unmask(masked.text, masked.masks) == "see the API Reference for details"


def test_glossary_works_alongside_existing_patterns() -> None:
    masked = mask(
        "ping @bob about Flowstate in PROJ-7",
        glossary_terms={"Flowstate"},
    )
    restored = unmask(masked.text, masked.masks)
    assert restored == "ping @bob about Flowstate in PROJ-7"


def test_empty_glossary_is_a_noop() -> None:
    masked = mask("hello world", glossary_terms=set())
    assert masked.text == "hello world"
    assert masked.masks == {}


def test_none_glossary_is_a_noop() -> None:
    masked = mask("hello world", glossary_terms=None)
    assert masked.text == "hello world"
