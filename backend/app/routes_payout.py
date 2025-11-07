# backend/app/routes_payout.py
from fastapi import APIRouter
from pydantic import BaseModel
import uuid
import logging

logger = logging.getLogger("backend.routes_payout")

router = APIRouter(prefix="/admin", tags=["admin"])

class PayoutRequest(BaseModel):
    txn_id: str
    correlation_id: str | None = None
    creditor_name: str
    amount: float
    currency: str = "USD"
    pain_xml: str | None = None

@router.post("/payout")
async def create_payout(req: PayoutRequest):
    """
    Minimal admin endpoint to accept a payout request.
    In production this should insert into payouts table/queue.
    """
    gateway_txn_id = f"ISS-{uuid.uuid4()}"
    logger.info("Admin payout requested txn=%s amount=%s", req.txn_id, req.amount)
    return {
        "approved": True,
        "de39": "00",
        "gateway_txn_id": gateway_txn_id,
        "txn_id": req.txn_id,
        "correlation_id": req.correlation_id,
        "raw": {"ok": True, "note": "payout route hit; DB enqueue not yet implemented"}
    }
