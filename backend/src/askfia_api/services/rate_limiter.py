"""Simple in-memory rate limiter middleware.

This provides basic rate limiting when Redis is not available.
For production with multiple workers, consider using Redis-backed rate limiting.
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter using sliding window algorithm.

    Note: This works well for single-process deployments.
    For multi-process/multi-worker deployments, use Redis-backed rate limiting.
    """

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """
        Check if a request is allowed under the rate limit.

        Args:
            key: Unique identifier for the client (e.g., IP address)
            max_requests: Maximum requests allowed in the window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, requests_remaining)
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            # Clean up old requests outside the window
            self._requests[key] = [
                ts for ts in self._requests[key]
                if ts > window_start
            ]

            current_count = len(self._requests[key])

            if current_count >= max_requests:
                return False, 0

            # Record this request
            self._requests[key].append(now)
            return True, max_requests - current_count - 1

    def cleanup_old_entries(self, max_age_seconds: int = 3600):
        """Remove entries older than max_age_seconds to prevent memory growth."""
        now = time.time()
        cutoff = now - max_age_seconds

        with self._lock:
            keys_to_remove = []
            for key, timestamps in self._requests.items():
                # Keep only recent timestamps
                self._requests[key] = [ts for ts in timestamps if ts > cutoff]
                if not self._requests[key]:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._requests[key]


# Global rate limiter instance
_rate_limiter = InMemoryRateLimiter()


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check for forwarded header (behind proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain (original client)
        return forwarded.split(",")[0].strip()

    # Check for real IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.

    Applies rate limits based on client IP address.
    """

    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ("/health", "/health/ready"):
            return await call_next(request)

        client_ip = get_client_ip(request)
        is_allowed, remaining = _rate_limiter.is_allowed(
            key=f"ip:{client_ip}",
            max_requests=self.requests_per_minute,
            window_seconds=60
        )

        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit is {self.requests_per_minute} per minute.",
                    "retry_after_seconds": 60,
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                }
            )

        response = await call_next(request)

        # Add rate limit headers to successful responses
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
