# app/gateway_client.py
import httpx
from app.config import settings
import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class GatewayClient:
    def __init__(self, base_url: str = None, timeout: int = 20):
        self.base = base_url or settings.GATEWAY_BASE
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))

    async def auth_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends canonical request to Gateway /auth endpoint which will translate to ISO8583.
        Expects JSON response: {approved: bool, de39: str, de38: str, gateway_txn_id: str}
        """
        if not self.base:
            raise RuntimeError("GATEWAY_BASE not configured")
        url = f"{self.base.rstrip('/')}/auth"
        logger.debug("Gateway auth -> %s", url)
        r = await self._client.post(url, json=payload)
        r.raise_for_status()
        return r.json()

    async def send_iso20022(self, xml_bytes: bytes) -> Dict[str, Any]:
        url = f"{self.base.rstrip('/')}/iso20022"
        r = await self._client.post(url, content=xml_bytes, headers={"Content-Type":"application/xml"})
        r.raise_for_status()
        return r.json()

gateway_client = GatewayClient()

# app/gateway_client.py (add or append)

import os, requests
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://gateway:8100").rstrip("/")

def forward_to_gateway(path: str, payload: dict, timeout: int = 15):
    url = f"{GATEWAY_URL}{path}"
    headers = {"Content-Type": "application/json"}
    r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {}



























