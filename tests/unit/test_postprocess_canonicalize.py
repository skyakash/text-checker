from text_checker.pipeline.postprocess import canonicalize_glossary_terms


def test_canonicalize_returns_unchanged_when_no_placeholders() -> None:
    out = canonicalize_glossary_terms("anything goes here", masks={}, glossary_placeholders=set())
    assert out == "anything goes here"


def test_canonicalize_corrects_lowercase_match() -> None:
    masks = {"<<MASK_0>>": "Hallucination Guard"}
    out = canonicalize_glossary_terms(
        "Improved the hallucination guard.", masks=masks, glossary_placeholders={"<<MASK_0>>"}
    )
    assert out == "Improved the Hallucination Guard."


def test_canonicalize_corrects_uppercase_match() -> None:
    masks = {"<<MASK_0>>": "Flowstate"}
    out = canonicalize_glossary_terms(
        "the FLOWSTATE editor", masks=masks, glossary_placeholders={"<<MASK_0>>"}
    )
    assert out == "the Flowstate editor"


def test_canonicalize_is_idempotent_for_already_canonical_text() -> None:
    masks = {"<<MASK_0>>": "Flowstate"}
    out = canonicalize_glossary_terms(
        "Flowstate is ready", masks=masks, glossary_placeholders={"<<MASK_0>>"}
    )
    assert out == "Flowstate is ready"


def test_canonicalize_handles_multiple_glossary_terms() -> None:
    masks = {"<<MASK_0>>": "Flowstate", "<<MASK_1>>": "Snapshot Loader"}
    out = canonicalize_glossary_terms(
        "the flowstate snapshot loader works",
        masks=masks,
        glossary_placeholders={"<<MASK_0>>", "<<MASK_1>>"},
    )
    assert "Flowstate" in out
    assert "Snapshot Loader" in out


def test_canonicalize_skips_non_glossary_placeholders() -> None:
    # URL placeholders are not glossary terms; they should not be re-injected
    # into matching prose by canonicalize.
    masks = {"<<MASK_0>>": "https://example.com"}
    out = canonicalize_glossary_terms(
        "see https://example.com", masks=masks, glossary_placeholders=set()
    )
    assert out == "see https://example.com"