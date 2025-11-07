# processor/app/create_tables.py
import logging
import os
import sqlite3
from sqlalchemy import create_engine
from app.models import Base

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("create_tables")


def normalize_url_for_sync(url: str) -> str:
    """
    Convert an input DATABASE_URL (maybe sqlite+aiosqlite:///...) into a sync
    sqlite URL that SQLAlchemy create_engine() will actually write to disk.

    Important: for an absolute path like /app/processor_debug.db we must return
    sqlite:////app/processor_debug.db (4 slashes).
    """
    if not url:
        return "sqlite:////app/processor_debug.db"
    # If user passed sqlite+aiosqlite:///..., convert to sqlite:///...
    url = url.replace("+aiosqlite", "")
    # If path part is absolute (starts with sqlite:/// /something) ensure 4 slashes
    # - if url starts with sqlite:/// and the next char is '/' we need 4 slashes
    #   to indicate absolute path: sqlite:////absolute/path.db
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///"):]
        # absolute path will start with "/" ; if so build sqlite:////{path}
        if path.startswith("/"):
            return "sqlite:////" + path.lstrip("/")
        # else it was relative; keep sqlite:///relative/path
        return "sqlite:///" + path
    return url


def ensure_file(path: str):
    # Ensure parent directory exists and touch file (creating zero-byte file) so
    # subsequent sqlite opens use the same file.
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    # Touch file
    open(path, "a").close()


def print_sqlite_info(path: str):
    if not os.path.exists(path):
        log.warning("sqlite file does not exist: %s", path)
        return
    log.info("Opening sqlite file at %s", path)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [r[0] for r in cur.fetchall()]
    log.info("sqlite .tables -> %s", tables)
    for t in tables:
        cur.execute(f"PRAGMA table_info({t});")
        cols = cur.fetchall()
        log.info("schema for %s -> %s", t, cols)
    cur.close()
    conn.close()


def main():
    raw = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///app/processor_debug.db")
    sync_url = normalize_url_for_sync(raw)
    log.info("Using sync DB URL for create_all: %s", sync_url)

    # If the sync_url points to a local file (sqlite:/// or sqlite:////), resolve path
    db_path = None
    if sync_url.startswith("sqlite:///"):
        # sqlite:///something  -> something (relative) or /absolute when we normalized
        # We only log when absolute path begins with /.
        # If 4 slashes form sqlite:////abs/path, strip prefix to get absolute path
        if sync_url.startswith("sqlite:////"):
            db_path = "/" + sync_url[len("sqlite:////") :].lstrip("/")
        else:
            # relative path
            db_path = sync_url[len("sqlite:///") :]

    if db_path:
        log.info("Resolved DB path -> %s", db_path)
        ensure_file(db_path)
    else:
        log.info("No local sqlite path detected in URL; proceeding.")

    # create engine and create tables (sync)
    engine = create_engine(sync_url, echo=False)
    # drop/create to ensure schema matches
    log.info("Dropping all tables (if any)...")
    Base.metadata.drop_all(bind=engine)
    log.info("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    log.info("SQLAlchemy drop/create completed.")

    # Verify by opening same file with Python sqlite3 (if it's a file)
    if db_path:
        print_sqlite_info(db_path)
    else:
        log.info("Skipping sqlite file verification (not a file-backed sqlite URL).")


if __name__ == "__main__":
    main()
