# backend_app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import os

app = FastAPI(title="Backend (orchestrator)")

# Configure gateway url (container/host mapping)
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://gateway:8100")  # container name 'gateway' by default
# If you run on host and gateway is on localhost:8100:
# GATEWAY_URL = "http://localhost:8100"

class ISO20022Payout(BaseModel):
    creditor_name: str
    amount: float
    currency: str = "USD"
    pain_xml: str  # the ISO20022 pain.001 XML document as string
    correlation_id: str | None = None

@app.post("/payout/iso20022")
def payout_iso20022(req: ISO20022Payout):
    payload = {
        "type": "iso20022",
        "creditor_name": req.creditor_name,
        "amount": req.amount,
        "currency": req.currency,
        "pain_xml": req.pain_xml,
        "correlation_id": req.correlation_id,
    }
    try:
        # forward to gateway
        r = requests.post(f"{GATEWAY_URL}/payout", json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gateway comms failed: {e}")

    return r.json()

@app.get("/health")
def health():
    return {"status": "ok"}
