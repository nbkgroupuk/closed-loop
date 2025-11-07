# backend/app/server.py
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Logging setup
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("backend.server")

# Create FastAPI app
app = FastAPI(title=os.environ.get("APP_NAME", "backend"), version="0.1.0")

# CORS - permissive for dev; tighten in production
_allowed = os.environ.get("ALLOWED_ORIGINS", "*")
if _allowed == "*":
    origins = ["*"]
else:
    origins = [o.strip() for o in _allowed.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static if present (optional)
STATIC_DIR = os.path.join(os.getcwd(), "app", "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info("Mounted static folder: %s", STATIC_DIR)
else:
    logger.debug("Static folder not found at %s", STATIC_DIR)

# Try to include the main application routes (if present)
try:
    from app import routes as routes_mod
    if hasattr(routes_mod, "router"):
        app.include_router(routes_mod.router)
        logger.info("Included main routes from app.routes")
    else:
        logger.warning("app.routes exists but has no 'router' attribute")
except Exception as e:
    logger.exception("Could not include app.routes (continuing without it): %s", e)

# Attempt to include payout admin router (if present)
try:
    from app.routes_payout import router as payout_router
    app.include_router(payout_router)
    logger.info("Included admin payout router (app.routes_payout)")
except ModuleNotFoundError:
    logger.info("app.routes_payout not found; skipping payout router (create app/routes_payout.py to enable)")
except Exception as e:
    logger.exception("Error including app.routes_payout: %s", e)

# Optional: other admin or monitoring routers can be included similarly
# e.g. try: from app.server_admin import app as admin_app ...

@app.get("/health")
async def health():
    """Simple health endpoint"""
    return {"status": "ok", "service": os.environ.get("APP_NAME", "backend")}

# run with: python -m app.server  (or uvicorn app.server:app ...)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), log_level="info")
