# backend/app/webhooks_stripe.py
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.storage.db import get_session
from app.storage.models import Outbox
import os
import stripe
import logging

logger = logging.getLogger("stripe.webhook")

router = APIRouter()

@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        logger.error("Missing Stripe-Signature header")
        raise HTTPException(status_code=400, detail="Missing signature")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=os.environ["STRIPE_WEBHOOK_SECRET"],
        )
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail="Webhook error")

    logger.info(f"Stripe event received: {event['type']}")

    if event["type"] == "payment_intent.succeeded":
        obj = Outbox(target="stripe", status="received")
        db.add(obj)
        await db.commit()
        logger.info("Outbox row inserted")

    return {"status": "ok"}
