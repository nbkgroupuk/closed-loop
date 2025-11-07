#!/bin/sh
# start_listener.sh — start iso listener in background and log to /tmp/iso_listener.log
nohup python /app/app/iso_listener.py.bak > /tmp/iso_listener.log 2>&1 &
echo "started iso_listener (background) -> /tmp/iso_listener.log"
