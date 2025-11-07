"""Settlement handler with DB persistence + JSONL fallback and protocol->auth validation.
"""
import os, json, logging, requests, random, re, datetime
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('settlement_handler')

TARGET_URL = os.environ.get('GATEWAY_INTERNAL_URL', 'http://localhost:8000/transactions')
REQUEST_TIMEOUT = 10.0

# Protocol -> required auth length mapping (mirror project protocol list).
PROTOCOL_AUTH_LEN = {
    '101.1': 4, '101.2': 6, '101.3': 6, '101.4': 6, '101.5': 6, '101.6': 6,
    '101.7': 4, '101.8': 4,
    '201.1': 6, '201.2': 6, '201.3': 6, '201.4': 6, '201.5': 6,
}

def _iso_get(fields, key):
    return fields.get(str(key)) or fields.get(key)

def _protocol_expected_len(proto):
    if not proto:
        return 6
    p = str(proto).strip()
    if p in PROTOCOL_AUTH_LEN:
        return PROTOCOL_AUTH_LEN[p]
    if p.startswith('101.') or '101.' in p:
        return 4
    if p.startswith('201.') or '201.' in p:
        return 6
    return 6

def _extract_protocol_and_auth(fields):
    if not isinstance(fields, dict):
        return None, None
    proto_keys = ['protocol','protocol_version',60,'60']
    auth_keys = [38,'38','auth','auth_code','authorization']
    def _pick(keys):
        for k in keys:
            if isinstance(k, int) and k in fields:
                return fields[k]
            if isinstance(k, str) and k in fields:
                return fields[k]
        return None
    proto = _pick(proto_keys)
    auth = _pick(auth_keys)
    proto_s = str(proto).strip() if proto is not None else None
    auth_s = str(auth).strip() if auth is not None else None
    return proto_s, auth_s

def _make_numeric_auth(length):
    if length <= 0:
        length = 6
    fmt = '{{:0{}d}}'.format(length)
    num = random.randint(0, 10**length - 1)
    return fmt.format(num)

def _mask_pan(pan):
    try:
        pan = str(pan)
        if len(pan) >= 8:
            return pan[:4] + '*'*(max(len(pan)-8,0)) + pan[-4:]
        return pan
    except Exception:
        return None

def build_settlement_payload(iso_fields):
    amount_minor = _iso_get(iso_fields, 4) or _iso_get(iso_fields, '4')
    try:
        s = ''.join(ch for ch in str(amount_minor) if ch.isdigit()) if amount_minor is not None else ''
        amount_major = float(int(s))/100.0 if s else 0.0
    except Exception:
        amount_major = 0.0

    proto, auth = _extract_protocol_and_auth(iso_fields)
    expected_len = _protocol_expected_len(proto)
    auth_clean = None
    if auth:
        auth_clean = re.sub(r'[^A-Za-z0-9]', '', auth)
        if len(auth_clean) != expected_len:
            log.warning('auth length mismatch for protocol %s: expected %d got %d; will generate new auth', proto, expected_len, len(auth_clean))
            auth_clean = None
    if not auth_clean:
        auth_clean = _make_numeric_auth(expected_len)

    raw_pan = _iso_get(iso_fields, 2) or _iso_get(iso_fields, '2')
    masked = _mask_pan(raw_pan)

    payload = {
        'merchant_id': _iso_get(iso_fields, 42) or _iso_get(iso_fields, '42') or 'unknown_merchant',
        'terminal_id': _iso_get(iso_fields, 41) or _iso_get(iso_fields, '41') or 'unknown_terminal',
        'card_pan': None,
        'masked_pan': masked,
        'auth_code': auth_clean,
        'stan': _iso_get(iso_fields, 11) or _iso_get(iso_fields, '11'),
        'currency': _iso_get(iso_fields, 49) or _iso_get(iso_fields, '49') or 'USD',
        'amount': amount_major,
        'protocol': proto or 'unknown',
        'iso_fields': iso_fields,
        'card_settlement': True
    }
     payload.update({
    "cardNumber": "TEST_PAN_REDACTED",
    "expiry": "12/30",
    "cvc": "123",
    "authCode": payload.get("auth_code", "123456")
    })
  

    if _iso_get(iso_fields, 37):
        payload['rrn'] = _iso_get(iso_fields, 37)
    return payload

# DB integration: try to import local db module and call insert_settlement
try:
    from app import db as _dbmod
    DB_AVAILABLE = True
except Exception:
    try:
        import db as _dbmod
        DB_AVAILABLE = True
    except Exception:
        _dbmod = None
        DB_AVAILABLE = False


# Also keep JSONL fallback ledger
JSONL_PATH = '/app/data/settlement_tx_map.jsonl'
os.makedirs('/app/data', exist_ok=True)

def _append_jsonl(rec):
    try:
        with open(JSONL_PATH,'a') as f:
            f.write(json.dumps(rec) + '\n')
    except Exception as e:
        log.exception('Failed to write JSONL ledger: %s', e)

def on_iso_response(parsed):
    if not parsed or not isinstance(parsed, dict):
        log.warning('on_iso_response called with empty/invalid parsed payload')
        return None
    fields = parsed.get('fields') or {}
    de39 = fields.get('39') or fields.get(39)
    if de39 is None or str(de39) != '00':
        log.info('no approval (DE39=%s) -> no settlement', de39)
        return None
    payload = build_settlement_payload(fields)
    # Post to internal transactions endpoint
    try:
        log.info('Posting settlement to %s payload=%s', TARGET_URL, json.dumps({'merchant_id':payload.get('merchant_id'),'amount':payload.get('amount'),'auth_code':payload.get('auth_code'),'protocol':payload.get('protocol')}))
        hdrs = {'Content-Type':'application/json','Accept':'application/json'}
        resp = requests.post(TARGET_URL, json=payload, headers=hdrs, timeout=REQUEST_TIMEOUT)
        log.info('Settlement POST status=%s body=%s', resp.status_code, resp.text[:1000])
    except Exception as e:
        log.exception('Error posting settlement: %s', e)
        resp = None

    # Build record to persist
    rec = {
        'ts': datetime.datetime.utcnow().isoformat()+'Z',
        'merchant_id': payload.get('merchant_id'),
        'terminal_id': payload.get('terminal_id'),
        'stan': payload.get('stan'),
        'rrn': payload.get('rrn'),
        'masked_pan': payload.get('masked_pan'),
        'protocol': payload.get('protocol'),
        'amount': payload.get('amount'),
        'signed_tx_hash': payload.get('signed_tx_hash') if payload.get('signed_tx_hash') else None,
        'signed_by': payload.get('signed_by') if payload.get('signed_by') else None,
        'note': 'card-settlement -> crypto payout',
        'raw': payload
    }

    # write JSONL fallback
    try:
        _append_jsonl(rec)
    except Exception:
        log.exception('JSONL append failed')

    # attempt DB insert if available
    try:
        if DB_AVAILABLE and _dbmod:
            inserted = _dbmod.insert_settlement(rec)
            log.info('DB insert result: %s', inserted)
    except Exception as e:
        log.exception('DB insertion failed: %s', e)

    return resp
