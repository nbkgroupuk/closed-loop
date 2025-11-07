# processor/app/config.py
from pydantic import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    APP_NAME: str = "Payment Processor"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 5000

    # DB
    DATABASE_URL: str = os.getenv("DATABASE_URL")

settings = Settings()

    # Settlement / payouts
    SETTLEMENT_BATCH_SIZE: int = 100
    CRYPTO_CONFIRMATIONS: int = 12

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


def normalize_sqlite_urls(url: str) -> str:
    """Ensure sqlite URLs that reference /app use absolute 4-slash form."""
    if not url:
        return url
    # Convert sqlite+aiosqlite:///app/... -> sqlite+aiosqlite:////app/...
    if url.startswith("sqlite+aiosqlite:///") and not url.startswith("sqlite+aiosqlite:////"):
        return url.replace("sqlite+aiosqlite:///", "sqlite+aiosqlite:////", 1)
    # Convert sqlite:///app/... -> sqlite:////app/...
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        return url.replace("sqlite:///", "sqlite:////", 1)
    return url


# Initialize settings and normalize DATABASE_URL
settings = Settings()
settings.DATABASE_URL = normalize_sqlite_urls(settings.DATABASE_URL)
