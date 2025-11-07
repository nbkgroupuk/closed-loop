# processor/app/app/server.py (patched TCP handler for length-prefixed frames)
import os
import logging
import threading
import socketserver
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger("processor")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Processor")
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "processor"}

# Minimal /payout handler - << REPLACE WITH REAL PROCESSING >>
@app.post("/payout")
async def payout(payload: Request):
    data = await payload.json()
    required = ["merchant_id", "cardNumber", "expiry", "cvc", "amount", "currency"]
    miss = [k for k in required if k not in data]
    if miss:
        raise HTTPException(status_code=400, detail={"missing": miss})
    resp = {
        "DE39": "00",
        "status": "approved",
        "auth_code": data.get("authCode") or "MOCK00",
        "job_id": data.get("job_id"),
    }
    return resp

# --- Robust TCP ISO-like listener that accepts 4-byte BE length + payload ---
class ISOHandler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            # 1) read 4-byte big-endian length header
            hdr = self.rfile.read(4)
            if not hdr or len(hdr) < 4:
                log.debug("No header or short header received")
                return
            try:
                length = int.from_bytes(hdr, byteorder="big")
            except Exception as e:
                log.exception("Invalid length header: %s", e)
                return

            # 2) read exactly `length` bytes
            data = self.rfile.read(length)
            if not data or len(data) < 1:
                log.warning("Empty payload after length header")
                return

            # 3) Try to decode payload: it may be MTI(4 ascii) + JSON body, or JSON-only
            mti = None
            fields = {}
            try:
                # If payload begins with 4 ASCII digits -> MTI prefix
                if len(data) >= 4 and data[:4].decode("ascii", errors="ignore").isdigit():
                    mti = data[:4].decode("ascii")
                    body_bytes = data[4:]
                    if body_bytes:
                        body_text = body_bytes.decode("utf-8", errors="replace")
                        parsed = json.loads(body_text)
                        if isinstance(parsed, dict) and "fields" in parsed:
                            fields = parsed["fields"] or {}
                        elif isinstance(parsed, dict):
                            fields = parsed
                    else:
                        fields = {}
                else:
                    # fallback: try entire payload as JSON text
                    text = data.decode("utf-8", errors="replace")
                    parsed = json.loads(text)
                    # accept {"mti":..., "fields":{...}} or {"fields":{...}} or flat dict
                    if isinstance(parsed, dict):
                        mti = parsed.get("mti", None)
                        if "fields" in parsed and isinstance(parsed["fields"], dict):
                            fields = parsed["fields"]
                        else:
                            fields = parsed
            except Exception as e:
                log.exception("Error decoding payload: %s", e)
                # reply with a safe error frame (JSON)
                err_payload = json.dumps({"mti":"0210","fields":{"39":"96","err":str(e)}}).encode("utf-8")
                frame = len(err_payload).to_bytes(4, "big") + err_payload
                try:
                    self.wfile.write(frame)
                except Exception:
                    pass
                return

            log.info("Received ISO msg mti=%s fields=%s", mti, fields)

            # Build response fields (approved by default for test)
            resp_fields = {"39": "00"}
            # echo auth code if present under common keys
            auth_val = None
            try:
                # fields keys may be strings or ints — normalize to strings for lookup
                if isinstance(fields, dict):
                    # direct lookup for "38"
                    if "38" in fields:
                        auth_val = fields.get("38")
                    # alternative keys
                    for alt in ("authCode", "auth_code"):
                        if alt in fields:
                            auth_val = fields.get(alt)
                    # if found and non-empty, include
                    if auth_val:
                        resp_fields["38"] = auth_val
            except Exception:
                pass

            # 4) Try to use app.iso_codec.pack_iso if available for proper framing
            try:
                from app.iso_codec import pack_iso
                # convert resp_fields keys to ints where possible
                resp_int_fields = {}
                for k, v in resp_fields.items():
                    try:
                        resp_int_fields[int(k)] = v
                    except Exception:
                        resp_int_fields[k] = v
                resp_frame = pack_iso("0210", resp_int_fields)
                self.wfile.write(resp_frame)
                return
            except Exception:
                # fallback: construct MTI+JSON body and length prefix
                resp_payload = b"0210" + json.dumps({"fields": resp_fields}, separators=(",", ":")).encode("utf-8")
                frame = len(resp_payload).to_bytes(4, "big") + resp_payload
                try:
                    self.wfile.write(frame)
                    return
                except Exception:
                    return

        except Exception as e:
            log.exception("Error processing tcp msg: %s", e)
            try:
                self.wfile.write(b'{"error":"bad"}\n')
            except Exception:
                pass

def start_iso_server(host="0.0.0.0", port=9000):
    class ThreadedTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
    server = ThreadedTCPServer((host, port), ISOHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    log.info("ISO8583 TCP server listening on port %s", port)
    return server

@app.on_event("startup")
def on_startup():
    start_iso_server(host="0.0.0.0", port=int(os.environ.get("ISO_PORT", "9000")))
