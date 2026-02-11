# backend/app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.storage.db import get_session
from app.storage.models import Outbox
import uuid

class AcquirerAuthRequest(BaseModel):
    amount: int
    currency: str
    protocol: str
    auth_code: str   # MUST be 4 digits (e.g. 1234)
    terminal_id: str
    card_pan: str | None = None  # masked PAN optional

class AcquirerAuthResponse(BaseModel):
    status: str
    txn_id: str

@app.post("/acquirer/auth", response_model=AcquirerAuthResponse)
async def acquirer_auth(req: AcquirerAuthRequest):
    # Basic validation (acquirer-style)
    if len(req.auth_code) != 4 or not req.auth_code.isdigit():
        raise HTTPException(status_code=400, detail="Invalid auth_code")

    txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

    payload = {
        "id": txn_id,
        "amount": req.amount,
        "currency": req.currency,
        "protocol": req.protocol,
        "auth_code": req.auth_code,
        "terminal_id": req.terminal_id,
        "card_pan": req.card_pan,
        "source": "ACQUIRER_AUTH"
    }

    async for db in get_session():
        db.add(Outbox(
            target="acquirer",
            status="received",
            payload=payload
        ))
        await db.commit()

    return {
        "status": "APPROVED",
        "txn_id": txn_id
    }

