import os, logging, threading, socketserver, json, gzip, base64
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

LOG = logging.getLogger("processor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

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

@app.post("/payout")
async def payout(payload: Request):
    data = await payload.json()
    required = ["merchant_id", "cardNumber", "expiry", "cvc", "amount", "currency"]
    miss = [k for k in required if k not in data]
    if miss:
        raise HTTPException(status_code=400, detail={"missing": miss})
    return {"DE39": "00", "status": "approved", "auth_code": data.get("authCode") or "MOCK00", "job_id": data.get("job_id")}

class ISOHandler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            hdr = self.rfile.read(4)
            if not hdr:
                return
            if hdr and hdr[0] == 0:
                rlen = int.from_bytes(hdr, "big")
                body = self.rfile.read(rlen) if rlen > 0 else b""
            else:
                rest = self.rfile.read(8192) or b""
                body = hdr + rest

            LOG.info("Received %d raw bytes", len(body))
            if len(body) >= 2 and body[0:2] == b"\x1f\x8b":
                try:
                    body = gzip.decompress(body)
                    LOG.info("Decompressed gzip payload, len=%d", len(body))
                except Exception as e:
                    LOG.warning("Gzip decompress failed: %s", e)

            try:
                text = body.decode("utf-8")
            except Exception:
                LOG.warning("Body not utf8; raw base64: %s", base64.b64encode(body).decode("ascii"))
                text = None

            if text:
                idx = None
                for ch in ("{", "["):
                    pos = text.find(ch)
                    if pos != -1 and (idx is None or pos < idx):
                        idx = pos
                if idx is not None and idx > 0:
                    LOG.info("Stripping %d-byte prefix before JSON (preview=%s)", idx, text[:idx])
                    text = text[idx:]
                LOG.info("Payload text preview: %s", (text[:300] + '...') if len(text) > 300 else text)
                try:
                    payload = json.loads(text)
                    LOG.info("Parsed payload keys: %s", list(payload.keys()) if isinstance(payload, dict) else type(payload))
                    resp = json.dumps({"mti": payload.get("mti", "0210") if isinstance(payload, dict) else "0210", "de39": "00", "echo": payload}).encode("utf-8")
                except Exception as e:
                    LOG.exception("Failed to parse JSON: %s", e)
                    resp = json.dumps({"de39": "30", "error": "bad json", "detail": str(e)}).encode("utf-8")
            else:
                resp = json.dumps({"de39": "30", "error": "unparseable payload"}).encode("utf-8")

            try:
                self.wfile.write(len(resp).to_bytes(4, "big") + resp)
                LOG.info("Sent framed response len=%d", len(resp))
            except Exception:
                try:
                    self.wfile.write(resp + b"\n")
                    LOG.info("Sent raw response fallback")
                except Exception:
                    LOG.exception("Failed to send response")
        except Exception:
            LOG.exception("Handler crashed")

def start_iso_server(host="0.0.0.0", port=9000):
    class ThreadedTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
    server = ThreadedTCPServer((host, port), ISOHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    LOG.info("ISO8583 TCP server listening on port %s", port)
    return server

@app.on_event("startup")
def on_startup():
    start_iso_server(host="0.0.0.0", port=int(os.environ.get("ISO_PORT", "9000")))
