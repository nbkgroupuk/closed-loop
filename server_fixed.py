import socketserver, threading, logging, json
from fastapi import FastAPI

LOG = logging.getLogger("processor")
logging.basicConfig(level=logging.INFO)

class ISOHandler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            hdr = self.rfile.read(4)
            if not hdr:
                return
            rlen = int.from_bytes(hdr, "big")
            body = self.rfile.read(rlen)
            LOG.info("Received %d bytes", len(body))
            try:
                text = body.decode("utf-8")
                LOG.info("Payload: %s", text)
                data = json.loads(text)
                resp = json.dumps({"de39": "00", "echo": data}).encode()
            except Exception as e:
                resp = json.dumps({"de39": "30", "error": str(e)}).encode()
            self.wfile.write(len(resp).to_bytes(4, "big") + resp)
        except Exception as e:
            LOG.exception("Handler crashed: %s", e)

def start_tcp_server():
    server = socketserver.ThreadingTCPServer(("0.0.0.0", 9000), ISOHandler)
    LOG.info("ISO8583 TCP server listening on port 9000")
    threading.Thread(target=server.serve_forever, daemon=True).start()

app = FastAPI(title="Processor Service")

@app.on_event("startup")
async def startup():
    start_tcp_server()

@app.get("/health")
async def health():
    return {"status": "ok", "service": "processor"}
