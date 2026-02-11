# worker/worker.py
import os
import time
import requests
from web3 import Web3
from eth_account import Account

# -----------------------------
# CONFIG
# -----------------------------
BACKEND_BASE = os.environ.get("BACKEND_BASE", "http://backend:8000")
INFURA_URL = os.environ.get("INFURA_URL")
WORKER_PRIVKEY = os.environ.get("WORKER_PRIVKEY")
CHAIN_ID = int(os.environ.get("CHAIN_ID", "1"))
POLL_INTERVAL = int(os.environ.get("WORKER_POLL_INTERVAL", "5"))

if not INFURA_URL:
    raise RuntimeError("INFURA_URL is not set in environment")

if not WORKER_PRIVKEY:
    raise RuntimeError("WORKER_PRIVKEY is not set in environment")

w3 = Web3(Web3.HTTPProvider(INFURA_URL))

# -----------------------------
# SIGN + BROADCAST USDT ERC20
# -----------------------------

ERC20_ABI = [{
    "constant": False,
    "inputs": [
        {"name": "_to", "type": "address"},
        {"name": "_value", "type": "uint256"}
    ],
    "name": "transfer",
    "outputs": [{"name": "", "type": "bool"}],
    "type": "function"
}]

USDT_ADDRESS = Web3.to_checksum_address("0xdAC17F958D2ee523a2206206994597C13D831ec7")
USDT_CONTRACT = w3.eth.contract(address=USDT_ADDRESS, abi=ERC20_ABI)


def send_usdt_tx(to, amount_usdt, privkey):
    """
    Send USDT (ERC20) from WORKER_PRIVKEY to `to` address.
    amount_usdt: float or string, in USDT units (not wei)
    """
    acct = Account.from_key(privkey)

    # Ensure checksum address
    to_checksum = Web3.to_checksum_address(to)

    # USDT has 6 decimals
    usdt_amount = int(round(float(amount_usdt) * 1_000_000))

    # Nonce & gas
    nonce = w3.eth.get_transaction_count(acct.address, "pending")
    gas_price = w3.eth.gas_price

    tx = USDT_CONTRACT.functions.transfer(
        to_checksum,
        usdt_amount
    ).build_transaction({
        "chainId": CHAIN_ID,
        "from": acct.address,
        "nonce": nonce,
        "gas": 90000,
        "gasPrice": gas_price,
    })

    # eth-account ≥0.10 uses .raw_transaction (NOT .rawTransaction)
    signed = acct.sign_transaction(tx)
    raw = signed.raw_transaction  # <--- important fix
    tx_hash = w3.eth.send_raw_transaction(raw)
    return tx_hash.hex()


# -----------------------------
# JOB PROCESSING
# -----------------------------

def process_job(job):
    job_id = job["job_id"]
    to_addr = job["to_address"]
    amount = job["amount"]

    try:
        tx_hash = send_usdt_tx(to_addr, float(amount), WORKER_PRIVKEY)

        # Report success back to backend
        requests.post(
            f"{BACKEND_BASE}/internal/job_result",
            json={"job_id": job_id, "txhash": tx_hash, "status": "success"},
            timeout=10
        )

        print("JOB OK:", job_id, tx_hash)

    except Exception as e:
        print("JOB FAILED:", job_id, str(e))
        try:
            requests.post(
                f"{BACKEND_BASE}/internal/job_result",
                json={"job_id": job_id, "txhash": None, "status": "failed"},
                timeout=10
            )
        except Exception:
            pass


def main_loop():
    print("Worker started — polling backend...")

    while True:
        try:
            r = requests.get(f"{BACKEND_BASE}/internal/queued", timeout=10)
            if r.status_code != 200:
                print("Worker poll error: HTTP", r.status_code, r.text[:200])
                time.sleep(POLL_INTERVAL)
                continue

            jobs = r.json().get("jobs", [])

            for job in jobs:
                process_job(job)

        except Exception as e:
            print("Worker poll error:", str(e))

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()
