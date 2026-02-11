# project/crypto-payout/app/worker.py
import asyncio
import os
import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

POLL_INTERVAL = 5
LOCK_SECONDS = 30
MAX_RETRIES = 5


async def process_crypto_job(session, row):
    """
    DRY-RUN crypto payout processor
    NO blockchain broadcast
    SAFE for production
    """

    payload = row["payload"]
    mode = payload.get("mode", "live")

    if mode != "dry_run":
        raise RuntimeError("Live payouts are disabled")

    fake_tx_hash = f"dryrun_{uuid.uuid4().hex}"

    payload["tx_hash"] = fake_tx_hash
    payload["processed_at"] = datetime.utcnow().isoformat()

    await session.execute(
        text("""
            UPDATE outbox
            SET
                status = 'COMPLETED',
                payload = :payload,
                locked_until = NULL,
                updated_at = NOW()
            WHERE id = :id
        """),
        {
            "id": row["id"],
            "payload": json.dumps(payload),
        }
    )


async def worker_loop():
    print("🚀 Crypto payout worker started")

    while True:
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        text("""
                            SELECT *
                            FROM outbox
                            WHERE
                                target = 'crypto'
                                AND status = 'PENDING'
                                AND (locked_until IS NULL OR locked_until < NOW())
                            ORDER BY created_at
                            LIMIT 1
                            FOR UPDATE SKIP LOCKED
                        """)
                    )

                    row = result.mappings().first()

                    if not row:
                        await asyncio.sleep(POLL_INTERVAL)
                        continue

                    await session.execute(
                        text("""
                            UPDATE outbox
                            SET locked_until = NOW() + INTERVAL '30 seconds'
                            WHERE id = :id
                        """),
                        {"id": row["id"]}
                    )

                async with session.begin():
                    try:
                        await process_crypto_job(session, row)
                    except Exception as e:
                        retries = (row["retry_count"] or 0) + 1

                        status = "FAILED" if retries >= MAX_RETRIES else "PENDING"

                        await session.execute(
                            text("""
                                UPDATE outbox
                                SET
                                    status = :status,
                                    retry_count = :retry_count,
                                    locked_until = NULL,
                                    updated_at = NOW()
                                WHERE id = :id
                            """),
                            {
                                "id": row["id"],
                                "status": status,
                                "retry_count": retries,
                            }
                        )

                        print(f"❌ Crypto job failed ({retries}): {e}")

        except Exception as fatal:
            print("🔥 Worker fatal error:", fatal)

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(worker_loop())
