"""Tests for Instagram publisher client cache (LRU + TTL)."""
import time
from unittest.mock import MagicMock
from app.services.publisher.instagram import InstagramPublisher, MAX_CACHED_CLIENTS, CLIENT_TTL_SECONDS


class TestInstagramClientCache:
    def test_cache_and_retrieve(self):
        pub = InstagramPublisher()
        mock_client = MagicMock()
        pub.cache_client("acct-1", mock_client)
        assert pub.get_cached_client("acct-1") is mock_client

    def test_cache_miss_returns_none(self):
        pub = InstagramPublisher()
        assert pub.get_cached_client("nonexistent") is None

    def test_remove_cached_client(self):
        pub = InstagramPublisher()
        mock_client = MagicMock()
        pub.cache_client("acct-1", mock_client)
        pub.remove_cached_client("acct-1")
        assert pub.get_cached_client("acct-1") is None

    def test_ttl_expiry(self):
        pub = InstagramPublisher()
        mock_client = MagicMock()
        # Insert with old timestamp
        pub._clients["acct-1"] = (mock_client, time.time() - CLIENT_TTL_SECONDS - 1)
        assert pub.get_cached_client("acct-1") is None

    def test_max_size_eviction(self):
        pub = InstagramPublisher()
        # Fill beyond max
        for i in range(MAX_CACHED_CLIENTS + 5):
            pub.cache_client(f"acct-{i}", MagicMock())
        assert len(pub._clients) <= MAX_CACHED_CLIENTS

    def test_lru_order_updated_on_access(self):
        pub = InstagramPublisher()
        pub.cache_client("acct-1", MagicMock())
        pub.cache_client("acct-2", MagicMock())
        # Access acct-1 to move it to end
        pub.get_cached_client("acct-1")
        keys = list(pub._clients.keys())
        assert keys[-1] == "acct-1"

    def test_remove_nonexistent_is_safe(self):
        pub = InstagramPublisher()
        pub.remove_cached_client("nonexistent")  # Should not raise
