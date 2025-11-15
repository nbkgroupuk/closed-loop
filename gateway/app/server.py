# gateway/app/server.py
# server.py  -- simplified gateway server that builds consistent DE fields
# gateway/app/server.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request
import logging, re, os
from app.tcp_client import send_iso_to_processor as tcp_send_iso_to_processor

app = FastAPI(title="Payment Gateway API")
LOG = logging.getLogger("gateway.server")
LOG.setLevel(logging.INFO)

# gateway/app/server.py (add near the top where `app` is created)

app = FastAPI(title="Payment Gateway API")

@app.get("/health", include_in_schema=False)
async def health():
    return JSONResponse({"status": "ok", "service": "gateway"})

#@app.get("/healthz")
#async def healthz():
#   return {"status": "ok", "service": "gateway"}

@app.get("/ui-config")
async def ui_config():
    # Let the browser/edge discover the correct base automatically
    # Your nginx maps /config.json to this as well.
    return {"api_base": os.getenv("PUBLIC_API_BASE", ""), "service": "gateway"}

@app.post("/transactions")
async def process_transaction(request: Request):
    body = await request.json()
    LOG.info("txn req: %s", body)

    # Inputs from UI (safe defaults)
    card_number = body.get("cardNumber")
    amount = body.get("amount", "0.00")
    merchant_id = body.get("merchant_id", "MERCHID000001")
    expiry = body.get("expiry", "12/30").replace("/", "")
    auth_code = body.get("authCode", "")  # we will echo this back for UI display
    proto_raw = str(body.get("protocol", ""))
    m = re.search(r"(\d{3}\.\d)", proto_raw)
    protocol = m.group(1) if m else "101.1"

    # Build ISO-like map for the processor
    fields = {
        2: card_number,
        3: "000000",
        4: f"{int(float(amount) * 100):012d}",
        7: "1010000000",
        11: "123456",
        12: "101000",
        13: "1022",
        14: expiry,
        22: "012",
        37: "000000000001",
        41: "TERM0001",
        42: merchant_id,
        43: "TERMINAL 01",
        49: "840",
        "protocol": protocol,
        "auth": auth_code,
    }

    # Call the processor
    result = await tcp_send_iso_to_processor(
        mti="0200", fields=fields, host="host.docker.internal", port=9000
    )

    # Network / processor error handling
    if not isinstance(result, dict) or not result.get("success"):
        detail = (result or {}).get("error") if isinstance(result, dict) else str(result)
        LOG.error("processor error: %s", detail)
        return JSONResponse(status_code=502, content={"detail": f"Processor error: {detail}"})

    # Normalize processor response
    jr = result.get("json_resp") or {}
    de39 = jr.get("de39")
    approved_flag = jr.get("approved")
    if approved_flag is None:
        # If processor didn’t send 'approved', infer from DE39 if present
        if de39 is not None:
            approved_flag = (str(de39) == "00")
        else:
            approved_flag = True  # last-resort default

    # Compose the response expected by your frontend
    resp = {
        "ok": True,
        "status": "approved" if approved_flag else "declined",
        "de39": str(de39) if de39 is not None else ("00" if approved_flag else "96"),
        "auth_code": auth_code or jr.get("de38"),  # prefer UI-sent code; fallback to DE38 if provided
    }

    # Pass through optional fields from processor only if present (no hardcoded 'SIMULATED')
    for k in ("job_id", "txhash", "de38", "txn_id"):
        if jr.get(k) not in (None, ""):
            resp[k] = jr[k]

    return JSONResponse(resp)
    

@app.get("/health")
def health():
    return {"status":"ok","service":"gateway"}
