"""
Instagram session rotation + proxy pool management.
Round-robin rotation across multiple IG accounts to distribute load.
Proxy health monitoring with auto-disable on repeated failures.
Thread-safe for 100+ concurrent users.
"""
import logging
import random
import threading
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class SessionPool:
    """
    Manages a pool of Instagram sessions with round-robin rotation.
    Tracks usage, cooldowns, and health per session.
    """

    def __init__(self, cooldown_minutes: int = 30, max_failures: int = 3):
        self.cooldown_minutes = cooldown_minutes
        self.max_failures = max_failures
        self._lock = threading.Lock()
        # State tracking (in-memory, refreshed from DB on each cycle)
        self._last_used: dict[str, datetime] = {}   # account_id -> last used time
        self._failure_count: dict[str, int] = defaultdict(int)  # account_id -> consecutive failures
        self._disabled: set[str] = set()  # account_ids temporarily disabled
        self._usage_count: dict[str, int] = defaultdict(int)  # account_id -> total uses today

    def pick_account(self, accounts: list[dict]) -> dict | None:
        """
        Pick the best account from available ones using round-robin + cooldown.
        Thread-safe: acquires lock for consistent state reads.

        Args:
            accounts: list of dicts with id, username, is_active, session_data, proxy, last_published_at

        Returns:
            best account dict or None if all on cooldown/disabled
        """
        with self._lock:
            now = datetime.utcnow()
            eligible = []

            for acct in accounts:
                acct_id = acct["id"]

                # Skip disabled (too many failures)
                if acct_id in self._disabled:
                    logger.debug(f"[SessionPool] Skip @{acct.get('username')} — disabled")
                    continue

                # Skip inactive
                if not acct.get("is_active"):
                    continue

                # Skip if no session
                if not acct.get("session_data"):
                    continue

                # Check cooldown
                last_used = self._last_used.get(acct_id)
                if last_used:
                    elapsed = (now - last_used).total_seconds() / 60
                    if elapsed < self.cooldown_minutes:
                        logger.debug(f"[SessionPool] Skip @{acct.get('username')} — cooldown ({elapsed:.0f}m/{self.cooldown_minutes}m)")
                        continue

                eligible.append(acct)

            if not eligible:
                # If all on cooldown, pick the one with least recent usage
                active = [a for a in accounts if a.get("is_active") and a.get("session_data") and a["id"] not in self._disabled]
                if active:
                    active.sort(key=lambda a: self._last_used.get(a["id"], datetime.min))
                    return active[0]
                return None

            # Sort by: least used today, then least recently used
            eligible.sort(key=lambda a: (
                self._usage_count.get(a["id"], 0),
                self._last_used.get(a["id"], datetime.min),
            ))

            return eligible[0]

    def mark_used(self, account_id: str):
        """Mark account as just used successfully. Thread-safe."""
        with self._lock:
            self._last_used[account_id] = datetime.utcnow()
            self._usage_count[account_id] = self._usage_count.get(account_id, 0) + 1
            self._failure_count[account_id] = 0  # Reset failures on success

    def mark_failed(self, account_id: str, reason: str = ""):
        """Mark a failed usage. Disable after max_failures. Thread-safe."""
        with self._lock:
            self._failure_count[account_id] += 1
            count = self._failure_count[account_id]
            logger.warning(f"[SessionPool] Account {account_id} failure #{count}: {reason}")

            if count >= self.max_failures:
                self._disabled.add(account_id)
                logger.error(f"[SessionPool] Account {account_id} DISABLED after {count} failures")

    def re_enable(self, account_id: str):
        """Manually re-enable a disabled account. Thread-safe."""
        with self._lock:
            self._disabled.discard(account_id)
            self._failure_count[account_id] = 0
            logger.info(f"[SessionPool] Account {account_id} re-enabled")

    def reset_daily_counts(self):
        """Reset daily usage counters (call at midnight or on demand). Thread-safe."""
        with self._lock:
            self._usage_count.clear()

    def get_pool_status(self, accounts: list[dict]) -> dict:
        """Get current pool status for monitoring. Thread-safe."""
        with self._lock:
            return self._get_pool_status_unlocked(accounts)

    def _get_pool_status_unlocked(self, accounts: list[dict]) -> dict:
        now = datetime.utcnow()
        statuses = []
        for acct in accounts:
            acct_id = acct["id"]
            last = self._last_used.get(acct_id)
            cooldown_remaining = 0
            if last:
                elapsed = (now - last).total_seconds() / 60
                cooldown_remaining = max(0, self.cooldown_minutes - elapsed)

            statuses.append({
                "account_id": acct_id,
                "username": acct.get("username"),
                "is_active": acct.get("is_active", False),
                "has_session": bool(acct.get("session_data")),
                "has_proxy": bool(acct.get("proxy")),
                "disabled": acct_id in self._disabled,
                "failure_count": self._failure_count.get(acct_id, 0),
                "usage_today": self._usage_count.get(acct_id, 0),
                "cooldown_remaining_min": round(cooldown_remaining, 1),
                "last_used": last.isoformat() if last else None,
            })

        return {
            "total_accounts": len(accounts),
            "active": sum(1 for s in statuses if s["is_active"] and not s["disabled"]),
            "disabled": sum(1 for s in statuses if s["disabled"]),
            "on_cooldown": sum(1 for s in statuses if s["cooldown_remaining_min"] > 0),
            "accounts": statuses,
        }


