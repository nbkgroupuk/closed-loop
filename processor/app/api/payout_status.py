from fastapi import APIRouter, HTTPException
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional

router = APIRouter(prefix="/payout", tags=["payout"])

# DB path relative to repository/container layout -> /app/app/processor_debug.db
DB_PATH = Path(__file__).resolve().parents[2] / "app" / "processor_debug.db"

def _fetch_txn(txn_id: str) -> Optional[Dict[str, Any]]:
    db = str(DB_PATH)
    conn = sqlite3.connect(db, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, reference, merchant_id, method, amount, currency, txn_id, status, created_ts
            FROM payouts
            WHERE txn_id = ?
            LIMIT 1
            """,
            (txn_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()

@router.get("/status/{txn_id}")
def payout_status(txn_id: str):
    """
    Return payout status for a given txn_id (reads local processor_debug.db).
    """
    rec = _fetch_txn(txn_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Not Found")

    # stable response shape
    return {
        "txn_id": rec.get("txn_id"),
        "reference": rec.get("reference"),
        "merchant_id": rec.get("merchant_id"),
        "method": rec.get("method"),
        "amount": rec.get("amount"),
        "currency": rec.get("currency"),
        "status": rec.get("status"),
        "created_ts": rec.get("created_ts"),
    }
