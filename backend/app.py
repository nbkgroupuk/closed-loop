# backend/app.py
"""
Minimal Payout backend for Render deployment.
Provides:
- POST /payout         -> enqueue payout job, return job_id
- GET  /payout/{job_id}-> get job status
- POST /internal/job_result -> worker posts result (txhash/status)
- GET  /health
- WS  /ws/{client_id}  -> web socket for notifications
Uses SQLite for persistence (file: payouts.db).
"""
import os
import uuid
import json
import sqlite3
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Optional

DATABASE = os.environ.get("PAYOUT_DB", "payouts.db")
app = FastAPI(title="Payout Backend")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for now allow all, tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DB helpers (simple SQLite) ---
def init_db():
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jobs(
      job_id TEXT PRIMARY KEY,
      merchant_id TEXT,
      to_address TEXT,
      amount REAL,
      card_ending TEXT,
      status TEXT,
      txhash TEXT,
      created_at REAL
    )""")
    conn.commit()
    return conn

DB = init_db()

def db_insert_job(job_id, merchant_id, to_address, amount, card_ending):
    cur = DB.cursor()
    cur.execute("INSERT INTO jobs(job_id, merchant_id, to_address, amount, card_ending, status, txhash, created_at) VALUES (?,?,?,?,?,?,?,strftime('%s','now'))",
                (job_id, merchant_id, to_address, amount, card_ending, "queued", None))
    DB.commit()

def db_get_job(job_id):
    cur = DB.cursor()
    cur.execute("SELECT job_id, merchant_id, to_address, amount, card_ending, status, txhash, created_at FROM jobs WHERE job_id=?", (job_id,))
    r = cur.fetchone()
    if not r: return None
    return {
        "job_id": r[0],
        "merchant_id": r[1],
        "to_address": r[2],
        "amount": r[3],
        "card_ending": r[4],
        "status": r[5],
        "txhash": r[6],
        "created_at": r[7]
    }

def db_update_job_result(job_id, status, txhash):
    cur = DB.cursor()
    cur.execute("UPDATE jobs SET status=?, txhash=? WHERE job_id=?", (status, txhash, job_id))
    DB.commit()

def db_pop_queued(limit=10):
    # Used by worker polling fallback; returns list of queued job dicts
    cur = DB.cursor()
    cur.execute("SELECT job_id, merchant_id, to_address, amount, card_ending FROM jobs WHERE status='queued' ORDER BY created_at LIMIT ?", (limit,))
    rows = cur.fetchall()
    jobs = []
    for r in rows:
        jobs.append({"job_id": r[0], "merchant_id": r[1], "to_address": r[2], "amount": r[3], "card_ending": r[4]})
        cur.execute("UPDATE jobs SET status='processing' WHERE job_id=?", (r[0],))
    DB.commit()
    return jobs

# --- Pydantic models ---
class PayoutRequest(BaseModel):
    merchant_id: str
    to_address: str
    amount: float
    card_ending: Optional[str] = None

class InternalJobResult(BaseModel):
    job_id: str
    txhash: Optional[str] = None
    status: str  # "success" or "failed"

# --- WebSocket client registry ---
WS_CLIENTS: Dict[str, WebSocket] = {}  # client_id -> websocket

async def notify_client(client_id: str, payload: dict):
    ws = WS_CLIENTS.get(client_id)
    if not ws:
        return
    try:
        await ws.send_json(payload)
    except Exception:
        WS_CLIENTS.pop(client_id, None)

# --- Routes ---
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/internal/queued")
async def internal_queued(limit: int = 10):
    cur = DB.cursor()
    cur.execute("SELECT job_id, merchant_id, to_address, amount, card_ending FROM jobs WHERE status='queued' ORDER BY created_at LIMIT ?", (limit,))
    rows = cur.fetchall()
    jobs = []
    for r in rows:
        jobs.append({"job_id": r[0], "merchant_id": r[1], "to_address": r[2], "amount": r[3], "card_ending": r[4]})
        cur.execute("UPDATE jobs SET status='processing' WHERE job_id=?", (r[0],))
    DB.commit()
    return {"jobs": jobs}

@app.post("/payout")
async def create_payout(req: PayoutRequest, background: BackgroundTasks):
    # create job_id and store
    job_id = str(uuid.uuid4())
    db_insert_job(job_id, req.merchant_id, req.to_address, req.amount, req.card_ending or "")
    # background worker could be used here to notify an external queue
    # but we return immediately with job_id; frontend should listen on WS for payout.result
    return {"approved": True, "de39": "00", "job_id": job_id, "txhash": None}

@app.get("/payout/{job_id}")
async def get_payout(job_id: str):
    job = db_get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"found": True, "job": job}

@app.post("/internal/job_result")
async def internal_job_result(body: InternalJobResult):
    # Worker posts results here once tx is broadcast and/or mined
    job = db_get_job(body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    status = "success" if body.status == "success" else "failed"
    db_update_job_result(body.job_id, status, body.txhash)
    # notify merchant client via WS; merchant_id used as client_id in this simple mapping
    payload = {"type": "payout.result", "job_id": body.job_id, "txhash": body.txhash, "status": status}
    # send to merchant client_id if connected
    await notify_client(job["merchant_id"], payload)
    return {"ok": True}

@app.websocket("/ws/{client_id}")
async def ws_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    WS_CLIENTS[client_id] = websocket
    try:
        while True:
            msg = await websocket.receive_text()
            # simple echo or ping handling (clients can request job status)
            try:
                data = json.loads(msg)
                if data.get("type") == "status" and data.get("job_id"):
                    j = db_get_job(data["job_id"])
                    await websocket.send_json({"type": "payout.status", "job": j})
            except Exception:
                # ignore malformed
                pass
    except WebSocketDisconnect:
        WS_CLIENTS.pop(client_id, None)
    except Exception:
        WS_CLIENTS.pop(client_id, None)
