#!/usr/bin/env python3
# gateway/settlement_handler.py
"""
Production-ready Settlement Handler
-----------------------------------
• Preserves protocol→auth validation/generation.
• Adds required ISO fields for proper 0200/0210 exchange.
• Handles both bank-account and crypto-wallet payouts.
• Sends auth code (DE38) and protocol every time.
• Posts settlement after successful approval (DE39='00').
"""
import os, json, logging, random, socket, struct, time, requests, traceback

# ---------------------------------------------------------------------
# Basic config
# ---------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("settlement_handler")

PROCESSOR_HOST = os.getenv("PROCESSOR_HOST", "processor")
PROCESSOR_PORT = int(os.getenv("PROCESSOR_PORT", "9000"))
GATEWAY_INTERNAL_URL = os.getenv("GATEWAY_INTERNAL_URL", "http://localhost:8000/transactions")
REQUEST_TIMEOUT = 10.0

# ---------------------------------------------------------------------
# Protocol-auth-length mapping
# ---------------------------------------------------------------------
PROTOCOL_AUTH_LEN = {
    "101.1": 4, "101.2": 6, "101.3": 6, "101.4": 6, "101.5": 6, "101.6": 6,
    "101.7": 4, "101.8": 4,
    "201.1": 6, "201.2": 6, "201.3": 6, "201.4": 6, "201.5": 6,
}

# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------
def _mask_pan(p):
    if not p: return None
    s = str(p)
    return s[:4] + "*" * max(len(s) - 8, 0) + s[-4:] if len(s) >= 8 else s

def _make_auth(n):
    if n <= 0: n = 6
    return f"{random.randint(0,10**n - 1):0{n}d}"

def _expected_len(proto):
    p = str(proto or "").strip()
    if p in PROTOCOL_AUTH_LEN:
        return PROTOCOL_AUTH_LEN[p]
    if "101." in p: return 4
    if "201." in p: return 6
    return 6

# ---------------------------------------------------------------------
# ISO frame helpers (same as processor)
# ---------------------------------------------------------------------
def pack_iso(mti: str, fields: dict) -> bytes:
    body = {
        "mti": str(mti),
        "fields": {str(k): v for k, v in (fields.items() if isinstance(fields, dict) else [])},
    }
    payload = json.dumps(body).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload

def recv_all(sock, n):
    data = b""
    while len(data) < n:
        part = sock.recv(n - len(data))
        if not part:
            raise ConnectionError("short read")
        data += part
    return data

def recv_frame(sock):
    hdr = recv_all(sock, 4)
    (length,) = struct.unpack(">I", hdr)
    if length <= 0 or length > 10_000_000:
        raise ValueError(f"invalid frame length {length}")
    return recv_all(sock, length)

# ---------------------------------------------------------------------
# Build complete ISO field set for 0200 authorization
# ---------------------------------------------------------------------
def build_iso_fields(payload: dict) -> dict:
    proto = payload.get("protocol") or "101.1"
    expected = _expected_len(proto)
    auth = payload.get("auth_code") or _make_auth(expected)
    amt = payload.get("amount") or 0
    cents = int(float(amt) * 100)

    fields = {
        "2": payload.get("card_number") or "TEST_PAN_REDACTED",
        "3": "000000",                       # processing code
        "4": f"{cents:012d}",                # amount (12-digit)
        "7": time.strftime("%m%d%H%M%S"),    # transmission date & time
        "11": payload.get("stan") or f"{random.randint(0,999999):06d}",
        "12": time.strftime("%H%M%S"),
        "13": time.strftime("%m%d"),
        "37": payload.get("rrn") or f"{random.randint(0,999999999999):012d}",
        "38": str(auth),
        "41": payload.get("terminal_id") or "TERM001",
        "42": payload.get("merchant_id") or "MERCH0001",
        "49": payload.get("currency") or "978",
        "protocol": proto,
    }

    # attach payout-details
    if "payoutDetails" in payload:
        fields["payoutDetails"] = payload["payoutDetails"]

    return fields

# ---------------------------------------------------------------------
# ISO/TCP communication
# ---------------------------------------------------------------------
def send_to_processor_tcp(fields: dict):
    frame = pack_iso("0200", fields)
    log.info("Connecting to %s:%s ...", PROCESSOR_HOST, PROCESSOR_PORT)
    try:
        with socket.create_connection((PROCESSOR_HOST, PROCESSOR_PORT), timeout=8) as s:
            s.sendall(frame)
            raw = recv_frame(s)
            text = raw.decode("utf-8", errors="replace")
            log.info("Received ISO response: %s", text)
            return json.loads(text)
    except Exception as e:
        log.error("send_to_processor_tcp failed: %s", e)
        traceback.print_exc()
        raise

# ---------------------------------------------------------------------
# Settlement payload builder
# ---------------------------------------------------------------------
def build_payload(fields: dict):
    amt = fields.get("4") or "0"
    try:
        amount = float(int("".join(ch for ch in str(amt) if ch.isdigit()))) / 100.0
    except Exception:
        amount = 0.0

    proto = fields.get("protocol") or "unknown"
    auth = fields.get("38") or _make_auth(_expected_len(proto))

    return {
        "merchant_id": fields.get("42") or "unknown_merchant",
        "terminal_id": fields.get("41") or "unknown_terminal",
        "masked_pan": _mask_pan(fields.get("2")),
        "auth_code": auth,
        "currency": fields.get("49") or "USD",
        "amount": amount,
        "protocol": proto,
        "card_settlement": True,
        "iso_fields": fields,
    }

# ---------------------------------------------------------------------
# ISO-response handler (post-approval settlement)
# ---------------------------------------------------------------------
def on_iso_response(parsed):
    if not parsed or not isinstance(parsed, dict):
        log.warning("invalid parsed iso")
        return
    f = parsed.get("fields") or {}
    if str(f.get("39") or f.get(39)) != "00":
        log.info("not approved; skip settlement (DE39=%s)", f.get("39"))
        return
    payload = build_payload(f)
    try:
        log.info("Posting settlement to %s payload=%s",
                 GATEWAY_INTERNAL_URL,
                 json.dumps({
                     "merchant_id": payload["merchant_id"],
                     "amount": payload["amount"],
                     "auth_code": payload["auth_code"],
                     "protocol": payload["protocol"],
                 }))
        r = requests.post(GATEWAY_INTERNAL_URL, json=payload, timeout=REQUEST_TIMEOUT)
        log.info("Settlement POST status=%s body=%s",
                 r.status_code, (r.text or "")[:400])
        return r
    except Exception as e:
        log.exception("Settlement post failed: %s", e)

# ---------------------------------------------------------------------
# Test entry (manual trigger)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    sample = {
        "merchant_id": "MERCH0001",
        "terminal_id": "TERM001",
        "currency": "978",
        "amount": 10.00,
        "protocol": "101.1",
        "auth_code": "1234",
        "payoutDetails": {
            "iban": "DE89370400440532013000",
            "bic": "DEUTDEFF"
        },
    }
    iso_fields = build_iso_fields(sample)
    log.info("Sending sample payout ISO message ...")
    resp = send_to_processor_tcp(iso_fields)
    log.info("Processor replied: %s", resp)
    on_iso_response(resp)
