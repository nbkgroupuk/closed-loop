# 
import os
import requests

PROCESSOR_BASE = os.environ.get("PROCESSOR_BASE", "http://processor:8000")

def send_to_processor(payload: dict) -> dict:
    r = requests.post(
        url = f"{PROCESSOR_BASE}/authorize",
        json=payload,
        timeout=15
    )
    r.raise_for_status()
    return r.json()
