import sqlite3, json, sys
db = "/app/processor_debug.db"
try:
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute("PRAGMA table_info(processor_events)")
    cols = cur.fetchall()
    print("processor_events columns (cid,name,type,notnull,dflt_value,pk):")
    print(json.dumps(cols, indent=2))
    con.close()
except Exception as e:
    print("ERROR:", e)
    sys.exit(2)
