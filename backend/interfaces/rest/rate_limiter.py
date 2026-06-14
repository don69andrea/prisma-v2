"""Simple in-process rate limiter for LLM-triggering endpoints.

No external dependencies — uses asyncio.Lock + deque for per-IP tracking.
Suitable for single-process deployments (Render free tier). For multi-process
or distributed deployments, replace with Redis-backed slowapi.
"""

import asyncio
import logging
from collections import defaultdict, deque
from time import monotonic

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_logger = logging.getLogger(__name__)

# Endpoints that trigger LLM calls and need rate limiting.
_LLM_PREFIXES = (
    "/memos/generate",
    "/memos/batch",
    "/api/v1/chat",
    "/api/v1/macro/score",
    "/api/v1/portfolio/monte-carlo",
    "/api/v1/portfolio",
    "/api/v1/discovery",
    "/api/v1/steuer",
    "/api/v1/decisions/explain",
    "/api/v1/news/ingest",
    "/api/v1/backtests",
    "/api/v1/stocks",
    "/api/v1/runs",
)

# 10 LLM-triggering requests per IP per 60 seconds.
_MAX_CALLS = 10
_WINDOW_SECONDS = 60.0


class LLMRateLimiterMiddleware(BaseHTTPMiddleware):
    """Limits requests to LLM endpoints per client IP within a sliding window."""

    def __init__(
        self, app: object, *, max_calls: int = _MAX_CALLS, window_seconds: float = _WINDOW_SECONDS
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max = max_calls
        self._window = window_seconds
        self._calls: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in _LLM_PREFIXES):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{path}"

        async with self._lock:
            now = monotonic()
            window_start = now - self._window
            bucket = self._calls[key]
            while bucket and bucket[0] < window_start:
                bucket.popleft()
            if len(bucket) >= self._max:
                _logger.warning("Rate limit exceeded: ip=%s path=%s", client_ip, path)
                return JSONResponse(
                    {"detail": "Rate limit exceeded. Please retry later."},
                    status_code=429,
                    headers={"Retry-After": str(int(self._window))},
                )
            bucket.append(now)

        return await call_next(request)
