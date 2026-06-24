import pytest

from text_checker.api.schemas import QualityTier
from text_checker.config import Settings
from text_checker.providers.registry import ProviderRegistry


@pytest.fixture
def local_only() -> ProviderRegistry:
    return ProviderRegistry(Settings(anthropic_api_key=None, openai_api_key=None))


@pytest.fixture
def with_anthropic() -> ProviderRegistry:
    return ProviderRegistry(Settings(anthropic_api_key="sk-test"))


@pytest.fixture
def with_openai() -> ProviderRegistry:
    return ProviderRegistry(Settings(openai_api_key="sk-test"))


def test_registry_always_has_ollama(local_only: ProviderRegistry) -> None:
    assert local_only.has("ollama")
    assert "ollama" in local_only.names()


def test_anthropic_only_registered_when_key_set(
    local_only: ProviderRegistry, with_anthropic: ProviderRegistry
) -> None:
    assert not local_only.has("anthropic")
    assert with_anthropic.has("anthropic")


def test_openai_only_registered_when_key_set(
    local_only: ProviderRegistry, with_openai: ProviderRegistry
) -> None:
    assert not local_only.has("openai")
    assert with_openai.has("openai")


def test_route_balanced_uses_default_ollama_model(local_only: ProviderRegistry) -> None:
    r = local_only.route(QualityTier.BALANCED, None)
    assert r.provider_name == "ollama"
    assert r.model == "qwen2.5:7b-instruct"


def test_route_fast_uses_small_ollama_model(local_only: ProviderRegistry) -> None:
    r = local_only.route(QualityTier.FAST, None)
    assert r.provider_name == "ollama"
    assert r.model == "qwen2.5:0.5b"


def test_route_high_prefers_anthropic_when_available(
    with_anthropic: ProviderRegistry,
) -> None:
    r = with_anthropic.route(QualityTier.HIGH, None)
    assert r.provider_name == "anthropic"
    assert r.model == "claude-haiku-4-5"


def test_route_high_falls_back_to_openai_when_no_anthropic(
    with_openai: ProviderRegistry,
) -> None:
    r = with_openai.route(QualityTier.HIGH, None)
    assert r.provider_name == "openai"


def test_route_high_falls_back_to_ollama_when_no_cloud(
    local_only: ProviderRegistry,
) -> None:
    r = local_only.route(QualityTier.HIGH, None)
    assert r.provider_name == "ollama"
    assert r.model == "qwen2.5:7b-instruct"


def test_route_respects_model_override(local_only: ProviderRegistry) -> None:
    r = local_only.route(QualityTier.BALANCED, "custom-model")
    assert r.model == "custom-model"


def test_available_models_includes_cloud_when_keys_set(
    with_anthropic: ProviderRegistry,
) -> None:
    models = with_anthropic.available_models()
    assert "claude-haiku-4-5" in models
    assert "qwen2.5:7b-instruct" in models
