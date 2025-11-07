from pydantic import BaseModel
from typing import Optional

class AuthRequest(BaseModel):
    pan: Optional[str] = None
    expiry: Optional[str] = None
    cvc: Optional[str] = None
    amount: Optional[str] = None
    currency: Optional[str] = None
    protocol: Optional[str] = None
    authCode: Optional[str] = None
    correlation_id: Optional[str] = None
    txn_id: Optional[str] = None
    terminal_id: Optional[str] = None
    merchant_id: Optional[str] = None
