# backend/app/create_payout_table.py
import os, sys
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, MetaData, Table
from sqlalchemy.sql import func
from sqlalchemy.exc import SQLAlchemyError

DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///./backend.db"

metadata = MetaData()

payouts = Table(
    "payouts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("txn_id", String(128), unique=True, nullable=False),
    Column("correlation_id", String(128), nullable=True),
    Column("creditor_name", String(255), nullable=False),
    Column("amount", Float, nullable=False),
    Column("currency", String(8), nullable=False, default="USD"),
    Column("pain_xml", Text, nullable=True),
    Column("status", String(32), nullable=False, default="pending"),
    Column("attempts", Integer, nullable=False, default=0),
    Column("gateway_response", Text, nullable=True),
    Column("created_at", DateTime, server_default=func.now()),
)

def main():
    print("Using DATABASE_URL:", DATABASE_URL)
    engine = create_engine(DATABASE_URL, future=True)
    try:
        metadata.create_all(engine)
        print("Created (or verified) payouts table.")
    except SQLAlchemyError as e:
        print("Failed to create payouts table:", e)
        sys.exit(2)

if __name__ == "__main__":
    main()
