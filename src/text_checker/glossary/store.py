from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

DEFAULT_PATH = Path("./data/glossary.json")


class GlossaryStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_PATH
        self._lock = Lock()
        self._terms: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open() as f:
            data = json.load(f)
        self._terms = set(data.get("terms", []))

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w") as f:
            json.dump({"terms": sorted(self._terms)}, f, indent=2)

    def add(self, term: str) -> bool:
        term = term.strip()
        if not term:
            return False
        with self._lock:
            if term in self._terms:
                return False
            self._terms.add(term)
            self._save()
            return True

    def remove(self, term: str) -> bool:
        with self._lock:
            if term not in self._terms:
                return False
            self._terms.discard(term)
            self._save()
            return True

    def terms(self) -> list[str]:
        with self._lock:
            return sorted(self._terms)

    def reset(self) -> None:
        with self._lock:
            self._terms.clear()
            self._save()

    def import_terms(self, terms: list[str]) -> int:
        added = 0
        with self._lock:
            for raw in terms:
                t = raw.strip()
                if t and t not in self._terms:
                    self._terms.add(t)
                    added += 1
            if added:
                self._save()
        return added


_store: GlossaryStore | None = None


def get_store() -> GlossaryStore:
    global _store
    if _store is None:
        from ..config import settings
        _store = GlossaryStore(Path(settings.glossary_path))
    return _store


def reset_store() -> None:
    global _store
    _store = None
