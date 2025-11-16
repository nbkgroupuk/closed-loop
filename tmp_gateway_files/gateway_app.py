from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import time, uuid, os


from fastapi import HTTPException

def _ensure_job(job_id):
    """Return _ensure_job(job_id) if present, otherwise raise 400 HTTPException."""
    try:
        j = globals().get('JOBS')
        if not isinstance(j, dict):
            raise HTTPException(400, 'unknown job')
        job = j.get(job_id)
        if not isinstance(job, dict):
            raise HTTPException(400, 'unknown job')
        return job
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, 'unknown job')

app = FastAPI(title="Gateway")
JOBS: Dict[str, Dict[str, Any]] = {}

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "gateway"}

@app.get("/ui-config")
async def ui_config(request: Request):
    api_base = os.environ.get("API_BASE")
    if not api_base:
        scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
        host   = request.headers.get("x-forwarded-host") or request.headers.get("host")
        api_base = f"{scheme}://{host}"
    return {"api_base": api_base, "service": "gateway"}

class TransactionIn(BaseModel):
    merchant_id: Optional[str] = "demo-merchant"
    amount: str
    currency: str = "USDT"
    network: Optional[str] = "ETH"
    to_address: Optional[str] = None
    wallet_address: Optional[str] = None
    auth_code: Optional[str] = None
    protocol: Optional[str] = None
    payout_method: Optional[str] = None

@app.post("/transactions")
async def transactions_create(tx: TransactionIn):
    to_addr = tx.to_address or tx.wallet_address or ""
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {
        "job_id": job_id,
        "request": {
            "merchant_id": tx.merchant_id,
            "amount": tx.amount,
            "currency": tx.currency,
            "network": (tx.network or "ETH"),
            "to_address": to_addr,
        },
        "status": "success",
        "message": None,
        "txhash": (_broadcast_tx(_ensure_job(job_id)["request"]) or None),
        "created_at": int(time.time()),
    }
    return {"ok": True, "status": "approved", "job_id": job_id, "txhash": _ensure_job(job_id)["txhash"]}

class BroadcastPayload(BaseModel):
    txhash: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None

@app.post("/payout")
async def payout_create(payload: TransactionIn):
    return await transactions_create(payload)

@app.get("/payout/{job_id}")
async def payout_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    return job

@app.post("/payout/{job_id}/broadcast")
async def payout_broadcast(job_id: str, payload: BroadcastPayload):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    if payload.txhash:
        job["txhash"] = payload.txhash
    if payload.status:
        job["status"] = payload.status
    job["message"] = payload.message
    return job


def _broadcast_tx(details):
    import os, requests
    # default internal broadcaster (change via CRYPTO_PAYOUT_URL env var if needed)
    url = os.getenv("CRYPTO_PAYOUT_URL", "http://crypto-payout:9001/broadcast")
    try:
        if not details:
            return None
        resp = requests.post(url, json=details, timeout=12)
        if resp.status_code == 200:
            try:
                j = resp.json()
            except Exception:
                return None
            return j.get("txhash") or j.get("tx_hash") or j.get("hash")
    except Exception:
        pass
    return None

