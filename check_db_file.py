# processor/check_db_file.py
import os
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("check_db_file")

path = "/app/processor_debug.db"
if not os.path.exists(path):
    log.info("DB file exists inside container at %s -> False", path)
else:
    log.info("DB file exists inside container at %s -> True", path)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [r[0] for r in cur.fetchall()]
    log.info("Tables: %s", tables)
    for t in tables:
        cur.execute(f"PRAGMA table_info({t});")
        cols = cur.fetchall()
        log.info("schema for %s -> %s", t, cols)
    cur.close()
    conn.close()
