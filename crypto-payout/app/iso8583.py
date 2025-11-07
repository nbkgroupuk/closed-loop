# gateway/app/iso8583.py
"""
Minimal ISO8583 packer/unpacker for core fields used in the Gateway.
This is a light-weight helper for dev & integration testing.
For production, replace with a full ISO8583 library that handles bitmaps, field types, binary packing, and TLV fields.

Framing used by pack_iso:
- 4 bytes MTI (ASCII)
- 4 bytes length (big-endian) of JSON payload
- JSON payload bytes (utf-8) where payload = {"fields": {...}}

unpack_iso is tolerant: if framing is absent it will try to parse the first JSON object from the bytes
and will log any trailing data so you can inspect what the processor actually sent.
"""
import struct
import json
import logging
from typing import Dict, Any

log = logging.getLogger(__name__)

def pack_iso(mti: str, fields: Dict[str, Any]) -> bytes:
    """
    Build a compact framed message:
    - 4 bytes MTI (ASCII)
    - 4 bytes length (big-endian) of JSON payload
    - JSON payload bytes (utf-8) where payload = {"fields": {...}}
    """
    if not isinstance(mti, str) or len(mti) != 4:
        raise ValueError("MTI must be 4-char string")
    payload = {"fields": fields}
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    header = mti.encode("ascii") + struct.pack("!I", len(payload_bytes))
    return header + payload_bytes

def _try_parse_framed(stream: bytes) -> Dict[str, Any]:
    """
    Try to parse the MTI+length framed message. Raises ValueError on failure.
    """
    if len(stream) < 8:
        raise ValueError("stream too short for framed message")
    try:
        mti = stream[0:4].decode("ascii")
    except Exception as e:
        raise ValueError(f"invalid MTI encoding: {e}") from e
    length = struct.unpack("!I", stream[4:8])[0]
    if len(stream) < 8 + length:
        raise ValueError("incomplete payload for framed message")
    payload_bytes = stream[8:8+length]
    try:
        payload = payload_bytes.decode("utf-8")
    except Exception:
        payload = payload_bytes.decode("utf-8", errors="replace")
    obj = json.loads(payload)
    fields = obj.get("fields", {})
    return {"mti": mti, "fields": fields}

def unpack_iso(stream: bytes) -> Dict[str, Any]:
    """
    Unpack the framing above and return {"mti":str, "fields": {...}}.
    Tolerant: if framing isn't present or fails, attempt to decode the first JSON object
    from the byte stream and log trailing data.
    """
    if not stream:
        raise ValueError("empty stream")

    # Log the raw bytes at debug level (hex + preview)
    log.debug("unpack_iso: raw bytes (len=%d): %r", len(stream), stream[:1024])

    # First, try the framed format (fast path)
    try:
        res = _try_parse_framed(stream)
        log.debug("unpack_iso: parsed framed message mti=%s", res.get("mti"))
        # If there is trailing data beyond the framed message, log it
        try:
            length = struct.unpack("!I", stream[4:8])[0]
            tail = stream[8+length:]
            if tail:
                # decode tail safely for logs
                tail_str = tail.decode("utf-8", errors="replace")
                log.warning("unpack_iso: trailing data after framed message (len=%d): %r", len(tail), tail_str[:1000])
        except Exception:
            # do not fail on tail logging errors
            log.debug("unpack_iso: unable to compute/log framed tail")
        return res
    except Exception as framed_exc:
        log.debug("unpack_iso: framed parse failed: %s; falling back to tolerant JSON parse", framed_exc)

    # Fallback: try to decode as one or more JSON objects; extract the first JSON object
    try:
        payload = stream.decode("utf-8", errors="replace")
    except Exception:
        payload = stream.decode("latin-1", errors="replace")

    log.debug("unpack_iso: fallback payload string preview: %r", payload[:2000])

    decoder = json.JSONDecoder()
    try:
        obj, idx = decoder.raw_decode(payload)
    except json.JSONDecodeError as e:
        # Log the payload for debugging then re-raise so caller sees the original error
        log.error("unpack_iso: JSON decode failed in fallback: %s; payload preview=%r", e, payload[:2000])
        raise

    tail = payload[idx:].lstrip()
    if tail:
        log.warning("unpack_iso: extra trailing data after JSON payload (first %d chars): %r", min(len(tail), 1000), tail[:1000])

    # Determine mti: prefer explicit value if present in payload, otherwise default to '0000'
    mti = "0000"
    if isinstance(obj, dict):
        # payload might be {"mti": "...", "fields": {...}} or {"fields": {...}}
        if "mti" in obj and isinstance(obj["mti"], str) and len(obj["mti"]) == 4:
            mti = obj["mti"]
        else:
            fields_candidate = obj.get("fields")
            if isinstance(fields_candidate, dict):
                # maybe fields contain an mti key (uncommon) -> ignore unless explicit
                mti = obj.get("mti") or "0000"
    fields = obj.get("fields", {}) if isinstance(obj, dict) else {}

    return {"mti": mti, "fields": fields}
