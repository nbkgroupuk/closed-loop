"""
Simple ISO20022 (pain.001) receiver for the gateway.

# How to use in production
- This file is safe for testing. To enable/disable verbose logging or
  extra validation in production you can:
    * read env var `ISO20022_STRICT=1` to enable stricter validation
    * read env var `ISO20022_VERBOSE=1` to enable detailed logging
  See the "# PRODUCTION" notes below for placeholders.

This module exposes a FastAPI APIRouter at /payouts/iso20022
"""
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import PlainTextResponse
import xml.etree.ElementTree as ET
import datetime
import os
import logging

log = logging.getLogger("gateway.iso20022")
router = APIRouter(prefix="/payouts", tags=["payouts"])

# PRODUCTION:
# - To enable strict validation (reject unexpected fields/structure) set ISO20022_STRICT=1
# - To enable verbose instrumentation set ISO20022_VERBOSE=1
# These let you toggle behavior from docker-compose (environment) without editing code.
ISO20022_STRICT = os.getenv("ISO20022_STRICT", "0") == "1"
ISO20022_VERBOSE = os.getenv("ISO20022_VERBOSE", "0") == "1"

def _ns_strip(tag):
    """helper to strip namespace from Element.tag"""
    if tag is None:
        return None
    return tag.split("}", 1)[-1] if "}" in tag else tag

@router.post("/iso20022", response_class=PlainTextResponse)
async def accept_iso20022(request: Request):
    """
    Accepts XML (pain.001) and returns a simple pain.002 acknowledgement.
    Minimal behavior:
      - parse XML
      - extract MsgId / EndToEndId for correlation (best-effort)
      - return pain.002 with status ACCP

    This endpoint is intentionally forgiving — enable ISO20022_STRICT
    to enforce stricter schema/field checks in production.
    """
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty body")

    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        log.exception("XML parse error for incoming pain.001")
        raise HTTPException(status_code=400, detail="invalid xml")

    # try to find common elements (namespace-agnostic)
    def findtext_any(root_element, localname):
        # search by local-name in tree
        for elem in root_element.iter():
            if _ns_strip(elem.tag) == localname:
                return elem.text
        return None

    msgid = findtext_any(root, "MsgId") or f"MSG-{datetime.datetime.utcnow().isoformat()}"
    e2e = findtext_any(root, "EndToEndId") or "UNKNOWN"
    cre_dt = datetime.datetime.utcnow().replace(microsecond=0).isoformat()

    if ISO20022_VERBOSE:
        log.info("Received pain.001 MsgId=%s EndToEnd=%s len=%d", msgid, e2e, len(body))

    # If strict validation is requested, perform minimal schema-like checks:
    if ISO20022_STRICT:
        # Example checks: presence of <PmtInf> and at least one <CdtTrfTxInf>
        has_pmtinf = any(_ns_strip(e.tag) == "PmtInf" for e in root.iter())
        has_cdt = any(_ns_strip(e.tag) == "CdtTrfTxInf" for e in root.iter())
        if not (has_pmtinf and has_cdt):
            log.warning("ISO20022_STRICT enabled: missing PmtInf/CdtTrfTxInf in %s", msgid)
            raise HTTPException(status_code=400, detail="invalid pain.001 structure")

    # Build a minimal pain.002 (payment status report) ack
    pain002 = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.002.001.09">
  <CstmrPmtStsRpt>
    <GrpHdr>
      <MsgId>{msgid}</MsgId>
      <CreDtTm>{cre_dt}</CreDtTm>
    </GrpHdr>
    <OrgnlGrpInfAndSts>
      <OrgnlMsgId>{msgid}</OrgnlMsgId>
      <GrpSts>ACCP</GrpSts>
    </OrgnlGrpInfAndSts>
  </CstmrPmtStsRpt>
</Document>"""

    log.info("Accepted pain.001 msg=%s EndToEnd=%s", msgid, e2e)
    return Response(content=pain002, media_type="application/xml")
