#!/bin/bash
set -eu

GATEWAY_URL="http://localhost:8000/transactions"

# Example authorization hex payload — starts with ASCII MTI '0100'
# This is the sample we used previously; adjust fields if you want different PAN/STAN/AMOUNT.
AUTH_HEX="30313030F23C449108E180180000000000000016373331363230303030303030303030303031323334353637383930303030303031323334353637383930313233303030303030303031323334353637383930313233343536373839303030303030303030303030313233"

SETTLE_HEX="30323130F23C449108E180180000000000000016373331363230303030303030303030303031323334353637383930303030303031323334353637383930313233303030303030303031323334353637383930313233343536373839303030303030303030303030313233"

echo "Writing auth_req.hex..."
printf "%s" "$AUTH_HEX" > /tmp/auth_req.hex

echo "Posting AUTH (MTI 0100) to $GATEWAY_URL"
curl -s -w "\nHTTP_STATUS:%{http_code}\n" -X POST "$GATEWAY_URL" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @/tmp/auth_req.hex > /tmp/auth_resp.txt || true
cat /tmp/auth_resp.txt
echo "----"

echo "Running local parser on AUTH payload:"
python3 /workspace/gateway/app/processor_parser.py /tmp/auth_req.hex | sed -n '1,200p'
echo "----"

echo "Writing settle_ack.hex..."
printf "%s" "$SETTLE_HEX" > /tmp/settle_ack.hex

echo "Posting SETTLEMENT ACK (MTI 0210) to $GATEWAY_URL"
curl -s -w "\nHTTP_STATUS:%{http_code}\n" -X POST "$GATEWAY_URL" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @/tmp/settle_ack.hex > /tmp/settle_resp.txt || true
cat /tmp/settle_resp.txt
echo "----"

echo "Running parser on SETTLE payload:"
python3 /workspace/gateway/app/processor_parser.py /tmp/settle_ack.hex | sed -n '1,200p'
