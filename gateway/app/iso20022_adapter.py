# app/iso20022_adapter.py
"""
ISO20022 pain.001 → payout adapter
Parses incoming XML and forwards to /payout (gateway → processor).
"""

from fastapi import APIRouter, Request, HTTPException
from defusedxml.ElementTree import fromstring as safe_fromstring
import requests, os

router = APIRouter()
PAYOUT_URL = os.environ.get("GATEWAY_PAYOUT_URL", "http://localhost:8000/payout")

def _text(elem):
    return elem.text.strip() if elem is not None and elem.text else None

def parse_pain_001(xml_text: str):
    root = safe_fromstring(xml_text)
    pmt = root.find('.//{*}CdtTrfTxInf') or root.find('.//CdtTrfTxInf')
    if pmt is None:
        raise ValueError("No <CdtTrfTxInf> found in pain.001")

    instr_id = _text(pmt.find('.//{*}InstrId')) or "000001"
    end_to_end = _text(pmt.find('.//{*}EndToEndId')) or instr_id
    amt_elem = pmt.find('.//{*}InstdAmt')
    amt = _text(amt_elem) or "0"
    ccy = amt_elem.attrib.get("Ccy") if amt_elem is not None else "EUR"
    cdtr_name = _text(pmt.find('.//{*}Cdtr/{*}Nm')) or "UNKNOWN"
    cdtr_iban = _text(pmt.find('.//{*}CdtrAcct/{*}Id/{*}IBAN')) or ""

    body = {
        "type": "iso20022",
        "fields": {
            "2": cdtr_iban.replace(" ", ""),
            "3": "000000",
            "4": str(int(float(amt) * 100)),   # convert to minor units
            "7": "",
            "11": end_to_end,
            "41": "PAIN001",
            "42": cdtr_name,
            "49": ccy,
            "protocol": "pain.001"
        }
    }
    return body

@router.post("/iso20022/pain001")
async def pain001(request: Request):
    xml_text = (await request.body()).decode("utf-8", errors="replace")
    if "<CstmrCdtTrfInitn" not in xml_text:
        raise HTTPException(400, "Not a valid pain.001 XML")
    try:
        body = parse_pain_001(xml_text)
    except Exception as e:
        raise HTTPException(400, f"Parse error: {e}")
    resp = requests.post(PAYOUT_URL, json=body, timeout=10)
    return {"status": resp.status_code, "response": resp.json() if resp.ok else resp.text}
