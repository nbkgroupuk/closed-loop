# mock_bank.py — simple ISO20022 mock server
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, sys

class MockBankHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/iso20022":
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length > 0 else b""
        print("\n=== MOCK BANK GOT /iso20022 ===")
        try:
            print(body.decode("utf-8")[:1000])
        except Exception:
            print("<binary data>")
        resp = {"status": "ok", "message": "mock accepted", "echo_length": len(body)}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode("utf-8"))

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5002
    server = HTTPServer(("0.0.0.0", port), MockBankHandler)
    print(f"Mock bank listening on http://0.0.0.0:{port}/iso20022")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
