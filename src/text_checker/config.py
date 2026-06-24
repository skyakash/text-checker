from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
    api_keys: str = ""

    ollama_base_url: str = "http://localhost:11434/v1"
    default_model: str = "qwen2.5:7b-instruct"
    fast_model: str = "qwen2.5:0.5b"

    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_model: str = "claude-haiku-4-5"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    redis_url: str | None = None
    otel_exporter_otlp_endpoint: str | None = None

    glossary_path: str = "./data/glossary.json"

    rag_enabled: bool = True
    rag_store_path: str = "./data/rag"
    rag_collection_name: str = "products"
    rag_embedding_model: str = "nomic-embed-text"
    rag_embedding_base_url: str | None = None
    rag_top_k: int = 3
    rag_min_score: float = 0.0

    @property
    def api_keys_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}


settings = Settings()
