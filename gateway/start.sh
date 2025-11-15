#!/usr/bin/env bash
set -e
# Railway provides $PORT at runtime; fallback to 8080 for local tests
PORT=${PORT:-8080}
cd gateway
exec uvicorn app.server:app --host 0.0.0.0 --port "$PORT"
