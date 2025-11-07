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
class ISOHandler(socketserver.StreamRequestHandler):
    def handle(self):
        # Read a length-prefixed frame: 4-byte big-endian length, then payload
        try:
            hdr = self.rfile.read(4)
            if not hdr or len(hdr) < 4:
                return
            try:
                payload_len = int.from_bytes(hdr, "big")
            except Exception:
                # fallback: treat hdr+rest as a single payload (compat)
                data = hdr + self.rfile.read()
                payload = data
            else:
                payload = self.rfile.read(payload_len)
                if payload is None:
                    return
        except Exception as e:
            log.exception("ISOHandler read error: %s", e)
            return

        # payload may be MTI(4) + JSON body OR JSON-only
        try:
            # if MTI prefix present (4 ascii digits)
            if len(payload) >= 4 and all(48 <= b <= 57 for b in payload[:4]):
                mti = payload[:4].decode('ascii', errors='ignore')
                body_bytes = payload[4:]
            else:
                # fallback: no MTI prefix
                mti = None
                body_bytes = payload

            text = body_bytes.decode('utf-8', errors='replace')
            obj = json.loads(text) if text else {}
        except Exception as e:
            log.exception("Error processing tcp msg during decode: %s", e)
            try:
                # send minimal error response
                resp_obj = {"mti":"0210","fields":{"39":"96"}}
                out = json.dumps(resp_obj) 
                out_payload = (mti or "0210").encode('ascii') + out.encode('utf-8')
                self.wfile.write(len(out_payload).to_bytes(4,"big") + out_payload)
            except Exception:
                pass
            return

        # Normalize fields map where possible
        fields = {}
        if isinstance(obj, dict):
            # if we have {"mti":..., "fields": {...}} pattern
            if "fields" in obj and isinstance(obj["fields"], dict):
                fields = {str(k): v for k, v in obj["fields"].items()}
            else:
                # copy direct keys (strings or numbers)
                fields = {str(k): v for k, v in obj.items()}

        log.info("Received ISO msg mti=%s fields=%s", mti or "?", fields)

        # Build response fields: standard approval (DE39=00) and echo auth if present
        resp_fields = {}
        # prefer numeric field keys as strings
        if "39" in fields:
            resp_fields["39"] = fields.get("39")
        else:
            resp_fields["39"] = "00"
        # if incoming included auth 38, echo it
        if "38" in fields:
            resp_fields["38"] = fields.get("38")
        else:
            # keep empty or not included
            pass

        resp_obj = {"mti": "0210", "fields": resp_fields}
        try:
            out_text = json.dumps(resp_obj, separators=(',', ':'))
            out_payload = b"0210" + out_text.encode('utf-8')
            self.wfile.write(len(out_payload).to_bytes(4,"big") + out_payload)
            log.info("Sent 0210 response fields=%s", resp_fields)
        except Exception as e:
            log.exception("Error writing response: %s", e)
