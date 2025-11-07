import logging
import time
from fastapi import APIRouter

router = APIRouter()

# minimal prometheus-like metrics placeholder
METRICS = {
    "uptime_seconds": lambda start: int(time.time() - start),
    "requests_total": 0,
}

start_time = time.time()

@router.get("/metrics")
async def metrics_endpoint():
    METRICS["requests_total"] += 1
    return {
        "uptime_seconds": METRICS["uptime_seconds"](start_time),
        "requests_total": METRICS["requests_total"],
    }
