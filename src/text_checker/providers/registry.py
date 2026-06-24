from dataclasses import dataclass

from ..api.schemas import QualityTier
from ..config import Settings, settings
from .base import Provider
from .openai_compat import OpenAICompatProvider


@dataclass(frozen=True)
class Route:
    provider_name: str
    model: str


class ProviderRegistry:
    def __init__(self, cfg: Settings) -> None:
        self._cfg = cfg
        self._providers: dict[str, Provider] = {
            "ollama": OpenAICompatProvider(base_url=cfg.ollama_base_url),
        }
        if cfg.anthropic_api_key:
            self._providers["anthropic"] = OpenAICompatProvider(
                base_url=cfg.anthropic_base_url,
                api_key=cfg.anthropic_api_key,
            )
        if cfg.openai_api_key:
            self._providers["openai"] = OpenAICompatProvider(
                base_url=cfg.openai_base_url,
                api_key=cfg.openai_api_key,
            )

    def has(self, name: str) -> bool:
        return name in self._providers

    def get(self, name: str) -> Provider:
        return self._providers[name]

    def names(self) -> list[str]:
        return list(self._providers)

    def available_models(self) -> list[str]:
        models = [self._cfg.default_model, self._cfg.fast_model]
        if "anthropic" in self._providers:
            models.append(self._cfg.anthropic_model)
        if "openai" in self._providers:
            models.append(self._cfg.openai_model)
        return models

    def route(self, tier: QualityTier, model_override: str | None) -> Route:
        if model_override:
            return Route("ollama", model_override)
        if tier == QualityTier.HIGH:
            if "anthropic" in self._providers:
                return Route("anthropic", self._cfg.anthropic_model)
            if "openai" in self._providers:
                return Route("openai", self._cfg.openai_model)
        if tier == QualityTier.FAST:
            return Route("ollama", self._cfg.fast_model)
        return Route("ollama", self._cfg.default_model)


_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry(settings)
    return _registry


def reset_registry() -> None:
    global _registry
    _registry = None
