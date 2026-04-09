"""
Anti-ban safety measures for Instagram publishing via instagrapi.
Implements: warmup browsing, rate limiting, human-like delays,
session rotation, cooldown periods, and account health scoring.
"""
import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


class SafetyManager:
    """
    Manages anti-ban measures for Instagram operations.
    Instagram flags accounts for:
    - Too many actions per hour/day
    - Publishing immediately after login (no browsing)
    - Posting at exact intervals (bot-like)
    - Mass operations without pauses
    - New accounts posting too fast
    """

    # Action limits per period (conservative defaults)
    LIMITS = {
        "posts_per_day": 5,
        "posts_per_hour": 2,
        "likes_per_hour": 30,
        "follows_per_hour": 15,
        "min_post_gap_seconds": 3600,     # 1 hour between posts minimum
        "min_session_age_hours": 24,      # New accounts: wait 24h before posting
        "warmup_days": 3,                  # Days of reduced activity for new accounts
        "warmup_post_limit": 1,            # Posts/day during warmup
    }

    def __init__(self):
        self.settings = get_settings()
        self._action_log: dict[str, list[datetime]] = {}  # username -> list of action timestamps

    # ─── RATE LIMITING ────────────────────────────────────────────

    def log_action(self, username: str, action: str = "publish"):
        """Record an action for rate limiting."""
        key = f"{username}:{action}"
        if key not in self._action_log:
            self._action_log[key] = []
        self._action_log[key].append(datetime.utcnow())
        # Cleanup old entries (keep last 24h)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self._action_log[key] = [t for t in self._action_log[key] if t > cutoff]

    def _count_actions(self, username: str, action: str, hours: int = 24) -> int:
        """Count actions in the last N hours."""
        key = f"{username}:{action}"
        if key not in self._action_log:
            return 0
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return len([t for t in self._action_log[key] if t > cutoff])

    def can_publish(
        self,
        username: str,
        last_published_at: Optional[datetime] = None,
        posts_today: int = 0,
        account_created_at: Optional[datetime] = None,
    ) -> dict:
        """
        Check if publishing is safe for this account right now.
        Returns {"allowed": bool, "reason": str, "wait_seconds": int}
        """
        max_daily = self.settings.max_daily_posts
        min_gap = self.settings.min_delay_between_posts

        # Check daily limit
        if posts_today >= max_daily:
            return {
                "allowed": False,
                "reason": f"Лимит {max_daily} постов/день. Подождите до завтра.",
                "wait_seconds": _seconds_until_midnight(),
            }

        # Check per-hour limit
        hourly = self._count_actions(username, "publish", hours=1)
        if hourly >= self.LIMITS["posts_per_hour"]:
            return {
                "allowed": False,
                "reason": "Макс 2 поста/час. Подождите.",
                "wait_seconds": 3600,
            }

        # Check minimum gap between posts
        if last_published_at:
            elapsed = (datetime.utcnow() - last_published_at).total_seconds()
            if elapsed < min_gap:
                remaining = int(min_gap - elapsed)
                return {
                    "allowed": False,
                    "reason": f"Между постами минимум {min_gap // 60} мин. Осталось {remaining // 60} мин.",
                    "wait_seconds": remaining,
                }

        # Check warmup period for new accounts
        if account_created_at:
            account_age = datetime.utcnow() - account_created_at
            warmup_limit = self.LIMITS["warmup_days"]
            if account_age < timedelta(days=warmup_limit):
                if posts_today >= self.LIMITS["warmup_post_limit"]:
                    return {
                        "allowed": False,
                        "reason": f"Аккаунт на прогреве. Макс {self.LIMITS['warmup_post_limit']} пост/день первые {warmup_limit} дней.",
                        "wait_seconds": _seconds_until_midnight(),
                    }

        return {"allowed": True, "reason": "OK", "wait_seconds": 0}

    # ─── HUMAN-LIKE DELAYS ────────────────────────────────────────

    def get_schedule_jitter(self) -> int:
        """
        Random jitter for scheduled posts (±15 min by default).
        Makes posting times look natural, not on-the-dot.
        """
        randomness = self.settings.schedule_randomness
        return random.randint(-randomness, randomness)

    async def random_pause(self, min_sec: float = 1.0, max_sec: float = 5.0):
        """Human-like random pause between actions."""
        delay = random.uniform(min_sec, max_sec)
        logger.debug(f"[Safety] Pausing {delay:.1f}s...")
        await asyncio.sleep(delay)

    # ─── PRE-PUBLISH WARMUP ──────────────────────────────────────

    async def pre_publish_warmup(self, client, intensity: str = "normal"):
        """
        Simulate human browsing BEFORE publishing.
        This prevents Instagram from flagging the publish
        as bot-like (login → instant post is very suspicious).

        intensity:
          - "light"   → just scroll feed (new accounts / frequent use)
          - "normal"  → scroll + like 1-2 posts
          - "deep"    → scroll + like 2-3 + view stories (cold session)
        """
        logger.info(f"[Safety] Pre-publish warmup ({intensity})...")

        try:
            # Step 1: Scroll timeline feed (always) — with short timeout
            await asyncio.sleep(random.uniform(1.5, 3.0))
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(client.get_timeline_feed),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
                logger.debug("[Safety] Timeline feed timed out (10s) — skipping warmup")
                return
            except Exception as e:
                logger.debug(f"[Safety] Timeline feed: {e} — continuing without feed")

            if intensity == "light":
                await asyncio.sleep(random.uniform(2, 4))
                logger.info("[Safety] Light warmup done")
                return

            # Step 2: Browse feed and like a few posts (normal/deep)
            await asyncio.sleep(random.uniform(2, 5))
            try:
                feed_items = await asyncio.wait_for(
                    asyncio.to_thread(client.get_timeline_feed),
                    timeout=10.0,
                )

                # Try to extract medias from feed
                medias = []
                if isinstance(feed_items, dict):
                    for item in feed_items.get("feed_items", [])[:10]:
                        m = item.get("media_or_ad")
                        if m and m.get("pk"):
                            medias.append(m["pk"])
                elif hasattr(feed_items, '__iter__'):
                    for item in list(feed_items)[:10]:
                        if hasattr(item, 'pk'):
                            medias.append(item.pk)

                # Like 1-2 random posts
                like_count = random.randint(2, 3) if intensity == "deep" else random.randint(1, 2)
                random.shuffle(medias)
                liked = 0

                for media_pk in medias[:like_count + 2]:
                    if liked >= like_count:
                        break
                    try:
                        await asyncio.sleep(random.uniform(1.5, 4.0))
                        await asyncio.to_thread(client.media_like, media_pk)
                        liked += 1
                        logger.debug(f"[Safety] Liked media {media_pk}")
                    except Exception as e:
                        logger.debug(f"[Safety] Like failed for media {media_pk}: {e}")

                logger.debug(f"[Safety] Liked {liked} posts during warmup")
            except asyncio.TimeoutError:
                logger.debug("[Safety] Feed browse timed out (10s) — skipping likes")
            except Exception as e:
                logger.debug(f"[Safety] Feed browse error: {e}")

            # Step 3: View stories tray (deep only)
            if intensity == "deep":
                await asyncio.sleep(random.uniform(2, 4))
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(client.get_reels_tray_feed),
                        timeout=10.0,
                    )
                    logger.debug("[Safety] Viewed stories tray")
                except (asyncio.TimeoutError, Exception):
                    logger.debug("[Safety] Stories tray skipped (timeout/error)")

            # Final pause before publish — critical for looking natural
            await asyncio.sleep(random.uniform(3, 8))
            logger.info(f"[Safety] Warmup done ({intensity})")

        except Exception as e:
            # Warmup failure is NOT critical — log and continue
            logger.warning(f"[Safety] Warmup error (non-critical): {e}")
            await asyncio.sleep(random.uniform(3, 6))

    def get_warmup_intensity(
        self,
        last_activity_at: Optional[datetime] = None,
        account_age_days: int = 30,
    ) -> str:
        """
        Determine warmup intensity based on account state.
        - Cold session (>6h since last activity) → deep
        - Normal session (<6h) → normal
        - Hot session (<1h) or new account → light
        """
        if account_age_days < self.LIMITS["warmup_days"]:
            return "light"  # New accounts: minimal extra actions to avoid flags

        if not last_activity_at:
            return "deep"  # Unknown last activity → assume cold session

        hours_since = (datetime.utcnow() - last_activity_at).total_seconds() / 3600

        if hours_since > 6:
            return "deep"
        elif hours_since > 1:
            return "normal"
        else:
            return "light"

    # ─── POST-PUBLISH COOLDOWN ────────────────────────────────────

    async def post_publish_cooldown(self, client):
        """
        Brief activity after publishing to look natural.
        Don't just publish and disconnect instantly.
        """
        logger.debug("[Safety] Post-publish cooldown...")
        try:
            await asyncio.sleep(random.uniform(3, 8))
            # Browse feed briefly after posting
            try:
                await asyncio.to_thread(client.get_timeline_feed)
            except Exception as e:
                logger.debug(f"[Safety] Post-publish feed browse failed: {e}")
            await asyncio.sleep(random.uniform(2, 5))
            logger.debug("[Safety] Post-publish cooldown done")
        except Exception as e:
            logger.warning(f"[Safety] Post-publish cooldown error: {e}")

    # ─── ACCOUNT HEALTH SCORING ──────────────────────────────────

    def calculate_health_score(
        self,
        posts_today: int = 0,
        posts_this_week: int = 0,
        last_error: Optional[str] = None,
        account_age_days: int = 30,
        has_proxy: bool = False,
    ) -> dict:
        """
        Calculate account health score (0-100).
        Shown in dashboard, used to throttle publishing.
        """
        score = 100

        # Posting frequency deductions
        if posts_today >= 3:
            score -= 15
        if posts_today >= 5:
            score -= 25
        if posts_this_week >= 20:
            score -= 20

        # Error history deductions
        if last_error:
            lower_error = last_error.lower()
            if "spam" in lower_error or "block" in lower_error or "feedback_required" in lower_error:
                score -= 40
            elif "challenge" in lower_error:
                score -= 20
            elif "login_required" in lower_error:
                score -= 15
            else:
                score -= 10

        # Account maturity deductions
        if account_age_days < 7:
            score -= 30
        elif account_age_days < 30:
            score -= 15

        # Proxy bonus (reduces flagging risk)
        if has_proxy:
            score += 5

        score = max(0, min(100, score))

        # Status label
        if score >= 80:
            status = "healthy"
            label = "Здоров"
        elif score >= 50:
            status = "caution"
            label = "Осторожно"
        elif score >= 25:
            status = "at_risk"
            label = "В зоне риска"
        else:
            status = "danger"
            label = "Опасность блокировки"

        return {
            "score": score,
            "status": status,
            "label": label,
            "recommendations": self._get_recommendations(score, posts_today, account_age_days, last_error),
        }

    def _get_recommendations(
        self,
        score: int,
        posts_today: int,
        account_age_days: int,
        last_error: Optional[str],
    ) -> list[str]:
        """Generate safety recommendations for user dashboard."""
        recs = []
        if score < 50:
            recs.append("Снизьте частоту публикаций на 1-2 дня")
        if posts_today >= 3:
            recs.append("Не публикуйте больше постов сегодня")
        if account_age_days < 7:
            recs.append("Новый аккаунт — макс 1 пост/день первую неделю")
        if account_age_days < 30:
            recs.append("Аккаунт на прогреве — макс 2-3 поста/день")
        if last_error and "spam" in (last_error or "").lower():
            recs.append("Был спам-блок. Подождите 48 часов перед следующей публикацией")
        if last_error and "challenge" in (last_error or "").lower():
            recs.append("Был challenge. Откройте Instagram на телефоне и подтвердите.")
        if not recs:
            recs.append("Всё в порядке. Можно публиковать.")
        return recs

    # ─── PROXY ────────────────────────────────────────────────────

    def should_use_proxy(self, account_count: int) -> bool:
        """Recommend proxy usage based on account count."""
        return account_count > 1

    def get_recommended_proxy_type(self, account_count: int) -> str:
        """Recommend proxy type."""
        if account_count <= 1:
            return "none"
        elif account_count <= 3:
            return "residential"  # Rotating residential proxy
        else:
            return "mobile"  # Mobile proxy for heavy use


# ─── HELPERS ──────────────────────────────────────────────────────

def _seconds_until_midnight() -> int:
    """Seconds until next midnight UTC."""
    now = datetime.utcnow()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


# Singleton
_safety: SafetyManager | None = None


def get_safety_manager() -> SafetyManager:
    global _safety
    if _safety is None:
        _safety = SafetyManager()
    return _safety
