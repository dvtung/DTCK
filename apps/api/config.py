"""Application settings (pydantic-settings).

Secrets come exclusively from environment variables / .env (see .env.example).
Never hardcode credentials here.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "dtck-api"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+psycopg://dtck:change_me@localhost:5432/dtck"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    # LLM abstraction (ADR-005) — Phase 5
    llm_provider: str = "mock"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 120

    # Embeddings — Phase 4
    embedding_provider: str = "sentence-transformers"
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384

    # Scoring baseline (§12)
    scoring_version: str = "baseline_1.0"

    # CORS
    cors_origins: list[str] = ["http://localhost:8501"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
