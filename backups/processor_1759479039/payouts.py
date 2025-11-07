# processor/app/app/api/payouts.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid
import logging

from app.storage import db

LOG = logging.getLogger("processor.api.payouts")

router = APIRouter(prefix="/payouts", tags=["payouts"])

class PayoutRequest(BaseModel):
    merchant_id: str
    amount: float
    currency: str
    crypto_wallet: dict | None = None
    payout_method: str | None = None
    reference: str | None = None

class PayoutResponse(BaseModel):
    approved: bool
    de39: str | None = None
    txn_id: str | None = None
    gateway_txn_id: str | None = None
    reference: str | None = None

@router.post("/payout", response_model=PayoutResponse)
async def payout(req: PayoutRequest):
    """
    Accepts a payout request and returns a simple simulated processor response.
    Stores a record in the in-memory DB and returns approved=true for demo.
    """
    try:
        rec_id = str(uuid.uuid4())
        record = {
            "id": rec_id,
            "merchant_id": req.merchant_id,
            "amount": req.amount,
            "currency": req.currency,
            "wallet": req.crypto_wallet,
            "reference": req.reference,
        }
        db.save_payout(record)
        # simple logic: any positive amount approved
        approved = True if req.amount and req.amount > 0 else False
        gateway_txn_id = f"PROC-{uuid.uuid4().hex[:12]}"
        resp = {
            "approved": approved,
            "de39": "00" if approved else "96",
            "txn_id": rec_id,
            "gateway_txn_id": gateway_txn_id,
            "reference": req.reference,
        }
        LOG.info("Payout processed: rec=%s approved=%s ref=%s", rec_id, approved, req.reference)
        return resp
    except Exception as e:
        LOG.exception("Error processing payout: %s", e)
        raise HTTPException(status_code=500, detail="processor error")

# register router on import (the server.py imports this module)
