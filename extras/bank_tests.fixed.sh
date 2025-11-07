#!/usr/bin/env bash
set -euo pipefail
echo "Bank flow tests"

BASE="http://localhost:8000/transactions"

cases=(
'{"cardNumber":"4242424242424242","expiry":"12/26","cvc":"123","amount":10.00,"payoutMethod":"bank","payoutDetails":{"account":"DE89370400440532013000"}}'
'{"cardNumber":"4000000000000002","expiry":"12/26","cvc":"123","amount":10.00,"payoutMethod":"bank","payoutDetails":{"account":"DE89370400440532013000"}}'
'{"cardNumber":"4242424242424242","expiry":"12/26","cvc":"123","amount":99999.00,"payoutMethod":"bank","payoutDetails":{"account":"DE89370400440532013000"}}'
)

for i in "${!cases[@]}"; do
  payload=$(jq -nc \
    --arg cardNumber "$(jq -r .cardNumber <<<"${cases[$i]}")" \
    --arg expiry "$(jq -r .expiry <<<"${cases[$i]}")" \
    --arg cvc "$(jq -r .cvc <<<"${cases[$i]}")" \
    --argjson amount "$(jq -r .amount <<<"${cases[$i]}")" \
    --argjson payoutDetails "$(jq -c .payoutDetails <<<"${cases[$i]}")" \
    '{
      merchant_id:"merchant_default",
      protocol:"101.1",
      authCode:"1234",
      terminal_id:"T001",
      currency:"USD",
      cardNumber:$cardNumber,
      expiry:$expiry,
      cvc:$cvc,
      amount:$amount,
      payoutMethod:"bank",
      payoutDetails:$payoutDetails
    }'
  )

  echo "== Test $((i+1)) =="
  echo "$payload" | jq .
  resp=$(curl -sS -X POST "$BASE" -H "Content-Type: application/json" -d "$payload")
echo "$resp" | jq . || echo "RAW: $resp"
  sleep 1
done
