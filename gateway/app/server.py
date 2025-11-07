# gateway/app/server.py
# server.py  -- simplified gateway server that builds consistent DE fields
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging
from app.tcp_client import send_iso_to_processor as tcp_send_iso_to_processor

app = FastAPI(title="Payment Gateway API")
LOG = logging.getLogger("gateway.server")
LOG.setLevel(logging.INFO)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}


@app.post("/transactions")
async def process_transaction(request: Request):
    data = await request.json()
    LOG.info("Received transaction: %s", data)

    card_number = data.get("cardNumber")
    amount = data.get("amount", "0.00")
    merchant_id = data.get("merchant_id", "MERCHID000001")
    expiry = data.get("expiry", "1230").replace("/", "")
    auth_code = data.get("authCode", "0000")
    # Normalize protocol short code like "101.1" if frontend provides "POS Terminal -101.1 (...)"
    proto_raw = data.get("protocol", "")
    import re
    m = re.search(r"(\d{3}\.\d)", str(proto_raw))
    protocol = m.group(1) if m else "101.1"

    # Build ISO-like fields (use numeric keys as ints where appropriate)
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
        43: "BLACKROCK TERMINAL 01 NYC",
        49: "840",
        "protocol": protocol,
        "auth": auth_code,
    }

    LOG.info("Forwarding to processor with fields keys: %s", list(fields.keys()))

    # call the tcp_client function and capture the full result dict for logging/debugging
    result = await tcp_send_iso_to_processor(mti="0200", fields=fields, host="host.docker.internal", port=9000)

    LOG.info("Processor returned raw: %s", result)
    # defensive handling if send failed
    if not isinstance(result, dict) or not result.get("success"):
        err = None
        try:
            err = result.get("error")
        except Exception:
            err = str(result)
        LOG.error("Processor call failed: %s", err)
        return JSONResponse(status_code=502, content={"detail": f"Processor error: {err}"})

    json_resp = result.get("json_resp") or {}
    return JSONResponse({
        "approved": json_resp.get("approved", False),
        "de39": json_resp.get("de39", "96"),
        "de38": json_resp.get("de38"),
        "txn_id": json_resp.get("txn_id", None),
    })
