from datetime import datetime
from decimal import Decimal
from textwrap import dedent

# Fixed beneficiary: Rutland Projects Ltd @ BMO Bank (USA)
BENEFICIARY = {
    "name": "RUTLAND PROJECTS LTD",
    "account_type": "CHECKING",
    "account_number": "3773272",
    "swift": "HATRUS44",
    "routing": "071000288",
    "bank_name": "BMO BANK",
    "bank_country": "USA",
    "bank_address": "320 SOUTH CANAL STREET,CHICAGO,IL,60606",
}

def _fmt_amount(amount, currency: str) -> str:
    """
    Format amount as ISO20022 decimal string.
    Accepts float, str, or Decimal.
    """
    if isinstance(amount, Decimal):
        val = amount
    else:
        val = Decimal(str(amount))
    # normalize to 2 decimal places for card settlements
    return f"{val:.2f}", currency.upper()

def build_pain001_xml(
    *,
    msg_id: str,
    end_to_end_id: str,
    amount,
    currency: str,
    rrn: str,
    stan: str,
    debtor_name: str,
    debtor_account: str,
    created_at: datetime | None = None,
) -> str:
    """
    Build a very simple pain.001.001.09 XML for a single credit transfer
    from the *card settlement pool* (debtor) to Rutland Projects Ltd (creditor).

    - msg_id: unique message id (you can use RRN or payout id)
    - end_to_end_id: unique per payment (e.g. STAN or transaction id)
    - amount/currency: settlement amount
    - rrn, stan: included in remittance text so the bank sees card references
    - debtor_name: your pool account name at the bank
    - debtor_account: your pool account number / IBAN (or '0000000000' placeholder)
    """
    dt = created_at or datetime.utcnow()
    cre_dt_tm = dt.isoformat(timespec="seconds") + "Z"

    amt_str, ccy = _fmt_amount(amount, currency)

    ben = BENEFICIARY
    msg = f"{rrn}/{stan}"

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>{msg_id}</MsgId>
      <CreDtTm>{cre_dt_tm}</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <CtrlSum>{amt_str}</CtrlSum>
      <InitgPty>
        <Nm>RUTLAND PROJECTS LTD Settlement</Nm>
      </InitgPty>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>{msg_id}</PmtInfId>
      <PmtMtd>TRF</PmtMtd>
      <BtchBookg>false</BtchBookg>
      <ReqdExctnDt>{dt.date().isoformat()}</ReqdExctnDt>
      <Dbtr>
        <Nm>{debtor_name}</Nm>
      </Dbtr>
      <DbtrAcct>
        <Id>
          <Othr>
            <Id>{debtor_account}</Id>
          </Othr>
        </Id>
      </DbtrAcct>
      <DbtrAgt>
        <FinInstnId>
          <Othr>
            <Id>NOTPROVIDED</Id>
          </Othr>
        </FinInstnId>
      </DbtrAgt>
      <ChrgBr>SHAR</ChrgBr>
      <CdtTrfTxInf>
        <PmtId>
          <EndToEndId>{end_to_end_id}</EndToEndId>
        </PmtId>
        <Amt>
          <InstdAmt Ccy="{ccy}">{amt_str}</InstdAmt>
        </Amt>
        <CdtrAgt>
          <FinInstnId>
            <BICFI>{ben["swift"]}</BICFI>
          </FinInstnId>
        </CdtrAgt>
        <Cdtr>
          <Nm>{ben["name"]}</Nm>
          <PstlAdr>
            <Ctry>{ben["bank_country"]}</Ctry>
            <AdrLine>{ben["bank_address"]}</AdrLine>
          </PstlAdr>
        </Cdtr>
        <CdtrAcct>
          <Id>
            <Othr>
              <Id>{ben["account_number"]}</Id>
            </Othr>
          </Id>
        </CdtrAcct>
        <RmtInf>
          <Ustrd>Card settlement RRN {rrn} / STAN {stan}</Ustrd>
        </RmtInf>
      </CdtTrfTxInf>
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>
'''
    # keep indentation but strip leading/trailing blank lines
    return dedent(xml).strip()
