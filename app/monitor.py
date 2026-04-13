"""
Request-level metrics middleware.

Tracks:
  - Total requests
  - Requests per endpoint
  - Average response latency
  - Error count

Access live stats via GET /metrics
"""
import time
import logging
from collections import defaultdict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

_metrics = {
    "total_requests": 0,
    "total_errors": 0,
    "endpoint_counts": defaultdict(int),
    "latency_sum_ms": 0.0,
    "latency_count": 0,
}


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as e:
            _metrics["total_errors"] += 1
            raise
        finally:
            elapsed_ms = (time.time() - start) * 1000
            _metrics["total_requests"] += 1
            _metrics["endpoint_counts"][request.url.path] += 1
            _metrics["latency_sum_ms"] += elapsed_ms
            _metrics["latency_count"] += 1

        if status >= 500:
            _metrics["total_errors"] += 1

        return response


def get_metrics() -> dict:
    count = _metrics["latency_count"]
    avg_latency = (
        round(_metrics["latency_sum_ms"] / count, 2) if count > 0 else 0
    )
    return {
        "total_requests": _metrics["total_requests"],
        "total_errors": _metrics["total_errors"],
        "avg_latency_ms": avg_latency,
        "endpoint_counts": dict(_metrics["endpoint_counts"]),
    }
