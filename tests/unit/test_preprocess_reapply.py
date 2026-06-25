from text_checker.pipeline.preprocess import mask, reapply_glossary_masks


def test_reapply_replaces_glossary_term_with_placeholder() -> None:
    m = mask("we ship Flowstate", glossary_terms={"Flowstate"})
    # m.text is "we ship <<MASK_0>>"
    chunk = "Flowstate is our editor"
    rewritten = reapply_glossary_masks(chunk, m.masks, m.glossary_placeholders)
    assert "Flowstate" not in rewritten
    assert "<<MASK_" in rewritten


def test_reapply_is_case_insensitive() -> None:
    m = mask("we ship Flowstate", glossary_terms={"Flowstate"})
    chunk = "flowstate is our editor"
    rewritten = reapply_glossary_masks(chunk, m.masks, m.glossary_placeholders)
    assert "flowstate" not in rewritten.lower()  # case-insensitive match replaced
    assert "<<MASK_" in rewritten


def test_reapply_uses_word_boundaries() -> None:
    m = mask("hello IO", glossary_terms={"IO"})
    chunk = "the ratio is 1:1"
    rewritten = reapply_glossary_masks(chunk, m.masks, m.glossary_placeholders)
    # "IO" should not match inside "ratio"
    assert "ratio" in rewritten


def test_reapply_handles_multiple_terms_longest_first() -> None:
    m = mask(
        "the Flowstate Editor and Flowstate work together",
        glossary_terms={"Flowstate", "Flowstate Editor"},
    )
    chunk = "Flowstate Editor includes Flowstate features"
    rewritten = reapply_glossary_masks(chunk, m.masks, m.glossary_placeholders)
    assert "Flowstate" not in rewritten
    assert "Editor" not in rewritten or "<<MASK_" in rewritten


def test_reapply_noop_when_no_glossary_placeholders() -> None:
    chunk = "anything goes here"
    rewritten = reapply_glossary_masks(chunk, {}, set())
    assert rewritten == chunk


def test_mask_tracks_glossary_placeholders_separately_from_pattern_masks() -> None:
    m = mask("ship Flowstate at https://example.com", glossary_terms={"Flowstate"})
    # Both masks present
    assert len(m.masks) == 2
    # Only one is a glossary mask
    assert len(m.glossary_placeholders) == 1
    # The glossary placeholder's value is Flowstate, not the URL
    placeholder = next(iter(m.glossary_placeholders))
    assert m.masks[placeholder] == "Flowstate"