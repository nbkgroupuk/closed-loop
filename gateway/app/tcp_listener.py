# gateway/app/tcp_listener.py
import asyncio
import logging
import traceback
from app import processor_parser, monitoring

log = logging.getLogger("gateway.tcp")

HOST = "0.0.0.0"
PORT = 9000

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    log.info(f"[TCP] Connection from {addr}")

    try:
        data = await reader.read(4096)
        if not data:
            return
        log.info(f"[TCP] Received {len(data)} bytes from {addr}: {data[:64].hex()}...")

        parsed = processor_parser.parse(data)
        mti = parsed.get("mti")
        stan = parsed.get("stan")
        amt = parsed.get("amount")

        log.info(f"[TCP] Parsed MTI={mti} STAN={stan} AMT={amt}")
        monitoring.observe_request("TCP", f"MTI_{mti or 'unknown'}", 200, 0.001)

        # Build ACK/Response depending on MTI
        if mti == "0100":  # Authorization request
            response = b"30313130" + data[8:32]  # "0110" + echo portion
        elif mti == "0200":  # Financial request
            response = b"30323130" + data[8:32]  # "0210"
        else:
            response = b"30393039"  # "909" generic error

        writer.write(response)
        await writer.drain()
        log.info(f"[TCP] Sent response {response[:16].hex()} to {addr}")

    except Exception:
        log.error(f"[TCP] Error processing message from {addr}")
        traceback.print_exc()
    finally:
        writer.close()
        await writer.wait_closed()
        log.info(f"[TCP] Closed connection from {addr}")

async def start_server():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    log.info(f"[TCP] Gateway TCP listener active on {addrs}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(start_server())
