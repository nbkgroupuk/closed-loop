# gateway/app/config.py
from pydantic import BaseSettings, AnyHttpUrl
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "Payment Gateway"
    DEBUG: bool = False
    # Processor TCP (where we forward ISO8583)
    PROCESSOR_HOST: str = "processor"
    PROCESSOR_PORT: int = 5000
    # HTTP listener
    HOST: str = "0.0.0.0"
    PORT: int = 8100
    # TLS/mTLS for bank ISO20022
    BANK_API_BASE: Optional[AnyHttpUrl] = None
    ISO20022_MTLS_CERT: Optional[str] = None
    ISO20022_MTLS_KEY: Optional[str] = None
    # Timeouts & retries
    ISO_TCP_TIMEOUT_SECONDS: int = 15
    ISO_TCP_RETRY_COUNT: int = 2
    # Logging/observability
    LOG_LEVEL: str = "INFO"
    # Path to connector config if any
    CONNECTOR_CONFIG: Optional[str] = None

    # Acquirer ISO8583 sandbox
    ACQUIRER_HOST: Optional[str] = None
    ACQUIRER_PORT: Optional[int] = None
    ACQUIRER_NETWORK: Optional[str] = None
    ACQUIRER_TPDU: Optional[str] = None
    ACQUIRER_MLI: Optional[int] = None
    ACQUIRER_TIMEOUT: Optional[int] = None
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
   
