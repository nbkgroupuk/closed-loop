# BlackRock Backend (FastAPI)

Production-grade FastAPI backend for the BlackRock Virtual Terminal.
Implements transaction validation, idempotency, outbox, websocket events and payout outbox for ISO20022 + crypto.

See frontend `index.html` for protocol/auth mapping which is enforced by server. :contentReference[oaicite:5]{index=5}

## Local development
1. Copy `.env.example` -> `.env` and adjust values.
2. Run `docker/docker-compose.yml`:
cd docker
docker-compose up --build

markdown
Copy code
3. Visit `http://localhost:8000/health`.

## Deploy to Render
- Create Web Service for backend: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Create Background Worker for `python -m app.worker`
- Configure env vars in Render UI.

## Security notes
- Do not store full PAN or CVC. The code only stores masked PAN.
- HSM integration for PIN and MAC must replace stubs before PCI scope reduction.
