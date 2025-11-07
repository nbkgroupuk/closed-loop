import sqlite3, os
db="/app/processor_debug.db"
print("Opening DB:", db, "exists?", os.path.exists(db))
sql = """
CREATE TABLE IF NOT EXISTS clearing_entries (
  id TEXT PRIMARY KEY,
  txn_id TEXT NOT NULL,
  amount REAL NOT NULL,
  currency TEXT NOT NULL,
  merchant_id TEXT,
  status TEXT,
  raw_iso TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
# ensure parent dir exists (sqlite file will be created inside container)
try:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.executescript(sql)
    conn.commit()
    cur.close()
    conn.close()
    print("OK: clearing_entries table ensured in", db)
except Exception as e:
    print("ERROR:", e)
    raise
