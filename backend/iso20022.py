# iso20022.py - minimal pain.001 generator
from xml.etree.ElementTree import Element, SubElement, tostring
from datetime import datetime
import uuid

def generate_pain001(payment: dict) -> str:
    # payment: {id, debtor_name, debtor_iban, creditor_name, creditor_iban, amount, currency, purpose}
    root = Element('Document', xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03")
    ccti = SubElement(root, 'CstmrCdtTrfInitn')
    grp = SubElement(ccti, 'GrpHdr')
    SubElement(grp, 'MsgId').text = payment.get('id') or str(uuid.uuid4())
    SubElement(grp, 'CreDtTm').text = datetime.utcnow().isoformat()
    SubElement(grp, 'NbOfTxs').text = "1"
    SubElement(grp, 'CtrlSum').text = f"{payment['amount']:.2f}"
    pmt = SubElement(ccti, 'PmtInf')
    SubElement(pmt, 'PmtInfId').text = "PMT-"+(payment.get('id') or str(uuid.uuid4()))
    SubElement(pmt, 'PmtMtd').text = "TRF"
    dbtr = SubElement(pmt, 'Dbtr')
    SubElement(dbtr, 'Nm').text = payment.get('debtor_name','')
    dbtracc = SubElement(pmt, 'DbtrAcct')
    idn = SubElement(dbtracc, 'Id')
    SubElement(idn, 'IBAN').text = payment.get('debtor_iban','')
    cdttr = SubElement(pmt, 'CdtTrfTxInf')
    pmtid = SubElement(cdttr, 'PmtId')
    SubElement(pmtid, 'EndToEndId').text = payment.get('id') or str(uuid.uuid4())
    amt = SubElement(cdttr, 'Amt')
    instdamt = SubElement(amt, 'InstdAmt', Ccy=payment.get('currency','USD'))
    instdamt.text = f"{payment['amount']:.2f}"
    cdtr = SubElement(cdttr, 'Cdtr')
    SubElement(cdtr, 'Nm').text = payment.get('creditor_name','')
    cdtracct = SubElement(cdttr, 'CdtrAcct')
    idc = SubElement(cdtracct, 'Id')
    SubElement(idc, 'IBAN').text = payment.get('creditor_iban','')
    if payment.get('purpose'):
        rmt = SubElement(cdttr, 'RmtInf')
        SubElement(rmt, 'Ustrd').text = payment['purpose']
    xml = tostring(root, encoding='utf-8', method='xml')
    return xml.decode('utf-8')
