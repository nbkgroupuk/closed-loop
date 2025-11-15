#!/bin/bash
set -e
PORT=${PORT:-8080}

# Go into gateway folder
cd gateway

# Start FastAPI
exec uvicorn app.server:app --host 0.0.0.0 --port $PORT
