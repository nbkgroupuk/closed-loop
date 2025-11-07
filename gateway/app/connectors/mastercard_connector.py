# gateway/connectors/mastercard_connector.py
"""
MastercardConnector skeleton.

Same responsibilities as VisaConnector but with Mastercard rules (BIN ranges, field mappings).
This skeleton provides points to insert Mastercard-specific field values (e.g. network id).
"""

import logging
from typing import Dict, Any
from app.card_utils import IssuerConnector
import uuid
import asyncio

logger = logging.getLogger(__name__)

class MastercardConnector(IssuerConnector):
    def __init__(self, name: str = "mastercard", endpoint: str = None, hsm_client=None):
        self.name = name
        self.endpoint = endpoint
        self.hsm = hsm_client

    async def authorize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        pan = payload["pan"]
        amount = payload["amount"]
        correlation_id = payload.get("correlation_id") or str(uuid.uuid4())

        iso_msg = {
            "mti": "0200",
            "pan": pan,
            "processing_code": "000000",
            "amount": amount,
            "currency": payload.get("currency", "INR"),
            "network_id": "MC",
            "correlation_id": correlation_id,
            "authCode": payload.get("authCode")
        }

        # optionally call HSM for MAC/PIN
        if self.hsm:
            logger.debug("MastercardConnector: HSM hook available")
            # perform pin block / mac calculation with HSM

        # placeholder for sending/receiving ISO8583 message
        await asyncio.sleep(0.08)

        # Example approval rule: decline if PAN ends with odd digit (dev)
        last_digit = int(pan[-1])
        if last_digit % 2 == 1:
            return {"approved": False, "de39": "05", "de38": None, "gateway_txn_id": f"MC-{uuid.uuid4()}", "raw_iso": {"req": iso_msg}}
        return {"approved": True, "de39": "00", "de38": payload.get("authCode")[-6:] if payload.get("authCode") else None, "gateway_txn_id": f"MC-{uuid.uuid4()}", "raw_iso": {"req": iso_msg}}

    async def reconcile(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"status":"NOT_IMPLEMENTED"}
