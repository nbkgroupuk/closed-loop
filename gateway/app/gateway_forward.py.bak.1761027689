# gateway_forward.py (drop into your Gateway app)
import socket
import json
import logging

log = logging.getLogger("gateway.forward")

def send_to_processor(host: str, port: int, payload: dict, timeout: int = 5):
    """
    Send JSON payload to processor over TCP, receive framed JSON back.

    Returns: normalized dict
      {
        "approved": bool,
        "de39": str,
        "de38": Optional[str],
        "raw": dict
      }
    """
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    header = len(data).to_bytes(4, "big")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)

    try:
        s.connect((host, port))
        s.sendall(header + data)

        # read 4-byte header
        hdr = b""
        while len(hdr) < 4:
            chunk = s.recv(4 - len(hdr))
            if not chunk:
                raise RuntimeError("no response header (socket closed)")
            hdr += chunk

        rlen = int.from_bytes(hdr, "big")
        body = b""
        while len(body) < rlen:
            chunk = s.recv(rlen - len(body))
            if not chunk:
                raise RuntimeError("response truncated")
            body += chunk

        resp = json.loads(body.decode("utf-8"))
        fields = resp.get("fields") or resp

        # normalize response
        de39 = str(fields.get("39") or fields.get("de39") or "91")
        de38 = str(fields.get("38") or fields.get("de38")) if fields.get("38") or fields.get("de38") else None

        return {
            "approved": (de39 == "00"),
            "de39": de39,
            "de38": de38,
            "raw": fields,
        }
    finally:
        s.close()
