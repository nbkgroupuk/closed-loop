from fastapi import FastAPI
app = FastAPI()
#!/usr/bin/env python3
# server.py — cleaned single FastAPI instance, CORS enabled (dev)
import os
import json
import socketserver
import threading
import logging
from datetime import datetime
import asyncio

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
# add this near the top with other imports
import asyncio, os
from app.iso_listener import start_server as start_iso_server

@app.on_event("startup")
async def startup_event():
    # existing startup logic (if any)
    asyncio.create_task(start_iso_server(host="0.0.0.0", port=int(os.environ.get("ISO_PORT", 9000))))

# Logging
log = logging.getLogger("processor")
logging.basicConfig(level=logging.INFO)

# Single FastAPI instance (only one)
app = FastAPI(title="Processor Service")

# --- CORS middleware (dev / local only) ---
# Reads ALLOWED_ORIGINS env var (comma separated). Defaults to "*"
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip()] or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Try to include payout_status router (if present)
try:
    from app.api.payout_status import router as payout_status_router
    app.include_router(payout_status_router)
except Exception:
    log.debug("app.api.payout_status not found or failed to import (safe to continue).")

# Health endpoint
@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "processor", "iso_port": int(os.environ.get("ISO_PORT", "9000"))}

# --------------------------------------------------------------------
# Payout endpoint: delegates to app.iso_processing.process_incoming_iso
# Returns canonical JSON shape so frontend can interpret codes consistently
# --------------------------------------------------------------------
def make_response(status: str, code: str, response_fields: dict = None, txn_id: str = None, error: str = None, message: str = None) -> dict:
    return {
        "status": status,
        "code": str(code),
        "error": error,
        "response": {
            "fields": response_fields or {},
            "txn_id": txn_id,
            "message": message,
        },
    }

@app.post("/payout")
async def payout(payload: Request):
    data = await payload.json()

    # Legacy card shortcut (keeps old dev behavior)
    if data.get("cardNumber"):
        auth_code = data.get("authCode") or __import__("secrets").token_hex(3)
        return make_response("approved", "00", {"39": "00", "38": auth_code}, txn_id=data.get("job_id") or data.get("txn_id"), message="Accepted (live card)")

    # Delegate to ISO processing pipeline
    try:
        from app.iso_processing import process_incoming_iso
    except Exception:
        log.exception("app.iso_processing not available")
        return make_response("error", "96", {"39": "96"}, error="processor_unavailable", message="Processor unavailable")

    try:
        result = await process_incoming_iso(data)
    except Exception as e:
        log.exception("payout processor raised: %s", e)
        return make_response("error", "96", {"39": "96"}, error="system_malfunction", message="Temporary system error — please retry")

    # If result is already canonical
    if isinstance(result, dict) and "status" in result and "code" in result:
        return result

    # Try to adapt legacy response
    code = None
    if isinstance(result, dict):
        code = result.get("de39") or result.get("DE39") or result.get("39") or None
    code = str(code) if code else "96"

    if code == "00":
        return make_response("approved", "00", {"39": "00", "38": (result.get("de38") if isinstance(result, dict) else None)}, txn_id=(result.get("txn_id") if isinstance(result, dict) else data.get("txn_id")), message="Accepted")
    else:
        return make_response("error", code, {"39": code}, txn_id=(result.get("txn_id") if isinstance(result, dict) else None), error=(result.get("error") if isinstance(result, dict) else None), message=(result.get("message") if isinstance(result, dict) else "Temporary system error — please retry"))

# --------------------------------------------------------------------
# Very small ISO8583-like TCP handler (kept for local testing)
# --------------------------------------------------------------------
class ISOHandler(socketserver.StreamRequestHandler):
    def handle(self):
        data = self.rfile.readline().strip()
        if not data:
            return
        try:
            text = data.decode()
            log.info("Received raw ISO msg: %s", text)
            j = json.loads(text)
            response = json.dumps({
                "mti": "0210",
                "fields": {"39": "00", "desc": "APPROVED"},
                "echo": j
            }) + "\n"
            self.wfile.write(response.encode())

            # Log transaction record locally
            os.makedirs("/var/log", exist_ok=True)
            with open("/var/log/iso_transactions.jsonl", "a") as f:
                f.write(json.dumps({
                    "timestamp": datetime.utcnow().isoformat(),
                    "mti": "0200",
                    "status": "approved",
                    "length": len(data)
                }) + "\n")
        except Exception as e:
            log.exception("Error processing tcp msg: %s", e)
            try:
                self.wfile.write(b'{"error":"bad"}\n')
            except Exception:
                pass

# --------------------------------------------------------------------
# Startup: start ISO listener in background if module available
# --------------------------------------------------------------------
def _start_iso_server_safe():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from app.iso_listener import start_server as start_iso_server
        except Exception:
            log.debug("app.iso_listener not present; skipping ISO TCP server")
            return
        loop.create_task(start_iso_server(host="0.0.0.0", port=int(os.environ.get("ISO_PORT", "9000"))))
        loop.run_forever()
    except Exception:
        log.exception("Failed to start ISO server")

@app.on_event("startup")
def startup_event():
    thread = threading.Thread(target=_start_iso_server_safe, daemon=True)
    thread.start()
