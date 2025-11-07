#docker exec project-gateway /bin/sh -c 'cat > /app/crypto_payout_engine.py <<'"'"'PY'"'"'
"""
crypto_payout_engine.py

Safe, opinionated helper to convert a settlement into a crypto payout (USDT ERC-20 on Ethereum-compatible chains).
Provides a single function:

    process_settlement_and_trigger(settlement: dict, dry_run: bool = True) -> dict

Expected settlement dict keys:
    - wallet: destination address (hex, e.g. "0xabc...")
    - amount_minor: integer amount in minor units (e.g. USDT with 6 decimals -> cents * 10^4; here we assume amount_minor is already in token minor units)
    - token_contract (optional): ERC-20 contract address for token (default: USDT placeholder)
    - chain (optional): name or chain id for logging (not used to pick RPC automatically)

Behavior:
    - Performs validation.
    - Converts to token human amount for logs.
    - If dry_run is True: returns a payload with estimated gas, prepared tx dict, but does NOT sign or send.
    - If dry_run is False: uses WEB3_RPC, PRIVATE_KEY, FROM_ADDRESS env vars to sign & send the tx.
    - Requires 'web3' package to be installed in the container to actually send.

Environment variables required to broadcast:
    - WEB3_RPC (e.g. https://mainnet.infura.io/v3/...)
    - PRIVATE_KEY (hex, no 0x prefix OR with)
    - FROM_ADDRESS (address corresponding to private key)

Security: keep PRIVATE_KEY out of logs and out of source control.
"""
from __future__ import annotations
import os
import decimal
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("crypto_payout_engine")
logger.setLevel(logging.INFO)

# default token: USDT (placeholder) — replace with your actual contract address per network
DEFAULT_USDT_CONTRACT = os.environ.get("DEFAULT_USDT_CONTRACT", "0xdAC17F958D2ee523a2206206994597C13D831ec7")  # mainnet USDT

DECIMALS = int(os.environ.get("TOKEN_DECIMALS", "6"))  # USDT usually 6

def _validate_address(addr: str) -> bool:
    return isinstance(addr, str) and addr.startswith("0x") and len(addr) == 42

def _to_human(amount_minor: int, decimals: int = DECIMALS) -> str:
    q = decimal.Decimal(amount_minor) / (decimal.Decimal(10) ** decimals)
    # normalize to string
    return format(q.normalize(), "f")

def _load_web3():
    try:
        from web3 import Web3, HTTPProvider
        from web3.middleware import geth_poa_middleware
    except Exception as e:
        raise RuntimeError("web3 package is required to broadcast transactions. Install with `pip install web3`") from e
    rpc = os.environ.get("WEB3_RPC")
    if not rpc:
        raise RuntimeError("WEB3_RPC environment variable not set (RPC endpoint required to broadcast)")
    w3 = Web3(HTTPProvider(rpc, request_kwargs={"timeout": 20}))
    # add POA middleware optionally if using BSC/other chain with POA
    if os.environ.get("WEB3_POWEROA", "false").lower() in ("1", "true", "yes"):
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    if not w3.isConnected():
        raise RuntimeError(f"Could not connect to RPC at {rpc}")
    return w3

def _prepare_erc20_transfer_data(token_contract: str, to_addr: str, amount_minor: int) -> bytes:
    """
    Build calldata for ERC-20 transfer(to, amount).
    Uses keccak and abi-encoded method id + params, but web3 can also do via Contract.functions.transfer().
    We'll return calldata to put into transaction.
    """
    try:
        from eth_abi import encode_single, encode_abi
        from eth_utils import keccak, to_checksum_address
    except Exception:
        # we will purposely keep a friendly fallback to use web3 Contract if available
        return b""
    # method id for transfer(address,uint256) -> keccak("transfer(address,uint256)")[:4]
    method_hash = keccak(text="transfer(address,uint256)")[:4]
    to_checksum = to_checksum_address(to_addr)
    # encode parameters
    # eth_abi encode_abi expects (types, values)
    encoded = encode_abi(["address", "uint256"], [to_checksum, amount_minor])
    return method_hash + encoded

