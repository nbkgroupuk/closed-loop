# gateway/app/server.py
import os
import uuid
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import httpx

LOG = logging.getLogger("gateway.server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Config from environment
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
PROCESSOR_URL = os.getenv("PROCESSOR_URL", "http://project-processor-1:8000")  # must point to processor service

app = FastAPI(title="Gateway")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DTO
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
    class Config:
        extra = "allow"

@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}

@app.post("/transactions")
async def transactions(txn: TransactionIn):
    # This remains a simplified ISO-like payload to your ISO client
    iso_fields: Dict[Any, Any] = {}
    if txn.cardNumber:
        iso_fields[2] = txn.cardNumber
    if txn.expiry:
        iso_fields[14] = txn.expiry.replace("/", "")
    if txn.cvc:
        iso_fields[123] = txn.cvc
    if txn.amount is not None:
        iso_fields[4] = f"{int(round(txn.amount * 100)):012d}"
    if txn.terminal_id:
        iso_fields[41] = txn.terminal_id
    iso_fields[49] = {"USD":"840","EUR":"978"}.get((txn.currency or "USD").upper(), "840")
    iso_fields[11] = int(uuid.uuid4().int & 0xFFFFFF)

    LOG.info("Sending ISO to processor via TCP client (or configured interface) fields=%s", iso_fields)
    # enforce protocol -> authCode length rules (protocol list enforced)
    PROTO_AUTH_LEN = {
        "101.1": 4, "101.2": 6, "101.3": 6, "101.4": 6, "101.5": 6, "101.6": 6, "101.7": 4, "101.8": 0,
        "201.1": 6, "201.2": 6, "201.3": 6, "201.4": 6, "201.5": 6,
    }
    proto = str(txn.protocol)
    auth = str(txn.authCode or "")
    req_len = PROTO_AUTH_LEN.get(proto)
    if req_len and req_len > 0 and len(auth) != req_len:
        raise HTTPException(status_code=400, detail=f"authCode length for protocol {proto} must be {req_len}")
    # include protocol + auth in ISO fields
    iso_fields[1011] = proto
    if auth:
        iso_fields[38] = auth
    # call tcp client to send framed ISO to processor
    try:
        from app.tcp_client import send_iso_to_processor
    except Exception as e:
        LOG.exception("tcp client import failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error: tcp client unavailable")
    parsed = await send_iso_to_processor("project-processor-1", 9000, "0200", iso_fields)
    de39 = parsed.get("de39") or (parsed.get("raw") or {}).get("DE39") or (parsed.get("raw") or {}).get("39")
    if de39 is None:
        raise HTTPException(status_code=502, detail="Invalid response from processor")
    return {"DE39": de39, "raw": parsed}

# Payout proxy endpoint: forwards to processor /payout
@app.post("/payouts/payout")
async def proxy_payout(request: Request):
    body = await request.json()
    LOG.info("proxy_payout called payload=%s", body)
    # validate minimal required fields for safety
    if "merchant_id" not in body:
        raise HTTPException(status_code=400, detail="merchant_id required")
    # forward to processor
    target = PROCESSOR_URL.rstrip("/") + "/payout"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(target, json=body, headers={"x-forwarded-by": "gateway"})
        except Exception as e:
            LOG.exception("Error contacting processor at %s", target)
            raise HTTPException(status_code=502, detail=f"Error proxying payout to processor: {e}")
    if resp.status_code >= 400:
        LOG.warning("processor returned error %s body=%s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail=f"Error proxying payout to processor: {resp.status_code} {resp.text}")
    try:
        return resp.json()
    except Exception:
        return {"detail": resp.text}

# Lightweight WebSocket endpoint (accepts any Origin in ALLOWED_ORIGINS)
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    # Manual origin check: (CORS middleware does not apply to WebSocket handshakes)
    origin = websocket.headers.get("origin")
    if ALLOWED_ORIGINS and origin and origin not in ALLOWED_ORIGINS:
        await websocket.close(code=403)
        LOG.info("connection rejected (403 Forbidden) origin=%s", origin)
        return
    await websocket.accept()
    LOG.info("WebSocket connected origin=%s client=%s", origin, websocket.client)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            else:
                # echo fallback
                await websocket.send_text("ack:" + data)
    except WebSocketDisconnect:
        LOG.info("WebSocket disconnected client=%s", websocket.client)
    except Exception as e:
        LOG.exception("WebSocket error: %s", e)
        try:
            await websocket.close()
        except Exception:
            pass
