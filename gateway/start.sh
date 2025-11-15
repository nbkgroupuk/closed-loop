#!/usr/bin/env bash
set -e
# Railway sets $PORT for you; fall back to 8080 only for local testing
PORT=${PORT:-8080}
cd gateway
exec uvicorn app.server:app --host 0.0.0.0 --port "$PORT"
