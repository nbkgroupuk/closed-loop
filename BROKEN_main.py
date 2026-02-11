# backend/app/main.py
from app.storage.db import AsyncSessionLocal
from app.storage.models import Outbox

from sqlalchemy.ext.asyncio import AsyncSession


from sqlalchemy import insert
from app.storage.db import AsyncSessionLocal
from app.storage.models import Outbox

import logging
import os
import time

import stripe
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import settlement_switch
from app.routes import router as api_router
from app.auth.routes import router as auth_router
from app.iso20022_api import router as iso20022_router
from app.config import settings
from app.telemetry.logging import configure_logging

from sqlalchemy import select

from sqlalchemy.exc import SQLAlchemyError



# ✅ IMPORT METRICS (DO NOT DEFINE THEM HERE)
from app.telemetry.metrics import (
    metrics_router,
    stripe_requests_total,
    stripe_amount_total_minor,
)

# ---------------------------------------------------
# Logging
# ---------------------------------------------------
configure_logging(getattr(settings, "LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# ---------------------------------------------------
# Stripe init
# ---------------------------------------------------
STRIPE_ENABLED = os.getenv("STRIPE_ENABLED", "false").lower() == "true"
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

if STRIPE_ENABLED:
    if not STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_ENABLED=true but STRIPE_SECRET_KEY missing")
    stripe.api_key = STRIPE_SECRET_KEY
    logger.info("Stripe ENABLED")
else:
    logger.info("Stripe DISABLED")

# ---------------------------------------------------
# FastAPI app
# ---------------------------------------------------
app = FastAPI(
    title=getattr(settings, "APP_NAME", "backend"),
    version="1.0.0",
)

# ---------------------------------------------------
# Middleware
# ---------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------
# Routers
# ---------------------------------------------------
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(iso20022_router)
app.include_router(settlement_switch.router)

# ✅ PROMETHEUS (ONLY PLACE /metrics EXISTS)
app.include_router(metrics_router)

# ---------------------------------------------------
# Health endpoints (NON-Prometheus)
# ---------------------------------------------------
START_TIME = time.time()
REQUEST_COUNT = 0

@app.middleware("http")
async def count_requests(request: Request, call_next):
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    return await call_next(request)

@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "service": "BlackRock Backend"}

@app.get("/health/metrics", include_in_schema=False)
def health_metrics():
    return {
        "uptime_seconds": int(time.time() - START_TIME),
        "requests_total": REQUEST_COUNT,
    }

# ---------------------------------------------------
# Stripe authorize
# ---------------------------------------------------
class StripeAuthorizeRequest(BaseModel):
    amount: float
    currency: str = "usd"
    merchant_id: str

@app.post("/stripe/authorize")
async def stripe_authorize(req: StripeAuthorizeRequest):

    if not STRIPE_ENABLED:
        stripe_requests_total.labels("authorize", "disabled").inc()
        raise HTTPException(400, "Stripe disabled")

    try:
        amount_minor = int(req.amount * 100)

        intent = stripe.PaymentIntent.create(
            amount=amount_minor,
            currency=req.currency.lower(),
            payment_method_types=["card"],
            capture_method="automatic",  # IMPORTANT
            confirm=True,                # IMPORTANT
            metadata={
                "merchant_id": req.merchant_id,
                "source": "frontend",
            },
        )

        stripe_requests_total.labels("authorize", "success").inc()
        stripe_amount_total_minor.labels(req.currency.lower()).inc(amount_minor)

    except Exception:
        stripe_requests_total.labels("authorize", "error").inc()
        raise

    return {
        "approved": True,
        "code": "00",
        "de39": "00",
        "stripe": True,
        "intent_id": intent.id,
        "client_secret": intent.client_secret,
    }

# ---------------------------------------------------
# Stripe webhook
# ---------------------------------------------------
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        raise HTTPException(400, "Invalid webhook")

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info("Stripe webhook received: %s", event_type)

    # ✅ ONLY HANDLE SUCCESS
    if event_type == "payment_intent.succeeded":
        async with AsyncSessionLocal() as session:
            outbox = Outbox(
                target="crypto_payout",
                status="PENDING",
                payload={
                    "provider": "stripe",
                    "event": event_type,
                    "payment_intent_id": data["id"],
                    "amount": data["amount_received"],
                    "currency": data["currency"],
                    "merchant_id": data.get("metadata", {}).get("merchant_id"),
                },
            )
            session.add(outbox)
            await session.commit()

            logger.info(
                "Crypto payout enqueued for payment_intent=%s",
                data["id"]
            )

    return {"received": True}


# ➕ ALSO enqueue crypto payout (parallel path)

# --- settlement outbox (existing) ---
settlement_outbox = Outbox(
    target="settlement",
    status="PENDING",
    payload={
        "provider": "stripe",
        "event": event_type,
        "payment_intent_id": data["id"],
        "amount": data["amount_received"],
        "currency": data["currency"],
        "merchant_id": data.get("metadata", {}).get("merchant_id"),
    },
)
session.add(settlement_outbox)

# --- crypto payout outbox (NEW) ---
crypto_outbox = Outbox(
    target="crypto_payout",
    status="PENDING",
    payload={
        "provider": "stripe",
        "event": event_type,
        "payment_intent_id": data["id"],
        "amount": data["amount_received"],
        "currency": data["currency"],
        "merchant_id": data.get("metadata", {}).get("merchant_id"),
    },
)
session.add(crypto_outbox)

await session.commit()











