# app/payouts/crypto_erc20.py
# NOTE: this is a minimal stub showing how to integrate web3.py;
# for production you must secure private keys in a vault/HSM and use a provider.
from web3 import Web3
from typing import Dict
import os
import logging

logger = logging.getLogger(__name__)

INFURA_URL = os.getenv("INFURA_URL", None)

def send_erc20_transfer(private_key: str, to_address: str, token_address: str, amount_wei: int, gas: int = 200_000):
    if not INFURA_URL:
        raise RuntimeError("INFURA_URL not configured")
    w3 = Web3(Web3.HTTPProvider(INFURA_URL))
    acct = w3.eth.account.from_key(private_key)
    # token minimal transfer ABI
    erc20_abi = [{"constant":False,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}]
    token = w3.eth.contract(address=w3.toChecksumAddress(token_address), abi=erc20_abi)
    nonce = w3.eth.get_transaction_count(acct.address)
    tx = token.functions.transfer(w3.toChecksumAddress(to_address), amount_wei).buildTransaction({
        "from":acct.address, "nonce":nonce, "gas":gas, "gasPrice":w3.toWei("5","gwei")
    })
    signed = acct.sign_transaction(tx)
    txhash = w3.eth.send_raw_transaction(signed.rawTransaction)
    logger.info("erc20 sent %s", txhash.hex())
    return txhash.hex()
