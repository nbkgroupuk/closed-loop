# gateway/tools/tcp_test_client.py
# tcp_test_client.py
import asyncio, json, struct

async def main():
    host = "host.docker.internal"
    port = 9000
    fields = {
        2: "4111111111111111",
        3: "000000",
        4: "000000001000",
        7: "1010000000",
        11: "123456",
        12: "101000",
        13: "1022",
        14: "1230",
        22: "012",
        37: "000000000001",
        41: "TERM0001",
        42: "MERCHID000001",
        49: "840",
        "protocol": "101.1",
        "auth": "1234"
    }
    body = json.dumps(fields, separators=(",", ":")).encode()
    mti = b"0200"
    payload = mti + body
    framed = struct.pack(">I", len(payload)) + payload

    reader, writer = await asyncio.open_connection(host, port)
    writer.write(framed)
    await writer.drain()

    raw_len = await reader.readexactly(4)
    resp_len = struct.unpack(">I", raw_len)[0]
    resp = await reader.readexactly(resp_len)
    print("Raw response:", resp)
    writer.close()
    await writer.wait_closed()

asyncio.run(main())
