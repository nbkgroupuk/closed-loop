# gateway/app/app/main.py  (alternate import path)
from fastapi import FastAPI
from app.server import app as gateway_app  # reuse the top-level server app for consistency
app = gateway_app
from fastapi import FastAPI

app = FastAPI(title="Gateway Service")

@app.get("/health")
async def health():
    try:
        return {"status": "ok", "service": "gateway"}
    except Exception as e:
        return {"status": "error", "service": "gateway", "detail": str(e)}
