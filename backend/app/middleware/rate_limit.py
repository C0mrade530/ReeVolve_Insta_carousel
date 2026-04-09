"""
In-memory rate limiter middleware for FastAPI.
No external dependencies (no slowapi/redis needed for single-instance).
Uses token bucket per user_id extracted from JWT sub claim.
"""
import time
import json
import base64
import logging
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request

logger = logging.getLogger(__name__)


class TokenBucket:
    """Simple token bucket rate limiter."""

    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: tokens per second
            capacity: max burst size
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


# Rate limit configs per path pattern
RATE_LIMITS = {
    # Generation endpoints: strict (expensive AI calls)
    "/api/carousels/generate": {"rate": 0.1, "capacity": 3},       # ~6 per min, burst 3
    "/api/carousels/generate/batch": {"rate": 0.033, "capacity": 1},  # ~2 per min, burst 1
    "/api/carousels/generate/batch/stream": {"rate": 0.033, "capacity": 1},
    "/api/competitors/rewrite": {"rate": 0.1, "capacity": 3},
    "/api/competitors/scrape": {"rate": 0.05, "capacity": 2},       # ~3 per min
    "/api/competitors/analyze": {"rate": 0.1, "capacity": 3},
    "/api/competitors/viral-ideas": {"rate": 0.1, "capacity": 3},

    # Publishing: moderate
    "/api/carousels/publish": {"rate": 0.05, "capacity": 2},

    # Analytics refresh: moderate
    "/api/analytics/stats/refresh": {"rate": 0.033, "capacity": 1},
}

# Default: lenient for reads
DEFAULT_RATE = {"rate": 2.0, "capacity": 30}  # 120/min burst 30


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-user rate limiting middleware."""

    def __init__(self, app, enable: bool = True):
        super().__init__(app)
        self.enable = enable
        self._buckets: dict[str, TokenBucket] = {}
        self._cleanup_counter = 0

    def _get_user_key(self, request: Request) -> str:
        """
        Extract stable user identifier from JWT 'sub' claim.
        This ensures the same user always gets the same rate limit bucket
        regardless of token refresh cycles.
        """
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer ") and len(auth) > 50:
            token = auth[7:]  # Strip "Bearer "
            try:
                # JWT payload is the second segment (base64url-encoded)
                payload_b64 = token.split(".")[1]
                # Fix padding
                padding = 4 - len(payload_b64) % 4
                if padding != 4:
                    payload_b64 += "=" * padding
                payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                sub = payload.get("sub")
                if sub:
                    return f"user:{sub}"
            except Exception as e:
                logger.warning(f"[RateLimit] Failed to decode JWT sub from token: {e}")
            # Fallback: last 16 chars of token (better than nothing)
            return f"token:{token[-16:]}"
        # Fallback to IP
        client = request.client
        return f"ip:{client.host if client else 'unknown'}"

    def _get_limit_config(self, path: str, method: str) -> dict:
        """Get rate limit config for the given path."""
        # Only rate-limit POST/PUT/PATCH (mutations)
        if method in ("GET", "HEAD", "OPTIONS"):
            return DEFAULT_RATE

        # Check specific path patterns
        for pattern, config in RATE_LIMITS.items():
            if path.startswith(pattern):
                return config

        return DEFAULT_RATE

    def _get_bucket(self, key: str, config: dict) -> TokenBucket:
        """Get or create bucket for the given key."""
        bucket_key = f"{key}:{config['rate']}:{config['capacity']}"
        if bucket_key not in self._buckets:
            self._buckets[bucket_key] = TokenBucket(config["rate"], config["capacity"])
        return self._buckets[bucket_key]

    def _cleanup(self):
        """Periodically clean up old buckets."""
        self._cleanup_counter += 1
        if self._cleanup_counter % 1000 == 0:
            now = time.monotonic()
            stale_keys = [
                k for k, b in self._buckets.items()
                if now - b.last_refill > 3600  # 1 hour idle
            ]
            for k in stale_keys:
                del self._buckets[k]
            if stale_keys:
                logger.info(f"[RateLimit] Cleaned up {len(stale_keys)} stale buckets")

    async def dispatch(self, request: Request, call_next):
        if not self.enable:
            return await call_next(request)

        self._cleanup()

        user_key = self._get_user_key(request)
        config = self._get_limit_config(request.url.path, request.method)
        bucket = self._get_bucket(user_key, config)

        if not bucket.consume():
            logger.warning(f"[RateLimit] 429 for {user_key} on {request.method} {request.url.path}")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Слишком много запросов. Подождите немного.",
                    "retry_after": int(1 / config["rate"]),
                },
                headers={"Retry-After": str(int(1 / config["rate"]))},
            )

        return await call_next(request)
