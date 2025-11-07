# app/idempotency.py
import hashlib
import json

def canonical_request_hash(obj: dict) -> str:
    """
    Produce a canonical sha256 hash for idempotency when client doesn't provide one.
    Sort keys for deterministic hash.
    """
    body = json.dumps(obj, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
