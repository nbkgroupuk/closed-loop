# processor/app/storage/db.py
"""
Tiny in-memory DB used for development/test runs.
If you want persistence later, replace with SQLAlchemy / Postgres calls.
"""

import threading
import logging

LOG = logging.getLogger("processor.storage.db")

_lock = threading.Lock()
_payouts = {}

def save_payout(record: dict) -> str:
    with _lock:
        rid = record.get("id")
        if not rid:
            raise ValueError("record must have id")
        _payouts[rid] = record.copy()
    LOG.debug("Saved payout %s", rid)
    return rid

def get_payout(rid: str) -> dict | None:
    with _lock:
        return _payouts.get(rid)

def list_payouts() -> list:
    with _lock:
        return list(_payouts.values())
