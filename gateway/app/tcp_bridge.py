# gateway/app/tcp_bridge.py

"""
gateway/app/tcp_bridge.py

Production-ready async TCP bridge for forwarding ISO8583 frames
from gateway -> processor OR acquirer sandbox.

Routing logic:
- If ACQUIRER_HOST / ACQUIRER_PORT are set → send to acquirer
- Else → fallback to processor
"""

import asyncio
import logging
import ssl
from typing import Optional

from gateway.app.config import settings

log = logging.getLogger("gateway.tcp_bridge")
log.setLevel(logging.INFO)

# ---------------- CONFIG ----------------

PROCESSOR_HOST = settings.PROCESSOR_HOST
PROCESSOR_PORT = settings.PROCESSOR_PORT

ACQUIRER_HOST = settings.ACQUIRER_HOST
ACQUIRER_PORT = settings.ACQUIRER_PORT

USE_TLS = False
TLS_CERT_REQUIRED = False

LENGTH_PREFIX_BYTES = settings.ACQUIRER_MLI or 2

CONNECT_TIMEOUT = 5.0
WRITE_TIMEOUT = 5.0
READ_TIMEOUT = settings.ACQUIRER_TIMEOUT or 10.0

RECONNECT_BASE = 0.5
RECONNECT_MAX = 10.0
QUEUE_MAX = 1000

# ---------------- INTERNAL STATE ----------------

_send_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX)
_bridge_task: Optional[asyncio.Task] = None


# ---------------- HELPERS ----------------

def _length_prefix(data: bytes) -> bytes:
    return len(data).to_bytes(LENGTH_PREFIX_BYTES, "big") + data


def _log_hex(prefix: str, b: bytes):
    try:
        h = b.hex().upper()
        log.debug("%s %s", prefix, " ".join(h[i:i+64] for i in range(0, len(h), 64)))
    except Exception:
        pass


# ---------------- CONNECTION ----------------

class ISOConnection:
    def __init__(self):
        if ACQUIRER_HOST and ACQUIRER_PORT:
            self.host = ACQUIRER_HOST
            self.port = ACQUIRER_PORT
            self.target = "ACQUIRER"
        else:
            self.host = PROCESSOR_HOST
            self.port = PROCESSOR_PORT
            self.target = "PROCESSOR"

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = asyncio.Event()

    async def connect(self):
        backoff = RECONNECT_BASE
        while True:
            try:
                log.info("[ISO] connecting to %s (%s:%s)", self.target, self.host, self.port)
                if USE_TLS:
                    ctx = ssl.create_default_context()
                    if not TLS_CERT_REQUIRED:
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                    self._reader, self._writer = await asyncio.wait_for(
                        asyncio.open_connection(self.host, self.port, ssl=ctx),
                        timeout=CONNECT_TIMEOUT,
                    )
                else:
                    self._reader, self._writer = await asyncio.wait_for(
                        asyncio.open_connection(self.host, self.port),
                        timeout=CONNECT_TIMEOUT,
                    )

                self._connected.set()
                log.info("[ISO] connected to %s", self.target)
                return
            except Exception as e:
                log.warning("[ISO] connect failed (%s): %s", self.target, e)
                await asyncio.sleep(backoff)
                backoff = min(RECONNECT_MAX, backoff * 2)

    async def close(self):
        try:
            if self._writer:
                self._writer.close()
                await self._writer.wait_closed()
        finally:
            self._reader = None
            self._writer = None
            self._connected.clear()

    async def send_frame(self, payload: bytes) -> Optional[bytes]:
        if not self._writer or self._writer.is_closing():
            await self.connect()

        framed = _length_prefix(payload)
        _log_hex("TX", framed)

        try:
            self._writer.write(framed)
            await asyncio.wait_for(self._writer.drain(), timeout=WRITE_TIMEOUT)

            prefix = await asyncio.wait_for(
                self._reader.readexactly(LENGTH_PREFIX_BYTES), timeout=READ_TIMEOUT
            )
            length = int.from_bytes(prefix, "big")
            data = await asyncio.wait_for(
                self._reader.readexactly(length), timeout=READ_TIMEOUT
            )

            _log_hex("RX", prefix + data)
            return data

        except Exception as e:
            log.warning("[ISO] IO error: %s", e)
            await self.close()
            return None


# ---------------- BRIDGE LOOP ----------------

async def _bridge_loop():
    log.info("[ISO] TCP bridge started")
    conn = ISOConnection()

    while True:
        payload = await _send_queue.get()
        try:
            if not isinstance(payload, (bytes, bytearray)):
                raise ValueError("ISO payload must be bytes")

            if not conn._connected.is_set():
                await conn.connect()

            resp = await conn.send_frame(bytes(payload))
            if resp is None:
                log.warning("[ISO] empty response")
        except Exception as e:
            log.exception("[ISO] forwarding error: %s", e)
        finally:
            _send_queue.task_done()


def ensure_bridge_started(loop: Optional[asyncio.AbstractEventLoop] = None):
    global _bridge_task
    if _bridge_task and not _bridge_task.done():
        return _bridge_task
    loop = loop or asyncio.get_event_loop()
    _bridge_task = loop.create_task(_bridge_loop())
    return _bridge_task


async def send_iso_message(payload: bytes) -> bool:
    try:
        _send_queue.put_nowait(payload)
        return True
    except asyncio.QueueFull:
        log.warning("[ISO] send queue full")
        return False


# Auto-start
try:
    ensure_bridge_started()
    log.info("[ISO] tcp_bridge ready")
except Exception:
    log.exception("[ISO] tcp_bridge startup failed")


