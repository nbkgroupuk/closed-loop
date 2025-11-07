# backend_app.py
import os
import json
import uuid
import time
from datetime import datetime, timezone
from typing import Any, Dict
import requests

from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Configuration via env
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://host.docker.internal:8100").rstrip("/")
DATA_DIR = os.environ.get("BACKEND_DATA_DIR", "/app/data")
PORT = int(os.environ.get("PORT", 8000))

os.makedirs(DATA_DIR, exist_ok=True)
TX_FILE = os.path.join(DATA_DIR, "transactions.json")
PO_FILE = os.path.join(DATA_DIR, "payouts.json")

# ensure files exist
for f in (TX_FILE, PO_FILE):
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as fh:
            json.dump([], fh)

app = FastAPI(title="Backend Orchestrator")

# CORS - allow your frontend (gateway UI or backend UI)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8100",    # gateway served UI
        "http://localhost:3000",    # local Python server (if used)
        "http://localhost:8000",    # backend origin
        "http://127.0.0.1:8100",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and templates
if not os.path.exists(os.path.join(os.getcwd(), "templates")):
    os.makedirs(os.path.join(os.getcwd(), "templates"), exist_ok=True)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static", html=True), name="static")


# --- Storage helpers (simple JSON append/read) ---
def _read_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []


def _write_json(path: str, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, default=str, indent=2)


def add_transaction(record: dict):
    arr = _read_json(TX_FILE)
    arr.insert(0, record)  # put newest first
    _write_json(TX_FILE, arr)


def add_payout(record: dict):
    arr = _read_json(PO_FILE)
    arr.insert(0, record)
    _write_json(PO_FILE, arr)


# --- Models ---
class TransactionRequest(BaseModel):
    merchant_id: str | None = None
    cardNumber: str
    expiry: str
    cvc: str
    amount: float
    currency: str = "USD"
    protocol: str | None = None
    authCode: str | None = None
    txn_id: str | None = None
    correlation_id: str | None = None


class ISO20022Payout(BaseModel):
    creditor_name: str
    amount: float
    currency: str = "USD"
    pain_xml: str
    correlation_id: str | None = None


class CryptoPayout(BaseModel):
    to_address: str
    amount: float
    currency: str = "ETH"
    correlation_id: str | None = None


# --- Routes ---
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    txns = _read_json(TX_FILE)
    payouts = _read_json(PO_FILE)
    summary = {"pending": sum(1 for t in txns if t.get("status") == "pending"),
               "success": sum(1 for t in txns if t.get("approved")),
               "failed": sum(1 for t in txns if t.get("status") == "failed")}
    now = datetime.now(timezone.utc).astimezone().isoformat()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "now": now,
        "txns": txns,
        "payouts": payouts,
        "summary": summary,
    })


@app.get("/monitor", response_class=HTMLResponse)
def monitor(request: Request):
    txns = _read_json(TX_FILE)
    payouts = _read_json(PO_FILE)
    now = datetime.now(timezone.utc).astimezone().isoformat()
    return templates.TemplateResponse("monitor.html", {
        "request": request,
        "now": now,
        "transactions": txns,
        "payouts": payouts,
    })


@app.post("/transactions")
def transactions_forward(req: TransactionRequest):
    # build standard payload expected by gateway compatibility route
    payload = req.dict()
    payload.setdefault("txn_id", payload.get("txn_id") or str(uuid.uuid4()))
    payload.setdefault("protocol", payload.get("protocol") or "POS Terminal -101.1 (4-digit approval)")
    payload.setdefault("authCode", payload.get("authCode") or "1234")
    payload["merchant_id"] = payload.get("merchant_id") or "M123"

    record = {
        "id": payload["txn_id"],
        "user_code": payload.get("merchant_id"),
        "amount": payload["amount"],
        "amount_minor": int(payload["amount"] * 100),
        "currency": payload["currency"],
        "status": "pending",
        "approved": False,
        "de39": None,
        "auth_code": None,
        "idempotency_key": None,
        "date_created": datetime.utcnow().isoformat(),
        "raw_request": payload,
        "raw_response": None,
    }
    add_transaction(record)

    # forward to gateway
    try:
        r = requests.post(f"{GATEWAY_URL}/transactions", json=payload, timeout=15)
        r.raise_for_status()
    except Exception as e:
        # mark failed in store
        record["status"] = "failed"
        record["raw_response"] = {"error": str(e)}
        add_transaction(record)
        raise HTTPException(status_code=502, detail=f"Gateway comms failed: {e}")

    resp = r.json()
    # update record and persist
    record["raw_response"] = resp
    record["de39"] = resp.get("de39")
    record["auth_code"] = resp.get("de38") or resp.get("authCode")
    record["approved"] = bool(resp.get("approved"))
    record["status"] = "success" if record["approved"] else "failed"
    add_transaction(record)

    return resp


@app.post("/payout/iso20022")
def payout_iso20022(req: ISO20022Payout):
    payload = {
        "type": "iso20022",
        "creditor_name": req.creditor_name,
        "amount": req.amount,
        "currency": req.currency,
        "pain_xml": req.pain_xml,
        "correlation_id": req.correlation_id or str(uuid.uuid4()),
    }
    # store pending payout
    rec = {
        "id": str(uuid.uuid4()),
        "user_code": "PAYOUT",
        "amount": payload["amount"],
        "amount_minor": int(payload["amount"] * 100),
        "currency": payload["currency"],
        "status": "pending",
        "reference_number": None,
        "tx_hash": None,
        "date_created": datetime.utcnow().isoformat(),
        "raw_request": payload,
        "raw_response": None,
    }
    add_payout(rec)

    try:
        r = requests.post(f"{GATEWAY_URL}/payout", json=payload, timeout=20)
        r.raise_for_status()
    except Exception as e:
        rec["status"] = "failed"
        rec["raw_response"] = {"error": str(e)}
        add_payout(rec)
        raise HTTPException(status_code=502, detail=f"Gateway comms failed: {e}")

    resp = r.json()
    rec["raw_response"] = resp
    rec["status"] = "success" if resp.get("ok") or resp.get("approved") else "failed"
    rec["reference_number"] = resp.get("gateway_txn_id") or resp.get("txn_id")
    add_payout(rec)
    return resp


@app.post("/payout/crypto")
def payout_crypto(req: CryptoPayout):
    payload = req.dict()
    payload["correlation_id"] = payload.get("correlation_id") or str(uuid.uuid4())

    rec = {
        "id": str(uuid.uuid4()),
        "user_code": "CRYPTO",
        "amount": payload["amount"],
        "amount_minor": int(payload["amount"] * 100),
        "currency": payload["currency"],
        "status": "pending",
        "reference_number": None,
        "tx_hash": None,
        "date_created": datetime.utcnow().isoformat(),
        "raw_request": payload,
        "raw_response": None,
    }
    add_payout(rec)

    try:
        r = requests.post(f"{GATEWAY_URL}/payout/crypto", json=payload, timeout=20)
        r.raise_for_status()
    except Exception as e:
        rec["status"] = "failed"
        rec["raw_response"] = {"error": str(e)}
        add_payout(rec)
        raise HTTPException(status_code=502, detail=f"Gateway comms failed: {e}")

    resp = r.json()
    rec["raw_response"] = resp
    rec["status"] = "success" if resp.get("ok") or resp.get("approved") else "failed"
    rec["tx_hash"] = resp.get("tx_hash") or None
    add_payout(rec)
    return resp
