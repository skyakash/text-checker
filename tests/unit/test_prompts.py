from text_checker.api.schemas import Mode
from text_checker.pipeline.prompts import system_prompt, user_prompt


def test_each_mode_has_distinct_system_prompt() -> None:
    prompts = {m: system_prompt(m) for m in Mode}
    assert len(set(prompts.values())) == len(Mode)


def test_every_system_prompt_mentions_mask_preservation() -> None:
    for mode in Mode:
        assert "<<MASK_n>>" in system_prompt(mode)


def test_user_prompt_passes_text_through() -> None:
    assert user_prompt("hello world") == "hello world"
