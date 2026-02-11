from sqlalchemy import Column, String
from app.storage.db import Base

class MerchantSettings(Base):
    __tablename__ = "merchant_settings"

    merchant_id = Column(String, primary_key=True)
    usdt_wallet = Column(String, nullable=True)
    usdt_network = Column(String, nullable=True)
