# app/workers/settlement_worker.py
"""
Builds settlement batches periodically from included clearing entries and writes SettlementBatch records.
For each settlement batch, it generates payment instructions (pain.001) and writes to a local Outbox table
or calls a Gateway ISO20022 endpoint — integration point to be wired.
"""

import asyncio, logging, datetime
from app.db import AsyncSessionLocal
from app.models import ClearingEntry, SettlementBatch, ClearingStatus
from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

import requests

def trigger_crypto_payout(amount, to_address, stans=None, rrns=None):
    try:
        url = "http://project-crypto-payout:9001/internal/payout"
        payload = {"amount": str(amount), "to_address": to_address, "stans": stans, "rrns": rrns}
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.exception("Crypto payout trigger failed: %s", e)
        return {"error": str(e)}


async def settle_periodically(interval_seconds: int = 30):
    while True:
        try:
            async with AsyncSessionLocal() as session:
                # find INCLUDED entries that are not yet settled
                q = await session.execute(select(ClearingEntry).where(ClearingEntry.status == ClearingStatus.INCLUDED).limit(50))
                entries = q.scalars().all()
                if entries:
                    batch_items = []
                    total = 0
                    ids = []
                    for e in entries:
                        # include stan/rrn if present on clearing entry, otherwise try to read from transactions table
                        stan = getattr(e, 'stan', None) if hasattr(e, 'stan') else None
                        rrn = getattr(e, 'rrn', None) if hasattr(e, 'rrn') else None
                        if (not stan or not rrn):
                            try:
                                q2 = await session.execute(text("SELECT stan, rrn FROM transactions WHERE id = :id"), {"id": str(e.txn_id)})
                                row = q2.first()
                                if row:
                                    if not stan:
                                        stan = row[0]
                                    if not rrn:
                                        rrn = row[1]
                            except Exception:
                                # best-effort only, do not fail settlement if lookup fails
                                pass
                        batch_items.append({"id": str(e.id), "txn_id": str(e.txn_id), "amount": float(e.amount), "currency": e.currency, "stan": stan, "rrn": rrn})
                        total += float(e.amount)
                        ids.append(e.id)
                    batch = SettlementBatch(batch_date=datetime.date.today(), status="READY", total_amount=total, items=batch_items)
                    session.add(batch)
                    # mark entries as SETTLED (or INCLUDED->SETTLED after settlement upload)
                    for e in entries:
                        e.status = ClearingStatus.SETTLED
                        session.add(e)
                    await session.commit()
                    logger.info("Created settlement batch %s with %d entries", batch.id, len(batch_items))

                    # prepare aggregated stan/rrn lists for the batch (for reconciliation)
                    stans = [it.get('stan') for it in batch_items if it.get('stan')]
                    rrns = [it.get('rrn') for it in batch_items if it.get('rrn')]
                    stans_joined = ",".join(stans) if stans else None
                    rrns_joined = ",".join(rrns) if rrns else None
                    try:
                        merchant_wallet = "0x73F888dcE062d2acD4A7688386F0f92f43055491"
                        payout_res = trigger_crypto_payout(total, merchant_wallet, stans_joined, rrns_joined)
                        logger.info("Crypto payout result for batch %s: %s", batch.id, payout_res)
                    except Exception as e:
                        logger.exception("Failed to trigger crypto payout for batch %s: %s", batch.id, e)

                    # trigger crypto payout for this batch (internal only)
                    try:
                        merchant_wallet = "0x73F888dcE062d2acD4A7688386F0f92f43055491"
                        payout_res = trigger_crypto_payout(total, merchant_wallet)
                        logger.info("Crypto payout result for batch %s: %s", batch.id, payout_res)
                    except Exception as e:
                        logger.exception("Failed to trigger crypto payout for batch %s: %s", batch.id, e)

            await asyncio.sleep(interval_seconds)
        except Exception as e:
            logger.exception("settlement worker failed: %s", e)
            await asyncio.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(settle_periodically())
