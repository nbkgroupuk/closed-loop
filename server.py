# project/server.py
"""
FastAPI Gateway Server
Receives frontend transactions and forwards ISO8583-style requests to the processor.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging
import asyncio
from tcp_client import send_iso_to_processor

app = FastAPI(title="Payment Gateway API")
LOG = logging.getLogger("gateway.server")
LOG.setLevel(logging.INFO)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}


@app.post("/transactions")
async def process_transaction(request: Request):
    """Accept frontend JSON transaction and forward to ISO processor."""
    data = await request.json()
    LOG.info(f"🌐 Received transaction from frontend: {data}")

    # Normalize fields
    card_number = data.get("cardNumber")
    amount = data.get("amount", "0.00")
    merchant_id = data.get("merchant_id", "MERCHID000001")
    expiry = data.get("expiry", "1230").replace("/", "")
    auth_code = data.get("authCode", "0000")
    protocol = "101.1"  # default for POS Terminal 4-digit approval

    fields = {
        "DE2": card_number,
        "DE3": "000000",
        "DE4": f"{int(float(amount) * 100):012d}",
        "DE7": "1010000000",
        "DE11": "123456",
        "DE12": "101000",
        "DE13": "1022",
        "DE14": expiry,
        "DE22": "012",
        "DE37": "000000000001",
        "DE41": "TERM0001",
        "DE42": merchant_id,
        "DE43": "BLACKROCK TERMINAL 01 NYC",
        "DE49": "840",
        "protocol": protocol,
        "auth": auth_code,
    }

    try:
        result = await send_iso_to_processor(
            mti="0200",
            fields=fields,
            host="host.docker.internal",
            port=9000
        )
    except Exception as e:
        LOG.error(f"Gateway→Processor communication failed: {e}")
        return JSONResponse(status_code=502, content={"detail": f"Gateway error: {e}"})

    LOG.info(f"✅ Processor response: {result}")

    if not result.get("success"):
        return JSONResponse(status_code=502, content={"detail": f"Processor error: {result.get('error')}"})

    return JSONResponse(
        {
            "approved": result["json_resp"].get("approved", False) if result["json_resp"] else False,
            "de39": result["json_resp"].get("de39", "96") if result["json_resp"] else "96",
            "de38": result["json_resp"].get("de38"),
            "txn_id": result["json_resp"].get("txn_id", "N/A"),
        }
    )

