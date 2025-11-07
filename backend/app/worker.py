# app/worker.py
"""
Simple outbox consumer loop. For Render Background Worker you can run:
python -m app.worker
"""
import asyncio
import logging
from app.storage.db import AsyncSessionLocal
from sqlalchemy import select, update
from app.storage.models import Outbox, Payout, PayoutStatus
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.config import settings
from app.gateway_client import gateway_client
from app.ws import ConnectionManager

logger = logging.getLogger(__name__)
ws_manager = ConnectionManager()

async def process_outbox_item(session: AsyncSession, item: Outbox):
    try:
        # route by target
        if item.target == "iso20022":
            # call Gateway /iso20022
            xml = item.payload.get("xml").encode("utf-8")
            resp = await gateway_client.send_iso20022(xml)
            return {"ok": True, "resp": resp}
        elif item.target == "crypto_send":
            # for this minimal worker we just mark as sent; real worker calls web3 client
            return {"ok": True, "resp": {"tx":"stubbed_tx_hash"}}
        else:
            return {"ok": False, "error": "unknown target"}
    except Exception as e:
        logger.exception("outbox failed")
        return {"ok": False, "error": str(e)}

async def worker_loop(poll_seconds: int = 2):
    while True:
        async with AsyncSessionLocal() as session:
            q = await session.execute(select(Outbox).where(Outbox.status=="PENDING").limit(5))
            rows = q.scalars().all()
            for item in rows:
                # lock by updating status to IN_PROGRESS
                item.status = "IN_PROGRESS"
                await session.commit()
                res = await process_outbox_item(session, item)
                if res.get("ok"):
                    item.status = "SENT"
                else:
                    item.retry_count = (item.retry_count or 0) + 1
                    item.status = "FAILED" if item.retry_count > 5 else "PENDING"
                session.add(item)
                await session.commit()
        await asyncio.sleep(poll_seconds)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker_loop())