class ProxyPool:
    """
    Manages a pool of proxies with health monitoring.
    Tracks latency, failures, and auto-rotates on errors.
    """

    def __init__(self, max_failures: int = 5, check_interval_min: int = 60):
        self.max_failures = max_failures
        self.check_interval_min = check_interval_min
        self._lock = threading.Lock()
        self._proxies: list[dict] = []  # {url, label, failures, last_check, latency_ms, disabled}
        self._failure_count: dict[str, int] = defaultdict(int)
        self._disabled: set[str] = set()

    def set_proxies(self, proxies: list[dict]):
        """
        Set the proxy pool. Thread-safe.
        Each dict: {"url": "socks5://...", "label": "proxy-1"}
        """
        with self._lock:
            self._proxies = []
            for p in proxies:
                url = p.get("url", "")
                self._proxies.append({
                    "url": url,
                    "label": p.get("label", url[:40]),
                    "failures": self._failure_count.get(url, 0),
                    "disabled": url in self._disabled,
                    "last_check": None,
                    "latency_ms": None,
                })

    def pick_proxy(self) -> str | None:
        """Pick the best available proxy. Thread-safe."""
        with self._lock:
            available = [p for p in self._proxies if p["url"] not in self._disabled]
            if not available:
                # Reset all if all disabled
                if self._proxies:
                    logger.warning("[ProxyPool] All proxies disabled — resetting")
                    self._disabled.clear()
                    self._failure_count.clear()
                    available = self._proxies
                else:
                    return None

            # Sort by fewest failures, then lowest latency
            available.sort(key=lambda p: (
                self._failure_count.get(p["url"], 0),
                p.get("latency_ms") or 9999,
            ))
            return available[0]["url"]

    def mark_success(self, proxy_url: str, latency_ms: int | None = None):
        """Mark proxy as healthy. Thread-safe."""
        with self._lock:
            self._failure_count[proxy_url] = 0
            self._disabled.discard(proxy_url)
            for p in self._proxies:
                if p["url"] == proxy_url:
                    p["latency_ms"] = latency_ms
                    p["last_check"] = datetime.utcnow()
                    p["failures"] = 0
                    p["disabled"] = False

    def mark_failed(self, proxy_url: str, reason: str = ""):
        """Mark proxy failure. Disable after threshold. Thread-safe."""
        with self._lock:
            self._failure_count[proxy_url] += 1
            count = self._failure_count[proxy_url]
            logger.warning(f"[ProxyPool] Proxy {proxy_url[:40]} failure #{count}: {reason}")

            if count >= self.max_failures:
                self._disabled.add(proxy_url)
                logger.error(f"[ProxyPool] Proxy {proxy_url[:40]} DISABLED after {count} failures")
                for p in self._proxies:
                    if p["url"] == proxy_url:
                        p["disabled"] = True

    def get_status(self) -> dict:
        """Get proxy pool status. Thread-safe."""
        with self._lock:
            return {
                "total": len(self._proxies),
                "active": sum(1 for p in self._proxies if p["url"] not in self._disabled),
                "disabled": sum(1 for p in self._proxies if p["url"] in self._disabled),
                "proxies": [
                    {
                        "label": p["label"],
                        "url_masked": p["url"][:30] + "...",
                        "failures": self._failure_count.get(p["url"], 0),
                        "disabled": p["url"] in self._disabled,
                        "latency_ms": p.get("latency_ms"),
                        "last_check": p.get("last_check").isoformat() if p.get("last_check") else None,
                    }
                    for p in self._proxies
                ],
            }


# Thread-safe singleton instances
_session_pool = None
_proxy_pool = None
_singleton_lock = threading.Lock()


def get_session_pool() -> SessionPool:
    global _session_pool
    if _session_pool is None:
        with _singleton_lock:
            if _session_pool is None:  # Double-check locking
                _session_pool = SessionPool(cooldown_minutes=30, max_failures=3)
    return _session_pool


def get_proxy_pool() -> ProxyPool:
    global _proxy_pool
    if _proxy_pool is None:
        with _singleton_lock:
            if _proxy_pool is None:  # Double-check locking
                _proxy_pool = ProxyPool(max_failures=5)
    return _proxy_pool
