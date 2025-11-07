# app/telemetry/metrics.py
"""
Prometheus metrics helper and FastAPI integration.
Expose /metrics endpoint by mounting the prometheus ASGI app or using pushgateway if required.
"""
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import Summary
from fastapi import Response

# Metrics (examples)
REQUEST_COUNT = Counter("backend_requests_total", "Total number of requests", ["method", "endpoint", "http_status"])
TRANSACTIONS_CREATED = Counter("transactions_created_total", "Total created transactions")
PAYOUTS_SENT = Counter("payouts_sent_total", "Total payouts sent", ["type"])
TRANSACTION_LATENCY = Histogram("transaction_processing_seconds", "Time to process transaction")

def metrics_endpoint():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
