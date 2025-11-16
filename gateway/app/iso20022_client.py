# gateway/app/iso20022_client.py
"""
ISO20022 HTTP client helper.

Usage:
  await send_iso20022_xml("http://live-bank:5002/iso20022", payload_dict)
  or
  await send_iso20022_xml("http://live-bank:5002", payload_dict)  # defaults to path "/iso20022"
"""

import os
import logging
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger("app.iso20022_client")

DEFAULT_PATH = os.environ.get("ISO20022_DEFAULT_PATH", "/iso20022")  # appended if URL has no path

async def build_iso20022_xml(payload: Dict[str, Any]) -> str:
    """
    Minimal example converter: convert a payload dict into a tiny XML string.
    Replace with your real ISO20022 builder.
    """
    # NOTE: This is just a placeholder. For production use a proper XML builder matching ISO20022 schema.
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<ISO20022>']
    for k, v in payload.items():
        # naive: convert nested dicts to their string representation
        xml_parts.append(f"<{k}>{httpx._models.to_bytes(str(v)).decode('utf-8')}</{k}>")
    xml_parts.append("</ISO20022>")
    return "\n".join(xml_parts)

async def send_iso20022_xml(url: str, payload: Dict[str, Any], *, mTLS: bool = False, timeout: float = 30.0) -> Dict[str, Any]:
    """
    Send a generated ISO20022 XML payload to `url`.
    - If `url` contains no path component (e.g. http://live-bank:5002), DEFAULT_PATH will be appended.
    - Returns a dict with keys: {"status_code": int, "text": str}
    - Raises httpx.HTTPStatusError on non-2xx.
    """
    # choose final URL:
    parsed = httpx.URL(url)
    final_url = url
    if not parsed.path or parsed.path == "/":
        final_url = str(parsed.join(DEFAULT_PATH))

    xml = await build_iso20022_xml(payload)
    logger.info("Posting ISO20022 to %s (mTLS:%s)", final_url, bool(mTLS))
    logger.debug("ISO20022 xml preview: %s", xml[:512].replace("\n", " "))

    # httpx client (async). mTLS can be added by passing client cert=...
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(final_url, content=xml, headers={"Content-Type": "application/xml"})
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # re-raise with more context
            logger.error("ISO20022 POST failed %s: %s", final_url, exc)
            raise

        # return a lightweight dict; adjust if you expect XML responses and want parsing
        return {"status_code": r.status_code, "text": r.text or ""}

# Small sync wrapper if you ever need it (not used by server.py which is async)
def send_iso20022_xml_sync(url: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    import asyncio
    return asyncio.run(send_iso20022_xml(url, payload, **kwargs))
