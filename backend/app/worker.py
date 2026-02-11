# app/worker.py
"""
Outbox worker.

- target == "iso20022"   -> send XML to Gateway ISO20022 endpoint
- target == "crypto_send" -> send JSON payload to an EXCHANGE withdrawal API (USDT)

Run inside backend container:
  python -m app.worker

You configure the exchange API via env vars:

  EXCHANGE_BASE            = https://api.exchange.com
  EXCHANGE_WITHDRAW_PATH   = /api/v1/withdraw
  EXCHANGE_API_KEY         = ...
  EXCHANGE_API_SECRET      = ...
  EXCHANGE_API_PASSPHRASE  = (optional)
"""

import asyncio
import logging
import os
import json
import time
import hmac
import hashlib
import base64
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.db import AsyncSessionLocal
from app.storage.models import Outbox
from app.gateway_client import gateway_client

logger = logging.getLogger(__name__)

# ---------- Exchange config (env) ----------

EXCHANGE_BASE = os.environ.get("EXCHANGE_BASE", "").rstrip("/")
EXCHANGE_WITHDRAW_PATH = os.environ.get("EXCHANGE_WITHDRAW_PATH", "/api/v1/withdraw")
EXCHANGE_API_KEY = os.environ.get("EXCHANGE_API_KEY", "")
EXCHANGE_API_SECRET = os.environ.get("EXCHANGE_API_SECRET", "")
EXCHANGE_API_PASSPHRASE = os.environ.get("EXCHANGE_API_PASSPHRASE", "")


def _sign_exchange_request(timestamp: str, method: str, path: str, body_str: str) -> str:
    """
    Generic HMAC-SHA256 + base64 signature:
      sig = base64( HMAC_SHA256(secret, timestamp + method + path + body) )

    This pattern is similar to many exchanges (OKX/Bitget-style).
    You MUST adjust to match your actual exchange’s API doc if needed.
    """
    if not EXCHANGE_API_SECRET:
        raise RuntimeError("EXCHANGE_API_SECRET not configured")

    msg = f"{timestamp}{method.upper()}{path}{body_str}"
    digest = hmac.new(
        EXCHANGE_API_SECRET.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


async def send_usdt_exchange_withdrawal(payload: dict) -> dict:
    """
    Send USDT withdrawal to your exchange.

    Expected fields in payload (coming from outbox):
      - amount        (int or str, e.g. 2000 = cents or "20.00")
      - currency      ("USD" etc, you map to asset if needed)
      - asset         (optional, default "USDT")
      - network       (optional, e.g. "TRON" / "ETH" / "BSC")
      - to_address    (destination USDT address)
      - external_id   (optional, use settlement_item_id / auth_tx_id, etc.)

    We build a JSON body the exchange can accept, e.g.:

      {
        "asset": "USDT",
        "network": "TRON",
        "address": "Txxxxx",
        "amount": "20.00",
        "external_id": "5aed86db-..."
      }

    You must align this with your real exchange’s withdrawal schema.
    """
    if not EXCHANGE_BASE or not EXCHANGE_API_KEY or not EXCHANGE_API_SECRET:
        raise RuntimeError("Exchange env vars not fully configured")

    path = EXCHANGE_WITHDRAW_PATH
    url = EXCHANGE_BASE + path

    # amount: we just pass through; upstream can convert cents → decimal
    raw_amount = payload.get("amount")
    if raw_amount is None:
        raise ValueError("payload.amount missing for crypto_send")

    body = {
        "asset": payload.get("asset", "USDT"),
        "network": payload.get("network", "TRON"),  # adjust if you use ERC20/BSC/etc.
        "address": payload["to_address"],           # must be provided in payload
        "amount": str(raw_amount),
        "external_id": payload.get("external_id")
            or payload.get("settlement_item_id")
            or payload.get("auth_tx_id"),
    }

    body_str = json.dumps(body, separators=(",", ":"), sort_keys=True)
    timestamp = str(int(time.time() * 1000))

    signature = _sign_exchange_request(timestamp, "POST", path, body_str)

    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": EXCHANGE_API_KEY,
        "X-SIGNATURE": signature,
        "X-TIMESTAMP": timestamp,
    }
    if EXCHANGE_API_PASSPHRASE:
        headers["X-PASSPHRASE"] = EXCHANGE_API_PASSPHRASE

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, data=body_str, headers=headers)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status_code": resp.status_code, "text": resp.text}


async def process_outbox_item(session: AsyncSession, item: Outbox):
    try:
        payload = item.payload or {}

        # 1) ISO20022 path -> bank PAIN.001
        if item.target == "iso20022":
            xml = (payload.get("xml") or "").encode("utf-8")
            resp = await gateway_client.send_iso20022(xml)
            return {"ok": True, "resp": resp}

        # 2) USDT via exchange withdrawal
        if item.target == "crypto_send":
            resp = await send_usdt_exchange_withdrawal(payload)
            return {"ok": True, "resp": resp}

        # 3) unknown
        return {"ok": False, "error": f"unknown target {item.target}"}

    except Exception as e:
        logger.exception("outbox failed")
        return {"ok": False, "error": str(e)}


async def worker_loop(poll_seconds: int = 2):
    while True:
        async with AsyncSessionLocal() as session:
            q = await session.execute(
                select(Outbox).where(Outbox.status == "PENDING").limit(5)
            )
            rows = q.scalars().all()

            for item in rows:
                # lock item
                item.status = "IN_PROGRESS"
                item.updated_at = datetime.utcnow()
                session.add(item)
                await session.commit()

                res = await process_outbox_item(session, item)

                if res.get("ok"):
                    item.status = "DONE"
                    item.last_error = None
                else:
                    item.retry_count = (item.retry_count or 0) + 1
                    item.status = "FAILED" if item.retry_count > 5 else "PENDING"
                    item.last_error = res.get("error")

                item.updated_at = datetime.utcnow()
                session.add(item)
                await session.commit()

        await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker_loop())
