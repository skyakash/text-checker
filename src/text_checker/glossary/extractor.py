from __future__ import annotations

import json
from pathlib import Path

from ..providers.base import GenerationRequest, Provider
from ..rag import chunker, loaders

EXTRACTION_SYSTEM_PROMPT = (
    "You extract product-specific terminology from documentation.\n\n"
    "Identify and return:\n"
    "- Product names\n"
    "- Feature names\n"
    "- Module or component names\n"
    "- Internal acronyms and jargon\n"
    "- Branded technical terms\n\n"
    "Do NOT include:\n"
    "- Generic English words\n"
    "- Common technical terms (API, HTTP, JSON, database, etc.)\n"
    "- Plain English phrases\n"
    "- Section headings unless they name a product or feature\n\n"
    "Return ONLY a JSON array of strings, deduplicated and sorted alphabetically. "
    "No prose, no explanation.\n\n"
    'Example output: ["Flowstate", "Snapshot Loader", "Editor Module"]'
)


def parse_terms(raw: str) -> list[str]:
    raw = raw.strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            arr = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            arr = None
        if isinstance(arr, list):
            return sorted({str(t).strip() for t in arr if str(t).strip()})

    junk = " \t\n-*•,\"'"
    terms: set[str] = set()
    for line in raw.split("\n"):
        cleaned = line.strip(junk)
        if cleaned and len(cleaned) < 80:
            terms.add(cleaned)
    return sorted(terms)


async def extract_from_text(
    text: str,
    provider: Provider,
    model: str,
    temperature: float = 0.0,
) -> list[str]:
    if not text.strip():
        return []
    req = GenerationRequest(
        model=model,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_prompt=f"Text:\n---\n{text}\n---\n\nReturn the JSON array of terms.",
        temperature=temperature,
        max_tokens=2048,
    )
    resp = await provider.generate(req)
    return parse_terms(resp.text)


async def extract_from_file(
    path: Path,
    provider: Provider,
    model: str,
    max_chunk_chars: int = 4000,
) -> list[str]:
    text = loaders.load(path)
    chunks = chunker.chunk_text(text, max_chars=max_chunk_chars, overlap=0)
    if not chunks:
        return []
    all_terms: set[str] = set()
    for c in chunks:
        all_terms.update(await extract_from_text(c.text, provider, model))
    return sorted(all_terms)


async def extract_from_path(
    path: Path,
    provider: Provider,
    model: str,
    recursive: bool = False,
) -> list[str]:
    files = loaders.discover(path, recursive=recursive)
    if not files:
        return []
    all_terms: set[str] = set()
    for f in files:
        all_terms.update(await extract_from_file(f, provider, model))
    return sorted(all_terms)
