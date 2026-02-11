# gateway/gateway_app.py
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os, logging, uuid
from datetime import datetime
import stripe

log = logging.getLogger("gateway")

# --------------------------------------------------
# Config
# --------------------------------------------------
STRIPE_ENABLED = os.getenv("STRIPE_ENABLED", "true").lower() == "true"
FORCE_APPROVE_MODE = os.getenv("FORCE_APPROVE_MODE", "false").lower() == "true"

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

app = FastAPI(title="Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# Transactions
# --------------------------------------------------
@app.post("/transactions")
async def transactions(
    request: Request,
    x_test_mode: str | None = Header(default=None),
):
    body = await request.json()

    amount = body.get("amount")
    currency = body.get("currency", "GBP").lower()
    protocol = body.get("protocol")
    auth_code = body.get("auth_code")
    card = body.get("card", {})

    # --------------------------------------------------
    # 1️⃣ FORCE APPROVE (CERTIFICATION ONLY)
    # --------------------------------------------------
    if (
        FORCE_APPROVE_MODE
        and x_test_mode == "FORCE_APPROVE"
        and card.get("type") == "closed_loop"
    ):
        log.warning("FORCE_APPROVE test mode invoked via gateway")

        return {
            "status": "APPROVED",
            "code": "00",
            "protocol": protocol,
            "auth_code": auth_code,
            "amount": amount,
            "currency": currency.upper(),
            "reference": body.get("reference"),
            "approval_type": "FORCE_TEST",
        }

    # --------------------------------------------------
    # 2️⃣ CLOSED LOOP FLOW (NO PAN / NO STRIPE)
    # --------------------------------------------------
    if card.get("type") == "closed_loop":
        if not protocol or not auth_code or not amount:
            return {
                "status": "DECLINED",
                "reason": "missing protocol, auth_code, or amount",
            }

        # Normal path → forward to processor / issuer later
        return {
            "status": "PENDING",
            "message": "Closed-loop transaction accepted",
            "protocol": protocol,
            "reference": body.get("reference"),
        }

    # --------------------------------------------------
    # 3️⃣ OPEN LOOP / STRIPE FLOW (PAN REQUIRED)
    # --------------------------------------------------
    if STRIPE_ENABLED:
        pan = body.get("pan")
        expiry = body.get("expiry")

        if not pan or not expiry or not amount:
            return {
                "status": "DECLINED",
                "reason": "missing card or amount",
            }

        try:
            exp_month = int(expiry.split("/")[0])
            exp_year = int("20" + expiry.split("/")[1])

            pm = stripe.PaymentMethod.create(
                type="card",
                card={
                    "number": pan,
                    "exp_month": exp_month,
                    "exp_year": exp_year,
                },
            )

            intent = stripe.PaymentIntent.create(
                amount=int(float(amount) * 100),
                currency=currency,
                payment_method=pm.id,
                confirm=True,
                payment_method_options={
                    "card": {"request_three_d_secure": "never"}
                },
                metadata={
                    "protocol": protocol,
                    "mode": "OPEN_LOOP",
                },
            )

            charge = intent.charges.data[0]

            return {
                "status": "APPROVED",
                "amount": amount,
                "currency": currency.upper(),
                "txn_id": intent.id,
                "arn": charge.id,
                "last4": charge.payment_method_details.card.last4,
            }

        except Exception as e:
            return {
                "status": "DECLINED",
                "reason": str(e),
            }

    # --------------------------------------------------
    # 4️⃣ FALLBACK
    # --------------------------------------------------
    return {
        "status": "DECLINED",
        "reason": "unsupported transaction type",
    }
