from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from ..config import settings
from . import loaders
from .embeddings import EmbeddingsClient
from .http_client import RagHttpClient
from .ingest import ingest_path
from .retriever import retrieve
from .store import RagStore, get_store


def _embedder() -> EmbeddingsClient:
    base_url = settings.rag_embedding_base_url or settings.ollama_base_url
    return EmbeddingsClient(base_url=base_url, model=settings.rag_embedding_model)


def _store_for(path: Path | None, collection: str) -> RagStore:
    if path:
        return RagStore(path, collection_name=collection)
    return get_store()


def _remote_client(args: argparse.Namespace) -> RagHttpClient | None:
    """Return an HTTP client if --server (or env) is set, else None (local mode)."""
    url = args.server or os.environ.get("TEXT_CHECKER_URL")
    if not url:
        return None
    api_key = args.api_key or os.environ.get("TEXT_CHECKER_API_KEY")
    return RagHttpClient(base_url=url, api_key=api_key)


def _ingest_remote(client: RagHttpClient, args: argparse.Namespace) -> int:
    files = loaders.discover(args.target, recursive=args.recursive)
    if not files:
        print("no supported files found")
        return 0

    total = 0
    for i, f in enumerate(files):
        text = loaders.load(f)
        # For a single-file target, use the caller-provided source verbatim.
        # For a directory, keep files distinct (source/filename) so `list`
        # shows them separately and users can remove individual files.
        effective_source = args.source if len(files) == 1 else f"{args.source}/{f.name}"
        try:
            n = client.ingest(content=text, source=effective_source, section=f.name)
        except Exception as e:
            print(f"error ingesting {f}: {e}", file=sys.stderr)
            return 2
        print(f"  {f.name}: {n} chunks (source={effective_source})")
        total += n

    print(f"\ningested {len(files)} file(s), {total} chunks total via {args.server or os.environ.get('TEXT_CHECKER_URL')}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    client = _remote_client(args)
    if client is not None:
        return _ingest_remote(client, args)

    store = _store_for(args.path, args.collection)
    embedder = _embedder()
    result = asyncio.run(
        ingest_path(
            path=args.target,
            source=args.source,
            store=store,
            embedder=embedder,
            recursive=args.recursive,
        )
    )
    print(f"ingested source={result.source} files={result.files} chunks={result.chunks}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    client = _remote_client(args)
    if client is not None:
        try:
            sources = client.list_sources()
        except Exception as e:
            print(f"error listing sources: {e}", file=sys.stderr)
            return 2
        if not sources:
            print("(empty)")
            return 0
        for s in sources:
            print(f"{s['source']:30} {s['chunks']:>6} chunks")
        return 0

    store = _store_for(args.path, args.collection)
    sources = store.list_sources()
    if not sources:
        print("(empty)")
        return 0
    for s in sources:
        print(f"{s.source:30} {s.chunks:>6} chunks")
    print(f"\ntotal: {store.count()} chunks across {len(sources)} source(s)")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    # Search intentionally stays local — it's a debug tool for tuning
    # min_score and inspecting the actual store, not a client operation.
    store = _store_for(args.path, args.collection)
    embedder = _embedder()
    results = asyncio.run(
        retrieve(args.query, k=args.k, store=store, embedder=embedder)
    )
    if not results:
        print("(no results)")
        return 0
    for i, r in enumerate(results, 1):
        section = f" § {r.section}" if r.section else ""
        preview = r.text.strip().replace("\n", " ")[:120]
        print(f"{i}. ({r.score:.2f}) {r.source}{section}")
        print(f"   {preview}...")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    client = _remote_client(args)
    if client is not None:
        try:
            n = client.delete_source(args.source)
        except Exception as e:
            print(f"error removing source: {e}", file=sys.stderr)
            return 2
        print(f"removed {n} chunk(s) from source '{args.source}'")
        return 0

    store = _store_for(args.path, args.collection)
    n = store.remove_source(args.source)
    print(f"removed {n} chunk(s) from source '{args.source}'")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    confirm = input("Delete ALL RAG content? Type YES to confirm: ")
    if confirm != "YES":
        print("aborted")
        return 0
    store = _store_for(args.path, args.collection)
    store.reset()
    print("rag store reset")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="text_checker.rag")
    parser.add_argument("--path", type=Path, default=None, help="override the rag store path (local mode)")
    parser.add_argument("--collection", default="products", help="collection name within the store")
    parser.add_argument(
        "--server",
        default=None,
        help="base URL of a running text-checker (e.g. http://localhost:8080). "
        "When set, ingest/list/remove talk to the server instead of touching "
        "local files. Also read from env TEXT_CHECKER_URL.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="X-API-Key for --server mode. Also read from env TEXT_CHECKER_API_KEY.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="ingest a file or directory")
    p_ingest.add_argument("target", type=Path)
    p_ingest.add_argument(
        "--source",
        required=True,
        help="logical source name; re-ingest with the same source replaces all chunks",
    )
    p_ingest.add_argument("--recursive", action="store_true")
    p_ingest.set_defaults(func=cmd_ingest)

    p_list = sub.add_parser("list", help="show sources and chunk counts")
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser("search", help="debug retrieval (local only)")
    p_search.add_argument("query")
    p_search.add_argument("--k", type=int, default=3)
    p_search.set_defaults(func=cmd_search)

    p_remove = sub.add_parser("remove", help="remove all chunks for a source")
    p_remove.add_argument("source")
    p_remove.set_defaults(func=cmd_remove)

    p_reset = sub.add_parser("reset", help="delete all RAG content (local only)")
    p_reset.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
