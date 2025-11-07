# app/card_utils.py
"""
Card utilities: brand detection, Luhn check, BIN ranges, tokenization & issuer connector interface.

This module intentionally does NOT implement issuer secret logic — those must be plugged
via secure connectors/HSM. The module provides deterministic utilities and interfaces
so Gateway/Processor can implement brand-specific logic (Visa/Mastercard/RuPay etc.)
without touching API layers.
"""

from typing import Optional, Dict, Any, Tuple
import re
import hashlib
import abc

# Minimal BIN ranges for brand detection (extend this with full BIN data)
BIN_RANGES = {
    "visa": [("4", "4")],  # any PAN starting with 4
    "mastercard": [("51", "55"), ("2221", "2720")],
    "rupay": [("60", "60"), ("6521", "6521")],  # simplified
    "amex": [("34","34"), ("37","37")]
}

def detect_brand(pan: str) -> Optional[str]:
    pan = pan.strip()
    if not pan.isdigit():
        return None
    for brand, ranges in BIN_RANGES.items():
        for start, end in ranges:
            l = len(start)
            prefix = pan[:l]
            if prefix.isdigit():
                if int(start) <= int(prefix) <= int(end):
                    return brand
    return None

def luhn_check(pan: str) -> bool:
    pan = re.sub(r"\D", "", pan)
    if not pan:
        return False
    total = 0
    reverse_digits = pan[::-1]
    for i, ch in enumerate(reverse_digits):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0

def mask_pan(pan: str, keep: int = 4) -> str:
    pan = re.sub(r"\D", "", pan)
    if len(pan) <= keep:
        return pan
    return "*" * (len(pan) - keep) + pan[-keep:]

def token_for_pan(pan: str, salt: str) -> str:
    """
    Deterministic tokenization for reference. Production: replace with HSM or vault-backed token service.
    """
    s = f"{pan}|{salt}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

# Issuer connector interface
class IssuerConnector(abc.ABC):
    """
    Implement this interface to connect to an issuer (or issuer simulator).
    An implementation handles per-issuer auth, field mappings, and secrets/HSM integration.
    """

    @abc.abstractmethod
    async def authorize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authorize a transaction.
        payload contains canonical fields:
        {
            "pan": "...",
            "expiry": "MM/YY",
            "cvc": "...",
            "amount": "12.34",
            "currency": "INR",
            "protocol": "POS Terminal -101.1 (4-digit approval)",
            "authCode": "...",
            "correlation_id": "..."
        }
        Returns:
            {"approved": bool, "de39": "00"/"05"/..., "de38": "AUTHCODE", "issuer_reference": "..."}
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def reconcile(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reconciliation hook; returns status and any settlement refs.
        """
        raise NotImplementedError

# Simple in-memory connector for testing
class MockIssuerConnector(IssuerConnector):
    def __init__(self, name: str = "mock"):
        self.name = name

    async def authorize(self, payload):
        # very naive rule: if authCode ends with '0' -> decline
        auth = payload.get("authCode", "")
        if auth.endswith("0"):
            return {"approved": False, "de39": "05", "de38": None, "issuer_reference": None}
        return {"approved": True, "de39": "00", "de38": auth[-6:], "issuer_reference": "MOCK-"+payload.get("correlation_id","")}

    async def reconcile(self, payload):
        return {"status":"SETTLED","ref":"MOCK-SETTLE-"+payload.get("correlation_id","")}
