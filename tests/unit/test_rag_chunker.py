from text_checker.rag.chunker import chunk_text


def test_empty_input_produces_no_chunks() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_is_one_chunk() -> None:
    chunks = chunk_text("hello world")
    assert len(chunks) == 1
    assert chunks[0].text == "hello world"
    assert chunks[0].section is None
    assert chunks[0].index == 0


def test_long_text_splits_into_multiple_chunks_with_overlap() -> None:
    paragraphs = ["paragraph %d %s" % (i, "x" * 400) for i in range(5)]
    chunks = chunk_text("\n\n".join(paragraphs), max_chars=500, overlap=50)
    assert len(chunks) > 1
    for i in range(1, len(chunks)):
        assert chunks[i - 1].text[-30:] in chunks[i].text or len(chunks[i - 1].text) < 30


def test_section_tracks_most_recent_heading() -> None:
    text = (
        "# Overview\n\n"
        "intro paragraph\n\n"
        "## Snapshots\n\n"
        "snapshot details paragraph\n\n"
        "## Permissions\n\n"
        "permission details"
    )
    chunks = chunk_text(text, max_chars=80, overlap=0)
    sections = [c.section for c in chunks]
    assert "Snapshots" in sections
    assert "Permissions" in sections


def test_chunks_have_incrementing_indices() -> None:
    text = "\n\n".join(["para %d" % i + " " + "x" * 200 for i in range(10)])
    chunks = chunk_text(text, max_chars=300, overlap=20)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_single_paragraph_exceeding_max_is_emitted_as_oversized() -> None:
    huge = "x" * 5000
    chunks = chunk_text(huge, max_chars=500)
    assert len(chunks) >= 1
    assert any(len(c.text) >= 500 for c in chunks)
