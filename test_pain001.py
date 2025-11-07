#!/usr/bin/env python3
import time, requests, sys

GATEWAY = "http://localhost:8000"   # change if needed
ENDPOINTS = ["/payouts/iso20022", "/payouts", "/api/payouts/iso20022"]

xmlpath = "pain001.xml"

def find_endpoint():
    for ep in ENDPOINTS:
        url = GATEWAY.rstrip("/") + ep
        try:
            r = requests.options(url, timeout=2)
            if r.status_code < 500:
                return url
        except Exception:
            pass
    # fallback to first endpoint
    return GATEWAY.rstrip("/") + ENDPOINTS[0]

def post_xml(url):
    headers = {"Content-Type":"application/xml", "Accept":"application/xml"}
    with open(xmlpath, "rb") as f:
        payload = f.read()
    t0 = time.monotonic()
    r = requests.post(url, data=payload, headers=headers, timeout=15)
    t1 = time.monotonic()
    print(f"POST {url} -> {r.status_code} in {(t1-t0)*1000:.1f} ms")
    print("Response headers:", r.headers.get("content-type"))
    print("Response body:")
    print(r.text)
    return r

if __name__ == "__main__":
    url = find_endpoint()
    print("Using endpoint:", url)
    for attempt in range(1,4):
        try:
            r = post_xml(url)
            break
        except Exception as e:
            print("Attempt", attempt, "failed:", e)
            time.sleep(1)
    else:
        print("All attempts failed")
        sys.exit(2)
