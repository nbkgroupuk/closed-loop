# backend/app/main.py
import uvicorn
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router as api_router
from app.config import settings
from app.telemetry.metrics import metrics_endpoint
from app.telemetry.logging import configure_logging
from app.auth_routes import router as auth_router

# configure logging early
configure_logging(getattr(settings, "LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# create FastAPI app
app = FastAPI(title=getattr(settings, "APP_NAME", "backend"), version="0.1.0")
app.include_router(auth_router)

# ✅ Correct CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "https://your-frontend-domain.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# telemetry endpoint
app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])

# include main routes
app.include_router(api_router)

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": getattr(settings, "APP_NAME", "backend")}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="info")