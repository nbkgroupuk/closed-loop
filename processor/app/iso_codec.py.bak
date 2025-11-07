# processor/app/iso_codec.py
#docker exec -i project-processor sh -c 'cat > /app/app/iso_codec.py <<'"'"'PY'
#!/usr/bin/env python3
"""
iso_codec.py — Robust ISO codec that accepts length-prefixed JSON frames
and legacy ASCII MTI frames. Designed for production: explicit errors,
backwards compatibility, and clear logging.
"""
from __future__ import annotations
import json, struct, logging

LOG = logging.getLogger("processor.iso_codec")
LOG.addHandler(logging.NullHandler())

MAX_FRAME = 10 * 1024 * 1024  # 10 MB

def pack_iso(mti: str, fields: dict) -> bytes:
    body = {"mti": str(mti), "fields": {str(k): v for k, v in (fields.items() if isinstance(fields, dict) else [])}}
    payload = json.dumps(body).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload

def unpack_iso(frame_or_payload: bytes):
    """
    Accept either:
      - full frame (4-byte BE length prefix + payload),
      - raw payload bytes (JSON or legacy),
      - legacy (first 4 bytes ASCII MTI + remainder raw data).

    Returns: {"mti": mti, "fields": fields} or raises ValueError on parse error.
    """
    if not frame_or_payload:
        raise ValueError("empty payload")

    data = frame_or_payload

    # If it looks like a length-prefixed frame, strip prefix
    if len(data) >= 4:
        try:
            (declen,) = struct.unpack(">I", data[:4])
            # If declared length looks plausible compared to remaining bytes, strip it
            if 0 < declen <= MAX_FRAME and (len(data) - 4) >= 0:
                # If remaining bytes length matches or at least not obviously wrong, use it.
                # Some senders may not include exact match (fragmentation), but this is safest.
                payload = data[4:]
                # Only accept this as "strip" if payload length is equal or payload starts like JSON/ASCII
                if len(payload) == declen or (len(payload) > 0 and payload.lstrip().startswith(b'{')):
                    data = payload
        except Exception:
            # not a valid length prefix — fall through to try parsing whole buffer
            pass

    # Try JSON payload (gateway-style)
    try:
        text = data.decode("utf-8")
        if text.strip().startswith("{"):
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "mti" in parsed and "fields" in parsed:
                return {"mti": str(parsed["mti"]), "fields": parsed["fields"]}
            # if json contains "fields" that looks like payload but missing mti, try to recover
            if isinstance(parsed, dict) and "fields" in parsed:
                return {"mti": parsed.get("mti", "0200"), "fields": parsed["fields"]}
    except Exception:
        # JSON decode failed; continue to legacy parsing
        pass

    # Legacy: expect ASCII MTI in first 4 bytes
    try:
        if len(data) < 4:
            raise ValueError("legacy parse: too short for MTI")
        mti = data[:4].decode("ascii")
        # Remaining fields left as raw (processor can decode further if needed)
        fields_raw = data[4:]
        # Attempt to return some parsed fields if possible, else provide raw_hex
        try:
            # try to parse as textual k=v pairs (best-effort) — optional
            text_rem = fields_raw.decode("utf-8", errors="ignore").strip()
            if text_rem.startswith("{"):
                # embedded JSON
                sub = json.loads(text_rem)
                return {"mti": mti, "fields": sub}
        except Exception:
            pass
        return {"mti": mti, "fields": {"raw_hex": fields_raw.hex()}}
    except Exception as e:
        raise ValueError("invalid MTI in payload") from e

def recv_frame(sock, timeout=5.0):
    """
    Read a length-prefixed frame from a socket: 4-byte BE length + payload.
    Returns payload bytes.
    """
    sock.settimeout(timeout)
    hdr = sock.recv(4)
    if not hdr or len(hdr) < 4:
        raise ConnectionError("short header read")
    (length,) = struct.unpack(">I", hdr)
    if length <= 0 or length > MAX_FRAME:
        raise ValueError(f"invalid frame length {length}")
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise ConnectionError("short payload read")
        data += chunk
    return data

if __name__ == "__main__":
    # quick local test
    f = {"2": "TEST_PAN_REDACTED", "4": "000000001000", "41": "TERM001", "42": "MERCH0001", "49": "978"}
    frame = pack_iso("0200", f)
    print("packed len:", len(frame))
    print("unpack:", unpack_iso(frame))
#PY'
