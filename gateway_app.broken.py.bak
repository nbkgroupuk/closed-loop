import sys, traceback
sys.path.insert(0, "/app")
try:
    import crypto_payout_engine
    globals()["process_payout"] = crypto_payout_engine.process_payout
    print("✅ crypto_payout_engine.process_payout linked at import time")
except Exception as e:
    print("⚠️ crypto_payout_engine not linked at import time:", e)
    traceback.print_exc()
# gateway/gateway_app.py
# FastAPI gateway updated with /transactions settlement endpoint (simple, test-friendly)
# - Accepts POST /transactions for settlement events (called by settlement_handler or processor)
# - Keeps an in-memory list of recent transactions for debugging (GET /transactions)
# - Existing /payout preserved (talks to processor)
# - Async trigger for crypto payout kept as before
# - Clear logging and status mapping for ISO response codes

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import socket, json, os, logging, re, asyncio, time
from typing import Optional, List, Dict, Any

# CORS call removed by script - moved

# setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

app = FastAPI(title="Gateway")
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com", "http://localhost:3000"],  # restrict in prod
    allow_credentials=True,
    allow_methods=["GET","POST","PUT","DELETE","OPTIONS"], # new line compared to old
    allow_headers=["*"],
)

PROCESSOR_HOST = os.environ.get("PROCESSOR_HOST", "processor")
try:
    PROCESSOR_PORT = int(os.environ.get("PROCESSOR_PORT", "9000"))
except Exception:
    PROCESSOR_PORT = 9000
TCP_TIMEOUT = float(os.environ.get("TCP_TIMEOUT", "5"))

# in-memory store (debug only) of settlements received
_transactions_store: List[Dict[str, Any]] = []


#@app.get("/health")
#def health():
#   return {"status": "ok"}

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "gateway"}

# -------------------------
# Settlement endpoint(s)
# -------------------------
@app.post("/transactions")
async def receive_transaction(request: Request):
    """
    Receiver for gateway settlement messages.
    Expected JSON:
      { "merchant_id": "...", "amount": 10.0, "auth_code": "...", "protocol": "101.1", ... }
    This endpoint is intentionally permissive for testing. In production validate & persist properly.
    """
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    # minimal validation
    merchant_id = body.get("merchant_id")
    amount = body.get("amount")
    auth_code = body.get("auth_code") or body.get("authCode") or body.get("auth")
    protocol = body.get("protocol")

    if merchant_id is None:
        raise HTTPException(400, "merchant_id is required")
    if amount is None:
        raise HTTPException(400, "amount is required")

    entry = {
        "received_at": time.time(),
        "merchant_id": merchant_id,
        "amount": amount,
        "auth_code": auth_code,
        "protocol": protocol,
        "raw": body
    }

    # append to debug store
    _transactions_store.append(entry)
    # keep store bounded
    if len(_transactions_store) > 200:
        _transactions_store.pop(0)

    logger.info("Received settlement POST: merchant=%s amount=%s auth=%s", merchant_id, amount, auth_code)
    # in real gateway you would: persist, emit event, reconcile settlement, call payout etc.
    try:
        import requests
        logger.info('Forwarding payout to /payout API...')
        payout_details = body.get('payoutDetails', {})
        payout_payload = {
            'merchant_id': merchant_id,
            'amount': amount,
            'auth_code': auth_code,
            'to_address': payout_details.get('address'),
            'network': payout_details.get('network')
        }
        try:
            r = requests.post('http://crypto-payout:9001/payout', json=payout_payload, timeout=10)
            logger.info('Payout response: %s %s', r.status_code, r.text[:200])
        except Exception as e:
            logger.exception('⚠️ Payout POST failed: %s', e)
    except Exception as e:
        logger.exception('⚠️ Payout forward wrapper failed: %s', e)


    return {"status": "accepted", "merchant_id": merchant_id, "amount": amount}


@app.get("/transactions")
def list_transactions(limit: Optional[int] = 50):
    """Debug listing of recent settlement posts (testing only)."""
    return {"count": len(_transactions_store), "items": _transactions_store[-limit:]}


