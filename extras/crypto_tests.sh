#!/usr/bin/env bash
set -euo pipefail
echo "Crypto payout tests"

BASE="http://localhost:8001/payouts/payout"

cases=(
'{"address":"0x73F888dcE062d2acD4A7688386F0f92f43055491","amount":5.00}'
'{"address":"0xdeadbeef00000000000000000000000000000000","amount":0.01}'  # edge: tiny amount or invalid
)

for i in "${!cases[@]}"; do
  addr=$(jq -r .address <<<"${cases[$i]}")
  amount=$(jq -r .amount <<<"${cases[$i]}")
  ref="crypto-test-$(date +%s)-$i"
  payload=$(jq -n \
    --arg m "merchant_default" \
    --arg method "crypto" \
    --argjson amount "$amount" \
    --arg currency "USD" \
    --arg protocol "101.1" \
    --arg auth_code "1234" \
    --arg addr "$addr" \
    --arg ref "$ref" \
    '{
      merchant_id: $m,
      method: $method,
      amount: ($amount+0.0),
      currency: $currency,
      protocol: $protocol,
      auth_code: $auth_code,
      crypto_wallet: { address: $addr },
      reference: $ref
    }')
  echo "== Test $((i+1)) ref=$ref =="
  echo "$payload" | jq .
  resp=$(curl -sS -X POST "$BASE" -H "Content-Type: application/json" -d "$payload")
  echo "Response: $resp" | jq . || echo "$resp"
  sleep 1
done
