"""Unit tests for the RAG CLI's remote (--server) mode, specifically the
directory-ingest cleanup pass added for A2.

Local mode drops the whole source; remote mode with a directory target
must delete every existing source == args.source or prefixed by
"args.source/" so files removed from the directory don't leave stale
chunks behind.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock

from text_checker.rag.__main__ import _ingest_remote


def _args(target: Path, source: str, recursive: bool = False) -> argparse.Namespace:
    ns = argparse.Namespace()
    ns.target = target
    ns.source = source
    ns.recursive = recursive
    ns.server = "http://svc.test"
    return ns


def test_directory_ingest_cleans_stale_prefixed_sources(tmp_path: Path) -> None:
    # Two files: only b.md remains. Remote store has stale chunks under
    # "docs/a.md" (file was deleted from the directory since last ingest).
    (tmp_path / "b.md").write_text("# b\n\nnew content")

    client = MagicMock()
    client.list_sources.return_value = [
        {"source": "docs/a.md", "chunks": 3},  # stale — deleted since last ingest
        {"source": "docs/b.md", "chunks": 2},  # will be replaced
        {"source": "other", "chunks": 1},  # unrelated — must not be touched
    ]
    client.ingest.return_value = 4

    # Need at least 2 files to hit the cleanup branch — add one more.
    (tmp_path / "c.md").write_text("# c\n\nmore content")

    rc = _ingest_remote(client, _args(tmp_path, source="docs"))
    assert rc == 0

    # Cleanup: docs/a.md AND docs/b.md were deleted (both matched the prefix),
    # but NOT "other".
    deleted = {call.args[0] for call in client.delete_source.call_args_list}
    assert deleted == {"docs/a.md", "docs/b.md"}
    assert "other" not in deleted

    # Then the two current files were ingested.
    ingested_sources = {call.kwargs["source"] for call in client.ingest.call_args_list}
    assert ingested_sources == {"docs/b.md", "docs/c.md"}


def test_directory_ingest_also_deletes_bare_source_match(tmp_path: Path) -> None:
    # If a previous single-file ingest used the bare source name (before
    # directory ingest was used), that stale record must also be cleaned.
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "b.md").write_text("b")

    client = MagicMock()
    client.list_sources.return_value = [
        {"source": "docs", "chunks": 5},  # bare match — must clean
        {"source": "docs/a.md", "chunks": 3},
    ]
    client.ingest.return_value = 1

    rc = _ingest_remote(client, _args(tmp_path, source="docs"))
    assert rc == 0

    deleted = {call.args[0] for call in client.delete_source.call_args_list}
    assert deleted == {"docs", "docs/a.md"}


def test_single_file_ingest_skips_cleanup_pass(tmp_path: Path) -> None:
    # Single-file targets keep the endpoint's built-in replace semantics
    # (POST /v1/rag/ingest already drops prior chunks per source) — no
    # need to call list_sources or delete_source.
    (tmp_path / "solo.md").write_text("just one file")

    client = MagicMock()
    client.ingest.return_value = 1

    rc = _ingest_remote(client, _args(tmp_path / "solo.md", source="handbook"))
    assert rc == 0

    client.list_sources.assert_not_called()
    client.delete_source.assert_not_called()
    # And the ingest used the caller-provided source verbatim.
    assert client.ingest.call_args.kwargs["source"] == "handbook"


def test_ingest_passes_label_not_section(tmp_path: Path) -> None:
    # A3 rename: the CLI must pass `label=`, not `section=`.
    (tmp_path / "guide.md").write_text("content")

    client = MagicMock()
    client.ingest.return_value = 1

    _ingest_remote(client, _args(tmp_path / "guide.md", source="handbook"))
    kwargs = client.ingest.call_args.kwargs
    assert "label" in kwargs
    assert kwargs["label"] == "guide.md"
    assert "section" not in kwargs
