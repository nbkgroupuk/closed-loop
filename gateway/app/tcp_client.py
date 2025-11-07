# tcp_client.py  -- debug, robust framing + hex-logging
"""
Debug TCP ISO Client for Gateway -> Processor

- Frames payload as: 4-byte big-endian length + 4-byte ASCII MTI + JSON body (flat).
- Converts numeric string keys to integers in JSON body.
- Writes a hex dump of framed bytes to /tmp/iso_last.hex for inspection.
- Validates MTI is exactly 4 ascii digits before send.
- Returns structured response.
"""

from __future__ import annotations
import asyncio
import json
import logging
import struct
from typing import Any, Dict, Optional

LOG = logging.getLogger("gateway.tcp_client")
LOG.setLevel(logging.INFO)

DEFAULT_HOST = "host.docker.internal"
DEFAULT_PORT = 9000
CONNECT_TIMEOUT = 6.0
RESPONSE_TIMEOUT = 6.0


def _normalize_fields(fields: Dict[str, Any]) -> Dict[Any, Any]:
    """Ensure JSON body uses integer keys where numeric keys exist."""
    normalized: Dict[Any, Any] = {}
    for k, v in fields.items():
        if isinstance(k, str) and k.isdigit():
            normalized[int(k)] = v
        else:
            normalized[k] = v
    return normalized


def _build_payload(mti: str, fields: Dict[str, Any]) -> bytes:
    """Return 4-char MTI + JSON body bytes. JSON body is flat (no {"fields":...})."""
    mti = str(mti).strip()[:4]
    if not (len(mti) == 4 and mti.isdigit()):
        raise ValueError(f"invalid MTI '{mti}', must be 4 ascii digits like '0200'")

    normalized = _normalize_fields(fields)
    body_bytes = json.dumps(normalized, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return mti.encode("ascii") + body_bytes


def _frame_payload(payload: bytes) -> bytes:
    """Prefix payload with 4-byte big-endian unsigned length header."""
    n = len(payload)
    if n > 0xFFFFFFFF:
        raise ValueError("payload too large for 4-byte header")
    return struct.pack(">I", n) + payload


def _hex_dump(path: str, data: bytes) -> None:
    """Write a compact hex dump file to disk for inspection (overwritten each call)."""
    with open(path, "wb") as f:
        # write raw bytes as hex with newline
        f.write(data.hex().encode("ascii") + b"\n")


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
) -> Dict[str, Any]:
    """Send ISO message to processor and await response, with verbose debug logging."""

    if fields is None:
        return {"success": False, "error": "fields must not be None"}

    # build payload and frame
    try:
        payload = _build_payload(mti, fields)
    except Exception as e:
        LOG.exception("Payload build error")
        return {"success": False, "error": f"payload build error: {e}"}

    framed = _frame_payload(payload)

    # log hex dump for debugging / forensic inspection
    try:
        _hex_dump("/tmp/iso_last.hex", framed)
        LOG.info("Wrote framed payload hex to /tmp/iso_last.hex")
    except Exception:
        LOG.exception("Failed to write iso_last.hex")

    LOG.info(f"→ Connecting to processor {host}:{port} mti={mti} bytes={len(framed)}")
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=connect_timeout)
    except Exception as e:
        LOG.exception("Connection failed")
        return {"success": False, "error": str(e)}

    try:
        writer.write(framed)
        await writer.drain()

        # read 4-byte length header then payload
        header = await _read_exact(reader, 4, response_timeout)
        resp_len = struct.unpack(">I", header)[0]
        raw_resp = await _read_exact(reader, resp_len, response_timeout) if resp_len else b""

        mti_resp = None
        json_resp = None
        if len(raw_resp) >= 4:
            try:
                mti_resp = raw_resp[:4].decode("ascii")
            except Exception:
                mti_resp = None
            try:
                json_resp = json.loads(raw_resp[4:].decode("utf-8"))
            except Exception:
                json_resp = None

        return {"success": True, "mti_resp": mti_resp, "json_resp": json_resp, "raw_resp": raw_resp.hex()}
    except Exception as e:
        LOG.exception("Communication error")
        return {"success": False, "error": str(e)}
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


def send_iso_to_processor_sync(*args, **kwargs) -> Dict[str, Any]:
    """Sync wrapper for non-async contexts."""
    import asyncio as _asyncio
    try:
        return _asyncio.run(send_iso_to_processor(*args, **kwargs))
    except RuntimeError:
        loop = _asyncio.get_event_loop()
        return loop.run_until_complete(send_iso_to_processor(*args, **kwargs))
