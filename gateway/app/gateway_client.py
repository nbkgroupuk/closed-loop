# backend/app/gateway_client.py

import requests

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://gateway:8000").rstrip("/")

def send_to_gateway(payload: dict) -> dict:
    """
    Send ISO8583-style payload to Gateway
    """
    response = requests.post(
        GATEWAY_URL,
        json=payload,
        timeout=10
    )
    response.raise_for_status()
    return response.json()

def send_to_gateway(payload: dict) -> dict:
    """
    Compatibility wrapper used by routes.py
    """
    return forward_to_gateway("/transactions", payload)
