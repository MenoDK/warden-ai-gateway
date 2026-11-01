"""Typed, validated configuration (12-factor: everything comes from the environment)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_KEY = "change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    api_key: SecretStr = SecretStr(_INSECURE_DEFAULT_KEY)

    # --- LLM providers (an empty URL disables the provider) -----------------
    local_llm_url: str = ""  # OpenAI-compatible endpoint, e.g. an Ollama server
    local_llm_model: str = "llama3.2"
    external_llm_url: str = ""
    external_llm_key: SecretStr = SecretStr("")
    external_llm_model: str = "gpt-4o-mini"
    provider_timeout_seconds: float = 30.0
    breaker_failure_threshold: int = 3
    breaker_reset_seconds: float = 30.0

    # --- RAG -----------------------------------------------------------------
    embedding_dim: int = Field(default=256, ge=32, le=4096)
    rag_min_score: float = Field(default=0.2, ge=0.0, le=1.0)
    rag_min_evidence: int = Field(default=1, ge=1)
    rag_top_k: int = Field(default=4, ge=1, le=20)
    allowed_sources: str = "docs/*,kb/*,wiki/*"
    max_document_chars: int = 200_000

    # --- Stores --------------------------------------------------------------
    database_url: str = ""  # empty -> in-memory knowledge store
    redis_url: str = ""  # empty -> in-memory idempotency store

    # --- Webhooks ------------------------------------------------------------
    # Comma-separated so that secrets can be rotated without downtime
    # (first = current, others = still accepted).
    webhook_secrets: SecretStr = SecretStr("")
    webhook_tolerance_seconds: int = 300
    webhook_dedupe_ttl_seconds: int = 86_400

    @model_validator(mode="after")
    def _refuse_insecure_production(self) -> Settings:
        if self.app_env == "production" and self.api_key.get_secret_value() == _INSECURE_DEFAULT_KEY:
            raise ValueError("API_KEY must be set to a non-default value in production")
        return self

    @property
    def allowed_source_patterns(self) -> list[str]:
        return [p.strip() for p in self.allowed_sources.split(",") if p.strip()]

    @property
    def webhook_secret_list(self) -> list[str]:
        raw = self.webhook_secrets.get_secret_value()
        return [s.strip() for s in raw.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
