from fastapi import FastAPI
app = FastAPI(title="Gateway (minimal stub)")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway-minimal"}

# Minimal root so uvicorn import works when container runs 'uvicorn gateway_app:app ...'
