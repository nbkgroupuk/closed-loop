# server.py - drop-in gateway server for ISO forwarding
# Place at: /app/app/app/app/gateway/app/server.py  (your container path)
# NOTE: When you are ready tell me and I'll give the single docker cp + restart command.

import asyncio
import logging
from typing import Any, Dict, Tuple

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

LOG = logging.getLogger("gateway.server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Gateway (ISO Gateway)")

#
# Attempt to import send_iso_to_processor() from likely locations in your repo.
# If your code exposes a different function name or module please update.
#
send_iso_to_processor = None
for mod_name in ("gateway.tcp_client", "app.tcp_client", "tcp_client", "gateway.tcpclient"):
    try:
        mod = __import__(mod_name, fromlist=["send_iso_to_processor"])
        send_iso_to_processor = getattr(mod, "send_iso_to_processor", None)
        if send_iso_to_processor:
            LOG.info("Using send_iso_to_processor from %s", mod_name)
            break
    except Exception:
        # ignore import errors; we will handle missing function later
        pass

# --- ISO normalizer / validators (purely syntactic, not business validation) ---


def _norm_auth_code(val: Any) -> str:
    """
    Normalize the authorization code (DE38).
    - Accepts 4-digit or 6-digit numeric values.
    - If 4-digit and expected is 6-digit this code pads with '00' prefix.
    - If empty/invalid -> returns '000000' (safe placeholder).
    """
    v = (val or "")
    v = str(v).strip()
    if not v:
        return "000000"
    if v.isdigit():
        if len(v) == 4:
            return "00" + v
        if len(v) == 6:
            return v
    return "000000"


def _pick_pan(payload: Dict[str, Any]) -> str:
    """
    Pick PAN from common aliases used by frontend/backends.
    """
    for key in ("cardNumber", "card_number", "pan", "card_pan"):
        val = payload.get(key)
        if val:
            return str(val).strip()
    return ""


# small mapping of friendly names -> numeric protocol codes (extend as needed)
_PROTOCOL_FRIENDLY_MAP = {
    "pos": "101.1",
    "pos-terminal": "101.1",
    "visa": "101.1",
    "mastercard": "101.2",
    "default": "201.1",
}


def _normalize_protocol(raw: Any, default: str = "201.1") -> str:
    """
    Normalize protocol field:
     - accept keys protocol, protocol_code, protocolCode
     - map friendly names if provided
     - default to '201.1' unless you want strict requirement
    """
    if not raw:
        return default
    s = str(raw).strip()
    if not s:
        return default
    # map friendly keys
    key = s.lower()
    return _PROTOCOL_FRIENDLY_MAP.get(key, s)


def _mask_pan(pan: str) -> str:
    if not pan:
        return "****"
    pan = str(pan)
    if len(pan) <= 10:
        return pan[:2] + "*" * max(2, len(pan) - 4) + pan[-2:]
    return pan[:6] + "*" * (len(pan) - 10) + pan[-4:]


async def _ensure_send_iso_available():
    if send_iso_to_processor is None:
        msg = "Gateway not configured: send_iso_to_processor helper not available."
        LOG.error(msg)
        raise HTTPException(status_code=500, detail=msg)


# health endpoints
@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "gateway"}


# main transaction receive endpoint
@app.post("/api/transactions")
async def transactions(request: Request):
    """
    Accept a JSON payload and forward as an ISO 0200-like dict to your processor.
    This endpoint deliberately accepts a flexible payload (no strict schema) so you can
    iterate from the frontend quickly while we normalize fields before sending.
    """
    payload = await request.json()
    LOG.info("Received transaction payload keys: %s", list(payload.keys()))

    # Build normalized fields dict (ISO-style numeric keys as strings)
    fields: Dict[str, Any] = {}

    # DE2: pan
    fields["2"] = _pick_pan(payload)

    # Basic required: amount -> DE4 (in cents with 12 digits)
    try:
        amount_val = float(payload.get("amount") or payload.get("amt") or 0.0)
    except Exception:
        amount_val = 0.0
    fields["4"] = f"{int(amount_val * 100):012d}"

    # DE3 processing code - default 000000 if not provided
    fields["3"] = payload.get("processing_code") or payload.get("processingCode") or payload.get("proc_code") or "000000"

    # Transmission/local times: keep any passed in, otherwise sensible defaults
    fields["7"] = payload.get("transmission_datetime") or "1010060054"
    fields["11"] = payload.get("stan") or payload.get("system_trace") or "000001"
    fields["12"] = payload.get("local_time") or "060054"
    fields["13"] = payload.get("local_date") or "1010"

    # Terminal / merchant
    fields["41"] = payload.get("terminal_id") or payload.get("terminalId") or payload.get("terminal") or "TERMINAL_ID_PLACEHOLDER"
    fields["42"] = payload.get("merchant_id") or payload.get("merchantId") or payload.get("merchant") or "M1"
    fields["49"] = payload.get("currency") or payload.get("currency_code") or payload.get("currencyCode") or "840"

    # Protocol (normalize from payload)
    raw_proto = payload.get("protocol") or payload.get("protocol_code") or payload.get("protocolCode")
    fields["protocol"] = _normalize_protocol(raw_proto, default="201.1")

    # Auth DE38: normalize/pad
    raw_auth = payload.get("authCode") or payload.get("auth_code") or payload.get("auth")
    fields["38"] = _norm_auth_code(raw_auth)

    # Optional fields: transaction reference
    if payload.get("reference") or payload.get("ref") or payload.get("tid"):
        fields["37"] = payload.get("reference") or payload.get("ref") or payload.get("tid")

    # Sanity checks: de2 present?
    if not fields.get("2"):
        LOG.warning("Missing PAN (DE2) in request: refusing to forward (format error)")
        return JSONResponse(status_code=400, content={"success": False, "error": "Missing PAN", "mti_resp": "30"})

    # Final logging before forwarding (mask PAN)
    masked_pan = _mask_pan(fields.get("2", ""))
    LOG.info("Forwarding ISO fields: DE2=%s protocol=%s DE38=%s DE4=%s", masked_pan, fields.get("protocol"), fields.get("38"), fields.get("4"))

    # Ensure helper exists
    await _ensure_send_iso_available()

    # Default MTI is 0200 (financial transaction)
    mti = payload.get("mti") or "0200"

    # Call the processor sender (user-provided helper)
    try:
        # send_iso_to_processor may be async or sync; support both
        if asyncio.iscoroutinefunction(send_iso_to_processor):
            result = await send_iso_to_processor(mti=mti, fields=fields)
        else:
            # run sync in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda: send_iso_to_processor(mti=mti, fields=fields))
    except Exception as exc:
        LOG.exception("Error calling send_iso_to_processor: %s", exc)
        return JSONResponse(status_code=500, content={"success": False, "error": "gateway_send_error", "detail": str(exc)})

    # Normalize result to expected structure
    if not isinstance(result, dict):
        LOG.error("send_iso_to_processor returned non-dict value: %r", result)
        return JSONResponse(status_code=502, content={"success": False, "error": "bad_downstream", "detail": "invalid response from processor"})

    # Return a tidy envelope to the frontend and include raw processor response
    return JSONResponse(
        status_code=200,
        content={
            "received": True,
            "data": payload,
            "processor_result": {
                "success": result.get("success"),
                "error": result.get("error"),
                "mti_resp": result.get("mti_resp"),
                "json_resp": result.get("json_resp"),
                "raw": result,
            },
        },
    )

