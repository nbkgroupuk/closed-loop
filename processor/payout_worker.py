# project/processor/payout_worker.py
import os, time, requests
from web3 import Web3

GATEWAY = os.getenv("GATEWAY_URL", "http://project-gateway:8000")  # internal DNS from compose
RPC_URL = os.getenv("RPC_URL")                     # e.g. https://mainnet.infura.io/v3/XXXX
PRIVATE_KEY = os.getenv("PAYOUT_PRIVATE_KEY")      # NEVER commit; pass via env
TOKEN = os.getenv("USDT_ADDRESS")                  # USDT contract address
DECIMALS = int(os.getenv("USDT_DECIMALS", "6"))
FROM_ADDR = os.getenv("FROM_ADDRESS")              # payout wallet (must match the private key)

# Minimal ERC20 ABI (balanceOf + transfer)
ERC20_ABI = [
  {"constant": False, "inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],
   "name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"},
  {"constant": True, "inputs":[{"name":"_owner","type":"address"}],
   "name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
token = w3.eth.contract(address=Web3.to_checksum_address(TOKEN), abi=ERC20_ABI)

def to_units(amount):
    return int(round(float(amount) * (10 ** DECIMALS)))

def broadcast(job):
    to_addr = job.get("to_address") or FROM_ADDR  # fallback to merchant’s default
    amount = job.get("amount", 0)
    if not to_addr or not amount:
        raise RuntimeError("missing to_address or amount")

    nonce = w3.eth.get_transaction_count(FROM_ADDR)
    tx = token.functions.transfer(Web3.to_checksum_address(to_addr), to_units(amount)).build_transaction({
        "from": FROM_ADDR,
        "nonce": nonce,
        "gas": 90000,
        "maxFeePerGas": w3.to_wei("30", "gwei"),
        "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
    })
    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction).hex()
    return tx_hash

def run():
    while True:
        # poll queued jobs
        # in a real system you’d consume from a queue; here we just scan last N job ids if you keep them
        # or receive job ids via HTTP callback. For demo we just sleep.
        time.sleep(3)

# You will likely call broadcast() from your processor entrypoint when you receive a new job id.
# Example handler:
def handle_job(job_id):
    job = requests.get(f"{GATEWAY}/payout/{job_id}").json()
    try:
        tx_hash = broadcast(job)
        requests.post(f"{GATEWAY}/payout/{job_id}/broadcast", json={
            "status": "success",
            "txhash": tx_hash
        })
    except Exception as e:
        requests.post(f"{GATEWAY}/payout/{job_id}/broadcast", json={
            "status": "failed",
            "message": str(e)
        })

