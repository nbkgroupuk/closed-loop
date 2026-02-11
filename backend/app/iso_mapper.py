# backend/app/iso_mapper.py
from datetime import datetime
import re


def _normalize_protocol(protocol: str) -> str:
    """
    Extract protocol number from UI string.
    Example:
      "POS Terminal -101.1 (4-digit approval)" → "101.1"
    """
    if not protocol:
        raise ValueError("protocol missing")

    m = re.search(r"(\d{3}\.\d)", protocol)
    return m.group(1) if m else protocol


def map_protocol_to_iso(protocol: str, payload: dict) -> dict:
    """
    Input:
      protocol: "101.1", "201.1" OR UI string
      payload: canonical request

    Output:
      ISO8583 dict: { mti, fields }
    """

    now = datetime.utcnow()
    proto = _normalize_protocol(protocol)

    # ---- REQUIRED FIELDS CHECK ----
    required = ["pan", "amount", "stan", "terminal_id", "merchant_id"]
    for f in required:
        if f not in payload:
            raise ValueError(f"Missing required field: {f}")

    auth_code = payload.get("authCode") or payload.get("auth_code")
    if not auth_code:
        raise ValueError("authCode/auth_code missing in payload")

    # ===== BASE ISO FIELDS =====
    iso = {
        "mti": "0200",
        "fields": {
            "2": payload["pan"],                       # PAN
            "3": "000000",                              # Processing code
            "4": f'{int(float(payload["amount"]) * 100):012}',  # Amount
            "7": now.strftime("%m%d%H%M%S"),            # Transmission datetime
            "11": payload["stan"],                      # STAN
            "12": now.strftime("%H%M%S"),
            "13": now.strftime("%m%d"),
            "41": payload["terminal_id"],               # Terminal ID
            "42": payload["merchant_id"],               # Merchant ID
            "49": payload.get("currency", "840"),       # Currency
            "60": proto,                                # Protocol indicator
        }
    }

    # ===== AUTH CODE RULE =====
    if proto in ("101.1", "101.7"):
        iso["fields"]["38"] = auth_code[:4]
    else:
        iso["fields"]["38"] = auth_code[:6]

    # ===== PROTOCOL-SPECIFIC BEHAVIOR =====

    # --- 101 SERIES (ONLINE) ---
    if proto.startswith("101."):

        if proto == "101.6":
            iso["fields"]["3"] = "003000"   # Pre-auth

        if proto == "101.5":
            iso["fields"]["22"] = "010"     # MOTO

    # --- 201 SERIES (OFFLINE / COMPLETION) ---
    if proto.startswith("201."):

        iso["mti"] = "0220"                # Advice / completion
        iso["fields"]["25"] = "00"         # POS condition code

        if proto in ("201.2", "201.3"):
            iso["fields"]["22"] = "021"    # Offline entry

    return iso


