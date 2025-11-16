# /app/app/iso_listener.py
import asyncio
import struct
import json
import logging
from typing import Optional

LOG = logging.getLogger("processor.iso_listener")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s:%(name)s:%(message)s'))
    LOG.addHandler(h)


async def async_read_frame(reader: asyncio.StreamReader) -> Optional[bytes]:
    """Read a length-prefixed frame (4-byte big-endian length). Returns payload bytes or None on EOF."""
    try:
        raw_len = await reader.readexactly(4)
    except asyncio.IncompleteReadError:
        return None
    if not raw_len:
        return None
    size = struct.unpack(">I", raw_len)[0]
    if size == 0:
        return b""
    data = await reader.readexactly(size)
    return data


async def send_frame(writer: asyncio.StreamWriter, payload: bytes):
    frame = struct.pack(">I", len(payload)) + payload
    writer.write(frame)
    try:
        await writer.drain()
    except Exception:
        # writer may be closed by peer
        pass


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info("peername")
    LOG.info("Client connected: %s", peer)
    try:
        # read one frame, process, respond — loop to support multiple frames per connection
        while True:
            framed = await async_read_frame(reader)
            if framed is None:
                # client closed connection
                LOG.info("Client disconnected (incomplete): %s", peer)
                break

            # Default fallback response (system malfunction)
            resp = {"fields": {"39": "96"}}

            # First try to detect / treat as JSON (ISO20022)
            text = None
            try:
                text = framed.decode("utf-8", errors="replace")
            except Exception:
                text = None

            if text:
                try:
                    js = json.loads(text)
                    if isinstance(js, dict) and js.get("type") == "iso20022":
                        # import inside handler to avoid circular import at module-level
                        from app.iso_processing import process_incoming_iso

                        LOG.info("ISO20022 JSON detected — delegating to app.iso_processing.process_incoming_iso")
                        # IMPORTANT: await the coroutine (do NOT call asyncio.run inside an already-running loop)
                        try:
                            result = await process_incoming_iso(js)
                        except Exception as e:
                            LOG.exception("process_incoming_iso raised exception: %s", e)
                            result = {"de39": "96"}

                        de39 = str(result.get("de39") or result.get("DE39") or "96")
                        auth_code = result.get("auth_code") or js.get("auth_code") or None
                        resp = {"fields": {"39": de39}}
                        if auth_code:
                            resp["fields"]["38"] = str(auth_code)

                except Exception as e:
                    # JSON parsing / ISO20022 handling failed — fall back to other formats
                    LOG.debug("ISO20022 detection skipped/failed: %s", e)

            # If not ISO20022, try to parse as ISO8583 (legacy) using local iso_codec if present
            if resp["fields"]["39"] == "96":
                try:
                    # try to import local iso codec if available
                    from app.iso_codec import unpack_iso, pack_iso  # optional
                    try:
                        unpacked = unpack_iso(framed)
                        # unpacked expected to be dict with 'mti' and 'fields'
                        # minimal behavior: if we get de39 in unpacked -> reflect it
                        if isinstance(unpacked, dict):
                            de39 = unpacked.get("fields", {}).get("39") or "96"
                            resp = {"fields": {"39": str(de39)}}
                    except Exception as e:
                        LOG.debug("Failed to unpack ISO from %s: %s", peer, e)
                except Exception:
                    # iso_codec not present or import failed — ignore and continue
                    pass

            # send response as framed JSON payload prefixed with '0210' (legacy behavior)
            try:
                resp_payload = b"0210" + json.dumps(resp, separators=(",", ":")).encode("utf-8")
                await send_frame(writer, resp_payload)
                LOG.info("Sent response to %s (%d bytes) de39=%s", peer, len(resp_payload), resp["fields"].get("39"))
            except Exception as e:
                LOG.exception("Failed to send response to %s: %s", peer, e)
                break

    except asyncio.IncompleteReadError:
        LOG.info("Client disconnected (incomplete): %s", peer)
    except Exception as e:
        LOG.exception("Listener error for %s: %s", peer, e)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        LOG.info("Client disconnected: %s", peer)


async def start_server(host: str = "0.0.0.0", port: int = 9000):
    server = await asyncio.start_server(handle_client, host, port)
    LOG.info("ISO Listener serving on (%s, %d)", host, port)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(start_server())
