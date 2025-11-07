# app/config.py
from pydantic import BaseSettings, Field, AnyHttpUrl
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "BlackRock Backend"
    DEBUG: bool = False
    DATABASE_URL = "postgresql+asyncpg://payments:payments_pw@pg_local:5432/payments_db"

    GATEWAY_BASE: Optional[AnyHttpUrl] = Field(None, env="GATEWAY_BASE")
    JWT_SECRET: str = Field(..., env="JWT_SECRET")
    WS_SECRET: str = Field(..., env="WS_SECRET")
    RENDER: bool = Field(False, env="RENDER")
    # payouts
    CRYPTO_CONFIRMATIONS: int = 12
    ISO20022_MTLS_CERT: Optional[str] = None
    ISO20022_MTLS_KEY: Optional[str] = None
    # service
    MAX_WORKER_CONCURRENCY: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
