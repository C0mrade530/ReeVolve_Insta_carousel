"""
Instagram competitor scraper via instagrapi.
Fetches posts from competitor accounts, extracts captions + engagement metrics.

Usage:
  scraper = InstagramScraper()
  await scraper.login(username, password, proxy)
  posts = await scraper.get_top_posts("competitor_username", count=20, sort_by="likes")
"""
import asyncio
import base64
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Monkey-patch: make extract_media_v1 tolerant to Pydantic errors
# instagrapi 2.x has strict clips_metadata models that break on
# newer Instagram API responses (missing mashup_info, None audio_filter_infos).
# We patch user_medias_paginated_v1 to skip posts that fail validation
# instead of crashing the entire batch.
# ═══════════════════════════════════════════════════════════════════
_media_patch_applied = False


def _apply_media_extraction_patch():
    """Monkey-patch instagrapi to handle Pydantic validation errors gracefully."""
    global _media_patch_applied
    if _media_patch_applied:
        return
    _media_patch_applied = True

    try:
        from instagrapi.extractors import extract_media_v1 as _original_extract
        import instagrapi.extractors as extractors_module

        def _safe_extract_media_v1(data):
            """Wrapper that catches Pydantic ValidationError for individual posts."""
            try:
                return _original_extract(data)
            except Exception as e:
                if "ValidationError" in type(e).__name__ or "validation error" in str(e).lower():
                    # Try fixing common issues in clips_metadata
                    if "clips_metadata" in data and isinstance(data["clips_metadata"], dict):
                        cm = data["clips_metadata"]
                        # Fix missing mashup_info
                        if "mashup_info" not in cm:
                            cm["mashup_info"] = {}
                        # Fix None audio_filter_infos
                        osi = cm.get("original_sound_info")
                        if isinstance(osi, dict) and osi.get("audio_filter_infos") is None:
                            osi["audio_filter_infos"] = []
                        try:
                            return _original_extract(data)
                        except Exception as e2:
                            logger.debug(f"[Scraper] Patched extract failed after fix: {e2}")
                    # Last resort: strip clips_metadata entirely
                    data_copy = dict(data)
                    data_copy.pop("clips_metadata", None)
                    try:
                        return _original_extract(data_copy)
                    except Exception as e3:
                        code = data.get("code", "?")
                        logger.warning(f"[Scraper] Skipping post {code}: {e3}")
                        return None
                raise

        extractors_module.extract_media_v1 = _safe_extract_media_v1

        # CRITICAL: media.py imports extract_media_v1 directly with
        # `from instagrapi.extractors import extract_media_v1`
        # so we must also patch the reference inside media.py's module namespace
        import instagrapi.mixins.media as media_module
        media_module.extract_media_v1 = _safe_extract_media_v1

        logger.info("[Scraper] Applied media extraction patch (Pydantic tolerance)")
    except Exception as e:
        logger.warning(f"[Scraper] Could not apply media extraction patch: {e}")


def _apply_proxy(client, proxy: str):
    """Apply proxy — auth handled via URL credentials by requests library."""
    parsed = urlparse(proxy)
    scheme = parsed.scheme or "http"
    client.set_proxy(proxy)

    # Set timeouts to avoid infinite hangs
    client.private.timeout = 30
    client.public.timeout = 30

    logger.info(f"[Scraper] Proxy: {scheme}://{parsed.hostname}:{parsed.port}")


DEVICE_SETTINGS = {
    "app_version": "357.0.0.25.101",
    "android_version": 34,
    "android_release": "14",
    "dpi": "420dpi",
    "resolution": "1080x2400",
    "manufacturer": "Google",
    "device": "shiba",
    "model": "Pixel 8",
    "cpu": "qcom",
    "version_code": "604247854",
}

SCRAPER_USER_AGENT = (
    "Instagram 357.0.0.25.101 Android "
    "(34/14; 420dpi; 1080x2400; Google/google; Pixel 8; shiba; qcom; en_US; 604247854)"
)


def _setup_client(client):
    """Apply modern device settings to avoid unsupported_version challenge."""
    client.set_device(DEVICE_SETTINGS)
    client.set_user_agent(SCRAPER_USER_AGENT)


