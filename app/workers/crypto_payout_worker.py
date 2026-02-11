# project/app/workers/crypto_payout_worker.py
import asyncio
import os
import logging
from decimal import Decimal

from sqlalchemy import select
from web3 import Web3
from web3.middleware import geth_poa_middleware

from app.storage.db import AsyncSessionLocal
from app.storage.models import Outbox

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")
ETH_RPC_URL = os.getenv("ETH_RPC_URL")
ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")

CHAIN_NAME = "ETH-SEPOLIA"
GAS_LIMIT = 21_000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crypto_payout_worker")

# -------------------------------------------------------------------
# Web3 setup
# -------------------------------------------------------------------

w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

ACCOUNT = w3.eth.account.from_key(ETH_PRIVATE_KEY)
FROM_ADDRESS = ACCOUNT.address

# -------------------------------------------------------------------
# Worker
# -------------------------------------------------------------------

async def process_payout(session, row: Outbox):
    payload = row.payload

    if payload.get("mode") != "dry_run":
        raise RuntimeError("Only dry_run allowed in this worker")

    to_address = Web3.to_checksum_address(payload["to_address"])
    amount_eth = Decimal(payload["amount"])
    value_wei = w3.to_wei(amount_eth, "ether")

    nonce = w3.eth.get_transaction_count(FROM_ADDRESS)

    tx = {
        "nonce": nonce,
        "to": to_address,
        "value": value_wei,
        "gas": GAS_LIMIT,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id,
    }

    signed_tx = w3.eth.account.sign_transaction(tx, ETH_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

    tx_hex = tx_hash.hex()

    payload["tx_hash"] = tx_hex
    payload["from_address"] = FROM_ADDRESS
    payload["chain"] = CHAIN_NAME

    row.payload = payload
    row.status = "SENT_ONCHAIN"

    logger.info(
        "✅ TX SENT | chain=%s tx=%s to=%s amount=%s",
        CHAIN_NAME,
        tx_hex,
        to_address,
        amount_eth,
    )


async def run():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Outbox)
            .where(Outbox.target == "crypto")
            .where(Outbox.status == "PENDING")
            .order_by(Outbox.created_at)
            .with_for_update(skip_locked=True)
        )

        rows = result.scalars().all()

        if not rows:
            logger.info("No crypto payouts pending")
            return

        for row in rows:
            try:
                await process_payout(session, row)
                session.add(row)
            except Exception as e:
                logger.exception("❌ Crypto payout failed")
                row.status = "FAILED"
                session.add(row)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(run())
