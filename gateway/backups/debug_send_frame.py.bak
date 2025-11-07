#docker exec project-gateway sh -c 'cat > /app/debug_send_frame.py <<PY
#gateway/debug_send_frame.py

import socket, json, struct, binascii, os, sys
HOST=os.environ.get("PROCESSOR_HOST","project-processor"); PORT=int(os.environ.get("PROCESSOR_PORT","9000"))
body={"type":"iso20022","fields":{"2":"TEST_PAN_REDACTED","3":"000000","4":"000000001000","7":"1010110000","11":"123456","12":"110000","13":"1010","37":"999999999999","41":"TERMINAL_ID_PLACEHOLDER","42":"MERCHANT0001","49":"840","protocol":"101.1","authCode":"1234"}}
json_bytes=json.dumps(body, default=str).encode("utf-8")
payload=b"0200"+json_bytes
frame=struct.pack(">I", len(payload))+payload
print("SENT framed (hex):", binascii.hexlify(frame).decode())
try:
    s=socket.create_connection((HOST,PORT),timeout=5)
    s.sendall(frame)
    hdr=s.recv(4)
    if not hdr or len(hdr)<4: print("! no response header",hdr); sys.exit(1)
    resp_len=struct.unpack(">I", hdr)[0]
    print("RECV length:", resp_len)
    resp=s.recv(resp_len)
    print("RECV payload (hex):", binascii.hexlify(resp).decode())
    print("DECODED:", resp.decode("utf-8",errors="replace"))
    s.close()
except Exception as e:
    print("ERROR:", e)

#PY'