# -------------------------
# Existing payout route
# -------------------------
@app.post("/payout")
async def payout_handler(request: Request):
    # Validate JSON
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    if not isinstance(body, dict):
        raise HTTPException(400, "payload must be JSON object")

    # ---- Normalize keys for processor compatibility ----
    # Accept both camelCase and snake_case and ensure required keys exist
    body.setdefault("auth_code", body.get("auth_code") or body.get("authCode") or body.get("auth"))
    body.setdefault("merchant_id", body.get("merchant_id") or body.get("merchant") or body.get("merchantId"))
    body.setdefault("protocol", body.get("protocol") or body.get("protocolCode") or "101.1")
    body.setdefault("method", body.get("method") or body.get("type") or "iso20022")
    body.setdefault("reference", body.get("reference") or body.get("txn_id") or body.get("msg_id") or "REF001")

    # ---- Frame ISO request for processor ----
    try:
        # build ISO-style payload using gateway_iso_mapper
        from gateway_iso_mapper import build_iso_fields
        fields = build_iso_fields(body)
        iso_frame = {"mti": "0200", "fields": fields}
        payload_bytes = json.dumps(iso_frame).encode("utf-8")
    except Exception as e:
        raise HTTPException(400, f"Serialization error: {e}")

    # ensure ISO MTI prefix if consumer expects it
    if not payload_bytes.startswith(b"0200"):
        payload_bytes = b"0200" + payload_bytes
    framed = len(payload_bytes).to_bytes(4, "big") + payload_bytes

    try:
        with socket.create_connection((PROCESSOR_HOST, PROCESSOR_PORT), timeout=TCP_TIMEOUT) as s:
            logger.info("SENDING to processor (%s:%s) frame_len=%d first24=%s",              # Added 19/10/2025
                        PROCESSOR_HOST, PROCESSOR_PORT, len(framed), framed[:24].hex())      # Added 19/10/2025
            s.sendall(framed)
            hdr = s.recv(4)
            if len(hdr) < 4:
                raise RuntimeError("no response header")
            to_read = int.from_bytes(hdr, "big")
            data = b""
            while len(data) < to_read:
                chunk = s.recv(to_read - len(data))
                if not chunk:
                    break
                data += chunk
    except Exception as e:
        logger.exception("Processor comms failed")
        raise HTTPException(502, f"Processor comms failed: {e}")

    try:
        text = data.decode("utf-8", "replace").strip()
        text = re.sub(r"^[0-9]{3,4}", "", text).strip()
        resp = json.loads(text)
    except Exception as e:
        raise HTTPException(502, f"Invalid processor response: {e}")

    code = resp.get("fields", {}).get("39")
    logger.info("Processor code=%s resp=%s", code, resp)

    if code == "00":
        asyncio.create_task(trigger_crypto_payout(resp))
        try:\n        arg = resp_json\n    except NameError:\n        arg = globals().get('resp') or {}\n    result = await trigger_crypto_payout(arg)
        logger.info("Triggered crypto payout for approved txn")
        return {"status": "approved", "code": "00", "response": resp}
    elif code == "91":
        raise HTTPException(502, "Processor error (91: issuer/host unavailable)")
    elif code == "96":
        raise HTTPException(502, "Processor error (96: system malfunction)")
    else:
        raise HTTPException(402, f"Payment declined ({code})")

# ========== ISO20022 Adapter ==========
try:
    from iso20022_adapter import router as iso20022_router
    app.include_router(iso20022_router)
    logger.info("✅ ISO20022 adapter loaded")
except Exception as e:
    logger.warning(f"⚠️ Failed to include iso20022_adapter: {e}")


# ========== Crypto Payout Engine ==========
async def trigger_crypto_payout(resp_json: dict):
    """Automatic ERC20 payout after approval (best-effort)."""
    try:
        from crypto_payout_engine import process_payout
    except Exception as e:
        logger.warning(f"Crypto payout engine not available: {e}")
        return

# Build payout payload (example/test)
    try:
        fields = resp_json.get('fields', {})
        merchant_wallet = os.environ.get('MERCHANT_WALLET', '0x0000000000000000000000000000000000000000')
        amount_minor = int(fields.get('4') or 0)
        amount_human = amount_minor / 1000.0 if amount_minor else 0.0
        payload = {'to_address': merchant_wallet, 'amount': amount_human, 'currency': 'USDT', 'meta': fields}
        result = await asyncio.to_thread(process_payout, payload)
        logger.info(f'💸 Crypto payout submitted: {result}')
    except Exception as e:
        logger.exception(f'Crypto payout failed: {e}')
