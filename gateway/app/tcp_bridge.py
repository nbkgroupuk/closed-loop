"""
gateway/app/tcp_bridge.py

Production-ready async TCP bridge for forwarding ISO8583 frames from gateway -> processor.

Features:
- Configurable host/port, TLS option, length-prefix framing (2 or 4 bytes)
- Backoff + reconnect loop
- Async queue for non-blocking hand-off from request handlers
- Detailed logging of sent/received bytes and parsed fields
- Safe: never throws to caller; returns a response object or raises on unrecoverable errors
"""

import asyncio
import logging
import socket
import ssl
import time
from typing import Optional

log = logging.getLogger("gateway.tcp_bridge")
log.setLevel(logging.INFO)

# Configuration (override via env vars in production container or pass values when importing)
PROCESSOR_HOST = "host.docker.internal"   # production: processor host (DNS/IP)
PROCESSOR_PORT = 9000
USE_TLS = False
TLS_CERT_REQUIRED = False
LENGTH_PREFIX_BYTES = 2   # 2 or 4
CONNECT_TIMEOUT = 5.0
WRITE_TIMEOUT = 5.0
READ_TIMEOUT = 10.0
RECONNECT_BASE = 0.5
RECONNECT_MAX = 10.0
QUEUE_MAX = 1000

# Internal queue: other code should import send_iso_message() to forward
_send_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX)
_bridge_task: Optional[asyncio.Task] = None

def _length_prefix(data: bytes) -> bytes:
    if LENGTH_PREFIX_BYTES == 2:
        return len(data).to_bytes(2, "big") + data
    else:
        return len(data).to_bytes(4, "big") + data

def _strip_length_prefix(data: bytes) -> bytes:
    if LENGTH_PREFIX_BYTES == 2:
        if len(data) < 2: raise ValueError("frame too short")
        l = int.from_bytes(data[:2], "big")
        return data[2:2+l]
    else:
        if len(data) < 4: raise ValueError("frame too short")
        l = int.from_bytes(data[:4], "big")
        return data[4:4+l]

def _log_hex(prefix: str, b: bytes):
    try:
        h = b.hex().upper()
        # chunk to keep logs readable
        log.debug("%s bytes=%s", prefix, " ".join(h[i:i+64] for i in range(0, len(h), 64)))
    except Exception:
        log.debug("%s (cannot hex)", prefix)

# Replace with real ISO pack/unpack adapters or import your iso_codec functions
def parse_iso_preview(b: bytes) -> dict:
    """
    Lightweight preview: attempt to parse ascii JSON-like bodies or show MTI if present.
    This is a fallback; replace with your iso_codec.unpack_iso for real parsing.
    """
    try:
        # if it looks like ASCII JSON, decode preview
        s = b.decode("utf-8", errors="ignore")
        preview = {"preview": s[:200]}
        # try to detect an MTI at start (e.g. b0200 or b0800)
        if len(s) >= 4 and s[:4].isdigit():
            preview["mti"] = s[:4]
        return preview
    except Exception:
        return {"len": len(b)}

