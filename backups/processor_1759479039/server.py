# processor/app/app/server.py
import asyncio
import json
import logging
import os
import uuid
from typing import Dict

import uvicorn
from fastapi import FastAPI

# Import the HTTP route module (it registers routes on `app`)
from app.api import payouts  # noqa: F401

LOG = logging.getLogger("processor.server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Processor")

# TCP server settings
TCP_HOST = os.getenv("TCP_HOST", "0.0.0.0")
TCP_PORT = int(os.getenv("TCP_PORT", os.getenv("PROCESSOR_TCP_PORT", "9000")))

# small helper for framing/unframing
def frame_payload(payload_bytes: bytes) -> bytes:
    length = len(payload_bytes)
    hdr = length.to_bytes(4, byteorder="big")
    return hdr + payload_bytes

async def handle_iso_tcp(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    LOG.info("ISO-TCP connection from %s", addr)
    try:
        # read 4-byte header
        raw_hdr = await reader.readexactly(4)
        rlen = int.from_bytes(raw_hdr, "big")
        # read the payload
        payload = await reader.readexactly(rlen)
    except asyncio.IncompleteReadError:
        LOG.warning("Client closed connection prematurely: %s", addr)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        return
    except Exception as e:
        LOG.exception("Error reading from TCP client %s: %s", addr, e)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        return

    # payload should be JSON (utf-8)
    try:
        text = payload.decode("utf-8")
        obj = json.loads(text)
        LOG.info("ISO-TCP recv: mti=%s fields=%s", obj.get("mti"), obj.get("fields"))
    except Exception as e:
        # respond with a basic negative response if we can't parse
        LOG.exception("Invalid ISO payload from %s: %s", addr, e)
        resp_obj = {"approved": False, "de39": "96", "error": "invalid_payload"}
        resp_bytes = ("0210" + json.dumps(resp_obj)).encode("utf-8")
        writer.write(frame_payload(resp_bytes))
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return

    # build success response -- your processor logic goes here
    # simple example: approved True, de39 00, gateway_txn_id, txn_id maybe None
    gateway_txn_id = f"PROC-{uuid.uuid4().hex[:12]}"
    resp_obj = {"approved": True, "de39": "00", "gateway_txn_id": gateway_txn_id, "txn_id": None}
    resp_text = json.dumps(resp_obj)
    resp_frame = ("0210" + resp_text).encode("utf-8")
    writer.write(frame_payload(resp_frame))
    await writer.drain()
    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass
    LOG.info("ISO-TCP responded to %s gateway_txn_id=%s", addr, gateway_txn_id)

async def tcp_server_task(host: str, port: int):
    server = await asyncio.start_server(handle_iso_tcp, host, port)
    addr_list = ", ".join(str(s.getsockname()) for s in server.sockets or [])
    LOG.info("ISO-TCP stub listening on %s:%s (sockets: %s)", host, port, addr_list)
    async with server:
        await server.serve_forever()

@app.on_event("startup")
async def startup_event():
    # start the TCP server as a background task
    loop = asyncio.get_running_loop()
    loop.create_task(tcp_server_task(TCP_HOST, TCP_PORT))
    LOG.info("Processor startup complete (HTTP + ISO-TCP background task scheduled).")

if __name__ == "__main__":
    uvicorn.run("app.server:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000)), log_level="info")
