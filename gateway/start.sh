#!/usr/bin/env bash
set -e
PORT=${PORT:-8080}
cd "$(dirname "$0")"
exec uvicorn app.server:app --host 0.0.0.0 --port "$PORT"
