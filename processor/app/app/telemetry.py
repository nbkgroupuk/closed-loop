# app/telemetry.py
import logging
from pythonjsonlogger import jsonlogger

def configure_logging(level="INFO"):
    handler = logging.StreamHandler()
    fmt = jsonlogger.JsonFormatter(fmt='%(asctime)s %(levelname)s %(name)s %(message)s')
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    logger = logging.getLogger("processor")
    logger.setLevel(level)
    return logger
