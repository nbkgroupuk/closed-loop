# app/telemetry/logging.py
"""
Structured JSON logging configuration to be used across the backend.
Uses python-json-logger for consistent structured logs including correlation ids.
"""
import logging
import os
from pythonjsonlogger import jsonlogger

def configure_logging(level: str = None):
    level = level or os.getenv("LOG_LEVEL", "INFO")
    handler = logging.StreamHandler()
    fmt = jsonlogger.JsonFormatter(fmt='%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s %(txn_id)s %(merchant_id)s')
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(level)
    # remove any default handlers
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)

# helper to add contextual fields to log records
class ContextFilter(logging.Filter):
    def __init__(self, correlation_id=None, txn_id=None, merchant_id=None):
        super().__init__()
        self.correlation_id = correlation_id
        self.txn_id = txn_id
        self.merchant_id = merchant_id

    def filter(self, record):
        record.correlation_id = getattr(record, "correlation_id", self.correlation_id or "")
        record.txn_id = getattr(record, "txn_id", self.txn_id or "")
        record.merchant_id = getattr(record, "merchant_id", self.merchant_id or "")
        return True
