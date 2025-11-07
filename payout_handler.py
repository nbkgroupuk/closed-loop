"""
payout_handler.py
Lightweight handler to send settlement results to crypto-payout service
and log JSONL fallback for audit.
"""

import os, json, logging, requests, datetime

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("payout_handler")

CRYPTO_PAYOUT_URL = os.environ.get("CRYPTO_PAYOUT_URL", "http://127.0.0.1:9001/payout")
JSONL_PATH = os.environ.get("PAYOUT_JSONL_PATH", "./data/payout_requests.jsonl")
REQUEST_TIMEOUT = float(os.environ.get("PAYOUT_REQUEST_TIMEOUT", "10.0"))

def _append_jsonl(path, rec):
    parent = os.path.dirname(path) or "."
    try:
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception as e:
        log.exception("Failed to append payout JSONL: %s", e)

def build_payout_payload(settlement):
    wallet = settlement.get("wallet") or settlement.get("merchant_wallet") or os.environ.get("MERCHANT_WALLET")
    amount_minor = int(settlement.get("amount_minor") or 0)
    currency = settlement.get("currency") or "USDT"
    payload = {
        "wallet": wallet,
        "amount_minor": amount_minor,
        "currency": currency,
        "dry_run": bool(settlement.get("dry_run", True)),
        "meta": settlement.get("meta", {"source": "payout_handler", "settlement": settlement.get("stan")}),
    }
    return payload

def post_payout(payload):
    try:
        log.info("Posting payout to %s", CRYPTO_PAYOUT_URL)
        resp = requests.post(CRYPTO_PAYOUT_URL, json=payload, timeout=REQUEST_TIMEOUT)
        log.info("crypto-payout status=%s body=%s", resp.status_code, resp.text[:800])
        return resp
    except Exception:
        log.exception("Error posting to crypto-payout")
        return None

def handle(settlement, dry_run_first=True):
    if not settlement or not isinstance(settlement, dict):
        log.warning("Invalid settlement payload")
        return None, None

    payout = build_payout_payload(settlement)
    payout["dry_run"] = dry_run_first
    resp = post_payout(payout)

    record = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "settlement": settlement,
        "payout": payout,
        "response": None,
    }
    if resp is not None:
        try:
            record["response"] = resp.json()
        except Exception:
            record["response"] = resp.text
    _append_jsonl(JSONL_PATH, record)
    return resp, payout

if __name__ == "__main__":
    test = {
        "merchant_id": "MERCH001",
        "amount_minor": 1000,
        "wallet": os.environ.get("MERCHANT_WALLET", "0x73F888dcE062d2acD4A7688386F0f92f43055491"),
    }
    r, p = handle(test, dry_run_first=True)
    print(json.dumps(p, indent=2))
    if r is not None:
        try:
            print(json.dumps(r.json(), indent=2))
        except Exception:
            print(r.text)
