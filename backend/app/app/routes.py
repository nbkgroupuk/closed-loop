from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
import json, re

router = APIRouter()

@router.post("/transactions")
async def create_transaction(request: Request):
    gw_resp = {}  # example placeholder for gateway response

    # --- fixed block ---
    # Determine de39 robustly
    de39_val = None
    resp = gw_resp if isinstance(gw_resp, dict) else {}
    de39_val = resp.get("de39") or resp.get("fields", {}).get("39") or resp.get("DE39")
    if de39_val is None and resp.get("raw"):
        m = re.search(r"DE39=(\d{2})", str(resp.get("raw")))
        de39_val = m.group(1) if m else None
    if de39_val is None:
        de39_val = "96"

    return {"de39": de39_val, "approved": de39_val == "00"}
