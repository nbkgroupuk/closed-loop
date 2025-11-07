#!/bin/sh
# start.sh — start iso listener in background, then exec uvicorn in foreground
# Logs from iso_listener go to /tmp/iso_listener.log
nohup python /app/app/iso_listener.py.bak > /tmp/iso_listener.log 2>&1 &
# Give listener a moment (safe short sleep)
sleep 1
# Exec uvicorn in foreground so Docker manages the main process
exec uvicorn app.server:app --host 0.0.0.0 --port 8000
