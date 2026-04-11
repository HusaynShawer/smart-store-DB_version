"""
Application settings with Pydantic BaseSettings.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    # App Configuration
    APP_TITLE: str = "Zaki Store AI Agent"
    APP_VERSION: str = "2.0.0"

    # ── Gemini (Primary for text and vision) ──────────────────────────────────
    GEMINI_API_KEY: str = ""  # Required for text and image analysis
    GEMINI_MODEL: str = "gemma-3-27b-it"
    GEMINI_TEMPERATURE: float = 0.7

    # ── OpenAI (For Whisper voice transcription) ─────────────────────────────
    OPENAI_API_KEY: str = ""  # Required for voice features

    # ── MySQL ─────────────────────────────────────────────────────────────────
    MYSQL_HOST: str = "mysql"  # Use service name for Docker
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "zaki"
    MYSQL_PASSWORD: str = "zakipass"
    MYSQL_DB: str = "zaki_store"

    # ── Agent ─────────────────────────────────────────────────────────────────
    AGENT_MAX_ITERATIONS: int = 7
    AGENT_VERBOSE: bool = True

    # ── Meta WhatsApp Cloud API ───────────────────────────────────────────────
    META_ACCESS_TOKEN: str = ""
    META_PHONE_NUMBER_ID: str = ""
    META_VERIFY_TOKEN: str = "zaki_meta_verify_2025"
    META_APP_SECRET: str = ""

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 20

    # ── Retry Configuration ──────────────────────────────────────────────────
    MESSAGE_MAX_RETRIES: int = 3
    MESSAGE_RETRY_DELAY: int = 2

    # ── Search Configuration ─────────────────────────────────────────────────
    SEARCH_CACHE_SIZE: int = 512
    SEARCH_FUZZY_THRESHOLD: float = 0.70
    SEARCH_MIN_RESULTS: int = 5
    SEARCH_MAX_RESULTS: int = 10

    @property
    def DATABASE_URL(self) -> str:
        """Construct async MySQL connection URL."""
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            f"?charset=utf8mb4"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached Settings instance."""
    return Settings()
