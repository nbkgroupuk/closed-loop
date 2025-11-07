# gateway/app/tcp_client.py
import asyncio
import json
import logging
from typing import Dict, Any, Optional

LOG = logging.getLogger("gateway.tcp_client")

# Configurable timeouts (env override possible in compose if you add)
CONNECT_TIMEOUT = 3.0
READ_TIMEOUT = 5.0

async def _read_exactly(reader: asyncio.StreamReader, n: int, timeout: float) -> bytes:
    return await asyncio.wait_for(reader.readexactly(n), timeout=timeout)

def _parse_payload(payload: bytes) -> Dict[str, Any]:
    """
    Accept payload that may be:
      - MTI(4 ASCII) + JSON body ({"fields": {...}}) OR
      - JSON body only
    Returns dict with keys: mti (optional), fields (dict) and raw (parsed JSON or raw text)
    """
    out = {"mti": None, "fields": {}, "raw": None}
    if not payload:
        return out
    try:
        # If payload starts with 4 ASCII digits -> MTI prefix
        if len(payload) >= 4 and payload[:4].decode('ascii', errors='ignore').isdigit():
            mti = payload[:4].decode('ascii')
            body = payload[4:]
            try:
                parsed = json.loads(body.decode('utf-8', errors='replace'))
                out.update({"mti": mti, "raw": parsed})
                if isinstance(parsed, dict):
                    # accept either {"fields": {...}} or flat dict
                    if "fields" in parsed and isinstance(parsed["fields"], dict):
                        out["fields"] = parsed["fields"]
                    else:
                        out["fields"] = parsed
                return out
            except Exception:
                # fallthrough to try JSON-only
                pass
        # JSON-only fallback
        try:
            parsed = json.loads(payload.decode('utf-8', errors='replace'))
            out.update({"raw": parsed})
            if isinstance(parsed, dict):
                if "fields" in parsed and isinstance(parsed["fields"], dict):
                    out["fields"] = parsed["fields"]
                else:
                    out["fields"] = parsed
            return out
        except Exception:
            text = payload.decode('utf-8', errors='replace').strip()
            out["raw"] = {"_raw_text": text}
            if "APPROVED" in text.upper():
                out["fields"] = {}
                out["de39"] = "00"
                out["approved"] = True
            return out
    except Exception as e:
        LOG.exception("parse error: %s", e)
        out["raw"] = {"_error": str(e)}
        return out

async def send_iso_to_processor(host: str, port: int, mti: str, fields: Dict[Any, Any], timeout: float = READ_TIMEOUT) -> Dict[str, Any]:
    """
    Send framed message: [4-byte BE len][MTI(4 ASCII)][JSON body={"fields": {...}}]
    Await framed response with same format and return parsed dict.
    Raises ConnectionError on repeated failure.
    """
    last_exc: Optional[Exception] = None
    # build payload: MTI + JSON({"fields":...})
    payload_body = json.dumps({"fields": {str(k): v for k, v in fields.items()}}, separators=(",", ":")).encode("utf-8")
    payload_bytes = mti.encode("ascii") + payload_body
    hdr = len(payload_bytes).to_bytes(4, byteorder="big")

    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            LOG.info("send_iso_to_processor attempt %d -> %s:%s mti=%s", attempt, host, port, mti)
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=CONNECT_TIMEOUT)
            writer.write(hdr + payload_bytes)
            await writer.drain()

            # read response header (4 bytes)
            raw_hdr = await _read_exactly(reader, 4, timeout=timeout)
            rlen = int.from_bytes(raw_hdr, byteorder="big")
            LOG.debug("response length=%d", rlen)

            body = await _read_exactly(reader, rlen, timeout=timeout)
            LOG.debug("response body len=%d", len(body))

            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

            parsed = _parse_payload(body)
            # convenience: pull de39 if present under common keys
            if isinstance(parsed.get("raw"), dict):
                parsed_de39 = parsed["raw"].get("de39") or parsed["raw"].get("DE39") or parsed["raw"].get("39")
                if parsed_de39 is not None:
                    parsed["de39"] = parsed_de39
                parsed["approved"] = parsed["raw"].get("approved", parsed.get("approved"))
            return parsed

        except asyncio.TimeoutError as e:
            last_exc = e
            LOG.warning("timeout on attempt %d: %s", attempt, e)
        except ConnectionRefusedError as e:
            last_exc = e
            LOG.warning("connection refused on attempt %d: %s", attempt, e)
        except Exception as e:
            last_exc = e
            LOG.exception("unexpected error on attempt %d:", attempt)
        await asyncio.sleep(0.25 * attempt)

    raise ConnectionError(f"failed to contact processor after {attempts} attempts: {last_exc}")
