"""CI client CLI for text-checker.

Reads files (or stdin), calls POST /v1/correct, and exits with a code that
CI systems can act on:

    0  clean run (no --fail-on-flagged, or nothing flagged)
    1  --fail-on-flagged set and at least one input flagged
    2  usage/connection error

Configuration priority: flag > env > default.
    --server / TEXT_CHECKER_URL       (default http://localhost:8080)
    --api-key / TEXT_CHECKER_API_KEY  (no default; required if service uses API_KEYS)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

DEFAULT_URL = "http://localhost:8080"
EXIT_OK = 0
EXIT_FLAGGED = 1
EXIT_ERROR = 2


def _read_input(target: str) -> str:
    if target == "-":
        return sys.stdin.read()
    path = Path(target)
    if not path.is_file():
        raise FileNotFoundError(f"not a file: {target}")
    return path.read_text(encoding="utf-8")


def _post_correct(
    base_url: str,
    api_key: str | None,
    text: str,
    mode: str,
    model: str | None,
    timeout: float = 90.0,
) -> dict[str, Any]:
    headers = {"X-API-Key": api_key} if api_key else {}
    payload: dict[str, Any] = {"text": text, "mode": mode}
    if model:
        payload["model"] = model
    r = httpx.post(
        f"{base_url.rstrip('/')}/v1/correct",
        json=payload,
        headers=headers,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def _print_human(label: str, resp: dict[str, Any], show_diff: bool) -> None:
    print(f"=== {label} ===")
    if resp.get("flagged"):
        print(f"  status: FLAGGED ({resp.get('flag_reason')})")
        if resp.get("model_output"):
            print(f"  model output (rejected): {resp['model_output']}")
    else:
        print("  status: ok")
        if show_diff and resp.get("diff"):
            for change in resp["diff"]:
                op = change.get("op", "?")
                old = change.get("old", "")
                new = change.get("new", "")
                print(f"    {op}: {old!r} -> {new!r}")
        elif not show_diff:
            print(f"  corrected: {resp.get('corrected_text', '')}")
    print(f"  model: {resp.get('model_used')}")
    if resp.get("rag_context_used"):
        print(f"  rag chunks used: {len(resp['rag_context_used'])}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="text-checker-check",
        description="Lint text files against a running text-checker service.",
    )
    parser.add_argument(
        "targets",
        nargs="+",
        help="Files to check, or '-' to read from stdin.",
    )
    parser.add_argument(
        "--mode",
        default="grammar",
        choices=["grammar", "style", "jira-story", "release-note"],
    )
    parser.add_argument("--model", default=None, help="Optional 'provider:model' override.")
    parser.add_argument("--server", default=None, help="Base URL of the text-checker service.")
    parser.add_argument("--api-key", default=None, help="X-API-Key for the service.")
    parser.add_argument("--fail-on-flagged", action="store_true")
    parser.add_argument("--diff", action="store_true", help="Show structured diff instead of corrected text.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON per target.")

    args = parser.parse_args(argv)

    # Stdin can only be read once. Passing '-' multiple times means the
    # second read gets an empty string, which is confusing at best and
    # a silent data corruption at worst — every subsequent target would
    # lint an empty file. Reject early with a clear message.
    if args.targets.count("-") > 1:
        print("error: '-' (stdin) may only appear once in targets", file=sys.stderr)
        return EXIT_ERROR

    base_url = args.server or os.environ.get("TEXT_CHECKER_URL") or DEFAULT_URL
    api_key = args.api_key or os.environ.get("TEXT_CHECKER_API_KEY")

    any_flagged = False
    results: list[dict[str, Any]] = []

    for target in args.targets:
        try:
            text = _read_input(target)
        except (FileNotFoundError, OSError) as e:
            print(f"error reading {target}: {e}", file=sys.stderr)
            return EXIT_ERROR

        try:
            resp = _post_correct(base_url, api_key, text, args.mode, args.model)
        except httpx.HTTPStatusError as e:
            print(f"service returned {e.response.status_code} for {target}: {e.response.text}", file=sys.stderr)
            return EXIT_ERROR
        except httpx.HTTPError as e:
            print(f"connection error for {target}: {e}", file=sys.stderr)
            return EXIT_ERROR

        if resp.get("flagged"):
            any_flagged = True

        if args.json:
            results.append({"target": target, "response": resp})
        else:
            _print_human(target, resp, show_diff=args.diff)

    if args.json:
        json.dump(results, sys.stdout, indent=2)
        sys.stdout.write("\n")

    if any_flagged and args.fail_on_flagged:
        return EXIT_FLAGGED
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
