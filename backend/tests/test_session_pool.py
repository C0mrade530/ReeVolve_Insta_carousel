"""Tests for session pool and proxy pool."""
from datetime import datetime, timedelta
from app.services.publisher.session_pool import SessionPool, ProxyPool


class TestSessionPool:
    def _make_account(self, acct_id, active=True, has_session=True):
        return {
            "id": acct_id,
            "username": f"user_{acct_id}",
            "is_active": active,
            "session_data": {"settings": {}} if has_session else None,
            "proxy": None,
        }

    def test_pick_account_returns_active(self):
        pool = SessionPool(cooldown_minutes=30, max_failures=3)
        accounts = [self._make_account("a1"), self._make_account("a2")]
        picked = pool.pick_account(accounts)
        assert picked is not None
        assert picked["id"] in ("a1", "a2")

    def test_pick_account_skips_inactive(self):
        pool = SessionPool(cooldown_minutes=30, max_failures=3)
        accounts = [
            self._make_account("a1", active=False),
            self._make_account("a2", active=True),
        ]
        picked = pool.pick_account(accounts)
        assert picked["id"] == "a2"

    def test_pick_account_skips_no_session(self):
        pool = SessionPool(cooldown_minutes=30, max_failures=3)
        accounts = [
            self._make_account("a1", has_session=False),
            self._make_account("a2", has_session=True),
        ]
        picked = pool.pick_account(accounts)
        assert picked["id"] == "a2"

    def test_pick_account_returns_none_if_all_inactive(self):
        pool = SessionPool(cooldown_minutes=30, max_failures=3)
        accounts = [self._make_account("a1", active=False)]
        picked = pool.pick_account(accounts)
        assert picked is None

    def test_mark_used_resets_failures(self):
        pool = SessionPool(cooldown_minutes=30, max_failures=3)
        pool.mark_failed("a1", "error")
        pool.mark_used("a1")
        assert pool._failure_count["a1"] == 0

    def test_mark_failed_disables_after_max(self):
        pool = SessionPool(cooldown_minutes=30, max_failures=3)
        pool.mark_failed("a1", "err1")
        pool.mark_failed("a1", "err2")
        pool.mark_failed("a1", "err3")
        assert "a1" in pool._disabled

    def test_re_enable_clears_disabled(self):
        pool = SessionPool(cooldown_minutes=30, max_failures=3)
        for _ in range(3):
            pool.mark_failed("a1")
        assert "a1" in pool._disabled
        pool.re_enable("a1")
        assert "a1" not in pool._disabled
        assert pool._failure_count["a1"] == 0

    def test_cooldown_skips_recently_used(self):
        pool = SessionPool(cooldown_minutes=30, max_failures=3)
        accounts = [self._make_account("a1"), self._make_account("a2")]
        pool.mark_used("a1")
        picked = pool.pick_account(accounts)
        # a1 is on cooldown, should prefer a2
        assert picked["id"] == "a2"

    def test_reset_daily_counts(self):
        pool = SessionPool(cooldown_minutes=30, max_failures=3)
        pool.mark_used("a1")
        pool.mark_used("a1")
        assert pool._usage_count["a1"] == 2
        pool.reset_daily_counts()
        assert pool._usage_count.get("a1", 0) == 0

    def test_pool_status(self):
        pool = SessionPool(cooldown_minutes=30, max_failures=3)
        accounts = [self._make_account("a1")]
        status = pool.get_pool_status(accounts)
        assert status["total_accounts"] == 1
        assert status["active"] == 1


class TestProxyPool:
    def test_pick_proxy_from_pool(self):
        pool = ProxyPool(max_failures=5)
        pool.set_proxies([
            {"url": "socks5://proxy1:1080", "label": "p1"},
            {"url": "socks5://proxy2:1080", "label": "p2"},
        ])
        proxy = pool.pick_proxy()
        assert proxy in ("socks5://proxy1:1080", "socks5://proxy2:1080")

    def test_pick_proxy_empty_pool(self):
        pool = ProxyPool(max_failures=5)
        assert pool.pick_proxy() is None

    def test_mark_failed_disables_after_threshold(self):
        pool = ProxyPool(max_failures=3)
        pool.set_proxies([{"url": "socks5://p1:1080", "label": "p1"}])
        for _ in range(3):
            pool.mark_failed("socks5://p1:1080", "timeout")
        assert "socks5://p1:1080" in pool._disabled

    def test_mark_success_resets_failures(self):
        pool = ProxyPool(max_failures=5)
        pool.set_proxies([{"url": "socks5://p1:1080", "label": "p1"}])
        pool.mark_failed("socks5://p1:1080")
        pool.mark_success("socks5://p1:1080", latency_ms=100)
        assert pool._failure_count["socks5://p1:1080"] == 0

    def test_all_disabled_resets(self):
        pool = ProxyPool(max_failures=1)
        pool.set_proxies([{"url": "socks5://p1:1080", "label": "p1"}])
        pool.mark_failed("socks5://p1:1080")
        assert "socks5://p1:1080" in pool._disabled
        # pick_proxy should reset when all are disabled
        proxy = pool.pick_proxy()
        assert proxy == "socks5://p1:1080"

    def test_get_status(self):
        pool = ProxyPool(max_failures=5)
        pool.set_proxies([{"url": "socks5://p1:1080", "label": "p1"}])
        status = pool.get_status()
        assert status["total"] == 1
        assert status["active"] == 1
