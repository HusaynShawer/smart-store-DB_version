# config/settings.py
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    APP_TITLE: str = "متجر زكي AI Agent"
    APP_VERSION: str = "1.0.0"

    # ── Gemini ──────────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemma-3-27b-it"
    GEMINI_TEMPERATURE: float = 0.7

    # ── MySQL ─────────────────────────────────────────────────────────────────
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "zaki"
    MYSQL_PASSWORD: str = "zakipass"
    MYSQL_DB: str = "zaki_store"

    # ── Agent ─────────────────────────────────────────────────────────────────
    AGENT_MAX_ITERATIONS: int = 3
    AGENT_VERBOSE: bool = True
    
    # ── WhatsApp / Twilio ──────────────────────────────────────────────────────
    CALLMEBOT_API_KEY: str = ""
    CALLMEBOT_PHONE: str = ""
    
    # Twilio Configuration
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""  # e.g., "+14155238886" (Twilio sandbox or verified number)

    @property
    def DATABASE_URL(self) -> str:
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
    return Settings()