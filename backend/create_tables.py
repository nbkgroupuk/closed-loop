#!/usr/bin/env python3
"""
create_tables.py - patched for SQLite

- Replaces UUID -> String(36)
- Replaces JSON/JSONB -> Text()
"""

import os, sys, traceback
from sqlalchemy import create_engine, String, Text

# ensure repo root is on sys.path
cwd = os.getcwd()
if cwd not in sys.path:
    sys.path.insert(0, cwd)

def main():
    try:
        from app.storage import models
    except Exception:
        print("ERROR: failed to import app.storage.models.")
        traceback.print_exc()
        return 2

    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./data.db")
    print("Using DATABASE_URL:", db_url)
    sync_url = db_url.replace("+aiosqlite", "")
    print("Sync URL for DDL:", sync_url)

    engine = create_engine(sync_url, connect_args={"check_same_thread": False} if sync_url.startswith("sqlite") else {})

    patched = False
    try:
        print("Attempting to create tables (first try)...")
        models.Base.metadata.create_all(bind=engine)
        print("OK: tables created (no patching required).")
        print("TABLES_CREATED_OK")
        return 0
    except Exception:
        print("create_all failed, attempting type patching...")
        traceback.print_exc()

    # Patch UUID + JSONB -> SQLite friendly
    for tbl in models.Base.metadata.tables.values():
        for col in tbl.columns:
            tname = getattr(col.type, "__class__", type(col.type)).__name__.lower()
            if "uuid" in tname:
                print(f"Patching {tbl.name}.{col.name} ({tname}) -> String(36)")
                col.type = String(36)            # instance
                patched = True
            elif "json" in tname:
                print(f"Patching {tbl.name}.{col.name} ({tname}) -> Text")
                col.type = Text()               # instance
                patched = True

    if not patched:
        print("No UUID/JSONB types found to patch. Aborting.")
        return 4

    try:
        print("Retrying create_all after patch...")
        models.Base.metadata.create_all(bind=engine)
        print("OK: tables created after patching.")
        print("TABLES_CREATED_OK")
        return 0
    except Exception:
        print("ERROR: create_all still failed after patching. Full traceback below:")
        traceback.print_exc()
        return 5

if __name__ == "__main__":
    sys.exit(main())
