# backend/app/routes.py
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field, validator
from typing import Optional
from app.idempotency import canonical_request_hash
from app.storage.db import AsyncSessionLocal
from app.storage.models import Transaction, TxStatus, Outbox, Payout, PayoutType, PayoutStatus, EventLog
from app.gateway_client import gateway_client
from app.ws import ConnectionManager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid, datetime, logging
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()
ws_manager = ConnectionManager()

# Protocol auth mapping copied from frontend index.html.
PROTOCOL_AUTH_LENGTH = {
  "POS Terminal -101.1 (4-digit approval)": 4,
  "POS Terminal -101.4 (6-digit approval)": 6,
  "POS Terminal -101.6 (Pre-authorization)": 6,
  "POS Terminal -101.7 (4-digit approval)": 4,
  "POS Terminal -101.8 (PIN-LESS transaction)": 4,
  "POS Terminal -201.1 (6-digit approval)": 6,
  "POS Terminal -201.3 (6-digit approval)": 6,
  "POS Terminal -201.5 (6-digit approval)": 6
}

class TransactionIn(BaseModel):
    merchant_id: str = Field(..., description="Merchant identifier")
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
        v2 = "".join([c for c in v if c.isdigit()])
        if len(v2) != 16:
            raise ValueError("cardNumber must be 16 digits")
        return v2

    @validator("expiry")
    def expiry_valid(cls, v):
        import re, datetime as _dt
        if not re.match(r"^(0[1-9]|1[0-2])\/\d{2}$", v):
            raise ValueError("expiry must be MM/YY")
        mm, yy = v.split("/")
        exp = _dt.datetime(2000+int(yy), int(mm), 1)
        now = _dt.datetime.utcnow()
        now = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if exp < now:
            raise ValueError("card expiry in past")
        return v

    @validator("cvc")
    def cvc_valid(cls, v):
        if not v.isdigit() or len(v) not in (3,4):
            raise ValueError("cvc invalid")
        return v

    @validator("protocol")
    def protocol_allowed(cls, v):
        if v not in PROTOCOL_AUTH_LENGTH:
            raise ValueError("protocol not allowed")
        return v

    @validator("authCode")
    def auth_code_len(cls, v, values):
        proto = values.get("protocol")
        if proto:
            required = PROTOCOL_AUTH_LENGTH.get(proto)
            if required and (not v.isdigit() or len(v) != required):
                raise ValueError(f"authCode must be {required} digits for {proto}")
        return v

@router.get("/health")
async def health():
    return {"status": "ok", "service": settings.APP_NAME}

@router.post("/transactions")
async def create_transaction(payload: TransactionIn, request: Request, idempotency_key: Optional[str] = Header(None)):
    correlation_id = str(uuid.uuid4())
    # idempotency handling
    raw = payload.dict()
    key = idempotency_key or canonical_request_hash(raw)
    async with AsyncSessionLocal() as session:
        # check existing idempotent
        q = await session.execute(select(Transaction).where(Transaction.idempotency_key == key))
        existing = q.scalars().first()
        if existing:
            return {
                "approved": existing.status == TxStatus.APPROVED,
                "de39": existing.de39,
                "de38": existing.de38,
                "txn_id": str(existing.id)
            }
        # persist transaction PENDING
        txn = Transaction(
            merchant_id=payload.merchant_id,
            amount=payload.amount,
            currency=payload.currency,
            pan_mask=f"****{payload.cardNumber[-4:]}",
            expiry=payload.expiry,
            protocol=payload.protocol,
            correlation_id=correlation_id,
            idempotency_key=key,
            meta={"payoutMethod": payload.payoutMethod}
        )
        session.add(txn)
        await session.commit()
        await session.refresh(txn)
        # Broadcast mti.outgoing
        await ws_manager.broadcast(
            payload.merchant_id,
            "mti.outgoing",
            {"correlation_id": correlation_id, "txn_id": str(txn.id), "masked_pan": txn.pan_mask}
        )
        # send to Gateway for ISO8583 auth
        gw_payload = {
            "txn_id": str(txn.id),
            "pan": payload.cardNumber,
            "expiry": payload.expiry,
            "cvc": payload.cvc,
            "amount": str(payload.amount),
            "currency": payload.currency,
            "protocol": payload.protocol,
            "authCode": payload.authCode,
            "correlation_id": correlation_id
        }
        try:
            gw_resp = await gateway_client.auth_transaction(gw_payload)
        except Exception as e:
            txn.status = TxStatus.FAILED
            txn.de39 = "96"
            session.add(txn)
            await session.commit()
            await ws_manager.broadcast(
                payload.merchant_id,
                "mti.incoming",
                {"correlation_id": correlation_id, "de39": "96", "error": str(e)}
            )
            raise HTTPException(status_code=502, detail="Gateway error: " + str(e))

        # update transaction based on gateway response
        txn.gateway_txn_id = gw_resp.get("gateway_txn_id")
        # Determine de39 robustly
        de39_val = None
        if gw_resp.get("de39") is not None:
            de39_val = gw_resp.get("de39")
        elif gw_resp.get("DE39") is not None:
            de39_val = gw_resp.get("DE39")
        elif gw_resp.get("raw") is not None:
            raw_data = gw_resp.get("raw")
            try:
                raw_str = raw_data.decode('utf-8', errors='ignore') if isinstance(raw_data, (bytes, bytearray)) else str(raw_data)
                import re
                match = re.search(r'DE39[^0-9]*([0-9]+)', raw_str)
                de39_val = match.group(1) if match else None
            except Exception:
                de39_val = None
        if de39_val is None:
            de39_val = "96"
        txn.de39 = de39_val
        txn.de38 = gw_resp.get("de38")
        approved = gw_resp.get("approved")
        if approved is None:
            approved = (de39_val == "00")
        if approved:
            txn.status = TxStatus.APPROVED
            # enqueue payout in outbox
            payout = Payout(
                transaction_id=txn.id,
                merchant_id=txn.merchant_id,
                type=PayoutType.BANK if (payload.payoutMethod or "").lower().startswith("bank") else PayoutType.CRYPTO,
                status=PayoutStatus.PENDING,
                payload={"auto": True, "requested_at": datetime.datetime.utcnow().isoformat()}
            )
            session.add(payout)
            # outbox entry for payout worker (iso20022 or crypto)
            target = "iso20022" if payout.type == PayoutType.BANK else "crypto_send"
            out = Outbox(target=target, payload={"transaction_id": str(txn.id), "payout_id": None})
            session.add(out)
        else:
            txn.status = TxStatus.REJECTED
        session.add(txn)
        # store event log
        ev = EventLog(correlation_id=correlation_id, topic="mti.incoming", payload=gw_resp)
        session.add(ev)
        await session.commit()

        # broadcast incoming MTI
        await ws_manager.broadcast(
            payload.merchant_id,
            "mti.incoming",
            {"correlation_id": correlation_id, "txn_id": str(txn.id), "de39": txn.de39, "de38": txn.de38, "status": txn.status.value}
        )
        return {
            "approved": txn.status == TxStatus.APPROVED,
            "de39": txn.de39,
            "de38": txn.de38,
            "txn_id": str(txn.id)
        }

