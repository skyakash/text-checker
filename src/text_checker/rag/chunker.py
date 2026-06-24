from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_MAX_CHARS = 1500
DEFAULT_OVERLAP = 200

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Chunk:
    text: str
    section: str | None
    index: int


def chunk_text(
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    if not text.strip():
        return []

    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[Chunk] = []
    current = ""
    current_section: str | None = None
    idx = 0

    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            continue

        heading = _HEADING_RE.match(stripped)
        joined = (current + "\n\n" + para).strip() if current else para

        if len(joined) <= max_chars:
            if heading:
                current_section = heading.group(2).strip()
            current = joined
            continue

        if current:
            chunks.append(Chunk(text=current, section=current_section, index=idx))
            idx += 1
            tail = current[-overlap:] if overlap > 0 else ""
            current = (tail + "\n\n" + para).strip() if tail else para
            if heading:
                current_section = heading.group(2).strip()
        else:
            if heading:
                current_section = heading.group(2).strip()
            chunks.append(Chunk(text=para, section=current_section, index=idx))
            idx += 1
            current = ""

    if current:
        chunks.append(Chunk(text=current, section=current_section, index=idx))

    return chunks
