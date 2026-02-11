import uvicorn
import logging
from uuid import uuid4
import stripe # stripe added on 22-dec-2025

from fastapi import FastAPI
from app import settlement_switch
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.routes import router as api_router
from app.app.iso20022_api import router as iso20022_router
from app.config import settings
from app.telemetry.metrics import metrics_endpoint
from app.telemetry.logging import configure_logging
from app.auth_routes import router as auth_router
from app.auth.routes import router as auth_router # NEW for UI Modification
from app.iso20022_api import router as iso20022_router

# configure logging early
configure_logging(getattr(settings, "LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title=getattr(settings, "APP_NAME", "backend"),
    version="0.1.0",
)

from app.routes import router as test_router # Added for test
app.include_router(test_router)              # Added for test

# Auth routes
app.include_router(api_router)
app.include_router(iso20022_router)
app.include_router(iso20022_router)
app.include_router(auth_router)  # New for UI Modification
app.include_router(settlement_switch.router)

# CORS – include your Cloudflare domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "https://rutlandprojects.com",
        "https://www.rutlandprojects.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# telemetry endpoint
app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])

# include main routes
from app.iso20022_api import router as iso20022_router

# --- lightweight health endpoints for nginx / frontend status checks ---
@app.get("/health", include_in_schema=False)
async def health_root():
    return {"status": "ok", "service": getattr(settings, "APP_NAME", "backend")}

@app.get("/api/health", include_in_schema=False)
async def health_api():
    return {"status": "ok", "service": getattr(settings, "APP_NAME", "backend")}
