from __future__ import annotations

from ..api.schemas import Mode

PROMPT_VERSION = "v1"

_PRESERVE_RULE = (
    "Preserve any placeholders of the form <<MASK_n>> exactly as they appear. "
    "Do not add explanations or quote marks. Return only the corrected text."
)

_SYSTEM_PROMPTS: dict[Mode, str] = {
    Mode.GRAMMAR: (
        "You are a strict grammar editor. Fix grammar, spelling, and punctuation only. "
        "Do not rewrite, summarize, or change meaning. " + _PRESERVE_RULE
    ),
    Mode.STYLE: (
        "You are a style editor. Improve clarity and tighten phrasing. Prefer active voice. "
        "Preserve facts and intent. " + _PRESERVE_RULE
    ),
    Mode.JIRA_STORY: (
        "You are an editor for Jira user stories. Rewrite the input as a clear user story "
        "in the form 'As a <role>, I want <outcome> so that <reason>.' when possible, "
        "otherwise keep it concise and unambiguous. " + _PRESERVE_RULE
    ),
    Mode.RELEASE_NOTE: (
        "You are a release-notes editor. Rewrite each item as a clear, verb-first one-liner "
        "suitable for customer-facing release notes. " + _PRESERVE_RULE
    ),
}


def system_prompt(mode: Mode) -> str:
    return _SYSTEM_PROMPTS[mode]


def user_prompt(text: str) -> str:
    return text


def with_context(system: str, contexts: list[tuple[str, str | None, str]]) -> str:
    if not contexts:
        return system
    blocks: list[str] = []
    for source, section, text in contexts:
        header = f"[{source} § {section}]" if section else f"[{source}]"
        blocks.append(f"{header}\n{text}")
    context_block = "\n\n".join(blocks)
    return (
        system
        + "\n\nContext about products and terminology that may appear in this text:\n"
        + "---\n"
        + context_block
        + "\n---\n"
        + "Use this context to preserve product-specific terminology and meaning. "
        + "Do not introduce information not present in the input text."
    )
