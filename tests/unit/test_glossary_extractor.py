from pathlib import Path

import pytest

from text_checker.glossary.extractor import (
    extract_from_file,
    extract_from_text,
    parse_terms,
)
from text_checker.providers.base import GenerationRequest, GenerationResponse, Provider


class _FakeProvider(Provider):
    def __init__(self, response_text: str) -> None:
        self._response = response_text
        self.calls: list[GenerationRequest] = []

    async def generate(self, req: GenerationRequest) -> GenerationResponse:
        self.calls.append(req)
        return GenerationResponse(
            text=self._response,
            tokens_in=10,
            tokens_out=10,
            model=req.model,
        )

    async def health(self) -> bool:
        return True


def test_parse_terms_from_clean_json_array() -> None:
    raw = '["Flowstate", "Editor", "Snapshot Loader"]'
    assert parse_terms(raw) == ["Editor", "Flowstate", "Snapshot Loader"]


def test_parse_terms_dedupes_and_sorts() -> None:
    raw = '["Editor", "Editor", "Flowstate"]'
    assert parse_terms(raw) == ["Editor", "Flowstate"]


def test_parse_terms_finds_json_inside_extra_prose() -> None:
    raw = 'Here are the terms:\n["Flowstate", "Editor"]\nThanks.'
    assert parse_terms(raw) == ["Editor", "Flowstate"]


def test_parse_terms_falls_back_to_line_splitting() -> None:
    raw = "- Flowstate\n* Editor\n- Snapshot Loader"
    out = parse_terms(raw)
    assert "Flowstate" in out
    assert "Editor" in out
    assert "Snapshot Loader" in out


def test_parse_terms_strips_bullets_quotes_commas() -> None:
    raw = '- "Flowstate",\n* \'Editor\','
    out = parse_terms(raw)
    assert "Flowstate" in out
    assert "Editor" in out


def test_parse_terms_handles_empty_and_garbage() -> None:
    assert parse_terms("") == []
    assert parse_terms("just some prose with no structure at all") != []


async def test_extract_from_text_calls_provider_with_correct_prompt() -> None:
    provider = _FakeProvider('["Flowstate", "Editor"]')
    terms = await extract_from_text("docs about Flowstate", provider, model="test-model")
    assert terms == ["Editor", "Flowstate"]
    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call.model == "test-model"
    assert "Flowstate" in call.user_prompt
    assert "product" in call.system_prompt.lower()


async def test_extract_from_text_skips_empty_input() -> None:
    provider = _FakeProvider("[]")
    assert await extract_from_text("", provider, model="m") == []
    assert provider.calls == []


async def test_extract_from_file_unions_chunk_results(tmp_path: Path) -> None:
    p = tmp_path / "big.md"
    p.write_text("section one\n\n" + "x" * 5000 + "\n\nsection two")
    provider = _FakeProvider('["TermA"]')
    terms = await extract_from_file(p, provider, model="m", max_chunk_chars=2000)
    assert terms == ["TermA"]
    assert len(provider.calls) >= 2
