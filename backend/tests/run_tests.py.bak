# tests/run_tests.py
import requests, json, time
BASE = "http://localhost:8000"

def test_transaction():
    payload = {
        "merchant_id":"M123",
        "cardNumber":"TEST_PAN_REDACTED",
        "expiry":"12/29",
        "cvc":"123",
        "amount":100.00,
        "currency":"USD",
        "protocol":"POS Terminal -101.1 (4-digit approval)",
        "authCode":"1234",
        "txn_id":"550e8400-e29b-41d4-a716-446655440000",
        "correlation_id":"corr-1"
    }
    r = requests.post(BASE + "/transactions", json=payload, timeout=20)
    print("txn:", r.status_code, r.text)
    return r.json()

def test_iso20022():
    payload = {
        "creditor_name":"Alice Corp",
        "amount":150.00,
        "currency":"USD",
        "pain_xml":"<Document><PmtInf>Test</PmtInf></Document>",
        "correlation_id":"payout-1"
    }
    r = requests.post(BASE + "/payout/iso20022", json=payload, timeout=20)
    print("iso20022:", r.status_code, r.text)
    return r.json()

def test_crypto():
    payload = {"to_address":"0xDEADBEEF", "amount":0.01, "currency":"ETH", "correlation_id":"crypto-1"}
    r = requests.post(BASE + "/payout/crypto", json=payload, timeout=20)
    print("crypto:", r.status_code, r.text)
    return r.json()

if __name__ == "__main__":
    print("Running transaction test")
    t = test_transaction()
    time.sleep(1)
    print("Running iso20022 test")
    i = test_iso20022()
    time.sleep(1)
    print("Running crypto test")
    c = test_crypto()
