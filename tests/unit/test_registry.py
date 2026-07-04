import pytest

from text_checker.api.schemas import QualityTier
from text_checker.config import Settings
from text_checker.providers.registry import (
    ProviderRegistry,
    UnknownProviderError,
    parse_model_override,
)


@pytest.fixture
def local_only() -> ProviderRegistry:
    return ProviderRegistry(Settings(anthropic_api_key=None, openai_api_key=None))


@pytest.fixture
def with_anthropic() -> ProviderRegistry:
    return ProviderRegistry(Settings(anthropic_api_key="sk-test"))


@pytest.fixture
def with_openai() -> ProviderRegistry:
    return ProviderRegistry(Settings(openai_api_key="sk-test"))


@pytest.fixture
def with_custom() -> ProviderRegistry:
    return ProviderRegistry(
        Settings(
            custom_base_url="http://vllm.local/v1",
            custom_api_key="sk-custom",
            custom_model="llama-3.3-70b",
        )
    )


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


def test_custom_only_registered_when_base_url_set(
    local_only: ProviderRegistry, with_custom: ProviderRegistry
) -> None:
    assert not local_only.has("custom")
    assert with_custom.has("custom")


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


# ----- new: parse_model_override -----


def test_parse_override_bare_name_is_not_a_provider() -> None:
    provider, model = parse_model_override("gpt-4o-mini")
    assert provider is None
    assert model == "gpt-4o-mini"


def test_parse_override_ollama_tag_with_double_colons() -> None:
    # ollama tags contain colons — parser must split on FIRST colon only.
    provider, model = parse_model_override("ollama:qwen2.5:7b-instruct")
    assert provider == "ollama"
    assert model == "qwen2.5:7b-instruct"


def test_parse_override_bare_ollama_tag_no_prefix() -> None:
    # Passing a raw ollama tag with no explicit prefix must stay
    # backwards-compatible — the leading segment ("qwen2.5") is not a
    # known provider, so treat the whole string as a model name.
    provider, model = parse_model_override("qwen2.5:0.5b")
    assert provider is None
    assert model == "qwen2.5:0.5b"


@pytest.mark.parametrize(
    "override,expected_provider,expected_model",
    [
        ("anthropic:claude-haiku-4-5", "anthropic", "claude-haiku-4-5"),
        ("openai:gpt-4o-mini", "openai", "gpt-4o-mini"),
        ("custom:llama-3.3-70b", "custom", "llama-3.3-70b"),
    ],
)
def test_parse_override_known_provider_prefixes(
    override: str, expected_provider: str, expected_model: str
) -> None:
    provider, model = parse_model_override(override)
    assert provider == expected_provider
    assert model == expected_model


# ----- new: route() honors prefixes -----


def test_route_bare_override_still_goes_to_ollama(
    local_only: ProviderRegistry,
) -> None:
    # Backwards-compat: existing callers pass raw tags.
    r = local_only.route(QualityTier.BALANCED, "custom-model")
    assert r.provider_name == "ollama"
    assert r.model == "custom-model"


def test_route_ollama_prefix_routes_to_ollama(local_only: ProviderRegistry) -> None:
    r = local_only.route(QualityTier.BALANCED, "ollama:qwen2.5:14b-instruct")
    assert r.provider_name == "ollama"
    assert r.model == "qwen2.5:14b-instruct"


def test_route_anthropic_prefix_routes_to_anthropic(
    with_anthropic: ProviderRegistry,
) -> None:
    r = with_anthropic.route(QualityTier.BALANCED, "anthropic:claude-haiku-4-5")
    assert r.provider_name == "anthropic"
    assert r.model == "claude-haiku-4-5"


def test_route_openai_prefix_routes_to_openai(with_openai: ProviderRegistry) -> None:
    r = with_openai.route(QualityTier.BALANCED, "openai:gpt-4o-mini")
    assert r.provider_name == "openai"
    assert r.model == "gpt-4o-mini"


def test_route_custom_prefix_routes_to_custom(with_custom: ProviderRegistry) -> None:
    r = with_custom.route(QualityTier.BALANCED, "custom:llama-3.3-70b")
    assert r.provider_name == "custom"
    assert r.model == "llama-3.3-70b"


def test_route_unknown_provider_raises(local_only: ProviderRegistry) -> None:
    with pytest.raises(UnknownProviderError) as excinfo:
        local_only.route(QualityTier.BALANCED, "anthropic:claude-haiku-4-5")
    assert "unknown_provider" in str(excinfo.value)
    assert "anthropic" in str(excinfo.value)


# ----- new: available_models returns (provider, model) tuples -----


def test_available_models_shape_local_only(local_only: ProviderRegistry) -> None:
    models = local_only.available_models()
    assert ("ollama", "qwen2.5:7b-instruct") in models
    assert ("ollama", "qwen2.5:0.5b") in models
    # No cloud/custom without configuration.
    assert not any(p in {"anthropic", "openai", "custom"} for p, _ in models)


def test_available_models_includes_anthropic_when_configured(
    with_anthropic: ProviderRegistry,
) -> None:
    models = with_anthropic.available_models()
    assert ("anthropic", "claude-haiku-4-5") in models


def test_available_models_includes_custom_when_configured(
    with_custom: ProviderRegistry,
) -> None:
    models = with_custom.available_models()
    assert ("custom", "llama-3.3-70b") in models
