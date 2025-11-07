#docker exec -i gateway-debug sh -c 'cat > /app/app/iso_sim.py <<'"'PY'"'
#!/usr/bin/env python3
"""
iso_sim.py - simple ISO sender for local testing.

Usage:
  python -u /app/app/iso_sim.py 0200
  python -u /app/app/iso_sim.py 0100
Optional env:
  PROCESSOR_HOST (default: processor-debug)
  PROCESSOR_PORT (default: 5000)
  PROTOCOL (e.g. "101.1")  - if omitted a sensible default is chosen
  AUTHCODE (explicit numeric auth code) - if given it will be used (length still validated)
"""
import sys, os, socket, struct, json, time, uuid, random

PROCESSOR_HOST = os.getenv("PROCESSOR_HOST", "processor-debug")
PROCESSOR_PORT = int(os.getenv("PROCESSOR_PORT", "5000"))
TIMEOUT = 5.0

# Protocol -> required auth length mapping (mirror frontend rules)
PROTOCOL_AUTH_LEN = {
    "101.1": 4, "101.2": 6, "101.3": 6, "101.4": 6, "101.5": 6, "101.6": 6, "101.7": 4, "101.8": 6,
    "201.1": 6, "201.2": 6, "201.3": 6, "201.4": 6, "201.5": 6
}
DEFAULT_PROTOCOL = "101.1"

def gen_auth_for_protocol(proto):
    L = PROTOCOL_AUTH_LEN.get(proto, 6)
    # numeric leading zeros allowed
    fmt = "{:0" + str(L) + "d}"
    return fmt.format(random.randint(0, 10**L - 1))

def build_payload(mti, protocol=None, authcode=None):
    protocol = protocol or os.getenv("PROTOCOL") or DEFAULT_PROTOCOL
    expected_len = PROTOCOL_AUTH_LEN.get(protocol, 6)
    if authcode is None:
        authcode = gen_auth_for_protocol(protocol)
    # if auth provided but wrong length -> warn and pad/truncate
    if not authcode.isdigit() or len(authcode) != expected_len:
        # attempt to coerce numeric and adjust length
        digits = "".join(ch for ch in authcode if ch.isdigit())
        if len(digits) < expected_len:
            digits = digits.zfill(expected_len)
        elif len(digits) > expected_len:
            digits = digits[:expected_len]
        authcode = digits

    # create basic fields similar to frontend expectations (use string keys to be tolerant)
    fields = {
        "mti": mti,
        "fields": {
            "2": "TEST_PAN_REDACTED",
            "3": "000000",
            "4": "000000001000",
            "7": time.strftime("%m%d%H%M%S", time.localtime()),
            "11": "{:06d}".format(int(time.time()) % 1000000),
            "14": "2408",
            "22": "051",
            "25": "00",
            "37": uuid.uuid4().hex[:12],
            "41": "TERM1234",
            "42": "MERCHANT1234567",
            "49": "840",
            # additional frontend fields required:
            "protocol": protocol,
            "authCode": authcode
        }
    }
    return fields

def send_and_recv(payload_obj, timeout=TIMEOUT):
    b = json.dumps(payload_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    msg = struct.pack(">I", len(b)) + b
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((PROCESSOR_HOST, PROCESSOR_PORT))
        s.sendall(msg)
        # read 4-byte length
        raw = s.recv(4)
        if not raw or len(raw) < 4:
            raise ConnectionError("short length read / no response length")
        resp_len = struct.unpack(">I", raw)[0]
        if resp_len <= 0:
            raise ConnectionError(f"invalid resp_len: {resp_len}")
        received = b""
        while len(received) < resp_len:
            chunk = s.recv(min(4096, resp_len - len(received)))
            if not chunk:
                break
            received += chunk
        # try decode json
        try:
            text = received.decode("utf-8")
            obj = json.loads(text)
            return obj
        except Exception:
            # fallback: show raw
            return {"raw": received.hex()}
    finally:
        try:
            s.close()
        except Exception:
            pass

def pretty_print_request(obj):
    print("-> Sending", obj.get("mti"), "fields:", obj.get("fields"))

def pretty_print_response(r):
    print("<<< RESPONSE:", json.dumps(r, indent=2))

def main():
    if len(sys.argv) >= 2:
        mti = sys.argv[1]
    else:
        mti = "0200"
    # allow override protocol/auth via env
    proto = os.getenv("PROTOCOL")
    auth = os.getenv("AUTHCODE")
    payload = build_payload(mti, protocol=proto, authcode=auth)
    pretty_print_request(payload)
    try:
        resp = send_and_recv(payload)
    except Exception as e:
        print("!!! simulator error:", repr(e))
        sys.exit(2)
    pretty_print_response(resp)

if __name__ == "__main__":
    main()
    
#PY'
