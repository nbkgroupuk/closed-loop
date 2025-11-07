# gateway/app/tcp_client.py
"""
Fixed TCP ISO client for gateway -> processor.

✅ Corrected payload framing:
   [4-byte big-endian length][4-char ASCII MTI][JSON body]
✅ Clean MTI handling and JSON encoding.
✅ Compatible with processor’s iso_listener.py.

"""

from __future__ import annotations
import asyncio
import json
import logging
import struct
import time
from typing import Any, Dict, Optional

LOG = logging.getLogger("gateway.tcp_client")
LOG.setLevel(logging.INFO)

DEFAULT_HOST = "host.docker.internal"
DEFAULT_PORT = 9000
CONNECT_TIMEOUT = 6.0
RESPONSE_TIMEOUT = 6.0
DEFAULT_RETRIES = 1


def _build_payload_from_fields(mti: str, fields: Dict[str, Any]) -> bytes:
    """Return bytes: 4-char ASCII MTI + JSON body (utf-8, compact)."""
    mti = str(mti).strip()[:4]
    if not (len(mti) == 4 and mti.isdigit()):
        raise ValueError(f"invalid MTI '{mti}', must be 4-digit ASCII like '0200'")

    body_bytes = json.dumps({"fields": fields}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return mti.encode("ascii") + body_bytes


def _frame_payload(payload: bytes) -> bytes:
    """Prefix payload with a 4-byte big-endian unsigned length header."""
    n = len(payload)
    if n > 0xFFFFFFFF:
        raise ValueError("payload too large for 4-byte header")
    return struct.pack(">I", n) + payload


async def _read_exact(reader: asyncio.StreamReader, n: int, timeout: float) -> bytes:
    return await asyncio.wait_for(reader.readexactly(n), timeout)


async def send_iso_to_processor(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    mti: str = "0200",
    fields: Optional[Dict[str, Any]] = None,
    connect_timeout: float = CONNECT_TIMEOUT,
    response_timeout: float = RESPONSE_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Dict[str, Any]:
    """Send ISO message to processor and await response."""

    if fields is None:
        raise ValueError("fields must not be None")

    fields = {str(k): v for k, v in fields.items()}
    payload = _build_payload_from_fields(mti, fields)
    framed = _frame_payload(payload)

    attempt = 0
    last_err: Optional[str] = None

    while attempt <= retries:
        attempt += 1
        try:
            LOG.info(f"→ Connecting to {host}:{port} (attempt {attempt}, mti={mti})")
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host=host, port=port),
                timeout=connect_timeout,
            )

            # send framed message
            writer.write(framed)
            await writer.drain()

            # read 4-byte length header
            header = await _read_exact(reader, 4, response_timeout)
            resp_len = struct.unpack(">I", header)[0]

            raw_resp = await _read_exact(reader, resp_len, response_timeout) if resp_len else b""

            # parse response
            mti_resp, json_resp = None, None
            if len(raw_resp) >= 4:
                try:
                    mti_resp = raw_resp[:4].decode("ascii")
                except Exception:
                    mti_resp = None
                try:
                    json_resp = json.loads(raw_resp[4:].decode("utf-8"))
                except Exception:
                    json_resp = None

            writer.close()
            await writer.wait_closed()

            return {
                "success": True,
                "mti_resp": mti_resp,
                "json_resp": json_resp,
                "raw_req": payload,
                "raw_resp": raw_resp,
            }

        except Exception as e:
            last_err = str(e)
            LOG.exception(f"Processor communication error: {e}")
            await asyncio.sleep(0.2 * attempt)

    return {"success": False, "error": last_err}


def send_iso_to_processor_sync(*args, **kwargs) -> Dict[str, Any]:
    """Sync wrapper for non-async contexts."""
    import asyncio
    try:
        return asyncio.run(send_iso_to_processor(*args, **kwargs))
    except RuntimeError:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(send_iso_to_processor(*args, **kwargs))

