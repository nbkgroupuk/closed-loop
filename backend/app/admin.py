# app/admin.py
"""
Admin dashboard and control endpoints.

Features:
- /admin/dashboard (HTML) : web UI summary (transactions, payouts, MTI log)
- /admin/api/transactions : JSON paged list of transactions (filter by status, protocol)
- /admin/api/payouts : JSON list of payouts
- /admin/api/events : JSON event logs (MTI events)
- /admin/api/merchant/toggle : enable/disable merchant terminal (auditable)
- /admin/api/payout/retry : force retry payout (enqueue outbox)
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from app.storage.db import AsyncSessionLocal
from app.storage.models import Transaction, Payout, Outbox, EventLog, TxStatus
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import datetime
from app.auth import verify_jwt
from app.telemetry.logging import ContextFilter
import logging

logger = logging.getLogger("admin")
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# simple dependency for admin auth: expects Authorization: Bearer <jwt>
def admin_required(token: str = None):
    if not token:
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        payload = verify_jwt(token)
    except Exception:
        raise HTTPException(status_code=403, detail="invalid token")
    roles = payload.get("roles", [])
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="admin role required")
    return payload

@router.get("/admin/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, admin=Depends(admin_required)):
    # provide a small summary
    async with AsyncSessionLocal() as session:
        q = await session.execute(select(Transaction).order_by(Transaction.created_at.desc()).limit(10))
        txs = q.scalars().all()
        q2 = await session.execute(select(Payout).order_by(Payout.created_at.desc()).limit(10))
        payouts = q2.scalars().all()
        q3 = await session.execute(select(EventLog).order_by(EventLog.created_at.desc()).limit(25))
        events = q3.scalars().all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "transactions": txs, "payouts": payouts, "events": events})

@router.get("/admin/api/transactions")
async def admin_transactions(status: Optional[str] = None, limit: int = 50, admin=Depends(admin_required)):
    async with AsyncSessionLocal() as session:
        q = select(Transaction).order_by(Transaction.created_at.desc()).limit(limit)
        if status:
            q = q.where(Transaction.status == TxStatus(status))
        res = await session.execute(q)
        rows = res.scalars().all()
        return JSONResponse([{
            "id": str(r.id), "merchant_id": r.merchant_id, "amount": float(r.amount),
            "currency": r.currency, "status": r.status.value, "de39": r.de39, "de38": r.de38, "created_at": r.created_at.isoformat()
        } for r in rows])

@router.get("/admin/api/payouts")
async def admin_payouts(limit: int = 50, admin=Depends(admin_required)):
    async with AsyncSessionLocal() as session:
        q = await session.execute(select(Payout).order_by(Payout.created_at.desc()).limit(limit))
        rows = q.scalars().all()
        return JSONResponse([{"id": str(r.id), "txn_id": str(r.transaction_id), "type": r.type.value, "status": r.status.value, "payload": r.payload, "external_ref": r.external_ref} for r in rows])

@router.post("/admin/api/payout/retry")
async def admin_payout_retry(payout_id: str = Form(...), admin=Depends(admin_required)):
    async with AsyncSessionLocal() as session:
        q = await session.execute(select(Payout).where(Payout.id==payout_id))
        p = q.scalars().first()
        if not p:
            raise HTTPException(404, "payout not found")
        # create outbox job
        target = "iso20022" if p.type.value == "bank" else "crypto_send"
        out = Outbox(target=target, payload={"payout_id": str(p.id), "transaction_id": str(p.transaction_id)})
        session.add(out)
        await session.commit()
    return RedirectResponse("/admin/dashboard", status_code=303)

@router.post("/admin/api/merchant/toggle")
async def admin_merchant_toggle(merchant_id: str = Form(...), enabled: bool = Form(...), admin=Depends(admin_required)):
    # This is a stub: in your system maintain merchants table and flip a flag
    # Here we just log the action in EventLog
    async with AsyncSessionLocal() as session:
        ev = EventLog(correlation_id=f"admin-{merchant_id}-{datetime.datetime.utcnow().isoformat()}", topic="merchant.toggle", payload={"merchant_id": merchant_id, "enabled": enabled, "by": "admin"})
        session.add(ev)
        await session.commit()
    return RedirectResponse("/admin/dashboard", status_code=303)

@router.get("/admin/api/events")
async def admin_events(limit: int = 100, admin=Depends(admin_required)):
    async with AsyncSessionLocal() as session:
        q = await session.execute(select(EventLog).order_by(EventLog.created_at.desc()).limit(limit))
        rows = q.scalars().all()
        return JSONResponse([{"id": str(r.id), "topic": r.topic, "payload": r.payload, "created_at": r.created_at.isoformat()} for r in rows])
