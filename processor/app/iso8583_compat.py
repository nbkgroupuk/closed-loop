# app/iso8583_compat.py
# This module must match the Gateway's pack_iso/unpack_iso framing.
import struct, json
from typing import Dict, Any

def pack_iso(mti: str, fields: Dict[str, Any]) -> bytes:
    if not isinstance(mti, str) or len(mti) != 4:
        raise ValueError("MTI must be 4-char string")
    payload = {"fields": fields}
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    header = mti.encode("ascii") + struct.pack("!I", len(payload_bytes))
    return header + payload_bytes

def unpack_iso(stream: bytes) -> Dict[str, Any]:
    if len(stream) < 4:
        raise ValueError("stream too short")
    length = int.from_bytes(stream[0:4], "big")
    payload = stream[4:4+length].decode("utf-8")
    obj = json.loads(payload)
    return {"mti": obj.get("mti"), "fields": obj.get("fields", {})}