class InstagramScraper:
    """Scrapes competitor Instagram posts via instagrapi."""

    def __init__(self):
        self._client = None
        self._logged_in = False
        _apply_media_extraction_patch()

    async def login(self, username: str, password: str, proxy: str | None = None) -> bool:
        """Login to Instagram (required to fetch posts)."""
        try:
            from instagrapi import Client

            self._client = Client()
            _setup_client(self._client)
            if proxy:
                _apply_proxy(self._client, proxy)

            # Run blocking login in thread
            result = await asyncio.to_thread(self._client.login, username, password)
            self._logged_in = bool(result)
            logger.info(f"[Scraper] Logged in as @{username}: {self._logged_in}")
            return self._logged_in

        except ImportError:
            logger.error("[Scraper] instagrapi not installed. Run: pip install instagrapi")
            return False
        except Exception as e:
            logger.error(f"[Scraper] Login failed: {e}")
            return False

    async def login_by_session(self, session_data: dict, proxy: str | None = None) -> bool:
        """Login using saved instagrapi settings dict.

        Skips heavy verification (get_timeline_feed) because it can trigger
        challenges on sessions saved during the challenge flow.
        Instead, we just load the session and try to use it directly.
        Errors are handled at the point of actual API calls.
        """
        try:
            from instagrapi import Client

            self._client = Client()
            _setup_client(self._client)
            if proxy:
                _apply_proxy(self._client, proxy)

            # Handle both formats: raw settings dict or {"settings": {...}} wrapper
            settings = session_data
            if isinstance(session_data, dict) and "settings" in session_data and isinstance(session_data["settings"], dict):
                settings = session_data["settings"]

            if not settings or not isinstance(settings, dict):
                logger.warning(f"[Scraper] Empty or invalid session data: type={type(session_data)}, keys={list(session_data.keys()) if isinstance(session_data, dict) else 'N/A'}")
                return False

            logger.info(f"[Scraper] Loading session settings (keys: {list(settings.keys())[:5]}...)")
            await asyncio.to_thread(self._client.set_settings, settings)

            # CRITICAL: re-apply device + proxy after set_settings (it overwrites both!)
            _setup_client(self._client)
            if proxy:
                _apply_proxy(self._client, proxy)
                logger.info("[Scraper] Re-applied device+proxy after set_settings")

            # Light verification: just check that we have authorization header
            # Don't call get_timeline_feed() — it triggers challenges
            auth = settings.get("authorization_data", {})
            uds_token = settings.get("uds_user_id")
            has_cookies = bool(settings.get("cookies"))

            if auth or uds_token or has_cookies:
                self._logged_in = True
                logger.info(f"[Scraper] Session loaded OK (auth={'yes' if auth else 'no'}, cookies={'yes' if has_cookies else 'no'})")
                return True

            # Fallback: try a lightweight API call
            try:
                logger.info("[Scraper] No auth tokens found, trying lightweight verification...")
                await asyncio.to_thread(self._client.account_info)
                self._logged_in = True
                logger.info("[Scraper] Session verified via account_info")
                return True
            except Exception as e:
                logger.warning(f"[Scraper] Session verification failed: {e}")
                return False

        except Exception as e:
            logger.error(f"[Scraper] Session login failed: {e}")
            return False

    async def get_user_info(self, username: str) -> dict | None:
        """Get basic user info (followers, bio, etc)."""
        if not self._client:
            return None

        try:
            user = await asyncio.to_thread(self._client.user_info_by_username, username)
            return {
                "user_id": str(user.pk),
                "username": user.username,
                "full_name": user.full_name,
                "biography": user.biography,
                "followers": user.follower_count,
                "following": user.following_count,
                "media_count": user.media_count,
                "is_business": user.is_business,
                "profile_pic_url": str(user.profile_pic_url),
            }
        except Exception as e:
            err_str = str(e).lower()
            if "login_required" in err_str or "challenge" in err_str:
                logger.error(f"[Scraper] Session invalid for @{username}: {e}")
                self._logged_in = False
            else:
                logger.error(f"[Scraper] Failed to get user info for @{username}: {e}")
            return None

    async def get_user_posts(
        self,
        username: str,
        count: int = 30,
    ) -> list[dict]:
        """Fetch recent posts from a user. Returns list of post dicts."""
        if not self._client:
            logger.error("[Scraper] Not logged in")
            return []

        try:
            # Get user ID
            user_id = await asyncio.to_thread(
                self._client.user_id_from_username, username
            )

            # Fetch medias
            medias = await asyncio.to_thread(
                self._client.user_medias, user_id, count
            )

            # Filter out None (from patched extract_media_v1 that skips broken posts)
            medias = [m for m in medias if m is not None]

            posts = []
            for m in medias:
                post = {
                    "media_id": str(m.pk),
                    "media_type": str(m.media_type),  # 1=Photo, 2=Video, 8=Album(carousel)
                    "caption": m.caption_text or "",
                    "likes": m.like_count or 0,
                    "comments": m.comment_count or 0,
                    "timestamp": m.taken_at.isoformat() if m.taken_at else None,
                    "is_carousel": m.media_type == 8,
                    "carousel_count": len(m.resources) if m.resources else 0,
                    "url": f"https://www.instagram.com/p/{m.code}/",
                    "thumbnail_url": str(m.thumbnail_url) if m.thumbnail_url else None,
                }
                # Engagement rate estimate (likes + comments * 2)
                post["engagement_score"] = post["likes"] + post["comments"] * 2
                posts.append(post)

            logger.info(f"[Scraper] Fetched {len(posts)} posts from @{username}")
            return posts

        except Exception as e:
            logger.error(f"[Scraper] Failed to fetch posts for @{username}: {e}")
            return []

    async def get_top_posts(
        self,
        username: str,
        count: int = 30,
        top_n: int = 5,
        sort_by: str = "engagement",  # engagement | likes | comments
        carousels_only: bool = False,
    ) -> list[dict]:
        """Fetch posts and return top N sorted by engagement."""
        posts = await self.get_user_posts(username, count)

        if carousels_only:
            posts = [p for p in posts if p["is_carousel"]]

        # Sort
        sort_key = {
            "engagement": lambda p: p["engagement_score"],
            "likes": lambda p: p["likes"],
            "comments": lambda p: p["comments"],
        }.get(sort_by, lambda p: p["engagement_score"])

        posts.sort(key=sort_key, reverse=True)

        return posts[:top_n]

    async def get_user_reels(
        self,
        username: str,
        count: int = 30,
    ) -> list[dict]:
        """Fetch reels/videos from a user. Returns list of reel dicts with view counts."""
        if not self._client:
            logger.error("[Scraper] Not logged in")
            return []

        try:
            user_id = await asyncio.to_thread(
                self._client.user_id_from_username, username
            )

            # user_clips returns reels specifically
            try:
                medias = await asyncio.to_thread(
                    self._client.user_clips, user_id, count
                )
            except (AttributeError, Exception) as clips_err:
                # Fallback: filter videos from user_medias
                logger.info(f"[Scraper] user_clips failed ({clips_err}), filtering from user_medias")
                all_medias = await asyncio.to_thread(
                    self._client.user_medias, user_id, count * 2
                )
                medias = [m for m in all_medias if m is not None and m.media_type == 2][:count]

            medias = [m for m in medias if m is not None]

            reels = []
            for m in medias:
                reel = {
                    "media_id": str(m.pk),
                    "code": m.code,
                    "media_type": "reel",
                    "caption": m.caption_text or "",
                    "likes": m.like_count or 0,
                    "comments": m.comment_count or 0,
                    "views": getattr(m, "view_count", 0) or getattr(m, "play_count", 0) or 0,
                    "timestamp": m.taken_at.isoformat() if m.taken_at else None,
                    "url": f"https://www.instagram.com/reel/{m.code}/",
                    "thumbnail_url": str(m.thumbnail_url) if m.thumbnail_url else None,
                    "duration_sec": getattr(m, "video_duration", 0) or 0,
                }
                # Viral score: views heavily weighted
                reel["engagement_score"] = reel["likes"] + reel["comments"] * 3
                reel["viral_score"] = reel["views"] + reel["likes"] * 5 + reel["comments"] * 10
                reels.append(reel)

            logger.info(f"[Scraper] Fetched {len(reels)} reels from @{username}")
            return reels

        except Exception as e:
            err_str = str(e).lower()
            if "login_required" in err_str or "challenge" in err_str:
                self._logged_in = False
            logger.error(f"[Scraper] Failed to fetch reels for @{username}: {e}")
            return []

    async def get_top_reels(
        self,
        username: str,
        count: int = 30,
        top_n: int = 10,
    ) -> list[dict]:
        """Fetch reels and return top N by viral score (views + engagement)."""
        reels = await self.get_user_reels(username, count)
        reels.sort(key=lambda r: r["viral_score"], reverse=True)
        return reels[:top_n]

    async def get_reels_analysis_text(
        self,
        username: str,
        count: int = 30,
        top_n: int = 10,
    ) -> str:
        """Get top reels as formatted text for AI analysis."""
        reels = await self.get_top_reels(username, count=count, top_n=top_n)
        if not reels:
            return ""

        lines = []
        for i, r in enumerate(reels, 1):
            lines.append(f"--- REELS #{i} ---")
            lines.append(f"Просмотры: {r['views']:,}, Лайки: {r['likes']:,}, Комменты: {r['comments']:,}")
            lines.append(f"Длительность: {r['duration_sec']}сек")
            lines.append(f"URL: {r['url']}")
            lines.append(f"Текст: {r['caption']}")
            lines.append("")

        return "\n".join(lines)

    async def get_post_captions_text(
        self,
        username: str,
        count: int = 30,
        top_n: int = 10,
        carousels_only: bool = False,
    ) -> str:
        """Get top posts as formatted text for GPT analysis."""
        posts = await self.get_top_posts(
            username, count=count, top_n=top_n,
            sort_by="engagement", carousels_only=carousels_only,
        )

        if not posts:
            return ""

        lines = []
        for i, p in enumerate(posts, 1):
            post_type = "Карусель" if p["is_carousel"] else "Пост"
            lines.append(f"--- ПОСТ #{i} ({post_type}) ---")
            lines.append(f"Лайки: {p['likes']}, Комменты: {p['comments']}")
            lines.append(f"Текст: {p['caption']}")
            lines.append("")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Singleton scraper instance (reuses login session)
# ═══════════════════════════════════════════════════════════════════

_scraper_instance: Optional[InstagramScraper] = None


async def get_scraper(
    username: str | None = None,
    password: str | None = None,
    proxy: str | None = None,
    session_data: dict | None = None,
) -> InstagramScraper:
    """Get or create a logged-in scraper instance."""
    global _scraper_instance

    if _scraper_instance and _scraper_instance._logged_in:
        return _scraper_instance

    scraper = InstagramScraper()

    if session_data:
        await scraper.login_by_session(session_data, proxy)
    elif username and password:
        await scraper.login(username, password, proxy)

    _scraper_instance = scraper
    return scraper
