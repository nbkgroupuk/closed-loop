# /app/server.py - canonical gateway FastAPI app (uvicorn server:app)
import os, uuid, logging
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.tcp_client import send_iso_to_processor  # keep existing tcp_client interface

LOG = logging.getLogger("gateway.server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Gateway")
from fastapi.middleware.cors
import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],

 )

PROCESSOR_HOST = os.getenv("PROCESSOR_HOST", "processor")
PROCESSOR_PORT = int(os.getenv("PROCESSOR_PORT", "9000"))

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
    # Build simple ISO-style dict (numeric keys) — match tcp_client contract
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

    LOG.info("Sending ISO to processor host=%s port=%s fields=%s", PROCESSOR_HOST, PROCESSOR_PORT, iso_fields)
    try:
        proc_resp = await send_iso_to_processor(PROCESSOR_HOST, PROCESSOR_PORT, "0200", iso_fields)
    except Exception as e:
        LOG.exception("Gateway -> Processor error")
        raise HTTPException(status_code=502, detail=f"Gateway error talking to processor: {e}")

    raw = proc_resp.get("raw") if isinstance(proc_resp, dict) and proc_resp.get("raw") else proc_resp
    approved = raw.get("approved") if isinstance(raw, dict) else bool(raw)
    de39 = raw.get("de39") if isinstance(raw, dict) else None
    txn_id = raw.get("txn_id") or raw.get("gateway_txn_id") or str(uuid.uuid4())

    return {"approved": bool(approved), "de39": de39 or ("00" if approved else "96"), "de38": None, "txn_id": txn_id}
