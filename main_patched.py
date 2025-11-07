# /app/app/main.py - patched to expose the FastAPI app from app.server
# This keeps one canonical app entrypoint for uvicorn while reusing your server module.
try:
    # import the app object from app.server (the file we patched earlier)
    from importlib import import_module
    server_mod = import_module("app.server")
    app = getattr(server_mod, "app")
except Exception as e:
    # Fallback minimal app so container still starts and exposes /health
    from fastapi import FastAPI
    app = FastAPI(title="Gateway Service (fallback)")
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "gateway", "fallback": True, "import_error": str(e)}
