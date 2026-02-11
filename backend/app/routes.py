# backend/app/routes.py

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, validator
from typing import Optional
from sqlalchemy import select
import uuid, logging, random

from app.config import settings
from app.idempotency import canonical_request_hash
from app.storage.db import AsyncSessionLocal
from app.storage.models import (
    Transaction,
    TxStatus,
    Payout,
    PayoutType,
    PayoutStatus,
)
from app.ws import ConnectionManager
# from app.processor_client import send_to_processor
# from app.iso_mapper import map_protocol_to_iso
from app.gateway_client import gateway_client

logger = logging.getLogger(__name__)
router = APIRouter()
ws_manager = ConnectionManager()

# -------------------------------------------------
# Protocol → auth code length
# -------------------------------------------------

PROTOCOL_AUTH_LENGTH = {
    "POS Terminal -101.1 (4-digit approval)": 4,
    "POS Terminal -101.4 (6-digit approval)": 6,
    "POS Terminal -101.6 (Pre-authorization)": 6,
    "POS Terminal -101.7 (4-digit approval)": 4,
    "POS Terminal -101.8 (PIN-LESS transaction)": 4,
    "POS Terminal -201.1 (6-digit approval)": 6,
    "POS Terminal -201.3 (6-digit approval)": 6,
    "POS Terminal -201.5 (6-digit approval)": 6,
}

# -------------------------------------------------
# Request schema
# -------------------------------------------------

class TransactionIn(BaseModel):
    merchant_id: str
    cardNumber: str
    expiry: str
    cvc: str
    amount: float
    currency: str
    protocol: str
    authCode: str
    payoutMethod: Optional[str] = None
    payoutDetails: Optional[dict] = None

    @validator("cardNumber")
    def card_valid(cls, v):
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) not in (15, 16):  # Visa / MC / Amex
            raise ValueError("Invalid PAN length")
        return digits

    @validator("expiry")
    def expiry_valid(cls, v):
        import re
        if not re.match(r"^(0[1-9]|1[0-2])\/\d{2}$", v):
            raise ValueError("expiry must be MM/YY")
        return v

    @validator("cvc")
    def cvc_valid(cls, v):
        if not v.isdigit() or len(v) not in (3, 4):
            raise ValueError("Invalid CVC")
        return v

    @validator("authCode")
    def auth_len(cls, v, values):
        proto = values.get("protocol")
        required = PROTOCOL_AUTH_LENGTH.get(proto)
        if required and (not v.isdigit() or len(v) != required):
            raise ValueError(f"authCode must be {required} digits")
        return v

# -------------------------------------------------
# Health
# -------------------------------------------------

@router.get("/health")
async def health():
    return {"status": "ok", "service": settings.APP_NAME}

# -------------------------------------------------
# Main transaction endpoint
# -------------------------------------------------

@router.post("/transactions")
async def create_transaction(
    payload: TransactionIn,
    request: Request,
    idempotency_key: Optional[str] = Header(None),
):
    correlation_id = str(uuid.uuid4())
    raw = payload.dict()
    key = idempotency_key or canonical_request_hash(raw)

    async with AsyncSessionLocal() as session:

        existing = (
            await session.execute(
                select(Transaction).where(Transaction.idempotency_key == key)
            )
        ).scalars().first()

        if existing:
            return {
                "approved": existing.status == TxStatus.APPROVED,
                "de39": existing.de39,
                "de38": existing.de38,
                "txn_id": str(existing.id),
            }

        txn = Transaction(
            merchant_id=payload.merchant_id,
            amount=payload.amount,
            currency=payload.currency,
            pan_mask=f"****{payload.cardNumber[-4:]}",
            expiry=payload.expiry,
            protocol=payload.protocol,
            correlation_id=correlation_id,
            idempotency_key=key,
            status=TxStatus.PENDING,
        )

        session.add(txn)
        await session.commit()
        await session.refresh(txn)

        iso_payload = map_protocol_to_iso(
            payload.protocol,
            {
                "pan": payload.cardNumber,
                "expiry": payload.expiry,
                "cvc": payload.cvc,
                "amount": payload.amount,
                "currency": payload.currency,
                "authCode": payload.authCode,
                "merchant_id": payload.merchant_id,
                "terminal_id": "RUTLAND TERMINAL",
                "stan": str(random.randint(100000, 999999)),
            },
        )

        try:
            resp = send_to_processor(iso_payload)
        except Exception as e:
            txn.status = TxStatus.FAILED
            txn.de39 = "96"
            await session.commit()
            raise HTTPException(status_code=502, detail=f"Processor error: {e}")

        txn.de39 = resp.get("de39", "96")
        txn.de38 = resp.get("de38")
        txn.stan = resp.get("stan")
        txn.rrn = resp.get("rrn")

        approved = txn.de39 == "00"
        txn.status = TxStatus.APPROVED if approved else TxStatus.REJECTED

        if approved:
            payout = Payout(
                transaction_id=txn.id,
                merchant_id=txn.merchant_id,
                type=PayoutType.BANK,
                status=PayoutStatus.PENDING,
                payload={"auto": True},
            )
            session.add(payout)

        await session.commit()

        return {
            "approved": approved,
            "de39": txn.de39,
            "de38": txn.de38,
            "txn_id": str(txn.id),
            "stan": txn.stan,
            "rrn": txn.rrn,
        }

# -------------------------------------------------
# TEST AUTHORIZE (DEV ONLY)
# -------------------------------------------------

@router.post("/test/authorize")
async def test_authorize():
    payload = {
        "pan": "4111111111111111",
        "expiry": "12/30",
        "cvc": "123",
        "amount": "10.00",
        "currency": "840",
        "protocol": "POS Terminal -101.1 (4-digit approval)",
        "authCode": "1234",
        "merchant_id": "MERCHID000001",
        "terminal_id": "RUTLAND TERMINAL",
        "stan": str(random.randint(100000, 999999)),
    }

    resp = await gateway_client.auth_transaction(payload)

    return {
        "request": payload,
        "gateway_response": resp,
    }



