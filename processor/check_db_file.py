# check_db_file.py
import sqlite3, sys
db = "/app/processor_debug.db"
print("DB file exists inside container at", db)
try:
    conn = sqlite3.connect(db)
except Exception as e:
    print("ERROR connecting:", e)
    sys.exit(1)

cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)
for t in tables:
    print("\nTable:", t)
    cur.execute(f"PRAGMA table_info('{t}');")
    rows = cur.fetchall()
    if not rows:
        print("  (no columns returned)")
    for r in rows:
        # (cid, name, type, notnull, dflt_value, pk)
        print(" ", r)
cur.close()
conn.close()
