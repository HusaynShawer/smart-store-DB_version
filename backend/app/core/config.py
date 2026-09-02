# app/core/config.py
"""
Application settings — single source of truth, loaded from environment / .env.

Uses pydantic-settings (v2). All secrets stay in env vars; never hard-coded.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── App ─────────────────────────────────────────────────────────────────
    APP_TITLE: str = "متجر زكي AI Agent"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: str = "INFO"

    # ── Agent LLM (DeepSeek via SovereignEG, OpenAI compatible) ────────────
    SOVEREIGNEG_API_KEY: str = ""
    LLM_BASE_URL: str = "https://backend.sovereigneg.com/v1"
    LLM_MODEL: str = "deepseek-v4-flash-0731"
    LLM_TEMPERATURE: float = 0.3
    AGENT_MAX_STEPS: int = 8

    # ── Multi-modal (Gemini STT + Vision) ──────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"

    # ── Embeddings (Cohere preferred, SovereignEG free fallback) ────────────
    # If COHERE_API_KEY is set → Cohere multilingual embeddings (1024d).
    # Otherwise → SovereignEG OpenAI-compatible /v1/embeddings (text-embedding-3-small, 1536d).
    COHERE_API_KEY: str = ""
    COHERE_MODEL: str = "embed-multilingual-v3.0"
    EMBEDDING_PROVIDER: Literal["auto", "cohere", "sovereign"] = "auto"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536

    # ── PostgreSQL (pgvector) ──────────────────────────────────────────────
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "zaki"
    POSTGRES_PASSWORD: str = "zakipass"
    POSTGRES_DB: str = "zaki_store"

    # ── CORS ───────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["*"])

    # ── WhatsApp / Twilio ──────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""

    # ── Derived ────────────────────────────────────────────────────────────

    @property
    def DATABASE_URL(self) -> str:
        """Async SQLAlchemy URL for PostgreSQL + asyncpg."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def CORS_ORIGINS_PARSED(self) -> list[str]:
        if isinstance(self.CORS_ORIGINS, str):
            return [o.strip() for o in self.CORS_ORIGINS.strip("[]").split(",")]
        return self.CORS_ORIGINS

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                import json
                return json.loads(value)
            return [o.strip() for o in value.split(",") if o.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton — one Settings instance per process."""
    return Settings()