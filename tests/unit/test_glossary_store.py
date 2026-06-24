import json
from pathlib import Path

from text_checker.glossary.store import GlossaryStore


def test_add_persists_to_disk(tmp_path: Path) -> None:
    p = tmp_path / "g.json"
    s = GlossaryStore(p)
    assert s.add("Flowstate")
    s2 = GlossaryStore(p)
    assert "Flowstate" in s2.terms()


def test_add_is_idempotent(tmp_path: Path) -> None:
    s = GlossaryStore(tmp_path / "g.json")
    assert s.add("Flowstate")
    assert not s.add("Flowstate")
    assert s.terms() == ["Flowstate"]


def test_add_rejects_empty_or_whitespace(tmp_path: Path) -> None:
    s = GlossaryStore(tmp_path / "g.json")
    assert not s.add("")
    assert not s.add("   ")
    assert s.terms() == []


def test_add_trims_whitespace(tmp_path: Path) -> None:
    s = GlossaryStore(tmp_path / "g.json")
    s.add("  Flowstate  ")
    assert s.terms() == ["Flowstate"]


def test_remove_returns_false_when_missing(tmp_path: Path) -> None:
    s = GlossaryStore(tmp_path / "g.json")
    assert not s.remove("nope")


def test_remove_drops_term(tmp_path: Path) -> None:
    s = GlossaryStore(tmp_path / "g.json")
    s.add("Flowstate")
    assert s.remove("Flowstate")
    assert s.terms() == []


def test_list_returns_sorted(tmp_path: Path) -> None:
    s = GlossaryStore(tmp_path / "g.json")
    s.add("Zebra")
    s.add("Alpha")
    s.add("Mu")
    assert s.terms() == ["Alpha", "Mu", "Zebra"]


def test_import_terms_counts_only_new(tmp_path: Path) -> None:
    s = GlossaryStore(tmp_path / "g.json")
    s.add("Flowstate")
    added = s.import_terms(["Flowstate", "Editor", "Snapshot", ""])
    assert added == 2
    assert set(s.terms()) == {"Flowstate", "Editor", "Snapshot"}


def test_reset_clears_and_persists(tmp_path: Path) -> None:
    p = tmp_path / "g.json"
    s = GlossaryStore(p)
    s.import_terms(["a", "b", "c"])
    s.reset()
    assert s.terms() == []
    data = json.loads(p.read_text())
    assert data == {"terms": []}


def test_load_from_existing_file(tmp_path: Path) -> None:
    p = tmp_path / "g.json"
    p.write_text(json.dumps({"terms": ["Flowstate", "Editor"]}))
    s = GlossaryStore(p)
    assert set(s.terms()) == {"Flowstate", "Editor"}
