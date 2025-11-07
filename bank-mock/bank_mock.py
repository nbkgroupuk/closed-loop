from fastapi import FastAPI, Request, Response
import uvicorn, json, logging

app = FastAPI()
LOG = logging.getLogger("bank-mock")
LOG.setLevel(logging.INFO)

@app.post("/iso20022")
async def bank_payout(request: Request):
    # Accept JSON or raw XML/text. Log headers and body for debugging.
    headers = dict(request.headers)
    try:
        # Try JSON first
        data = await request.json()
        LOG.info("bank-mock received JSON payload")
    except Exception:
        # Fallback: read raw bytes (XML likely)
        raw = await request.body()
        try:
            data = raw.decode('utf-8', errors='replace')
            LOG.info("bank-mock received RAW payload (len=%d)", len(raw))
        except Exception:
            data = None
            LOG.info("bank-mock received unreadable raw payload")
    LOG.info("Headers: %s", {k: headers.get(k) for k in ("content-type","user-agent")})
    LOG.info("Body (sample): %s", (json.dumps(data) if isinstance(data, (dict,list)) else (data[:100] if data else "<empty>")))

    # Return a stable accepted response for tests (propagate fields if useful)
    resp = {"status": "accepted", "response_code": "00", "message": "Mock bank approved (00)"}
    return Response(content=json.dumps(resp), media_type="application/json")

@app.get("/health")
async def health():
    return {"status":"ok","service":"bank-mock"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
