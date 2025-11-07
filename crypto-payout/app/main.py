from fastapi import FastAPI

# ✅ Minimal working gateway FastAPI app

from fastapi import FastAPI

app = FastAPI(title="Gateway Service")

@app.get("/health")
async def health():
    try:
        return {"status": "ok", "service": "gateway"}
    except Exception as e:
        return {"status": "error", "service": "gateway", "detail": str(e)}
