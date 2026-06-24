import argparse
import sys
from pathlib import Path

from .store import GlossaryStore, get_store


def _store_for(path: Path | None) -> GlossaryStore:
    return GlossaryStore(path) if path else get_store()


def main() -> int:
    parser = argparse.ArgumentParser(prog="text_checker.glossary")
    parser.add_argument("--path", type=Path, default=None, help="override the glossary file path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="show all glossary terms")

    p_add = sub.add_parser("add", help="add a single term")
    p_add.add_argument("term")

    p_remove = sub.add_parser("remove", help="remove a single term")
    p_remove.add_argument("term")

    p_import = sub.add_parser("import", help="import terms from a file (one per line); '-' for stdin")
    p_import.add_argument("file", type=str)

    sub.add_parser("reset", help="delete all terms")

    args = parser.parse_args()
    store = _store_for(args.path)

    if args.cmd == "list":
        all_terms = store.terms()
        if not all_terms:
            print("(empty)")
            return 0
        for t in all_terms:
            print(t)
        return 0

    if args.cmd == "add":
        if store.add(args.term):
            print(f"added: {args.term}")
        else:
            print(f"already present (or empty): {args.term}")
        return 0

    if args.cmd == "remove":
        if store.remove(args.term):
            print(f"removed: {args.term}")
        else:
            print(f"not found: {args.term}")
        return 0

    if args.cmd == "import":
        if args.file == "-":
            lines = sys.stdin.read().splitlines()
        else:
            lines = Path(args.file).read_text().splitlines()
        added = store.import_terms(lines)
        print(f"added {added} new term(s); total: {len(store.terms())}")
        return 0

    if args.cmd == "reset":
        confirm = input("Delete all glossary terms? Type YES to confirm: ")
        if confirm == "YES":
            store.reset()
            print("glossary reset")
        else:
            print("aborted")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