class ProcessorConnection:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = asyncio.Event()

    async def connect(self):
        backoff = RECONNECT_BASE
        while True:
            try:
                log.info("[TCP] connecting to %s:%s", self.host, self.port)
                if USE_TLS:
                    ctx = ssl.create_default_context()
                    if not TLS_CERT_REQUIRED:
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                    conn = await asyncio.wait_for(asyncio.open_connection(self.host, self.port, ssl=ctx), timeout=CONNECT_TIMEOUT)
                else:
                    conn = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), timeout=CONNECT_TIMEOUT)
                self._reader, self._writer = conn
                self._connected.set()
                log.info("[TCP] connected to %s:%s", self.host, self.port)
                return
            except Exception as e:
                log.warning("[TCP] connect failed: %s, retrying in %.2fs", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(RECONNECT_MAX, backoff * 2)

    async def close(self):
        try:
            if self._writer:
                self._writer.close()
                await asyncio.wait_for(self._writer.wait_closed(), timeout=2.0)
        except Exception:
            pass
        finally:
            self._reader = None
            self._writer = None
            self._connected.clear()

    async def send_frame(self, payload: bytes) -> Optional[bytes]:
        if not self._writer or self._writer.is_closing():
            # ensure connected
            await self.connect()

        framed = _length_prefix(payload)
        _log_hex("TX", framed)
        try:
            self._writer.write(framed)
            await asyncio.wait_for(self._writer.drain(), timeout=WRITE_TIMEOUT)
        except Exception as e:
            log.warning("[TCP] write failed: %s", e)
            await self.close()
            raise

        # read response length first
        try:
            # read prefix bytes
            prefix = await asyncio.wait_for(self._reader.readexactly(LENGTH_PREFIX_BYTES), timeout=READ_TIMEOUT)
            if LENGTH_PREFIX_BYTES == 2:
                length = int.from_bytes(prefix, "big")
            else:
                length = int.from_bytes(prefix, "big")
            data = await asyncio.wait_for(self._reader.readexactly(length), timeout=READ_TIMEOUT)
            _log_hex("RX", prefix + data)
            return data
        except asyncio.IncompleteReadError:
            log.warning("[TCP] incomplete read from processor")
            await self.close()
            return None
        except Exception as e:
            log.warning("[TCP] read failed: %s", e)
            await self.close()
            return None

async def _bridge_loop():
    log.info("[TCP] bridge loop started")
    conn = ProcessorConnection(PROCESSOR_HOST, PROCESSOR_PORT)
    # keep connection alive and process queue items
    while True:
        item = await _send_queue.get()
        try:
            # item expected to be bytes (already ISO-framed body without length prefix)
            if not isinstance(item, (bytes, bytearray)):
                # if dict given, convert with your packer
                raise ValueError("bridge expects bytes payload")
            # ensure connection
            if not conn._connected.is_set():
                await conn.connect()
            # send and await response
            resp = await conn.send_frame(bytes(item))
            if resp is None:
                log.warning("[TCP] response empty")
            else:
                # log parsed preview
                try:
                    preview = parse_iso_preview(resp)
                    log.info("[TCP] processor response preview: %s", preview)
                except Exception as e:
                    log.debug("[TCP] parsing preview failed: %s", e)
        except Exception as exc:
            log.exception("[TCP] error forwarding to processor: %s", exc)
        finally:
            _send_queue.task_done()

def ensure_bridge_started(loop: Optional[asyncio.AbstractEventLoop] = None):
    global _bridge_task
    if _bridge_task and not _bridge_task.done():
        return _bridge_task
    if loop is None:
        loop = asyncio.get_event_loop()
    _bridge_task = loop.create_task(_bridge_loop())
    return _bridge_task

async def send_iso_message(payload: bytes, timeout: float = 5.0) -> bool:
    """
    Public method for other gateway code to forward an ISO payload (raw bytes).
    - payload: raw ISO payload (WITHOUT length prefix). This function will queue it for sending.
    - Returns True if queued successfully, False otherwise.
    """
    try:
        # check minimal validation
        if not payload or not isinstance(payload, (bytes, bytearray)):
            raise ValueError("payload must be non-empty bytes")
        _send_queue.put_nowait(payload)
        log.debug("[TCP] queued payload len=%d", len(payload))
        return True
    except asyncio.QueueFull:
        log.warning("[TCP] send queue full - dropping message")
        return False
    except Exception as e:
        log.exception("[TCP] send_iso_message failure: %s", e)
        return False

# For convenience: synchronous helper to start the bridge when importing in uvicorn startup
def start_on_import():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    ensure_bridge_started(loop)

# Start automatically if module imported in running event loop (fastapi uvicorn)
try:
    start_on_import()
    log.info("tcp_bridge imported - bridge start requested")
except Exception:
    log.exception("tcp_bridge import failed to start bridge")
