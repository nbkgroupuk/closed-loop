# backend/app/acquirer_client_bank.py
"""
Bank Acquirer Integration Client
--------------------------------
This client will talk to the BANK's server for:

    1. Authorization (financial or pre-auth)
    2. Reversal (void)
    3. Settlement Advice (clearing confirmation)

NOTE:
The bank will provide:
    - Base URL (HTTP or HTTPS)
    - Authentication method (API key, HMAC, MTLS, token)
    - Required request fields
    - Response fields
    - ISO8583/JSON/XML message definitions

This module is designed so you only fill in their specifications.
"""

# backend/app/acquirer_client_bank.py

import os
import stripe
from typing import Dict, Any

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

BANK_ACQUIRER = os.getenv("BANK_ACQUIRER", "stripe")
BANK_ACQUIRER_ENABLED = os.getenv("BANK_ACQUIRER_ENABLED", "false").lower() == "true"


class BankAcquirerClient:

    async def settlement_advice(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes BANK settlement.
        Called ONLY when payout_method == BANK
        """

        if not BANK_ACQUIRER_ENABLED:
            raise RuntimeError("Bank acquirer disabled")

        if BANK_ACQUIRER != "stripe":
            raise RuntimeError(f"Unsupported bank acquirer: {BANK_ACQUIRER}")

        amount_minor = int(payload["amount_minor"])
        currency = payload.get("currency", "usd").lower()
        description = f"Card settlement STAN={payload.get('stan')} RRN={payload.get('rrn')}"

        intent = stripe.PaymentIntent.create(
            amount=amount_minor,
            currency=currency,
            capture_method="automatic",
            confirm=True,
            description=description,
            metadata={
                "stan": payload.get("stan"),
                "rrn": payload.get("rrn"),
                "terminal_id": payload.get("terminal_id"),
                "protocol": payload.get("protocol"),
                "settlement_id": payload.get("settlement_item_id"),
            }
        )

        charge = intent.charges.data[0]

        return {
            "acquirer": "stripe",
            "status": "CLEARED",
            "payment_intent_id": intent.id,
            "charge_id": charge.id,
            "balance_transaction": charge.balance_transaction,
        }
    
from app.metrics import stripe_settlement_total

stripe_settlement_total.labels(status="success").inc()
# or on exception
stripe_settlement_total.labels(status="failed").inc()

async def refund(self, payload: dict) -> dict:
    """
    Executes BANK refund via Stripe.
    Called only if payout_method == BANK
    """

    import stripe

    charge_id = payload.get("charge_id")
    amount_minor = payload.get("amount_minor")  # optional (partial refund)

    if not charge_id:
        raise RuntimeError("Missing charge_id for refund")

    refund = stripe.Refund.create(
        charge=charge_id,
        amount=amount_minor,  # omit for full refund
        metadata={
            "stan": payload.get("stan"),
            "rrn": payload.get("rrn"),
            "settlement_id": payload.get("settlement_item_id"),
            "reason": payload.get("reason", "customer_request")
        }
    )

    return {
        "acquirer": "stripe",
        "refund_id": refund.id,
        "status": refund.status
    }
