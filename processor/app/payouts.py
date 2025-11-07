# processor/app/payouts.py
from fastapi import APIRouter
from pydantic import BaseModel
import os, logging

LOG = logging.getLogger("processor.payouts")

router = APIRouter()

class PayoutRequest(BaseModel):
    merchant_id: str
    cardNumber: str
    expiry: str
    cvc: str
    amount: str
    currency: str
    protocol: str = "POS"
    authCode: str = ""
    payoutMethod: str = ""
    payoutDetails: dict = None

@router.post("/payout")
async def payout(req: PayoutRequest):
    LOG.info("processor.payouts: received payout request: %s", req.dict())
    # MOCK: approve everything for now. Replace with production logic before VPS.
    resp = {
        "approved": True,
        "de39": "00",
        "txn_id": f"proc-{os.urandom(3).hex()}",
        "raw": {"approved": True, "de39":"00"}
    }
    return resp
