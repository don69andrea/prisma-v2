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

# Endpoints that trigger LLM (Claude) or embedding (VoyageAI) calls and need
# rate limiting. Kept as precise as possible — bare prefixes like
# "/api/v1/stocks" or "/api/v1/portfolio" previously over-matched and
# throttled LLM-free GET endpoints too (F-PERF-1 / K-5). Decisions-Router
# kept as a prefix because /live, "" (list) and /explain all transitively
# call MacroService.get_context(), which makes a real Claude call — only
# /decisions/{ticker}/audit is LLM-free but is intentionally left out of
# scope here (not part of the reported finding).
_LLM_PREFIXES = (
    "/api/v1/memos/generate",
    "/api/v1/memos/batch",
    "/api/v1/chat",
    "/api/v1/macro",
    "/api/v1/portfolio/allocate",
    "/api/v1/discovery/session",
    "/api/v1/discovery/answer",
    "/api/v1/discovery/complete",
    "/api/v1/steuer",
    "/api/v1/decisions",
    "/api/v1/news/ingest",
    "/api/v1/news/retrieve",
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
            try:
                return await call_next(request)
            except Exception:
                _logger.exception("Unhandled exception for %s", path)
                return JSONResponse({"detail": "Interner Serverfehler."}, status_code=500)

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

        try:
            return await call_next(request)
        except Exception:
            _logger.exception("Unhandled exception for %s", path)
            return JSONResponse({"detail": "Interner Serverfehler."}, status_code=500)
