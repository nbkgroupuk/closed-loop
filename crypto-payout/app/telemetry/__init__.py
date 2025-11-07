from .logging import configure_logging
from .metrics import router as metrics_router, metrics_endpoint
# initialize a default logger at import-time (apps may call configure_logging again)
logger = configure_logging()

__all__ = ("configure_logging", "logger", "metrics_router", "metrics_endpoint")
