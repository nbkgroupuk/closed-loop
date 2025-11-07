# processor/app/models.py
from datetime import datetime
from uuid import uuid4
import enum

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Numeric,
    Index,
    Enum as SAEnum,
    Integer,
    JSON,
    ForeignKey,
    TIMESTAMP,
)
from sqlalchemy.orm import declarative_base

# single Base used across the file
Base = declarative_base()


class ClearingStatus(str, enum.Enum):
    INCLUDED = "INCLUDED"
    SETTLED = "SETTLED"
    FAILED = "FAILED"


class ClearingEntry(Base):
    __tablename__ = "clearing_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    txn_id = Column(String(36), nullable=False, default=lambda: str(uuid4()), index=True)
    amount = Column(Numeric(18, 6), nullable=False)
    currency = Column(String(8), nullable=False)
    merchant_id = Column(String(64), nullable=True)
    status = Column(
        SAEnum(ClearingStatus, name="clearing_status", native_enum=False),
        nullable=False,
        default=ClearingStatus.INCLUDED,
    )
    raw_iso = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ClearingEntry id={self.id} txn_id={self.txn_id} amount={self.amount} {self.currency} status={self.status}>"


class ProcessorEvent(Base):
    __tablename__ = "processor_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    topic = Column(String(128), nullable=False, index=True)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ProcessorEvent id={self.id} topic={self.topic} created_at={self.created_at}>"


Index("ix_clearing_txn_id", ClearingEntry.txn_id)
Index("ix_event_topic", ProcessorEvent.topic)


# -------------------------
# Payout model (uses same Base above)
# -------------------------
class Payout(Base):
    __tablename__ = "payouts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=False)
    merchant_id = Column(String(64), nullable=False, index=True)
    type = Column(String(64), nullable=False)  # payouttype enum in DB
    status = Column(String(64), nullable=False)  # payoutstatus enum in DB
    payload = Column(JSON)
    external_ref = Column(String(256), unique=False)
    attempts = Column(Integer, default=0)
    error_msg = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Payout id={self.id} txn={self.transaction_id} ref={self.external_ref} status={self.status}>"
