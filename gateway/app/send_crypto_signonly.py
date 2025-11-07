#!/usr/bin/env python3
# gateway/app/send_crypto_signonly.py — prepare (and optionally sign & broadcast) an ETH tx
import os, sys, time
print("=== send_crypto_signonly ===")

INFURA_URL = os.environ.get("INFURA_URL")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
TO_ADDRESS = os.environ.get("TO_ADDRESS")
AMOUNT = os.environ.get("AMOUNT")  # in ETH as decimal string, e.g. "0.01"
NETWORK = os.environ.get("NETWORK", "mainnet")
BROADCAST = os.environ.get("BROADCAST", "0")  # "1" to broadcast

for v in ("INFURA_URL","PRIVATE_KEY","TO_ADDRESS","AMOUNT","NETWORK","BROADCAST"):
    print(f"{v}=", os.environ.get(v))

if not INFURA_URL:
    print("ERROR: INFURA_URL not set")
    sys.exit(2)

try:
    from web3 import Web3, HTTPProvider
    from eth_account import Account
except Exception as e:
    print("ERROR: required web3 libraries not installed:", e)
    sys.exit(3)

w3 = Web3(HTTPProvider(INFURA_URL))
try:
    connected = w3.is_connected()
except AttributeError:
    # older/newer compatibility fallback if method name differs
    connected = getattr(w3, "isConnected", lambda: False)()
print("web3 connected:", connected)
if not connected:
    print("WARNING: web3 provider not connected — check INFURA_URL and network access")

# simple demo: show chain id (best effort)
try:
    chain_id = w3.eth.chain_id
    print("chain_id:", chain_id)
except Exception as e:
    print("Could not read chain_id:", e)
    chain_id = None

# Build transaction (unsigned) if TO_ADDRESS + AMOUNT are provided
if not TO_ADDRESS or not AMOUNT:
    print("No TO_ADDRESS or AMOUNT provided — showing connection test only.")
    sys.exit(0)

try:
    to_addr = Web3.to_checksum_address(TO_ADDRESS)
except Exception as e:
    print("Invalid TO_ADDRESS:", e)
    sys.exit(4)

try:
    # must use your account to get nonce. If PRIVATE_KEY not provided, we need a sender
    if PRIVATE_KEY:
        acct = Account.from_key(PRIVATE_KEY)
        sender = acct.address
        print("Using sender (from PRIVATE_KEY):", sender)
    else:
        # fallback: try to fetch a default account from node (rare for Infura)
        sender = None
        print("No PRIVATE_KEY provided; will attempt to estimate nonce from 'sender' if available.")
    # if sender known, get nonce
    if sender:
        nonce = w3.eth.get_transaction_count(sender)
    else:
        print("Cannot determine nonce without PRIVATE_KEY (sender). Provide PRIVATE_KEY to sign.")
        nonce = 0

    value_wei = int(float(AMOUNT) * 10**18)
    # gas price / estimate
    try:
        gas_price = w3.eth.gas_price
    except Exception:
        gas_price = None

    tx = {
        "to": to_addr,
        "value": value_wei,
        "nonce": nonce,
        "chainId": chain_id or 1,
    }

    # try to estimate gas; if fails, use safe default
    try:
        est_gas = w3.eth.estimate_gas({
            "from": sender if sender else to_addr,
            "to": to_addr,
            "value": value_wei,
        })
        tx["gas"] = est_gas
    except Exception as e:
        fallback_gas = 21000
        tx["gas"] = fallback_gas
        print("Gas estimate failed, using fallback:", fallback_gas, "err:", e)

    if gas_price:
        tx["gasPrice"] = gas_price
    else:
        # EIP-1559 style? try maxFee/maxPriority
        try:
            base = w3.eth.get_block("latest").baseFeePerGas
            max_priority = int(2 * 10**9)  # 2 gwei
            max_fee = base + max_priority * 2
            tx["maxPriorityFeePerGas"] = max_priority
            tx["maxFeePerGas"] = max_fee
            # remove gasPrice if present
            tx.pop("gasPrice", None)
            print("Using EIP-1559 fields:", tx["maxFeePerGas"], tx["maxPriorityFeePerGas"])
        except Exception:
            # last fallback
            tx["gasPrice"] = int(30 * 10**9)  # 30 gwei
            print("Using fallback gasPrice:", tx["gasPrice"])

    print("Prepared unsigned tx:")
    for k in ("to","value","nonce","gas","gasPrice","maxFeePerGas","maxPriorityFeePerGas","chainId"):
        if k in tx:
            print(" ", k, "=", tx[k])

    # show raw tx dict
    import json
    print("TX dict JSON:", json.dumps(tx))

    if PRIVATE_KEY:
        signed = Account.sign_transaction(tx, PRIVATE_KEY)
        print("SIGNED RAW TX:", signed.rawTransaction.hex())
        if BROADCAST == "1":
            try:
                tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
                print("BROADCAST OK tx_hash:", w3.to_hex(tx_hash))
            except Exception as e:
                print("Broadcast failed:", e)
        else:
            print("BROADCAST disabled (BROADCAST != '1'). To broadcast set BROADCAST=1")
    else:
        print("No PRIVATE_KEY — cannot sign. To sign set PRIVATE_KEY env var.")
except Exception as e:
    print("Unexpected error building tx:", e)
    sys.exit(10)

print("Done.")
