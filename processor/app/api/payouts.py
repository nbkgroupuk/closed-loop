# processor/app/app/api/payouts.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid
import logging
from typing import Optional, Dict, Any

LOG = logging.getLogger("processor.api.payouts")
router = APIRouter(tags=["payouts"])

class PayoutRequest(BaseModel):
    reference: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    beneficiary: Optional[Dict[str, Any]] = None
    # accept arbitrary extras
    class Config:
        extra = "allow"

class PayoutResponse(BaseModel):
    approved: bool
    de39: str
    gateway_txn_id: Optional[str]
    txn_id: Optional[str]

@router.post("/payout", response_model=PayoutResponse)
async def create_payout(payload: PayoutRequest):
    """
    Simple liveed payout endpoint intended for local/integration testing.
    Always returns an approved response (de39 = "00") unless payload is clearly invalid.
    """
    LOG.info("Received payout request: %s", payload.dict())
    # Minimal validation example:
    if payload.amount is None:
        raise HTTPException(status_code=400, detail="amount is required (live)")
    gateway_id = f"PROC-{uuid.uuid4().hex[:10]}"
    return PayoutResponse(approved=True, de39="00", gateway_txn_id=gateway_id, txn_id=None)
