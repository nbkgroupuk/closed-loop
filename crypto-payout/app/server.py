# crypto-payout/app/server.py
import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from app.send_crypto_signonly import prepare_and_send_tx

import time
log = logging.getLogger("gateway.server")
logging.basicConfig(level=logging.INFO)

# Allow localhost frontend
ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

from fastapi import FastAPI, Request
from fastapi import FastAPI
from app.app.payouts_iso20022 import router as iso20022_router
#from app.payouts_iso20022 import router as iso20022_router - (ignored - 09-12-2025)

app = FastAPI(title="Gateway Service")

app.include_router(iso20022_router)

@app.post("/internal/payout")      # NEW APPEND - 09-12-2025
async def internal_payout(req: Request):
    """
    Internal-only payout trigger from settlement engine.
    """
    data = await req.json()
    amount = data.get("amount")
    to_addr = data.get("to_address")

    if not amount or not to_addr:
        raise HTTPException(status_code=400, detail="Missing amount or to_address")

    try:
        tx_hash = prepare_and_send_tx(amount, to_addr)
        return {"status": "sent", "tx_hash": tx_hash}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transactions")
async def transactions(req: Request):
    data = await req.json()
    # ... construct ISO, send to processor ...
    return {"received": True, "data": data}

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health(request: Request):
    origin = request.headers.get("origin")
    resp = JSONResponse({"status": "ok", "service": "gateway"})
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
    return resp

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    origin = ws.headers.get("origin")
    if origin not in ALLOWED_ORIGINS:
        log.warning(f"Rejected WS connection from {origin}")
        await ws.close(code=4003)
        return

    await ws.accept()
    log.info(f"Accepted WS connection from {origin}")
    try:
        while True:
            msg = await ws.receive_text()
            if msg.lower() == "ping":
                await ws.send_text("pong")
            else:
                await ws.send_text(f"echo: {msg}")
    except WebSocketDisconnect:
        log.info("WS disconnected")
