# app/workers/recon_worker.py
"""
Reconciliation worker: compares settlement batches with bank statements and marks exceptions.
This is a skeleton to be extended for real camt.053 parsing and pacs.002 handling.
"""

import asyncio, logging
from app.db import AsyncSessionLocal
from app.models import SettlementBatch, ProcessorEvent
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

async def recon_loop(poll_seconds: int = 60):
    while True:
        async with AsyncSessionLocal() as session:
            # skeleton: simply emit an event
            ev = ProcessorEvent(topic="recon.heartbeat", payload={"ts": str(asyncio.get_event_loop().time())})
            session.add(ev)
            await session.commit()
        await asyncio.sleep(poll_seconds)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(recon_loop())
