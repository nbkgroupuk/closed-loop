# backend/app/workers/crypto_payout_worker.py

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.storage.db import AsyncSessionLocal
from app.storage.models import Outbox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crypto_payout_worker")

POLL_LIMIT = 10
LOCK_SECONDS = 60


async def run():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Outbox)
            .where(Outbox.target == "crypto")          # ✅ FIXED
            .where(Outbox.status == "PENDING")
            .where(
                (Outbox.locked_until.is_(None))
                | (Outbox.locked_until < datetime.utcnow())
            )
            .order_by(Outbox.created_at)
            .limit(POLL_LIMIT)
        )

        rows = result.scalars().all()

        if not rows:
            logger.info("No crypto payout jobs found")
            return

        for row in rows:
            try:
                # 🔒 lock row
                row.locked_until = datetime.utcnow() + timedelta(seconds=LOCK_SECONDS)
                session.add(row)
                await session.flush()

                payload = row.payload or {}
                mode = payload.get("mode", "live")

                logger.info(
                    "🚀 Crypto payout | mode=%s amount=%s asset=%s to=%s",
                    mode,
                    payload.get("amount"),
                    payload.get("asset"),
                    payload.get("to_address"),
                )

                if mode == "dry_run":
                    # ✅ SIMULATION ONLY
                    payload["tx_hash"] = f"dryrun_{row.id}"
                    row.payload = payload
                    row.status = "COMPLETED"

                else:
                    # 🔴 REAL PAYOUT (NOT ENABLED YET)
                    raise RuntimeError("Live crypto payouts not enabled")

                session.add(row)

            except Exception as e:
                logger.exception("❌ Crypto payout failed: %s", e)
                row.status = "FAILED"
                row.retry_count += 1
                session.add(row)

        await session.commit()
        logger.info("✅ Crypto payout worker cycle finished")


if __name__ == "__main__":
    asyncio.run(run())
