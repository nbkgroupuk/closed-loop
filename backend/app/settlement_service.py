import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.storage.db import AsyncSessionLocal
from app.models_settlement import AuthTransaction, SettlementItem
from app.storage.models import Outbox


async def create_auth_and_settlement(payload):
    """
    Insert into auth_transactions and settlement_items.
    Returns: (auth_id, settlement_id)
    """
    async with AsyncSessionLocal() as session:
        try:
            # 1) Create auth transaction
            auth_id = str(uuid.uuid4())
            auth_row = AuthTransaction(
                id=auth_id,
                stan=payload.stan,
                rrn=payload.rrn,
                merchant_id=payload.merchant_id,
                terminal_id=payload.terminal_id,
                scheme=payload.scheme,
                currency=payload.currency,
                amount_auth=payload.amount_auth,
                auth_code=payload.auth_code,
                status="AUTHORIZED",
                protocol=getattr(payload, "protocol", None),
            )
            session.add(auth_row)

            # 2) Create settlement item
            settlement_id = str(uuid.uuid4())
            settlement_row = SettlementItem(
                id=settlement_id,
                auth_tx_id=auth_id,
                merchant_id=payload.merchant_id,
                currency=payload.currency,
                amount_clearing=payload.amount_auth,
                clearing_status="PENDING",
            )
            session.add(settlement_row)

            await session.commit()
            return auth_id, settlement_id

        except SQLAlchemyError as e:
            await session.rollback()
            raise e


async def clear_and_enqueue_crypto_payout(
    settlement_item_id: str,
    new_status: str = "CLEARED",
):
    """
    1) Mark settlement_items.clearing_status
    2) Enqueue crypto payout job into outbox (target='crypto_send')
    Returns updated SettlementItem or None if not found.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Load settlement item
            result = await session.execute(
                select(SettlementItem).where(SettlementItem.id == settlement_item_id)
            )
            item = result.scalar_one_or_none()
            if item is None:
                return None

            # Update status
            item.clearing_status = new_status

            # Load auth to enrich payload (stan, rrn, protocol, etc.)
            auth = None
            if item.auth_tx_id:
                res_auth = await session.execute(
                    select(AuthTransaction).where(AuthTransaction.id == item.auth_tx_id)
                )
                auth = res_auth.scalar_one_or_none()

            payload = {
                "kind": "CARD_SETTLEMENT_PAYOUT",
                "settlement_item_id": item.id,
                "auth_tx_id": item.auth_tx_id,
                "merchant_id": item.merchant_id,
                "currency": item.currency,
                "amount": item.amount_clearing,
                "clearing_status": new_status,
            }

            if auth is not None:
                payload.update(
                    {
                        "stan": auth.stan,
                        "rrn": auth.rrn,
                        "scheme": auth.scheme,
                        "protocol": auth.protocol,
                    }
                )

            # Outbox job → handled by worker target "crypto_send"
            outbox_job = Outbox(
                target="crypto_send",
                payload=payload,
                status="PENDING",
            )
            session.add(outbox_job)
            session.add(item)

            await session.commit()
            await session.refresh(item)
            return item

        except SQLAlchemyError as e:
            await session.rollback()
            raise e
