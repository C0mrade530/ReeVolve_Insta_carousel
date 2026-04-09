"""Tests for token bucket rate limiter."""
import time
from app.middleware.rate_limit import TokenBucket, RateLimitMiddleware


class TestTokenBucket:
    def test_initial_capacity(self):
        bucket = TokenBucket(rate=1.0, capacity=5)
        assert bucket.tokens == 5

    def test_consume_reduces_tokens(self):
        bucket = TokenBucket(rate=1.0, capacity=5)
        assert bucket.consume() is True
        assert bucket.tokens < 5

    def test_consume_until_empty(self):
        bucket = TokenBucket(rate=0.001, capacity=3)
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is False

    def test_refill_over_time(self):
        bucket = TokenBucket(rate=1000.0, capacity=5)
        # Drain
        for _ in range(5):
            bucket.consume()
        # Force refill by advancing time
        bucket.last_refill = time.monotonic() - 1.0
        assert bucket.consume() is True

    def test_capacity_cap(self):
        bucket = TokenBucket(rate=1000.0, capacity=3)
        bucket.last_refill = time.monotonic() - 100  # lots of elapsed time
        bucket.consume()
        # Tokens should not exceed capacity
        assert bucket.tokens <= 3


class TestRateLimitMiddleware:
    def test_get_limit_config_default_for_get(self):
        middleware = RateLimitMiddleware(app=None, enable=True)
        config = middleware._get_limit_config("/api/carousels", "GET")
        assert config["rate"] == 2.0
        assert config["capacity"] == 30

    def test_get_limit_config_strict_for_generation(self):
        middleware = RateLimitMiddleware(app=None, enable=True)
        config = middleware._get_limit_config("/api/carousels/generate/topic", "POST")
        assert config["rate"] == 0.1
        assert config["capacity"] == 3

    def test_get_bucket_creates_new(self):
        middleware = RateLimitMiddleware(app=None, enable=True)
        bucket = middleware._get_bucket("user:123", {"rate": 1.0, "capacity": 5})
        assert isinstance(bucket, TokenBucket)

    def test_get_bucket_reuses_existing(self):
        middleware = RateLimitMiddleware(app=None, enable=True)
        config = {"rate": 1.0, "capacity": 5}
        b1 = middleware._get_bucket("user:123", config)
        b2 = middleware._get_bucket("user:123", config)
        assert b1 is b2
