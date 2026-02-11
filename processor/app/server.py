# processor/app/server.py
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# --------------------------------------------------
# Logging
# --------------------------------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("processor")

# --------------------------------------------------
# FastAPI app (SINGLE instance)
# --------------------------------------------------
app = FastAPI(title="Processor Service")

# --------------------------------------------------
# CORS
# --------------------------------------------------
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip()] or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# Environment flags
# --------------------------------------------------
FORCE_APPROVE_MODE = os.environ.get("FORCE_APPROVE_MODE", "false").lower() == "true"

# --------------------------------------------------
# Health
# --------------------------------------------------
@app.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "service": "processor",
        "force_approve": FORCE_APPROVE_MODE,
        "mode": "api-only",
    }

# --------------------------------------------------
# Canonical response helper
# --------------------------------------------------
def make_response(
    status: str,
    code: str,
    response_fields: dict = None,
    txn_id: str = None,
    error: str = None,
    message: str = None,
):
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

# --------------------------------------------------
# TRANSACTIONS API (Gateway → Processor)
# --------------------------------------------------
@app.post("/transactions")
async def transactions(request: Request):
    """
    Closed-loop transaction processor.
    Supports FORCE_APPROVE test mode for acquirer certification.
    """
    try:
        payload: Dict[str, Any] = await request.json()
        log.info("Received transaction: %s", payload)
    except Exception:
        return make_response(
            status="DECLINED",
            code="96",
            error="invalid_json",
            message="Invalid JSON payload",
        )

    # --------------------------------------------------
    # FORCE-APPROVE TEST MODE (ACQUIRER SAFE)
    # --------------------------------------------------
    test_header = request.headers.get("X-Test-Mode") == "FORCE_APPROVE"

    if FORCE_APPROVE_MODE and test_header:
        log.warning("FORCE_APPROVE test mode applied")

        return make_response(
            status="APPROVED",
            code="00",
            response_fields={
                "approval_type": "FORCE_TEST",
                "protocol": payload.get("protocol"),
                "auth_code": payload.get("auth_code") or "999999",
                "amount": payload.get("amount"),
                "currency": payload.get("currency"),
                "timestamp": datetime.utcnow().isoformat(),
            },
            txn_id=payload.get("reference"),
            message="Force-approved for certification testing",
        )

    # --------------------------------------------------
    # NORMAL VALIDATION (PRODUCTION PATH)
    # --------------------------------------------------
    amount = payload.get("amount")
    card = payload.get("card")

    if not amount or not card:
        return make_response(
            status="DECLINED",
            code="05",
            error="validation_error",
            message="missing card or amount",
        )

    # --------------------------------------------------
    # Business processing hook (real logic)
    # --------------------------------------------------
    try:
        from app.iso_processing import process_incoming_iso
    except Exception:
        log.exception("iso_processing module missing")
        return make_response(
            status="DECLINED",
            code="96",
            error="processor_unavailable",
            message="Processor logic unavailable",
        )

    try:
        result = await process_incoming_iso(payload)
        return result
    except Exception as e:
        log.exception("Processing failed")
        return make_response(
            status="DECLINED",
            code="96",
            error="system_error",
            message=str(e),
        )

# --------------------------------------------------
# Payout API (Gateway → Processor bridge)
# --------------------------------------------------
@app.post("/payout")
async def payout(request: Request):
    try:
        payload = await request.json()
        log.info("Received payout request: %s", payload)
    except Exception:
        return make_response(
            status="error",
            code="96",
            error="invalid_json",
            message="Invalid JSON payload",
        )

    try:
        from app.iso_processing import process_incoming_iso
    except Exception:
        log.exception("iso_processing module missing")
        return make_response(
            status="error",
            code="96",
            error="processor_unavailable",
            message="Processor logic unavailable",
        )

    try:
        result = await process_incoming_iso(payload)
        return result
    except Exception as e:
        log.exception("Processing failed")
        return make_response(
            status="error",
            code="96",
            error="system_error",
            message=str(e),
        )

# --------------------------------------------------
# Startup
# --------------------------------------------------
@app.on_event("startup")
async def startup_event():
    log.info(
        "Processor started (API-only). FORCE_APPROVE_MODE=%s",
        FORCE_APPROVE_MODE,
    )

