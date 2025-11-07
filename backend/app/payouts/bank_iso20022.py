# app/payouts/bank_iso20022.py
from lxml import etree
from typing import Dict
import uuid
import datetime

def build_pain_001(creditor_name: str, creditor_iban: str, amount: str, currency: str, end_to_end_id: str = None) -> bytes:
    """
    Minimal pain.001 builder. IMPORTANT: For production, ensure full pain.001.001.09 schema compliance.
    """
    ns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    Document = etree.Element("{%s}Document" % ns, nsmap={None: ns})
    CstmrCdtTrfInitn = etree.SubElement(Document, "CstmrCdtTrfInitn")
    GrpHdr = etree.SubElement(CstmrCdtTrfInitn, "GrpHdr")
    etree.SubElement(GrpHdr, "MsgId").text = str(uuid.uuid4())
    etree.SubElement(GrpHdr, "CreDtTm").text = datetime.datetime.utcnow().isoformat()
    etree.SubElement(GrpHdr, "NbOfTxs").text = "1"
    etree.SubElement(GrpHdr, "CtrlSum").text = amount

    PmtInf = etree.SubElement(CstmrCdtTrfInitn, "PmtInf")
    etree.SubElement(PmtInf, "PmtInfId").text = str(uuid.uuid4())
    CdtTrfTxInf = etree.SubElement(PmtInf, "CdtTrfTxInf")
    PmtId = etree.SubElement(CdtTrfTxInf, "PmtId")
    etree.SubElement(PmtId, "EndToEndId").text = end_to_end_id or str(uuid.uuid4())
    Amt = etree.SubElement(CdtTrfTxInf, "Amt")
    InstdAmt = etree.SubElement(Amt, "InstdAmt", Ccy=currency)
    InstdAmt.text = str(amount)
    Cdtr = etree.SubElement(CdtTrfTxInf, "Cdtr")
    etree.SubElement(Cdtr, "Nm").text = creditor_name
    CdtrAcct = etree.SubElement(CdtTrfTxInf, "CdtrAcct")
    Id = etree.SubElement(CdtrAcct, "Id")
    etree.SubElement(Id, "IBAN").text = creditor_iban

    xml = etree.tostring(Document, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    return xml
