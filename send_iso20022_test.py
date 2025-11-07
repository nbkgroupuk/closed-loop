import socket, struct, json, sys, time
host='project-processor'; port=9000
payload = b"0200" + json.dumps({
  "type":"iso20022",
  "protocol":"101.1",
  "auth_code":"3469",
  "payoutDetails":{"iban":"GB82WEST12345698765432"},
  "amount":100,
  "card":"4111111111111111"
}).encode('utf-8')

s = socket.create_connection((host,port), timeout=5)
s.sendall(struct.pack(">I", len(payload)) + payload)
raw = s.recv(4)
if not raw:
    print("no response length"); sys.exit(1)
length = struct.unpack(">I", raw)[0]
body = b''
while len(body) < length:
    chunk = s.recv(length - len(body))
    if not chunk: break
    body += chunk
print("resp:", body)
s.close()
