# app/workers/outbox_processor.py
import asyncio
from sqlalchemy import text
from app.storage.db import get_session

BATCH_SIZE = 10

async def process_outbox():
    async for db in get_session():
        rows = await db.execute(text("""
            UPDATE outbox
            SET
              status = 'processing',
              locked_until = NOW() + INTERVAL '30 seconds'
            WHERE id IN (
              SELECT id FROM outbox
              WHERE status = 'received'
              AND (locked_until IS NULL OR locked_until < NOW())
              ORDER BY created_at
              LIMIT :limit
              FOR UPDATE SKIP LOCKED
            )
            RETURNING id, target, payload
        """), {"limit": BATCH_SIZE})

        events = rows.fetchall()

        for event_id, target, payload in events:
            try:
                # 👉 PLACE BUSINESS LOGIC HERE
                print(f"Processing {target} event {payload['id']}")

                await db.execute(text("""
                    UPDATE outbox
                    SET status = 'done'
                    WHERE id = :id
                """), {"id": event_id})

            except Exception:
                await db.execute(text("""
                    UPDATE outbox
                    SET
                      status = 'received',
                      retry_count = retry_count + 1,
                      locked_until = NOW() + INTERVAL '1 minute'
                    WHERE id = :id
                """), {"id": event_id})

        await db.commit()

async def main():
    while True:
        await process_outbox()
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
