# gateway/app/server.py
import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import time
log = logging.getLogger("gateway.server")
logging.basicConfig(level=logging.INFO)

# Allow localhost frontend
ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

from fastapi import FastAPI, Request
from fastapi import FastAPI
from app.payouts_iso20022 import router as iso20022_router

app = FastAPI(title="Gateway Service")

app.include_router(iso20022_router)

@app.post("/transactions")
async def transactions(req: Request):
    data = await req.json()
    # ... construct ISO, send to processor ...
    return {"received": True, "data": data}

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health(request: Request):
    origin = request.headers.get("origin")
    resp = JSONResponse({"status": "ok", "service": "gateway"})
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
    return resp

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    origin = ws.headers.get("origin")
    if origin not in ALLOWED_ORIGINS:
        log.warning(f"Rejected WS connection from {origin}")
        await ws.close(code=4003)
        return

    await ws.accept()
    log.info(f"Accepted WS connection from {origin}")
    try:
        while True:
            msg = await ws.receive_text()
            if msg.lower() == "ping":
                await ws.send_text("pong")
            else:
                await ws.send_text(f"echo: {msg}")
    except WebSocketDisconnect:
        log.info("WS disconnected")