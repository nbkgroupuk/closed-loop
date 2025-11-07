#docker exec project-gateway bash -lc "cat > /workspace/gateway/app/monitoring.py" <<'PYMON'
"""
Production-safe monitoring helper for the gateway.

- Uses a private CollectorRegistry (no collisions on re-import).
- Falls back to a non-op implementation when prometheus_client is missing.
- Exposes /metrics via an APIRouter and never returns HTTP 500 to scrapers.
"""
import logging
from typing import Optional

log = logging.getLogger("gateway.metrics")

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Histogram,
        generate_latest as _generate_latest_lib,
        CONTENT_TYPE_LATEST,
    )

    _REGISTRY = CollectorRegistry()
    REQUESTS = Counter(
        "gateway_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
        registry=_REGISTRY,
    )
    FAILURES = Counter(
        "gateway_failures_total",
        "Total failures by endpoint",
        ["endpoint"],
        registry=_REGISTRY,
    )
    DURATION = Histogram(
        "gateway_request_duration_seconds",
        "Request duration in seconds",
        ["method", "endpoint"],
        registry=_REGISTRY,
    )
    HAVE_PROM = True

    def _generate_latest(registry: Optional[CollectorRegistry] = None) -> bytes:
        """Wrapper that always accepts an optional registry arg."""
        try:
            if registry is None:
                return _generate_latest_lib()
            return _generate_latest_lib(registry)
        except TypeError:
            # Older prometheus_client versions may ignore the arg
            return _generate_latest_lib()

except Exception as e:
    log.warning("prometheus_client not available: %s", e)
    HAVE_PROM = False

    class _NoOp:
        def __getattr__(self, name):
            def _noop(*a, **k):
                return None
            return _noop

    REQUESTS = FAILURES = DURATION = _NoOp()

    def _generate_latest(_=None):
        return b""

    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

from fastapi import APIRouter, Response

router = APIRouter()

@router.get("/metrics")
def metrics():
    """
    Return prometheus metrics. Always returns 200 (empty body if metrics unavailable).
    Using a private registry avoids duplicate registration errors when the module is imported
    multiple times (e.g. during reloads).
    """
    try:
        data = _generate_latest(_REGISTRY if HAVE_PROM else None)
        # Use plain text as media_type and explicitly set header to avoid duplicate charset
        return Response(
            content=data,
            media_type="text/plain",
            headers={"Content-Type": CONTENT_TYPE_LATEST},
            status_code=200,
        )
    except Exception:
        log.exception("metrics generation failed; returning empty payload")
        return Response(
            content=b"",
            media_type="text/plain",
            headers={"Content-Type": CONTENT_TYPE_LATEST},
            status_code=200,
        )

def observe_request(method: str, endpoint: str, status: int, duration: float, failed: bool = False):
    """
    Safe helper for middleware to call. Never raises.
    """
    try:
        if not HAVE_PROM:
            return
        DURATION.labels(method=method, endpoint=endpoint).observe(duration)
        REQUESTS.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        if failed:
            FAILURES.labels(endpoint=endpoint).inc()
    except Exception:
        log.debug("observe_request failed", exc_info=True)

#PYMON
