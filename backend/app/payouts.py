# backend/app/payouts.py
import asyncio
import httpx
import logging
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.storage.db import AsyncSessionLocal  # adjust import if your project uses different path
from app.models_payout import Payout, PayoutStatus
from datetime import datetime

logger = logging.getLogger("backend.payouts")

# Config: gateway host/port as used by your gateway service (from env)
import os
GATEWAY_BASE = os.environ.get("GATEWAY_BASE", "http://gateway:8000")  # container name in compose
GATEWAY_PAYOUT_PATH = os.environ.get("GATEWAY_PAYOUT_PATH", "/payout")
GATEWAY_URL = GATEWAY_BASE.rstrip("/") + GATEWAY_PAYOUT_PATH

# Retry/backoff config
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 1.0  # seconds, exponential

async def create_or_get_payout(txn_id: str, correlation_id: Optional[str], amount: str,
                               currency: str, creditor_name: str, pain_xml: str) -> Payout:
    """
    Create a Payout row if txn_id not present (idempotency). If present, return existing row.
    """
    async with AsyncSessionLocal() as session:
        # Try to find existing
        q = await session.execute(select(Payout).where(Payout.txn_id == txn_id))
        existing = q.scalars().first()
        if existing:
            logger.debug("Found existing payout %s status=%s", txn_id, existing.status)
            return existing

        # Create new
        p = Payout(
            txn_id=txn_id,
            correlation_id=correlation_id,
            amount=str(amount),
            currency=str(currency),
            creditor_name=creditor_name,
            pain_xml=pain_xml,
            status=PayoutStatus.CREATED,
            attempts=0,
        )
        session.add(p)
        try:
            await session.commit()
            await session.refresh(p)
            logger.info("Created payout %s", txn_id)
            return p
        except IntegrityError:
            await session.rollback()
            q = await session.execute(select(Payout).where(Payout.txn_id == txn_id))
            return q.scalars().first()

async def _update_payout(session, payout: Payout, **fields):
    for k, v in fields.items():
        setattr(payout, k, v)
    payout.updated_at = datetime.utcnow()
    session.add(payout)
    await session.commit()
    await session.refresh(payout)
    return payout

async def send_payout_to_gateway(payout: Payout, timeout: float = 15.0) -> Dict[str, Any]:
    """
    Attempt to send the pain XML to the gateway /payout.
    Updates the payout record with status/attempts/gateway_response.
    Returns the gateway response dict (may be empty).
    """
    client = httpx.AsyncClient(timeout=timeout)
    url = GATEWAY_URL
    payload = {
        "txn_id": payout.txn_id,
        "correlation_id": payout.correlation_id,
        "pain_xml": payout.pain_xml,
        "amount": payout.amount,
        "currency": payout.currency,
        "creditor_name": payout.creditor_name,
    }

    async with AsyncSessionLocal() as session:
        # mark sending
        payout.attempts += 1
        payout.status = PayoutStatus.SENDING
        session.add(payout)
        await session.commit()
        await session.refresh(payout)

    last_exc = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            logger.info("Payout %s attempt %d -> %s", payout.txn_id, attempt, url)
            resp = await client.post(url, json=payload)
            text = resp.text or ""
            # try parse json response
            try:
                j = resp.json()
            except Exception:
                j = {"status_code": resp.status_code, "text": text}

            # update DB
            async with AsyncSessionLocal() as session:
                from sqlalchemy import update
                payout.status = PayoutStatus.SENT if resp.status_code in (200,201,202) else PayoutStatus.FAILED
                payout.gateway_response = j
                payout.last_error = None if resp.status_code in (200,201,202) else f"HTTP {resp.status_code}"
                payout.attempts = attempt
                session.add(payout)
                await session.commit()
                await session.refresh(payout)

            logger.info("Payout %s gateway responded status=%s", payout.txn_id, resp.status_code)
            await client.aclose()
            return j

        except Exception as exc:
            last_exc = exc
            logger.warning("Payout %s attempt %d failed: %s", payout.txn_id, attempt, repr(exc))
            # update attempts & last_error
            async with AsyncSessionLocal() as session:
                payout.attempts = attempt
                payout.last_error = repr(exc)
                payout.status = PayoutStatus.FAILED
                session.add(payout)
                await session.commit()
                await session.refresh(payout)
            if attempt < RETRY_ATTEMPTS:
                await asyncio.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
                continue
            else:
                await client.aclose()
                raise

    await client.aclose()
    # if we get here raise last exception
    if last_exc:
        raise last_exc
    return {}
