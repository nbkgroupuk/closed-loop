# processor/app/storage/db.py
import sqlite3
from pathlib import Path
import logging
from typing import Dict, Any

logger = logging.getLogger("processor.storage")

# SQLite DB path -> processor/app/processor_debug.db
DB_PATH = Path(__file__).resolve().parents[1] / "processor_debug.db"

def get_conn():
    """Get a SQLite connection (with row factory)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_db_and_tables():
    """Ensure the payouts table exists."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS payouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT,
            merchant_id TEXT,
            method TEXT,
            amount REAL,
            currency TEXT,
            txn_id TEXT,
            created_ts DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
    finally:
        conn.close()

def insert_payout(data: Dict[str, Any]) -> int:
    """Insert a payout row and return its ID."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO payouts (reference, merchant_id, method, amount, currency, txn_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data.get("reference"),
            data.get("merchant_id"),
            data.get("method"),
            float(data.get("amount") or 0.0),
            data.get("currency"),
            data.get("txn_id")
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
