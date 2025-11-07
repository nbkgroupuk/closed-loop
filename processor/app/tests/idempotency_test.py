# processor/app/tests/idempotency_test.py
import asyncio
import json
import os
import sys
from pathlib import Path

# allow importing local app package when /app is a mounted read-only path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import get_session
from app.services.payout_service import create_or_get_payout

async def _worker(reference):
    async with get_session() as session:
        payout, created = await create_or_get_payout(
            session=session,
            merchant_id="test_merchant",
            method="bank",
            amount=1.0,
            currency="USD",
            protocol="101",
            auth_code="test",
            payload={"foo": "bar"},
            reference=reference,
        )
        return (reference, getattr(payout, "id", None), created)

async def run_test(concurrency=10, reference="idempotency-test-concurrent"):
    tasks = [asyncio.create_task(_worker(reference)) for _ in range(concurrency)]
    results = await asyncio.gather(*tasks)
    print("RESULTS:")
    for r in results:
        print(r)

if __name__ == "__main__":
    concurrency = int(os.environ.get("CONCURRENCY", "10"))
    reference = os.environ.get("REFERENCE", "idempotency-test-concurrent")
    asyncio.run(run_test(concurrency=concurrency, reference=reference))
