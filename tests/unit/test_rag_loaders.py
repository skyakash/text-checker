from pathlib import Path

import pytest

from text_checker.rag.loaders import (
    SUPPORTED_EXTENSIONS,
    UnsupportedFormatError,
    discover,
    load,
)


def test_load_markdown(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("# Title\n\nbody text")
    text = load(p)
    assert "Title" in text
    assert "body text" in text


def test_load_plain_text(tmp_path: Path) -> None:
    p = tmp_path / "notes.txt"
    p.write_text("just text\nwith two lines")
    assert load(p) == "just text\nwith two lines"


def test_load_html_strips_tags_and_scripts(tmp_path: Path) -> None:
    p = tmp_path / "page.html"
    p.write_text(
        "<html><head><script>alert('x')</script><style>body{}</style></head>"
        "<body><h1>Title</h1><p>Paragraph text.</p></body></html>"
    )
    text = load(p)
    assert "Title" in text
    assert "Paragraph text." in text
    assert "alert" not in text
    assert "body{}" not in text


def test_load_unsupported_extension_raises(tmp_path: Path) -> None:
    p = tmp_path / "x.xyz"
    p.write_text("nope")
    with pytest.raises(UnsupportedFormatError):
        load(p)


def test_discover_single_file_returns_that_file(tmp_path: Path) -> None:
    p = tmp_path / "a.md"
    p.write_text("hi")
    assert discover(p) == [p]


def test_discover_directory_non_recursive(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    (tmp_path / "ignore.xyz").write_text("nope")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.md").write_text("c")
    found = discover(tmp_path, recursive=False)
    names = [p.name for p in found]
    assert "a.md" in names
    assert "b.txt" in names
    assert "ignore.xyz" not in names
    assert "c.md" not in names


def test_discover_directory_recursive(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("a")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.md").write_text("c")
    found = discover(tmp_path, recursive=True)
    names = sorted(p.name for p in found)
    assert names == ["a.md", "c.md"]


def test_all_documented_extensions_are_in_supported_set() -> None:
    assert ".md" in SUPPORTED_EXTENSIONS
    assert ".markdown" in SUPPORTED_EXTENSIONS
    assert ".txt" in SUPPORTED_EXTENSIONS
    assert ".html" in SUPPORTED_EXTENSIONS
    assert ".htm" in SUPPORTED_EXTENSIONS
    assert ".pdf" in SUPPORTED_EXTENSIONS
