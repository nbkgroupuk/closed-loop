# backend/app/gateway_client.py
import httpx
import os
import requests
import logging
from typing import Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# ASYNC CLIENT (used by main transaction flow)
# ============================================================

class GatewayClient:
    def __init__(self, base_url: str = None, timeout: int = 20):
        # MUST use docker service name + internal port
        self.base = base_url or settings.GATEWAY_BASE  # http://gateway:8000
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))

    async def auth_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.base:
            raise RuntimeError("GATEWAY_BASE not configured")

        url = f"{self.base.rstrip('/')}/transactions"
        logger.info("Gateway auth -> %s", url)

        r = await self._client.post(url, json=payload)
        r.raise_for_status()
        return r.json()

    async def send_iso20022(self, xml_bytes: bytes) -> Dict[str, Any]:
        url = f"{self.base.rstrip('/')}/iso20022"
        r = await self._client.post(
            url,
            content=xml_bytes,
            headers={"Content-Type": "application/xml"},
        )
        r.raise_for_status()
        return r.json()


gateway_client = GatewayClient()

# ============================================================
# SYNC CLIENT (USED BY /test/authorize)
# ============================================================

GATEWAY_URL = os.environ.get(
    "GATEWAY_BASE",
    "http://gateway:8000",   # ✅ CORRECT PORT
).rstrip("/")


def forward_to_gateway(path: str, payload: dict, timeout: int = 15) -> dict:
    url = f"{GATEWAY_URL}{path}"
    logger.info("Forwarding to gateway -> %s", url)

    r = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


# ============================================================
# COMPATIBILITY WRAPPER (USED BY routes.py)
# ============================================================

def send_to_gateway(payload: dict) -> dict:
    return forward_to_gateway("/transactions", payload)
