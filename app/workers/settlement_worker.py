# backend/app/workers/settlement_worker.py

import asyncio
import json
import logging

from sqlalchemy import select, update

from app.storage.db import AsyncSessionLocal
from app.storage.models import Outbox

logger = logging.getLogger("settlement-worker")


async def run_once():
    """
    Consume PENDING settlement outbox events and mark them PROCESSED.
    """

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Outbox)
            .where(Outbox.target == "settlement")
            .where(Outbox.status == "PENDING")
            .order_by(Outbox.created_at)
            .limit(10)
        )

        rows = result.scalars().all()

        if not rows:
            logger.info("No settlement events to process")
            return

        for row in rows:
            payload = row.payload

            logger.info(
                "Processing settlement event: id=%s event=%s payment_intent=%s",
                row.id,
                payload.get("event"),
                payload.get("payment_intent_id"),
            )

            # 👉 Here is where ISO / crypto will come later

            row.status = "PROCESSED"
            session.add(row)

        await session.commit()
        logger.info("Processed %d settlement events", len(rows))


if __name__ == "__main__":
    asyncio.run(run_once())
