# backend/app/telemetry/metrics.py
from fastapi import APIRouter, Response
from prometheus_client import (
    Counter,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# ---------------------------------------------------
# Router
# ---------------------------------------------------
router = APIRouter(tags=["metrics"])

# ---------------------------------------------------
# BUSINESS METRICS (DEFINED ONCE, HERE ONLY)
# ---------------------------------------------------

stripe_requests_total = Counter(
    "stripe_requests_total",
    "Stripe requests",
    ["operation", "status"],
)

stripe_amount_total_minor = Counter(
    "stripe_amount_total_minor",
    "Total Stripe processed amount (minor units)",
    ["currency"],
)

payouts_total = Counter(
    "payouts_total",
    "Total payouts",
    ["method", "status"],
)

# ---------------------------------------------------
# /metrics endpoint (ONLY ONE IN SYSTEM)
# ---------------------------------------------------
@router.get("/metrics", include_in_schema=False)
def metrics():
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

# ---------------------------------------------------
# EXPORTS
# ---------------------------------------------------
metrics_router = router
