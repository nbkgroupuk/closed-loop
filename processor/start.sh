#!/bin/bash
cd /app || cd /usr/src/app || true
if [ -d app ]; then
  exec uvicorn app.server:app --host 0.0.0.0 --port 8000
else
  exec uvicorn server:app --host 0.0.0.0 --port 8000
fi
