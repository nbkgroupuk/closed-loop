# Payment Gateway — README

## Purpose
This Gateway translates canonical backend transactions into ISO8583 messages, forwards them to the Processor over TCP, and handles ISO20022 bank payouts over mTLS. It provides connector skeletons for Visa/Mastercard and HSM integration hooks. The Gateway is designed to be deployed behind a Load Balancer and to integrate with the Backend service you already have.

## Endpoints
- `GET /health` — healthcheck.
- `POST /auth` — (required by Backend) Input model:
  ```json
  {
    "txn_id":"<uuid>",
    "pan":"<16-digit>",
    "expiry":"MM/YY",
    "cvc":"123",
    "amount":"12.34",
    "currency":"INR",
    "protocol":"POS Terminal -101.1 (4-digit approval)",
    "authCode":"1234",
    "correlation_id":"<uuid>"
  }
