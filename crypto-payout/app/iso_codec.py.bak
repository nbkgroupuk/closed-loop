#gateway/app/app/iso_codec.py
"""
Minimal ISO codec used by the Processor and the simulator.

Frame format:
  4-byte big-endian length prefix + UTF-8 JSON payload

JSON payload shape:
  {"mti": "0200", "fields": { "2": "4111...", "3": "000000", ... }}

Exports:
  - pack_iso(mti: str, fields: dict) -> bytes   # full frame (4-byte len + payload)
  - unpack_iso(frame_or_payload: bytes) -> dict
      returns {"mti": mti, "fields": fields} with string keys for fields
  - recv_frame(sock, timeout=5.0) -> payload_bytes (raises ConnectionError on short read)
This module intentionally uses JSON for interoperability.
"""
from __future__ import annotations
import struct
import json
import socket
import logging
from typing import Dict, Any, Tuple, Union

LOG = logging.getLogger("app.iso_codec")
LOG.addHandler(logging.NullHandler())

MAX_FRAME = 10 * 1024 * 1024  # 10 MB safety cap


def pack_iso(mti: str, fields: Dict[Union[int, str], Any]) -> bytes:
    """
    Build a length-prefixed JSON frame.
    Fields keys are converted to strings to be JSON-safe.
    Returns: 4-byte BE length + payload bytes
    """
    body = {
        "mti": str(mti),
        "fields": {str(k): v for k, v in (fields.items() if isinstance(fields, dict) else [])}
    }
    b = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(b)) + b


def unpack_iso(frame_or_payload: bytes) -> Dict[str, Any]:
    """
    Accept either:
      - full frame (4-byte len + payload) OR
      - raw payload (payload bytes)
    Returns dict {"mti": "...", "fields": {...}} with string keys for fields.
    Raises ValueError on invalid framing or JSON decode errors.
    """
    if not isinstance(frame_or_payload, (bytes, bytearray)):
        raise ValueError("unpack_iso expects bytes")

    # If frame looks like 4-byte length + payload, strip length if it matches length
    if len(frame_or_payload) >= 4:
        possible_len = int.from_bytes(frame_or_payload[:4], "big")
        if possible_len == len(frame_or_payload) - 4:
            payload = frame_or_payload[4:]
        else:
            # maybe caller gave just the payload
            payload = frame_or_payload
    else:
        payload = frame_or_payload

    # decode payload
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        # fallback to latin-1 decode if needed
        text = payload.decode("latin-1", errors="replace")
        LOG.warning("unpack_iso: payload not utf-8, used latin-1 fallback")

    obj = json.loads(text)  # will raise JSONDecodeError if invalid
    # normalize: ensure structure
    if not isinstance(obj, dict) or "mti" not in obj or "fields" not in obj:
        raise ValueError("unpack_iso: payload must be object with 'mti' and 'fields' keys")
    # ensure fields is dict and keys are strings
    f = obj.get("fields") or {}
    if not isinstance(f, dict):
        raise ValueError("unpack_iso: 'fields' must be an object")
    # return {'mti': str, 'fields': {str: value}}
    return {"mti": str(obj.get("mti")), "fields": {str(k): v for k, v in f.items()}}


def recv_frame(sock: socket.socket, timeout: float = 5.0) -> bytes:
    """
    Blocking read on a blocking or timeout-enabled socket.
    Reads exactly 4 bytes length prefix, then payload. Returns payload bytes (without length).
    Raises ConnectionError on short read or invalid length.
    """
    # Save original timeout and set temporary
    orig_to = sock.gettimeout()
    sock.settimeout(timeout)
    try:
        # read 4 bytes length
        chunks = []
        to_read = 4
        while to_read > 0:
            chunk = sock.recv(to_read)
            if not chunk:
                raise ConnectionError("short length read")
            chunks.append(chunk)
            to_read -= len(chunk)
        raw_len = b"".join(chunks)
        if len(raw_len) != 4:
            raise ConnectionError("short length read")
        length = int.from_bytes(raw_len, "big")
        if length <= 0 or length > MAX_FRAME:
            raise ValueError(f"invalid frame length: {length}")
        # read payload
        payload_chunks = []
        remaining = length
        while remaining > 0:
            chunk = sock.recv(min(4096, remaining))
            if not chunk:
                raise ConnectionError("short payload read")
            payload_chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(payload_chunks)
        if len(payload) != length:
            raise ConnectionError("short payload read")
        return payload
    finally:
        try:
            sock.settimeout(orig_to)
        except Exception:
            pass


# quick self-test when module run directly (not executed on import)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    sample = {"mti": "0200", "fields": {"2": "TEST_PAN_REDACTED", "4": "1000", "41": "TERM1234"}}
    frame = pack_iso(sample["mti"], sample["fields"])
    print("packed len:", len(frame))
    parsed = unpack_iso(frame)
    print("parsed:", parsed)
