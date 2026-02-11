# backend/app/reversal_handler.py

from app.acquirer_client_bank import BankAcquirerClient

bank_client = BankAcquirerClient()

async def handle_iso_reversal(iso_payload: dict, settlement: dict):
    """
    Handles ISO8583 reversal (0400 / 0420)
    """

    iso_mti = iso_payload.get("mti")
    payout_method = settlement.get("payout_method")  # BANK / CRYPTO

    # Only reversal MTIs
    if iso_mti not in ("0400", "0420"):
        return {"ignored": True}

    # Idempotency guard
    rrn = settlement.get("rrn")
    stan = settlement.get("stan")
    reversal_key = f"{rrn}:{stan}"

    # BANK payout → Stripe refund
    if payout_method == "BANK":
        stripe.Refund.create(
            charge=charge_id,
            amount=amount_minor,
            idempotency_key=f"{rrn}:{stan}",
            metadata={...}
        )

        refund_payload = {
            "charge_id": settlement.get("charge_id"),
            "amount_minor": settlement.get("amount_minor"),  # full refund
            "stan": stan,
            "rrn": rrn,
            "settlement_item_id": settlement.get("id"),
            "reason": "iso8583_reversal",
            "idempotency_key": reversal_key
        }

        result = await bank_client.refund(refund_payload)
        return {"stripe_refund": result}

    # CRYPTO payout → compensating payout
    if payout_method == "CRYPTO":
        # call existing crypto compensation logic
        return {"crypto_compensation": True}

    return {"error": "Unknown payout method"}
