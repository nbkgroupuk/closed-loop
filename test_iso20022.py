import time, requests, sys, os

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8000")
ENDPOINT = "/payouts/iso20022"
XML_PATH = "pain001.xml"

with open(XML_PATH, "rb") as f:
    xml = f.read()

print(f"→ Sending pain.001 ({len(xml)} bytes) to {GATEWAY}{ENDPOINT}")
headers = {"Content-Type": "application/xml", "Accept": "application/xml"}

t0 = time.monotonic()
try:
    r = requests.post(GATEWAY + ENDPOINT, data=xml, headers=headers, timeout=10)
except Exception as e:
    print("❌ Connection failed:", e)
    sys.exit(1)
t1 = time.monotonic()

print(f"← HTTP {r.status_code} in {(t1-t0)*1000:.2f} ms")
print("Response headers:", r.headers.get("content-type"))
print("Body:")
print(r.text)
