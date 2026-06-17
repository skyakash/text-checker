from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
    api_keys: str = ""

    ollama_base_url: str = "http://localhost:11434/v1"
    default_model: str = "qwen2.5:7b-instruct"

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    redis_url: str | None = None
    otel_exporter_otlp_endpoint: str | None = None

    @property
    def api_keys_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}


settings = Settings()
