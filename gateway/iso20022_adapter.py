# iso20022_adapter.py
# Async ISO20022 pain.001 -> gateway /payout adapter
from fastapi import APIRouter, Request, HTTPException
from defusedxml.ElementTree import fromstring as safe_fromstring
import httpx
import os
from typing import Optional

router = APIRouter()
PAYOUT_URL = os.environ.get("GATEWAY_PAYOUT_URL", "http://localhost:8000/payout")
HTTP_TIMEOUT = float(os.environ.get("ISO20022_FORWARD_TIMEOUT", "10"))

def _text(elem):
    return elem.text.strip() if elem is not None and elem.text else None

def parse_pain_001(xml_text: str):
    root = safe_fromstring(xml_text)
    pmt = root.find('.//{*}CdtTrfTxInf') or root.find('.//CdtTrfTxInf')
    if pmt is None:
        raise ValueError("No <CdtTrfTxInf> found in pain.001")

    instr_id = _text(pmt.find('.//{*}InstrId')) or "000001"
    end_to_end = _text(pmt.find('.//{*}EndToEndId')) or instr_id
    amt_elem = pmt.find('.//{*}InstdAmt') or pmt.find('.//InstdAmt')
    amt = _text(amt_elem) or "0"
    ccy = amt_elem.attrib.get("Ccy") if amt_elem is not None else "EUR"
    cdtr_name = _text(pmt.find('.//{*}Cdtr/{*}Nm')) or _text(pmt.find('.//Cdtr/Nm')) or "UNKNOWN"
    cdtr_iban = _text(pmt.find('.//{*}CdtrAcct/{*}Id/{*}IBAN')) or _text(pmt.find('.//CdtrAcct/Id/IBAN')) or ""

    body = {
        "type": "iso20022",
        "fields": {
            # Map pain fields into your gateway/processor fields — adjust as needed
            "2": cdtr_iban.replace(" ", ""),
            "3": "000000",
            "4": str(int(float(amt) * 100)),   # minor units (e.g., cents)
            "7": "",
            "11": end_to_end,
            "41": "PAIN001",
            "42": cdtr_name,
            "49": ccy,
            "protocol": "pain.001",
        }
    }
    return body

@router.post("/iso20022/pain001")
async def pain001(request: Request):
    xml_text = (await request.body()).decode("utf-8", errors="replace")
    if not xml_text.strip():
        raise HTTPException(400, "Empty request body")
    if "<CstmrCdtTrfInitn" not in xml_text and "<CdtTrfTxInf" not in xml_text:
        raise HTTPException(400, "Not a recognized pain.001 payload")

    try:
        body = parse_pain_001(xml_text)
    except Exception as e:
        raise HTTPException(400, f"Parse error: {e}")

    # Forward to payout using async httpx so we don't block the event loop
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.post(PAYOUT_URL, json=body)
    except httpx.RequestError as e:
        raise HTTPException(502, f"Forward to payout failed: {e}")

    # pass through processor response where possible
    content = resp.text
    try:
        resp_json = resp.json()
    except Exception:
        resp_json = content

    # normalize successful (200) response mapping
    if resp.status_code >= 200 and resp.status_code < 300:
        return {"status": "forwarded", "code": resp.status_code, "response": resp_json}
    else:
        # bubble up non-2xx from payout as 502
        raise HTTPException(502, f"Upstream payout returned {resp.status_code}: {content}")
