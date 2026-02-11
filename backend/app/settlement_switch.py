# backend/app/settlement_switch.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.settlement_service import create_auth_and_settlement
from app.storage.db import AsyncSessionLocal
from app.storage.models import Outbox
from app.models_settlement import AuthTransaction, SettlementItem

router = APIRouter(prefix="/api/settlement", tags=["settlement"])


# ------------------------------------------------------------------
# AUTH + CAPTURE
# ------------------------------------------------------------------

class AuthCaptureRequest(BaseModel):
    auth_tx_id: Optional[str] = None
    stan: str
    rrn: str
    mti_auth: str
    pan_hash: str
    bin: str
    last4: str
    merchant_id: str
    terminal_id: str
    scheme: str
    currency: str
    amount_auth: int
    protocol: Optional[str] = None
    auth_code: Optional[str] = None


class AuthCaptureResponse(BaseModel):
    status: str
    auth_tx_id: str
    settlement_item_id: str


@router.post("/auth-capture", response_model=AuthCaptureResponse)
async def auth_capture(payload: AuthCaptureRequest):
    try:
        auth_id, settlement_id = await create_auth_and_settlement(payload)

        return AuthCaptureResponse(
            status="ok",
            auth_tx_id=auth_id,
            settlement_item_id=settlement_id,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# CLEAR SETTLEMENT → EMIT CRYPTO PAYOUT
# ------------------------------------------------------------------

class SettlementClearRequest(BaseModel):
    settlement_item_id: str
    new_status: str  # e.g. CLEARED


class SettlementClearResponse(BaseModel):
    status: str
    settlement_item_id: str
    clearing_status: str


@router.post("/clear", response_model=SettlementClearResponse)
async def clear_settlement(payload: SettlementClearRequest):
    async with AsyncSessionLocal() as session:
        try:
            # 1) Load settlement item
            result = await session.execute(
                select(SettlementItem).where(
                    SettlementItem.id == payload.settlement_item_id
                )
            )
            item = result.scalars().first()
            if not item:
                raise HTTPException(status_code=404, detail="settlement_item not found")

            # 2) Update clearing status
            item.clearing_status = payload.new_status
            session.add(item)
            await session.commit()
            await session.refresh(item)

            # 3) Load auth transaction (optional context)
            result_auth = await session.execute(
                select(AuthTransaction).where(
                    AuthTransaction.id == item.auth_tx_id
                )
            )
            auth_tx = result_auth.scalars().first()

            # 4) Build payout payload (MATCHES crypto_payout_worker)
            payload_outbox = {
                "provider": "card",
                "event": "settlement.cleared",
                "settlement_item_id": item.id,
                "amount": item.amount_clearing,
                "currency": item.currency,
                "merchant_id": item.merchant_id,
            }

            if auth_tx:
                payload_outbox.update({
                    "stan": auth_tx.stan,
                    "rrn": auth_tx.rrn,
                    "scheme": auth_tx.scheme,
                    "protocol": auth_tx.protocol,
                    "auth_tx_id": auth_tx.id,
                })

            # 5) Emit crypto payout job (✅ FIXED TARGET)
            session.add(
                Outbox(
                    target="crypto_payout",   # 🔥 THIS WAS THE BUG
                    status="PENDING",
                    payload=payload_outbox,
                )
            )

            await session.commit()

            return SettlementClearResponse(
                status="ok",
                settlement_item_id=item.id,
                clearing_status=item.clearing_status,
            )

        except SQLAlchemyError as e:
            await session.rollback()
            raise HTTPException(status_code=500, detail=f"DB error: {e}")

        except HTTPException:
            raise

        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=500, detail=str(e))



        
