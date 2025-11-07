# processor/check_sqlite_direct.py
import os, sqlite3, sys
p = "/app/processor_debug.db"
print("Exists?", os.path.exists(p))
if not os.path.exists(p):
    sys.exit(0)
conn = sqlite3.connect(p)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)
for t in tables:
    cur.execute(f"PRAGMA table_info({t});")
    print("Columns for", t, ":", cur.fetchall())
cur.close()
conn.close()
