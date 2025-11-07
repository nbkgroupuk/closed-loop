# gateway/app/main.py

from fastapi import FastAPI
from . import iso20022_adapter

# ✅ Minimal working gateway FastAPI app

app = FastAPI(title="Gateway Service")

app.include_router(iso20022_adapter.router)

@app.get("/health")
async def health():
    try:
        return {"status": "ok", "service": "gateway"}
    except Exception as e:
        return {"status": "error", "service": "gateway", "detail": str(e)}
