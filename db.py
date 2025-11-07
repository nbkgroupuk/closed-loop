"""DB helper: SQLAlchemy wrapper that uses DATABASE_URL or falls back to SQLite file.
Provides insert_settlement(record: dict).
"""
import os, json, datetime
from sqlalchemy import create_engine, Table, Column, Integer, String, Float, MetaData, Text, DateTime, select, UniqueConstraint
from sqlalchemy.exc import IntegrityError

DATABASE_URL = os.environ.get('DATABASE_URL') or 'sqlite:////app/data/settlements.db'
# ensure data dir exists for sqlite fallback
if DATABASE_URL.startswith('sqlite:'):
    os.makedirs('/app/data', exist_ok=True)

engine = create_engine(DATABASE_URL, echo=False, future=True)
metadata = MetaData()

settlement_table = Table(
    'settlement_tx_map', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('ts', DateTime, nullable=False),
    Column('merchant_id', String(128)),
    Column('terminal_id', String(64)),
    Column('stan', String(32)),
    Column('rrn', String(64)),
    Column('masked_pan', String(64)),
    Column('protocol', String(64)),
    Column('amount', Float),
    Column('signed_tx_hash', String(128), unique=True, nullable=True),
    Column('signed_by', String(66)),
    Column('note', Text),
    Column('raw_json', Text),
    UniqueConstraint('stan', 'rrn', name='uq_stan_rrn')
)

def init_db():
    metadata.create_all(engine)

def insert_settlement(rec: dict):
    """Insert dict  into DB. Returns True if inserted, False if duplicate/ignored."""
    # Normalize rec
    r = dict(rec)
    # ensure ts is a datetime
    if isinstance(r.get('ts'), str):
        try:
            from datetime import datetime
            r['ts'] = datetime.fromisoformat(r['ts'].replace('Z',''))
        except Exception:
            r['ts'] = datetime.utcnow()
    if 'raw' not in r:
        r['raw'] = json.dumps(rec)
    ins = settlement_table.insert().values(
        ts = r.get('ts'),
        merchant_id = r.get('merchant_id'),
        terminal_id = r.get('terminal_id'),
        stan = r.get('stan'),
        rrn = r.get('rrn'),
        masked_pan = r.get('masked_pan'),
        protocol = r.get('protocol'),
        amount = r.get('amount'),
        signed_tx_hash = r.get('signed_tx_hash'),
        signed_by = r.get('signed_by'),
        note = r.get('note'),
        raw_json = r.get('raw')
    )
    with engine.connect() as conn:
        try:
            conn.execute(ins)
            conn.commit()
            return True
        except IntegrityError:
            # duplicate key (signed_tx_hash or stan/rrn); ignore
            return False
        except Exception as e:
            # bubble up for caller to log
            raise

# initialize when imported
try:
    init_db()
except Exception as e:
    # avoid import-time hard failure; callers should handle errors but this logs to /tmp
    with open('/tmp/db_init_error.log','a') as f:
        f.write(repr(e)+'\n')
