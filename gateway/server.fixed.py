# gateway/app/server.py
import os
import logging
import uuid
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import the tcp client used to send ISO frames to the processor.
# This assumes tcp_client.py is at gateway/app/tcp_client.py and exposes
# `send_iso_to_processor(host, port, mti, fields)` returning a dict.

from app.tcp_client import send_iso_to_processor

LOG = logging.getLogger("gateway.server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Gateway")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROCESSOR_HOST = os.getenv("PROCESSOR_HOST", "processor")
# use PROCESSOR_PORT env or fallback to 9000
PROCESSOR_PORT = int(os.getenv("PROCESSOR_PORT", os.getenv("PROCESSOR_PORT", "9000")))

class TransactionIn(BaseModel):
    merchant_id: str
    protocol: str
    authCode: str
    terminal_id: str
    currency: str
    cardNumber: Optional[str] = None
    expiry: Optional[str] = None
    cvc: Optional[str] = None
    amount: Optional[float] = None
    payoutMethod: Optional[str] = None
    payoutDetails: Optional[Dict[str, Any]] = None

@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}

def normalize_iso_fields(raw: Dict[Any, Any]) -> Dict[int, Any]:
    """
    Make sure ISO fields keys are integers (tcp client/codec usually expects that)
    and values are strings (or primitives) suitable for encoding.
    """
    out: Dict[int, Any] = {}
    for k, v in raw.items():
        try:
            ik = int(k)
        except Exception:
            # ignore non-integer keys
            continue
        out[ik] = v
    return out

def map_processor_response(proc_resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map the processor tcp client response into the HTTP response expected by tests.
    Accepts wrappers seen in logs:
      - maybe keys 'approved', 'de39', 'txn_id', 'gateway_txn_id'
      - sometimes nested under 'raw'
      - also returns 'raw_frame_bytes' which we ignore
    Returns a dict like:
      { "approved": bool, "de39": "xx", "de38": optional, "txn_id": <str|null> }
    """
    LOG.debug("Mapping processor response: %r", proc_resp)
    # proc_resp may be the parsed ISO object (dict). Accept multiple shapes.
    # Prefer top-level keys, fallback to proc_resp['raw'].
    candidate = proc_resp
    if isinstance(proc_resp.get("raw"), dict):
        candidate = {**proc_resp.get("raw", {}), **proc_resp}
        # candidate now has top-level values with raw merged in.

    de39 = candidate.get("de39")
    approved = candidate.get("approved")
    # Normalize string booleans or numeric codes
    if approved is None:
        # determine from de39 if provided
        if isinstance(de39, (int,)) or (isinstance(de39, str) and de39.isdigit()):
            approved = str(de39) == "00"
        else:
            approved = bool(candidate.get("approved", False))

    txn_id = candidate.get("txn_id") or candidate.get("gateway_txn_id") or None
    return {
        "approved": bool(approved),
        "de39": None if de39 is None else str(de39),
        "de38": candidate.get("de38"),
        "txn_id": txn_id,
        # include raw for debug (optional; small)
        # "raw": candidate
    }

@app.post("/transactions")
async def transactions(txn: TransactionIn):
    """
    Build ISO-like fields from incoming transaction and send them to the processor via TCP client.
    The tcp client function `send_iso_to_processor(host, port, mti, fields)` is expected to return
    a dict-like response (see mapping function).
    """
    # Build ISO fields (keys as ints).
    iso_fields: Dict[int, Any] = {}

    # PAN / Primary Account Number
    if txn.cardNumber:
        iso_fields[2] = txn.cardNumber

    # Processing code (example) - minimal example, domain depends on your iso_codec
    # Put a default processing code; adjust if your processor expects something else
    iso_fields[3] = "000000"

    # Amount (field 4) must be an integer cents string for some processors; keep numeric-safe
    if txn.amount is not None:
        # Format cents without decimal point if that's how ISO expects it.
        # Here we send as string representing integer cents (e.g. 10.00 -> "000000001000")
        try:
            cents = int(round(float(txn.amount) * 100))
            iso_fields[4] = f"{cents:012d}"
        except Exception:
            iso_fields[4] = str(txn.amount)

    # Date/time / transmission date/time (field 7) - provide simple placeholder yyyyMMDDhhmm or MMDDhhmmss
    # Many ISO demos expect MMDDhhmmss (length 10). We'll set a simple value to avoid empty field.
    import datetime
    dt = datetime.datetime.utcnow()
    iso_fields[7] = dt.strftime("%m%d%H%M%S")

    # STAN (field 11) - use low-entropy counter
    iso_fields[11] = f"{uuid.uuid4().int % 1000000:06d}"

    # Local time (12) and date (13)
    iso_fields[12] = dt.strftime("%H%M%S")
    iso_fields[13] = dt.strftime("%m%d")

    # Expiry (field 14) - adapt "MM/YY" -> "MYY" or "YYMM" depending on iso codec; we'll send "YYMM" as usual
    if txn.expiry:
        e = txn.expiry.replace("/", "")
        # if given as MMYY convert to YYMM if necessary — keep a safe fallback
        if len(e) == 4:
            # assume MMYY -> YYMM
            iso_fields[14] = e[2:] + e[:2]
        else:
            iso_fields[14] = e

    # Terminal id / merchant
    if txn.terminal_id:
        iso_fields[41] = txn.terminal_id
    if txn.currency:
        # numeric currency code example: "USD" -> "840" (but we won't convert here)
        iso_fields[49] = txn.currency if len(txn.currency) != 3 else txn.currency

    # If payoutMethod is bank and payoutDetails contains account, attach it to a retained custom field
    if txn.payoutMethod and txn.payoutMethod.lower() == "bank" and txn.payoutDetails:
        # Put the beneficiary IBAN or account in a custom field (example 102)
        try:
            acct = txn.payoutDetails.get("account")
            if acct:
                iso_fields[102] = acct
        except Exception:
            pass

    LOG.info("Sending ISO to processor: host=%s port=%s fields=%s", PROCESSOR_HOST, PROCESSOR_PORT, iso_fields)

    # Ensure keys are ints (tcp_client/iso codec expects int keys)
    iso_fields = normalize_iso_fields(iso_fields)

    try:
        # MTI for a payout/financial transaction - adjust if your processor expects a different MTI
        mti = "0200"
        resp = await send_iso_to_processor(PROCESSOR_HOST, PROCESSOR_PORT, mti, iso_fields)
        LOG.info("Processor response: %r", resp)
    except Exception as e:
        LOG.exception("Error sending ISO to processor: %s", e)
        # Relay a gateway-level 502 or return a useful message for tests. Tests earlier expected a JSON response,
        # not an HTTP error; but returning an HTTP 502 is also reasonable. We'll return a JSON error for test runner.
        raise HTTPException(status_code=502, detail=f"Gateway error: {e}")

    # Map processor response into expected HTTP JSON
    result = map_processor_response(resp)
    return result

# If run directly (rare for container), allow uvicorn invocation
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), log_level="info")
