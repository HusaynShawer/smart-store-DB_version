# config/settings.py
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    APP_TITLE:   str = "متجر زكي AI Agent"
    APP_VERSION: str = "2.0.0"

    # ── Gemini ────────────────────────────────────────────────────────────────
    GEMINI_API_KEY:     str
    GEMINI_MODEL:       str   = "gemma-3-27b-it"
    GEMINI_TEMPERATURE: float = 0.7

    # ── MySQL ─────────────────────────────────────────────────────────────────
    MYSQL_HOST:     str = "127.0.0.1"
    MYSQL_PORT:     int = 3306
    MYSQL_USER:     str = "zaki"
    MYSQL_PASSWORD: str = "zakipass"
    MYSQL_DB:       str = "zaki_store"

    # ── Agent ─────────────────────────────────────────────────────────────────
    AGENT_MAX_ITERATIONS: int  = 7       # رفعنا من 3 إلى 7
    AGENT_VERBOSE:        bool = True

    # ── Meta WhatsApp Cloud API ───────────────────────────────────────────────
    META_ACCESS_TOKEN:    str = ""   # Permanent token من Meta Business
    META_PHONE_NUMBER_ID: str = ""   # Phone Number ID من Meta Dashboard
    META_VERIFY_TOKEN:    str = "zaki_meta_verify_2025"
    META_APP_SECRET:      str = ""   # لـ Webhook HMAC signature verification

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 20

    # ── Retry ────────────────────────────────────────────────────────────────
    MESSAGE_MAX_RETRIES: int = 3
    MESSAGE_RETRY_DELAY: int = 5     # ثواني بين كل محاولة

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            f"?charset=utf8mb4"
        )

    class Config:
        env_file = ".env"
        extra    = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()