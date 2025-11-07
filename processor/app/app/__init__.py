# processor/app/app/__init__.py
# Expose FastAPI `app` so uvicorn target "app.app:app" works.
# Prefer processor/app/app/server.py, fallback to processor/app/server.py.
try:
    from .server import app as app  # type: ignore
except Exception as _e1:
    try:
        from server import app as app  # type: ignore
    except Exception as _e2:
        raise ImportError(
            "Could not import FastAPI 'app' for module 'app.app'. "
            "Tried '.server' and 'server'. "
            f"Errors: primary={_e1!r}, fallback={_e2!r}"
        )
