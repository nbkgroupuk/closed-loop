# app/workers/crypto_worker.py
"""
A worker that picks payouts (simulated here) and calls an external node or service to broadcast ERC20 TXs.
For demo, it writes events to ProcessorEvent and simulates confirmations.
"""

import asyncio, logging
from app.db import AsyncSessionLocal
from app.models import ProcessorEvent
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

async def crypto_loop(poll_seconds: int = 10):
    while True:
        async with AsyncSessionLocal() as session:
            # placeholder: in a real system, query Payouts table
            # simulate: emit a heartbeat event
            ev = ProcessorEvent(topic="crypto_worker.heartbeat", payload={"ts": str(asyncio.get_event_loop().time())})
            session.add(ev)
            await session.commit()
        await asyncio.sleep(poll_seconds)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crypto_loop())
