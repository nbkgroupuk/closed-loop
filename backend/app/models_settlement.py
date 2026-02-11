# BACKEND/APP/MODELS_SETTLEMENT.PY
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    CHAR,
    TIMESTAMP,
    ForeignKey,
)
from sqlalchemy.orm import relationship

# Try to reuse existing Base from your project; fall back if unavailable
try:
    from app.db import Base  # adjust if your project has a central Base here
except ImportError:
    from sqlalchemy.orm import declarative_base
    Base = declarative_base()


class AuthTransaction(Base):
    __tablename__ = "auth_transactions"

    id = Column(String(36), primary_key=True)
    stan = Column(String(12), nullable=False)
    rrn = Column(String(20), nullable=False)
    merchant_id = Column(String(64), nullable=False)
    terminal_id = Column(String(64), nullable=False)
    scheme = Column(String(16), nullable=False)
    currency = Column(CHAR(3), nullable=False)
    amount_auth = Column(BigInteger, nullable=False)
    auth_code = Column(String(16), nullable=True)
    status = Column(String(16), nullable=False)  # AUTHORIZED, DECLINED, etc.
    protocol = Column(String(16), nullable=True)  # e.g. 101.1, 201.3
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    settlement_items = relationship(
        "SettlementItem",
        back_populates="auth_transaction",
        cascade="all, delete-orphan",
    )


class SettlementItem(Base):
    __tablename__ = "settlement_items"

    id = Column(String(36), primary_key=True)
    auth_tx_id = Column(
        String(36),
        ForeignKey("auth_transactions.id"),
        nullable=False,
    )
    merchant_id = Column(String(64), nullable=False)
    currency = Column(CHAR(3), nullable=False)
    amount_clearing = Column(BigInteger, nullable=False)
    clearing_status = Column(String(16), nullable=False)  # PENDING, SETTLED, etc.
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    auth_transaction = relationship(
        "AuthTransaction",
        back_populates="settlement_items",
    )
