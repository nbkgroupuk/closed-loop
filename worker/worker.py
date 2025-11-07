# worker/worker.py
import os
import time
import requests
import json
import binascii
from web3 import Web3
from eth_account import Account

# CONFIG
BACKEND_BASE = os.environ.get("BACKEND_BASE", "https://api.blackrock.yourdomain")
GATEWAY_SIGN_URL = os.environ.get("GATEWAY_SIGN_URL")  # e.g. http://gateway.internal/sign (optional)
GATEWAY_BROADCAST_URL = os.environ.get("GATEWAY_BROADCAST_URL")  # e.g. http://gateway.internal/broadcast or use Infura
INFURA_URL = os.environ.get("INFURA_URL")  # fallback broadcast
WORKER_POLL_INTERVAL = int(os.environ.get("WORKER_POLL_INTERVAL", "5"))
WORKER_PRIVKEY = os.environ.get("WORKER_PRIVKEY")  # optional local signing key
CHAIN_ID = int(os.environ.get("CHAIN_ID", "1"))

w3 = Web3(Web3.HTTPProvider(INFURA_URL)) if INFURA_URL else None

def fetch_queued_jobs():
    # Simple approach: backend exposes GET /internal/queued (not implemented above).
    # If not available, use DB polling on VPS or implement endpoint; here we call GET /payout/scan (not present).
    # Instead we use GET /payout/{job_id} only when job ids are known. So fallback: call a lightweight API you add.
    # For now, we will poll via a simple "list queued" endpoint if you add it; otherwise use DB on same filesystem.
    resp = requests.get(f"{BACKEND_BASE}/internal/queued")  # recommend you add this endpoint
    if resp.status_code != 200:
        return []
    return resp.json().get("jobs", [])

def sign_and_broadcast_local(to_address, amount_eth, nonce=None, gas_price_gwei=None, privkey=None):
    # Local sign + broadcast via Infura
    acct = Account.from_key(privkey)
    value_wei = int(amount_eth * 10**18)
    gas_price = int(gas_price_gwei * 10**9) if gas_price_gwei else int(w3.eth.gas_price)
    if nonce is None:
        nonce = w3.eth.get_transaction_count(acct.address, "pending")
    tx = {
        "nonce": nonce,
        "to": to_address,
        "value": value_wei,
        "gas": 21000,
        "gasPrice": gas_price,
        "chainId": CHAIN_ID,
    }
    signed = Account.sign_transaction(tx, privkey)
    raw = signed.rawTransaction.hex()
    # broadcast
    txhash = w3.eth.send_raw_transaction(bytes.fromhex(raw[2:] if raw.startswith("0x") else raw)).hex()
    return txhash

def broadcast_raw_with_infura(raw_hex):
    payload = {"jsonrpc":"2.0","method":"eth_sendRawTransaction","params":[raw_hex],"id":1}
    headers = {"Content-Type":"application/json"}
    # use INFURA_URL or GATEWAY_BROADCAST_URL
    url = INFURA_URL
    r = requests.post(INFURA_URL, json=payload, headers=headers, timeout=30)
    if r.status_code == 200:
        j = r.json()
        if "result" in j:
            return j["result"]
        else:
            raise Exception(f"Broadcast error: {j}")
    else:
        raise Exception(f"Broadcast HTTP error {r.status_code}: {r.text}")

def process_job(job):
    job_id = job["job_id"]
    to_addr = job["to_address"]
    amount = job["amount"]
    merchant_id = job["merchant_id"]

    try:
        # Prefer gateway signing if available
        if GATEWAY_SIGN_URL:
            # ask gateway to return signed raw tx (it should accept JSON {to, amount, job_id})
            r = requests.post(GATEWAY_SIGN_URL, json={"to": to_addr, "amount": amount, "job_id": job_id}, timeout=30)
            r.raise_for_status()
            signed_hex = r.json().get("signed_raw_tx")
            if not signed_hex:
                raise Exception("gateway sign returned no signed_raw_tx")
            # broadcast via gateway or directly
            if GATEWAY_BROADCAST_URL:
                br = requests.post(GATEWAY_BROADCAST_URL, json={"signed_tx_hex": signed_hex}, timeout=30)
                br.raise_for_status()
                txhash = br.json().get("txhash") or br.json().get("result")
            else:
                txhash = broadcast_raw_with_infura(signed_hex)
        else:
            # local sign & broadcast
            if not WORKER_PRIVKEY:
                raise Exception("No signing method available (set GATEWAY_SIGN_URL or WORKER_PRIVKEY)")
            txhash = sign_and_broadcast_local(to_addr, float(amount), privkey=WORKER_PRIVKEY)
        # report back success
        post = requests.post(f"{BACKEND_BASE}/internal/job_result", json={"job_id": job_id, "txhash": txhash, "status": "success"}, timeout=10)
        post.raise_for_status()
        print("Job", job_id, "broadcasted:", txhash)
    except Exception as e:
        try:
            requests.post(f"{BACKEND_BASE}/internal/job_result", json={"job_id": job_id, "txhash": None, "status": "failed"}, timeout=10)
        except:
            pass
        print("Job", job_id, "failed:", str(e))

def main_loop():
    print("Worker starting, polling backend for queued jobs...")
    while True:
        try:
            # This relies on you adding GET /internal/queued on backend which returns queued jobs.
            r = requests.get(f"{BACKEND_BASE}/internal/queued", timeout=10)
            if r.status_code == 200:
                jobs = r.json().get("jobs", [])
            else:
                jobs = []
            if not jobs:
                time.sleep(WORKER_POLL_INTERVAL)
                continue
            for job in jobs:
                process_job(job)
        except Exception as e:
            print("Worker poll error:", e)
            time.sleep(WORKER_POLL_INTERVAL)

if __name__ == "__main__":
    main_loop()
