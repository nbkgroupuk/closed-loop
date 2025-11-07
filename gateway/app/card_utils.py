# gateway/app/card_utils.py

import logging
import random
from typing import Dict, Any

logger = logging.getLogger("card-utils")


class IssuerConnector:
    """
    Base Issuer Connector that simulates authorization requests to issuer banks.
    In production this would implement ISO8583/101.x/201.x protocols to bank APIs.
    """

    def __init__(self, issuer_name: str):
        self.issuer_name = issuer_name

    def authorize(self, card_number: str, expiry: str, cvc: str,
                  amount: float, currency: str, protocol: str, auth_code: str) -> Dict[str, Any]:
        """
        Simulates authorization against issuer.
        Returns ISO8583-like response dict.
        """
        logger.info(f"[{self.issuer_name}] Authorizing card {card_number[-4:]} for {amount} {currency}")

        # Simple approval simulation: 80% success rate
        approved = random.random() < 0.8
        response_code = "00" if approved else "05"

        return {
            "issuer": self.issuer_name,
            "approved": approved,
            "response_code": response_code,
            "auth_code": auth_code,
            "amount": amount,
            "currency": currency,
            "protocol": protocol,
        }

    def payout(self, method: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulates payout instruction to issuer (bank transfer or crypto).
        """
        logger.info(f"[{self.issuer_name}] Payout via {method}: {details}")
        return {"issuer": self.issuer_name, "status": "submitted", "method": method, "details": details}
