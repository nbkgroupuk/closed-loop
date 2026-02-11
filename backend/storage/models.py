# project/backend/storage/models.py
from sqlalchemy import Column, Text, JSON, TIMESTAMP, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.storage.db import Base
import uuid

class Outbox(Base):
    __tablename__ = "outbox"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    payload = Column(JSON, nullable=False)
    retry_count = Column(Integer, default=0)
    locked_until = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
