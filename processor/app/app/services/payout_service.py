# processor/app/app/services/payout_service.py
import json
import logging
import datetime
import uuid
from typing import Tuple, Optional

from sqlalchemy import text
from sqlalchemy.sql import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import Result

from app.storage.db import AsyncSessionLocal  # should exist in your processor app
from app.storage import models as storage_models  # local SQLAlchemy models (if needed)

LOG = logging.getLogger("app.app.services.payout_service")


async def _insert_transaction_if_missing(session, tx_id: str, merchant_id: str, amount: float, currency: str, protocol: str) -> None:
    """
    Insert a minimal transaction row if it doesn't already exist.
    This provides a valid FK target for payouts.
    """
    now = datetime.datetime.utcnow()
    # Use parameterized SQL to avoid ORM import mismatch issues
    insert_sql = text(
        """
        INSERT INTO transactions (
            id, merchant_id, amount, currency, pan_mask, expiry, status, protocol,
            de39, de38, gateway_txn_id, correlation_id, idempotency_key, meta, created_at, updated_at
        ) VALUES (
            :id, :merchant_id, :amount, :currency, :pan_mask, :expiry, :status, :protocol,
            :de39, :de38, :gateway_txn_id, :correlation_id, :idempotency_key, :meta, :created_at, :updated_at
        )
        ON CONFLICT (id) DO NOTHING
        """
    )

    params = {
        "id": tx_id,
        "merchant_id": merchant_id,
        "amount": amount,
        "currency": currency,
        "pan_mask": "0000",     # placeholder mask for payouts (no PAN)
        "expiry": "",           # unknown for payouts
        "status": "PENDING",
        "protocol": protocol or "unknown",
        "de39": None,
        "de38": None,
        "gateway_txn_id": None,
        "correlation_id": str(uuid.uuid4()),
        "idempotency_key": None,
        "meta": json.dumps({}),
        "created_at": now,
        "updated_at": now,
    }
    await session.execute(insert_sql, params)


async def create_or_get_payout(
    session_factory: AsyncSessionLocal,
    merchant_id: str,
    method: str,
    amount: float,
    currency: str,
    protocol: str,
    auth_code: str,
    payout_payload: dict,
    reference: Optional[str] = None,
) -> Tuple[dict, bool]:
    """
    Create a payout (or return existing by external_ref).
    Returns (payout_row_dict_or_None, created_bool).
    """
    reference = reference or f"payout-{int(datetime.datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6]}"
    payout_type = "CRYPTO" if method.lower() == "crypto" else "BANK"

    async with session_factory() as session:
        async with session.begin():
            # Make sure there's a transaction record referenced by the payout.
            txn_id = str(uuid.uuid4())
            try:
                await _insert_transaction_if_missing(
                    session,
                    tx_id=txn_id,
                    merchant_id=merchant_id,
                    amount=amount,
                    currency=currency,
                    protocol=protocol or "unknown",
                )
            except Exception as e:
                LOG.exception("failed to ensure transaction row exists: %s", e)
                raise

            # Build payout payload (store the original payload JSON)
            payload_json = json.dumps({
                "merchant_id": merchant_id,
                "method": method,
                "amount": amount,
                "currency": currency,
                "protocol": protocol,
                "auth_code": auth_code,
                **payout_payload,
                "reference": reference,
            })

            insert_sql = text(
                """
                INSERT INTO payouts (
                  id, transaction_id, merchant_id, type, status, payload, external_ref,
                  attempts, error_msg, created_at, updated_at
                ) VALUES (
                  :id, :transaction_id, :merchant_id, :type, :status, CAST(:payload AS json), :external_ref,
                  0, NULL, :created_at, :updated_at
                )
                ON CONFLICT (external_ref) DO NOTHING
                RETURNING id, transaction_id, external_ref, status, payload, created_at, updated_at
                """
            )

            now = datetime.datetime.utcnow()
            params = {
                "id": str(uuid.uuid4()),
                "transaction_id": txn_id,
                "merchant_id": merchant_id,
                "type": payout_type,
                "status": "PENDING",
                "payload": payload_json,
                "external_ref": reference,
                "created_at": now,
                "updated_at": now,
            }

            try:
                result: Result = await session.execute(insert_sql, params)
                row = result.fetchone()
                if row:
                    payout_row = dict(row._mapping)
                    LOG.info("payout created (reference=%s id=%s)", reference, payout_row.get("id"))
                    return payout_row, True

                # If ON CONFLICT occurred, fetch existing payout by external_ref
                fetch_sql = text(
                    "SELECT id, transaction_id, external_ref, status, payload, created_at, updated_at FROM payouts WHERE external_ref = :external_ref"
                )
                got = await session.execute(fetch_sql, {"external_ref": reference})
                existing = got.fetchone()
                if existing:
                    LOG.info("payout already exists (reference=%s id=%s)", reference, existing._mapping.get("id"))
                    return dict(existing._mapping), False

                # Unexpected: no row returned and no existing found
                LOG.warning("payout not created and not found (reference=%s)", reference)
                return {}, False

            except IntegrityError as ie:
                LOG.exception("DB integrity error creating payout: %s", ie)
                raise
            except Exception as exc:
                LOG.exception("unexpected error creating payout: %s", exc)
                raise
