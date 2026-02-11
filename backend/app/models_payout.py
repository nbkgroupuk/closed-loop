# backend/app/models_payout.py
import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Enum, Text, JSON
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class PayoutStatus(str, enum.Enum):
    CREATED = "created"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"

class Payout(Base):
    __tablename__ = "payouts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    txn_id = Column(String, unique=True, nullable=False)  # idempotency key (from client)
    correlation_id = Column(String, index=True, nullable=True)
    amount = Column(String, nullable=False)
    currency = Column(String, nullable=False)
    creditor_name = Column(String, nullable=True)
    pain_xml = Column(Text, nullable=False)
    stan = Column(String, nullable=True)
    rrn = Column(String, nullable=True)
    status = Column(Enum(PayoutStatus), default=PayoutStatus.CREATED, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    gateway_response = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)
