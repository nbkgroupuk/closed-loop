# app/workers/settlement_worker.py
"""
Builds settlement batches periodically from included clearing entries and writes SettlementBatch records.
For each settlement batch, it generates payment instructions (pain.001) and writes to a local Outbox table
or calls a Gateway ISO20022 endpoint — integration point to be wired.
"""

import asyncio, logging, datetime
from app.db import AsyncSessionLocal
from app.models import ClearingEntry, SettlementBatch, ClearingStatus
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

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
                        batch_items.append({"id": str(e.id), "txn_id": str(e.txn_id), "amount": float(e.amount), "currency": e.currency})
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
            await asyncio.sleep(interval_seconds)
        except Exception as e:
            logger.exception("settlement worker failed: %s", e)
            await asyncio.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(settle_periodically())
