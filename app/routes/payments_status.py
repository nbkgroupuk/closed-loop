# backend/app/routes/payments_status.py
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.storage.db import AsyncSessionLocal
from app.storage.models import Outbox

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/{payment_intent_id}/status")
async def payment_status(payment_intent_id: str):
    """
    Returns settlement status for a Stripe payment_intent_id
    """

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Outbox)
            .where(Outbox.target == "settlement")
            .where(Outbox.payload["payment_intent_id"].astext == payment_intent_id)
            .order_by(Outbox.created_at.desc())
            .limit(1)
        )

        row = result.scalars().first()

        if not row:
            raise HTTPException(status_code=404, detail="Payment not found")

        return {
            "payment_intent_id": payment_intent_id,
            "status": row.status,   # PENDING | PROCESSED
        }
