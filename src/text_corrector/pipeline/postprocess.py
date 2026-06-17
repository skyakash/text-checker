import difflib
from typing import TypedDict

from ..api.schemas import Mode


class DiffChunk(TypedDict):
    op: str
    old: str
    new: str


_EDIT_RATIO_THRESHOLD: dict[Mode, float] = {
    Mode.GRAMMAR: 0.30,
    Mode.STYLE: 0.55,
    Mode.JIRA_STORY: 0.80,
    Mode.RELEASE_NOTE: 0.80,
}

_MAX_NEW_ENTITY_TOKENS = 2


def edit_ratio(original: str, corrected: str) -> float:
    return 1.0 - difflib.SequenceMatcher(None, original, corrected).ratio()


def structured_diff(original: str, corrected: str) -> list[DiffChunk]:
    orig_words = original.split()
    corr_words = corrected.split()
    sm = difflib.SequenceMatcher(None, orig_words, corr_words)
    chunks: list[DiffChunk] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        chunks.append(
            DiffChunk(
                op=op,
                old=" ".join(orig_words[i1:i2]),
                new=" ".join(corr_words[j1:j2]),
            )
        )
    return chunks


def hallucination_guard(
    original: str, corrected: str, mode: Mode
) -> tuple[bool, str | None]:
    if "<<MASK_" in corrected:
        return False, "model dropped or altered a masked placeholder"

    ratio = edit_ratio(original, corrected)
    threshold = _EDIT_RATIO_THRESHOLD[mode]
    if ratio > threshold:
        return False, f"edit ratio {ratio:.2f} exceeds threshold {threshold:.2f} for {mode}"

    orig_lower = {w.lower() for w in original.split()}
    new_entities = [
        w for w in corrected.split()
        if w[:1].isupper() and w.lower() not in orig_lower
    ]
    if len(new_entities) > _MAX_NEW_ENTITY_TOKENS:
        return False, f"introduced {len(new_entities)} new capitalized tokens: {new_entities[:3]}"

    return True, None
