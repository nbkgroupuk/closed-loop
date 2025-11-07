# app/ws.py
from fastapi import WebSocket
from typing import Dict, List, Any
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, List[WebSocket]] = {}  # merchant_id -> websockets
        self.lock = asyncio.Lock()

    async def connect(self, merchant_id: str, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.active.setdefault(merchant_id, []).append(websocket)
            logger.info("WS connect %s (%d sockets)", merchant_id, len(self.active[merchant_id]))

    async def disconnect(self, merchant_id: str, websocket: WebSocket):
        async with self.lock:
            if merchant_id in self.active and websocket in self.active[merchant_id]:
                self.active[merchant_id].remove(websocket)
                logger.info("WS disconnect %s (%d)", merchant_id, len(self.active[merchant_id]))

    async def broadcast(self, merchant_id: str, topic: str, payload: dict):
        """
        Sends payload to all sockets for merchant_id. If merchant_id == "*", broadcast to all.
        """
        message = {"topic": topic, "payload": payload}
        msg_text = json.dumps(message, default=str)
        targets = []
        async with self.lock:
            if merchant_id == "*" :
                for lst in self.active.values():
                    targets.extend(lst)
            else:
                targets = list(self.active.get(merchant_id, []))
        for ws in targets:
            try:
                await ws.send_text(msg_text)
            except Exception:
                logger.exception("ws send failed")
