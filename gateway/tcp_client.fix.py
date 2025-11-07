# gateway/tcp_client.fix.py
import socket
import struct
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

def recvall(sock: socket.socket, n: int) -> bytes:
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)

def send_iso_to_processor(host: str, port: int, payload_bytes: bytes, timeout: float = 5.0) -> bytes:
    """
    Connect to host:port and send framed ISO payload:
      [4-byte BE length][payload_bytes]
    Then read a 4-byte BE length and the response payload.
    Returns the response payload bytes (body only).
    """
    if not isinstance(payload_bytes, (bytes, bytearray)):
        raise ValueError("payload_bytes must be bytes")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        logger.debug("Connecting to %s:%s", host, port)
        s.connect((host, int(port)))

        hdr = struct.pack(">I", len(payload_bytes))
        s.sendall(hdr + payload_bytes)
        logger.debug("Sent %d bytes", len(payload_bytes))

        raw_len = recvall(s, 4)
        if len(raw_len) < 4:
            raise ConnectionError("short length read (header)")

        resp_len = struct.unpack(">I", raw_len)[0]
        if resp_len > 50 * 1024 * 1024:
            raise ConnectionError("response too large: %d" % resp_len)

        resp_body = recvall(s, resp_len)
        if len(resp_body) < resp_len:
            raise ConnectionError("short length read (body)")

        logger.debug("Received %d bytes", len(resp_body))
        return resp_body
    finally:
        try:
            s.close()
        except Exception:
            pass
