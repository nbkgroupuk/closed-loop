import asyncio
import struct
import json
import logging

LOG = logging.getLogger("processor.iso_listener")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s:%(name)s:%(message)s'))
    LOG.addHandler(h)

async def send_frame(writer, payload: bytes):
    frame = struct.pack('>I', len(payload)) + payload
    writer.write(frame)
    await writer.drain()

async def handle_client(reader, writer):
    peer = writer.get_extra_info('peername')
    LOG.info("Client connected: %s", peer)
    try:
        while True:
            hdr = await reader.readexactly(4)
            size = struct.unpack('>I', hdr)[0]
            data = await reader.readexactly(size)
            text = data.decode('utf-8', errors='replace')
            LOG.info("Received raw payload (first 200 chars): %s", text[:200])

            # default 96 (system malfunction) fallback
            resp = {"fields": {"39": "96"}}

            # attempt to parse as ISO20022-like JSON and delegate
            try:
                js = json.loads(text)
                if isinstance(js, dict) and js.get("type") == "iso20022":
                    LOG.info("ISO20022 JSON detected — delegating to app.iso_processing.process_incoming_iso")
                    # import inside handler to avoid import-time circular problems
                    from app.iso_processing import process_incoming_iso
                    # call the async processor synchronously
                    result = asyncio.run(process_incoming_iso(js))
                    de39 = str(result.get("de39") or result.get("DE39") or "00")
                    auth_code = result.get("auth_code") or js.get("auth_code") or None
                    resp = {"fields": {"39": de39}}
                    if auth_code:
                        resp["fields"]["38"] = str(auth_code)
            except Exception as e:
                LOG.debug("ISO20022 detection skipped/failed: %s", e)

            resp_payload = b"0210" + json.dumps(resp, separators=(",", ":")).encode("utf-8")
            await send_frame(writer, resp_payload)

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

async def start_server(host='0.0.0.0', port=9000):
    server = await asyncio.start_server(handle_client, host, port)
    LOG.info("ISO Listener serving on (%s, %d)", host, port)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(start_server())
