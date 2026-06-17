import re
from dataclasses import dataclass, field

from .exceptions import InputTooLongError, NonEnglishInputError

MAX_INPUT_CHARS = 5000

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("code_fence", re.compile(r"```[\s\S]*?```")),
    ("inline_code", re.compile(r"`[^`\n]+`")),
    ("url", re.compile(r"https?://\S+")),
    ("mention", re.compile(r"@[\w.-]+")),
    ("ticket", re.compile(r"\b[A-Z]{2,}-\d+\b")),
]


@dataclass
class MaskedInput:
    text: str
    masks: dict[str, str] = field(default_factory=dict)


def is_likely_english(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    ascii_letters = sum(1 for c in letters if c.isascii())
    return ascii_letters / len(letters) >= 0.9


def mask(text: str) -> MaskedInput:
    masks: dict[str, str] = {}
    counter = 0
    for _name, pattern in _PATTERNS:
        def _replace(m: re.Match[str]) -> str:
            nonlocal counter
            placeholder = f"<<MASK_{counter}>>"
            masks[placeholder] = m.group(0)
            counter += 1
            return placeholder

        text = pattern.sub(_replace, text)
    return MaskedInput(text=text, masks=masks)


def unmask(text: str, masks: dict[str, str]) -> str:
    for placeholder, original in masks.items():
        text = text.replace(placeholder, original)
    return text


def preprocess(text: str, max_chars: int = MAX_INPUT_CHARS) -> MaskedInput:
    if len(text) > max_chars:
        raise InputTooLongError(len(text), max_chars)
    if not is_likely_english(text):
        raise NonEnglishInputError("input does not appear to be English")
    return mask(text)