def process_settlement_and_trigger(settlement: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
    """
    settlement: {
        "wallet": "0xabc...",
        "amount_minor": 1000000,   # integer minor units (token decimals)
        "token_contract": "0x..."  # optional, default uses DEFAULT_USDT_CONTRACT
    }
    dry_run: if True, do not send — just return prepared payload and estimates
    returns: dict with keys: status, prepared_tx, estimate, tx_hash (if sent), message
    """
    # validation
    if not isinstance(settlement, dict):
        raise ValueError("settlement must be a dict")
    wallet = settlement.get("wallet")
    amount_minor = settlement.get("amount_minor")
    token_contract = settlement.get("token_contract") or DEFAULT_USDT_CONTRACT

    if not wallet or not _validate_address(wallet):
        raise ValueError("invalid or missing wallet address")
    if not isinstance(amount_minor, int) or amount_minor <= 0:
        raise ValueError("amount_minor must be a positive integer (token minor units)")

    human_amount = _to_human(amount_minor, decimals=int(os.environ.get("TOKEN_DECIMALS", DECIMALS)))
    logger.info("Preparing payout -> wallet=%s amount=%s token=%s", wallet, human_amount, token_contract)

    # Build prepared transaction using web3 to estimate gas (if available)
    prepared = {
        "to": token_contract,
        "value": 0,  # ERC-20 transfer uses data only
        "data": None,
        "gas": None,
        "gasPrice": None,
        "nonce": None,
        "chain_specific": {
            "decimals": int(os.environ.get("TOKEN_DECIMALS", DECIMALS))
        }
    }

    try:
        w3 = _load_web3()
    except Exception as e:
        # if web3 not available or RPC missing, still return prepared payload for dry-run usage.
        prepared["data"] = None
        prepared["message"] = f"web3 unavailable or RPC not configured: {e}"
        return {"status": "prepared", "dry_run": dry_run, "prepared": prepared, "amount_human": human_amount}

    # prefer to use Contract API if possible
    try:
        from web3 import Web3
        token = w3.eth.contract(address=w3.toChecksumAddress(token_contract), abi=[
            # minimal ABI with transfer
            {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
             "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
        ])
        calldata = token.encodeABI(fn_name="transfer", args=[w3.toChecksumAddress(wallet), int(amount_minor)])
    except Exception as e:
        # fallback: try low-level build of calldata
        try:
            calldata = _prepare_erc20_transfer_data(token_contract, wallet, int(amount_minor)).hex()
            if calldata == "":
                raise RuntimeError("could not prepare calldata")
        except Exception:
            raise RuntimeError(f"Failed to prepare calldata for ERC20 transfer: {e}")

    # base tx
    from_addr = os.environ.get("FROM_ADDRESS")
    if not from_addr:
        raise RuntimeError("FROM_ADDRESS env var must be set to the sender address for on-chain txs")

    prepared["data"] = calldata
    prepared["to"] = token_contract
    prepared["value"] = 0

    # fill dynamic fields: nonce, gasPrice
    nonce = w3.eth.get_transaction_count(w3.toChecksumAddress(from_addr))
    prepared["nonce"] = nonce

    # gas price or maxFee/maxPriority depending on network; we'll try gasPrice first
    gas_price = None
    try:
        gas_price = w3.eth.gas_price
        prepared["gasPrice"] = int(gas_price)
    except Exception:
        prepared["gasPrice"] = None

    # estimate gas
    try:
        estimate_tx = {
            "from": w3.toChecksumAddress(from_addr),
            "to": w3.toChecksumAddress(token_contract),
            "data": calldata,
            "value": 0
        }
        gas_est = w3.eth.estimate_gas(estimate_tx)
        # add small buffer
        gas_est_buffered = int(gas_est * 1.2)
        prepared["gas"] = gas_est_buffered
    except Exception as e:
        # If estimate fails, return prepared info and let caller decide
        prepared["gas"] = None
        prepared["estimate_error"] = str(e)

    # dry-run: return prepared payload, do not sign/send
    if dry_run:
        logger.info("Dry-run prepared: nonce=%s gas=%s gasPrice=%s", prepared.get("nonce"), prepared.get("gas"), prepared.get("gasPrice"))
        return {"status": "prepared", "dry_run": True, "prepared": prepared, "amount_human": human_amount}

    # live send path
    priv = os.environ.get("PRIVATE_KEY")
    if not priv:
        raise RuntimeError("PRIVATE_KEY env var not set — cannot sign transaction")

    # sign & send
    try:
        tx = {
            "nonce": prepared["nonce"],
            "to": w3.toChecksumAddress(prepared["to"]),
            "value": int(prepared["value"]),
            "data": bytes.fromhex(prepared["data"][2:]) if prepared["data"].startswith("0x") else bytes.fromhex(prepared["data"]),
        }
        if prepared.get("gas"):
            tx["gas"] = int(prepared["gas"])
        if prepared.get("gasPrice"):
            tx["gasPrice"] = int(prepared["gasPrice"])
        # sign
        acct = w3.eth.account.from_key(priv if priv.startswith("0x") else "0x" + priv)
        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        tx_hex = tx_hash.hex()
        logger.info("Broadcasted tx %s -> %s (%s %s)", tx_hex, wallet, amount_minor, prepared["chain_specific"])
        return {"status": "sent", "tx_hash": tx_hex, "amount_human": human_amount}
    except Exception as e:
        logger.exception("Failed to sign/send tx")
        raise RuntimeError(f"Failed to send tx: {e}")

# convenience alias
def trigger_from_card_settlement(settlement_record: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
    """
    Backwards-compatible alias used by higher-level code.
    """
    return process_settlement_and_trigger(settlement_record, dry_run=dry_run)

# When this file is executed directly, show a short self-test (dry run)
if __name__ == "__main__":
    test = {
        "wallet": os.environ.get("TEST_WALLET", "0x000000000000000000000000000000000000dEaD"),
        "amount_minor": int(os.environ.get("TEST_AMOUNT_MINOR", "1000000")),
    }
    try:
        out = process_settlement_and_trigger(test, dry_run=True)
        print(json.dumps(out, indent=2))
    except Exception as e:
        print("ERROR:", e)
#PY' && docker restart project-gateway
