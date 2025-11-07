# Payment Processor

This Processor listens for ISO messages (framed) from the Gateway and runs clearing, settlement, and simple payout workers.

## Quick start (local)
1. Copy `.env.example` -> `.env` and set `DATABASE_URL`.
2. Run docker-compose in `docker/`:
docker-compose up --build

pgsql
Copy code
3. Admin HTTP is available at `http://localhost:8000/health` and `http://localhost:8000/events`.
4. TCP listener listens on port 5000 (framed ISO) and will accept messages from Gateway.

## Compatibility
- Uses the simple JSON-framing used by Gateway `iso8583.pack_iso` / `unpack_iso`. If you swap to binary ISO8583, update both gateway and processor iso pack/unpack modules.

## Extending
- Replace `IssuerSimulator` with real issuer connectors and HSM calls.
- Add reconciliation with bank statements and pacs.002 parsing.
- Add secure key storage and operations for crypto worker.
