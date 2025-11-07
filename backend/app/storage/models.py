# app/storage/models.py
#from app import models (If models file is at /app/app/models.py)
import enum
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base
import datetime
import uuid

Base = declarative_base()

def now():
    return datetime.datetime.utcnow()

class TxStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"

class PayoutType(enum.Enum):
    BANK = "bank"
    CRYPTO = "crypto"

class PayoutStatus(enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"

class Transaction(Base):
    __tablename__ = "transactions"
    id = sa.Column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    merchant_id = sa.Column(sa.String(64), nullable=False, index=True)
    amount = sa.Column(sa.Numeric(18,2), nullable=False)
    currency = sa.Column(sa.String(8), nullable=False)
    pan_mask = sa.Column(sa.String(8), nullable=False)  # last4 (store masked)
    expiry = sa.Column(sa.String(5), nullable=False)
    status = sa.Column(sa.Enum(TxStatus), default=TxStatus.PENDING, nullable=False)
    protocol = sa.Column(sa.String(64), nullable=False)
    de39 = sa.Column(sa.String(3), nullable=True)
    de38 = sa.Column(sa.String(12), nullable=True)
    gateway_txn_id = sa.Column(sa.String(128), nullable=True)
    correlation_id = sa.Column(sa.String(128), nullable=False, index=True)
    idempotency_key = sa.Column(sa.String(128), nullable=True, index=True)
    meta = sa.Column(sa.JSON, default={})
    created_at = sa.Column(sa.DateTime, default=now)
    updated_at = sa.Column(sa.DateTime, default=now, onupdate=now)

class Payout(Base):
    __tablename__ = "payouts"
    id = sa.Column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = sa.Column(sa.String(36), sa.ForeignKey("transactions.id"), nullable=False, index=True)
    merchant_id = sa.Column(sa.String(64), nullable=False, index=True)
    type = sa.Column(sa.Enum(PayoutType), nullable=False)
    status = sa.Column(sa.Enum(PayoutStatus), default=PayoutStatus.PENDING, nullable=False)
    payload = sa.Column(sa.JSON, default={})
    external_ref = sa.Column(sa.String(256), nullable=True)
    attempts = sa.Column(sa.Integer, default=0)
    error_msg = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime, default=now)
    updated_at = sa.Column(sa.DateTime, default=now, onupdate=now)

class Outbox(Base):
    __tablename__ = "outbox"
    id = sa.Column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    target = sa.Column(sa.String(128), nullable=False)
    payload = sa.Column(sa.JSON, nullable=False)
    status = sa.Column(sa.String(32), default="PENDING", nullable=False, index=True)
    locked_until = sa.Column(sa.DateTime, nullable=True)
    retry_count = sa.Column(sa.Integer, default=0)
    created_at = sa.Column(sa.DateTime, default=now)
    updated_at = sa.Column(sa.DateTime, default=now, onupdate=now)

class EventLog(Base):
    __tablename__ = "event_logs"
    id = sa.Column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    correlation_id = sa.Column(sa.String(128), nullable=False, index=True)
    topic = sa.Column(sa.String(64), nullable=False)
    payload = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime, default=now)
