#!/bin/bash
set -e
PORT=${PORT:-8000}
cd gateway
exec uvicorn app.server:app --host 0.0.0.0 --port $PORT
