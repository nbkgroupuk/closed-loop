# app/server_admin.py
"""
A small admin HTTP server exposing /health and a JSON API for events (for external monitoring).
You can run it alongside iso_listener.
"""

from fastapi import FastAPI
from app.telemetry import configure_logging
from app.config import settings
from app.db import AsyncSessionLocal
from app.models import ProcessorEvent
from sqlalchemy import select
from fastapi.responses import JSONResponse

logger = configure_logging(settings.LOG_LEVEL)
app = FastAPI(title=settings.APP_NAME + " Admin")

@app.get("/health")
async def health():
    return {"status":"ok"}

@app.get("/events")
async def events(limit: int = 50):
    async with AsyncSessionLocal() as session:
        q = await session.execute(select(ProcessorEvent).order_by(ProcessorEvent.created_at.desc()).limit(limit))
        rows = q.scalars().all()
        return JSONResponse([{"id": str(r.id), "topic": r.topic, "payload": r.payload, "created_at": r.created_at.isoformat()} for r in rows])
