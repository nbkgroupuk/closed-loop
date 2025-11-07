# app/telemetry.py
import logging
import os
from pythonjsonlogger import jsonlogger

def configure_logging(level="INFO"):
    handler = logging.StreamHandler()
    fmt = jsonlogger.JsonFormatter(fmt='%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s')
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(level)
    # remove default handlers
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    # module-level logger
    global logger
    logger = logging.getLogger("payment-gateway")
    logger.setLevel(level)
    return logger

# expose logger
logger = logging.getLogger("payment-gateway")
