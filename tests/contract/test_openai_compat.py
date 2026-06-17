import json

import httpx
import pytest
import respx

from text_corrector.providers.base import GenerationRequest
from text_corrector.providers.openai_compat import OpenAICompatProvider


@pytest.mark.asyncio
async def test_generate_posts_chat_completions_with_expected_payload() -> None:
    provider = OpenAICompatProvider(base_url="http://test.local/v1")

    with respx.mock(base_url="http://test.local/v1") as mock:
        route = mock.post("/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "test-model",
                    "choices": [{"message": {"content": "corrected"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                },
            )
        )

        result = await provider.generate(
            GenerationRequest(
                model="test-model",
                system_prompt="You correct text.",
                user_prompt="Fix: hellow",
            )
        )

    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["model"] == "test-model"
    assert body["messages"][0] == {"role": "system", "content": "You correct text."}
    assert body["messages"][1] == {"role": "user", "content": "Fix: hellow"}
    assert result.text == "corrected"
    assert result.tokens_in == 10
    assert result.tokens_out == 5
    assert result.model == "test-model"


@pytest.mark.asyncio
async def test_generate_sends_bearer_auth_when_api_key_present() -> None:
    provider = OpenAICompatProvider(base_url="http://test.local/v1", api_key="sk-secret")

    with respx.mock(base_url="http://test.local/v1") as mock:
        mock.post("/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "m",
                    "choices": [{"message": {"content": "x"}}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                },
            )
        )

        await provider.generate(
            GenerationRequest(model="m", system_prompt="s", user_prompt="u")
        )

        sent = mock.calls.last.request
        assert sent.headers["authorization"] == "Bearer sk-secret"


@pytest.mark.asyncio
async def test_generate_raises_on_upstream_error() -> None:
    provider = OpenAICompatProvider(base_url="http://test.local/v1")

    with respx.mock(base_url="http://test.local/v1") as mock:
        mock.post("/chat/completions").mock(return_value=httpx.Response(503))

        with pytest.raises(httpx.HTTPStatusError):
            await provider.generate(
                GenerationRequest(model="m", system_prompt="s", user_prompt="u")
            )


@pytest.mark.asyncio
async def test_health_returns_true_on_200() -> None:
    provider = OpenAICompatProvider(base_url="http://test.local/v1")
    with respx.mock(base_url="http://test.local/v1") as mock:
        mock.get("/models").mock(return_value=httpx.Response(200, json={"data": []}))
        assert await provider.health() is True


@pytest.mark.asyncio
async def test_health_returns_false_on_connection_error() -> None:
    provider = OpenAICompatProvider(base_url="http://test.local/v1")
    with respx.mock(base_url="http://test.local/v1") as mock:
        mock.get("/models").mock(side_effect=httpx.ConnectError("nope"))
        assert await provider.health() is False
