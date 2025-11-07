# ====== server.fix.py (drop-in) ======
# (This file is meant to replace the route that builds ISO fields and forwards to send_iso_to_processor)
from fastapi.responses import JSONResponse
from typing import Dict

# Helper: normalize auth codes to 6 digits (pad 4->6)
def _norm_auth_code(val: str) -> str:
    v = (val or "")
    v = str(v).strip()
    if not v:
        return ""  # leave empty, processor will return decline if required
    if v.isdigit():
        if len(v) == 4:
            return "00" + v
        if len(v) == 6:
            return v
    # non-digit or other length -> return empty to be safe
    return ""

# In your POST handler (replace the existing fields = { ... } block with the following)
# make sure imports and function names match your server file
data = await request.json()
LOG.info("Received transaction: %s", data)

mti = data.get("mti", "0200")  # default to 0200 for financial
# Build fields with common aliases & defaults
fields: Dict[str, str] = {
    "2": data.get("card_number") or data.get("cardNumber") or data.get("pan") or data.get("card_pan") or "",
    "3": data.get("processing_code") or data.get("processingCode") or "000000",
    "4": f"{int(float(data.get('amount', 0)) * 100):012d}",
    "7": data.get("transmission_datetime") or "1010060054",
    "11": data.get("stan") or data.get("system_trace") or "000001",
    "12": data.get("local_time") or "060054",
    "13": data.get("local_date") or "1010",
    "41": data.get("terminal_id") or data.get("terminalId") or "TERMINAL_ID_PLACEHOLDER",
    "42": data.get("merchant_id") or data.get("merchantId") or "M1",
    "49": data.get("currency") or "840",
    # protocol forwarded (try several aliases), default to 201.1
    "protocol": str(
        data.get("protocol")
        or data.get("protocol_code")
        or data.get("protocolCode")
        or data.get("protocolCode")
        or "201.1"
    ),
    # 38 normalized/padded (use alias names)
    "38": _norm_auth_code(data.get("auth_code") or data.get("auth") or data.get("authCode")),
}

# Basic API-side sanity checks
if not fields["2"]:
    LOG.warning("Missing PAN (DE2) in request; returning ISO 30 format error")
    return JSONResponse(status_code=400, content={"success": False, "error": "Missing PAN", "mti_resp": "0800", "json_resp": {"de39": "30"}})

LOG.info("Forwarding ISO fields: 2=%s protocol=%s 38=%s 4=%s",
         (fields["2"][:6] + "*" * max(0, len(fields["2"]) - 10) + fields["2"][-4:]) if fields["2"] else "<none>",
         fields.get("protocol"), fields.get("38"), fields.get("4"))

# now forward
try:
    result = await send_iso_to_processor(mti=mti, fields=fields)
except Exception as e:
    LOG.exception("send_iso_to_processor failed")
    return JSONResponse(status_code=500, content={"success": False, "error": str(e), "mti_resp": "0800", "json_resp": {"de39": "96"}})

# Return the processor response as before
return JSONResponse(
    {
        "received": True,
        "processor_result": {
            "success": result.get("success"),
            "error": result.get("error"),
            "mti_resp": result.get("mti_resp"),
            "json_resp": result.get("json_resp"),
        },
    }
)
# ====== end server.fix.py ======
