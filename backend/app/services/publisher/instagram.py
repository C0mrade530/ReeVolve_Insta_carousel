"""
Instagram publisher via instagrapi.
Handles: login, session management, carousel publishing, insights.
"""
import asyncio
import logging
import json
import random
import time
import threading
from collections import OrderedDict
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_CACHED_CLIENTS = 50
CLIENT_TTL_SECONDS = 7200  # 2 hours


class InstagramPublisher:
    """Publishes carousels to Instagram via instagrapi."""

    def __init__(self):
        self._clients: OrderedDict[str, tuple] = OrderedDict()  # account_id -> (client, last_used_ts)
        self._clients_lock = threading.Lock()

    def _cleanup_clients(self):
        """Remove expired and excess cached clients. Must hold _clients_lock."""
        now = time.time()
        expired = [k for k, (_, ts) in self._clients.items() if now - ts > CLIENT_TTL_SECONDS]
        for k in expired:
            del self._clients[k]
            logger.debug(f"[Instagram] Evicted expired client: {k}")
        while len(self._clients) > MAX_CACHED_CLIENTS:
            evicted_key, _ = self._clients.popitem(last=False)
            logger.debug(f"[Instagram] Evicted LRU client: {evicted_key}")

    def get_cached_client(self, account_id: str):
        """Get cached client by account_id. Returns Client or None."""
        with self._clients_lock:
            self._cleanup_clients()
            entry = self._clients.get(account_id)
            if entry:
                client, _ = entry
                self._clients[account_id] = (client, time.time())
                self._clients.move_to_end(account_id)
                return client
        return None

    def cache_client(self, account_id: str, client):
        """Cache a client for later reuse."""
        with self._clients_lock:
            self._clients[account_id] = (client, time.time())
            self._clients.move_to_end(account_id)
            self._cleanup_clients()

    def remove_cached_client(self, account_id: str):
        """Remove a client from cache (e.g. on failure)."""
        with self._clients_lock:
            self._clients.pop(account_id, None)

    # Modern device settings to avoid "unsupported_version" challenge
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

    USER_AGENT = (
        "Instagram 357.0.0.25.101 Android "
        "(34/14; 420dpi; 1080x2400; Google/google; Pixel 8; shiba; qcom; en_US; 604247854)"
    )

    def _create_client(self, proxy: str | None = None):
        """Create a new instagrapi Client instance."""
        from instagrapi import Client
        cl = Client()

        # Set modern device to avoid "unsupported_version" challenge
        cl.set_device(self.DEVICE_SETTINGS)
        cl.set_user_agent(self.USER_AGENT)

        if proxy:
            self._apply_proxy(cl, proxy)
        # Human-like settings
        cl.delay_range = [1, 3]
        return cl

    def _apply_proxy(self, cl, proxy: str):
        """
        Apply proxy with proper auth handling.
        Supports http://, socks5://, socks5h:// formats.
        Auth credentials are passed via URL (handled by requests library).
        If no scheme provided, defaults to socks5h://.
        """
        from urllib.parse import urlparse

        # Auto-add socks5h:// if no scheme provided
        if not proxy.startswith(("http://", "https://", "socks5://", "socks5h://", "socks4://")):
            proxy = f"socks5h://{proxy}"
            logger.info(f"[Instagram] Auto-prefixed proxy with socks5h://")

        parsed = urlparse(proxy)
        scheme = parsed.scheme or "socks5h"

        # Set proxy via instagrapi (auth is handled via URL credentials)
        cl.set_proxy(proxy)

        # Set timeouts to avoid infinite hangs
        cl.private.timeout = 30
        cl.public.timeout = 30

        logger.info(f"[Instagram] Proxy set: {scheme}://{parsed.hostname}:{parsed.port}")

    def _do_login_raw(self, cl, username: str, password: str):
        """
        Low-level login that captures session even on challenge.
        Returns dict with status info and settings if available.

        IMPORTANT: We override login_flow() to prevent instagrapi from calling
        get_reels_tray_feed / get_timeline_feed after login. These calls
        trigger challenges on new devices/IPs and taint the session.
        """
        from instagrapi.exceptions import (
            BadPassword,
            ChallengeRequired,
            LoginRequired,
            PleaseWaitFewMinutes,
            ChallengeUnknownStep,
            ChallengeError,
            ClientJSONDecodeError,
            ProxyAddressIsBlocked,
            RateLimitError,
            SentryBlock,
        )

        # Override login_flow to skip post-login verification
        # (get_reels_tray_feed + get_timeline_feed trigger challenges)
        original_login_flow = cl.login_flow
        cl.login_flow = lambda: True
        logger.info("[Instagram] login_flow overridden to skip post-login checks")

        try:
            result = cl.login(username, password)
            if result:
                settings = cl.get_settings()
                logger.info(f"[Instagram] Login OK! user_id={cl.user_id}")
                return {"ok": True, "settings": settings}
            return {"ok": False, "error": "login_failed"}

        except (ChallengeRequired, ChallengeUnknownStep, ChallengeError) as e:
            logger.warning(f"[Instagram] Challenge for @{username}: {type(e).__name__}")
            # Login likely succeeded (got 200 on /accounts/login/) but
            # post-login requests triggered challenge. Session may be valid.
            try:
                settings = cl.get_settings()
                logger.info(f"[Instagram] Got settings despite challenge for @{username}")
                return {"ok": False, "challenge": True, "settings": settings}
            except Exception as e:
                logger.warning(f"[Instagram] Failed to get settings after challenge for @{username}: {e}")
                return {"ok": False, "challenge": True, "settings": None}

        except ClientJSONDecodeError as e:
            logger.warning(f"[Instagram] JSON error (likely challenge) for @{username}: {e}")
            try:
                settings = cl.get_settings()
                logger.info(f"[Instagram] Got settings despite JSON error for @{username}")
                return {"ok": False, "challenge": True, "settings": settings}
            except Exception as e:
                logger.warning(f"[Instagram] Failed to get settings after JSON error for @{username}: {e}")
                return {"ok": False, "challenge": True, "settings": None}

        except BadPassword:
            return {"ok": False, "error": "bad_password"}

        except (PleaseWaitFewMinutes, RateLimitError):
            return {"ok": False, "error": "rate_limited"}

        except ProxyAddressIsBlocked:
            return {"ok": False, "error": "ip_blocked"}

        except SentryBlock:
            return {"ok": False, "error": "ip_blocked"}

        except Exception as e:
            err = str(e)
            err_lower = err.lower()

            # IP blacklist
            if "blacklist" in err_lower or "change your ip" in err_lower:
                return {"ok": False, "error": "ip_blocked"}

            # JSON parse → likely challenge, try to grab settings
            if "expecting value" in err_lower or "jsondecodeerror" in err_lower:
                logger.warning(f"[Instagram] JSON parse error for @{username}, trying to save settings")
                try:
                    settings = cl.get_settings()
                    return {"ok": False, "challenge": True, "settings": settings}
                except Exception as e:
                    logger.warning(f"[Instagram] Failed to get settings after JSON parse error for @{username}: {e}")
                    return {"ok": False, "challenge": True, "settings": None}

            # Rate limit
            if "please wait" in err_lower or "few minutes" in err_lower:
                return {"ok": False, "error": "rate_limited"}

            # Bad password
            if "bad_password" in err_lower:
                return {"ok": False, "error": "bad_password"}

            logger.error(f"[Instagram] Unexpected login error for @{username}: {err}")
            return {"ok": False, "error": err}

    async def login(self, username: str, password: str, proxy: str | None = None) -> dict:
        """
        Login to Instagram.
        If challenge happens but login (200) succeeded, returns
        status='challenge_required' WITH settings so they can be saved.
        """
        logger.info(f"[Instagram] Logging in @{username} via proxy={'YES: ' + proxy[:30] + '...' if proxy else 'NO (direct)'}")

        cl = self._create_client(proxy)
        result = await asyncio.to_thread(self._do_login_raw, cl, username, password)

        if result.get("ok"):
            logger.info(f"[Instagram] Successfully logged in as @{username}")
            return {
                "status": "active",
                "username": username,
                "settings": result["settings"],
            }

        if result.get("challenge"):
            settings = result.get("settings")
            if settings:
                logger.info(f"[Instagram] Challenge but got session for @{username} — saving it")
                return {
                    "status": "challenge_required",
                    "username": username,
                    "settings": settings,  # <-- KEY: session is included!
                    "error": "Instagram требует подтверждение. Откройте Instagram, нажмите «Это я», потом нажмите «Я подтвердил».",
                }
            else:
                logger.warning(f"[Instagram] Challenge and NO session for @{username}")
                return {
                    "status": "challenge_required",
                    "username": username,
                    "settings": None,
                    "error": "Instagram требует подтверждение. Откройте Instagram, подтвердите вход и попробуйте снова.",
                }

        # Error cases
        error = result.get("error", "unknown")
        error_messages = {
            "bad_password": ("bad_password", "Неверный пароль Instagram."),
            "rate_limited": ("rate_limited", "Слишком много попыток входа. Подождите 10-15 минут."),
            "ip_blocked": ("ip_blocked", "IP-адрес заблокирован Instagram. Используйте мобильный прокси (4G/LTE)."),
        }

        if error in error_messages:
            status, msg = error_messages[error]
            return {"status": status, "error": msg, "username": username}

        return {"status": "error", "error": error, "username": username}

    async def login_by_session(self, session_data: dict, proxy: str | None = None):
        """
        Login using saved session settings.
        Returns instagrapi Client or None on failure.

        Skips heavy verification (get_timeline_feed) which triggers challenges.
        Uses lightweight check instead.
        """
        try:
            settings = session_data.get("settings")
            if not settings:
                logger.warning("[Instagram] No settings in session data")
                return None

            cl = self._create_client(proxy)
            await asyncio.to_thread(cl.set_settings, settings)

            # IMPORTANT: Do NOT override device after set_settings.
            # set_settings restores the exact device fingerprint that was used
            # at login time. Overriding creates a mismatch between cookies
            # (bound to old device) and new device → Instagram challenge.
            # Only re-apply proxy if needed (proxy can change, device can't).
            if proxy:
                self._apply_proxy(cl, proxy)
            logger.info("[Instagram] Session restored with original device fingerprint")

            # Light verification: check if session has auth data
            auth = settings.get("authorization_data", {})
            has_cookies = bool(settings.get("cookies"))

            if auth or has_cookies:
                logger.info(f"[Instagram] Session loaded OK (auth={'yes' if auth else 'no'}, cookies={'yes' if has_cookies else 'no'})")
                return cl

            # Fallback: try lightweight API call instead of get_timeline_feed
            try:
                await asyncio.to_thread(cl.account_info)
                logger.info("[Instagram] Session verified via account_info")
                return cl
            except Exception as e:
                logger.warning(f"[Instagram] Session expired: {e}")
                return None

        except Exception as e:
            logger.error(f"[Instagram] Session login failed: {e}")
            return None

    async def save_session_to_db(self, client, account_id: str):
        """
        Save updated session back to DB after any operation.
        CRITICAL: instagrapi updates cookies/tokens after each API call.
        Without saving, next operation uses stale session → re-login.
        """
        try:
            from app.database import get_supabase_admin
            from app.utils.encryption import encrypt_data

            new_settings = await asyncio.to_thread(client.get_settings)
            session_data = {"settings": new_settings}
            encrypted = encrypt_data(session_data)

            db = get_supabase_admin()
            db.table("instagram_accounts").update({
                "session_data": encrypted,
            }).eq("id", account_id).execute()

            logger.debug(f"[Instagram] Session saved to DB for account {account_id}")
        except Exception as e:
            logger.warning(f"[Instagram] Failed to save session to DB: {e}")

    async def search_music(self, client, query: str) -> list[dict]:
        """Search Instagram music library. Returns list of tracks."""
        try:
            tracks = await asyncio.to_thread(client.search_music, query)
            result = []
            for t in tracks[:20]:
                result.append({
                    "id": str(t.id),
                    "title": t.title,
                    "artist": t.display_artist,
                    "duration_ms": t.duration_in_ms,
                    "cover_url": t.cover_artwork_thumbnail_uri,
                    "audio_cluster_id": str(t.audio_cluster_id),
                    "highlight_start_ms": t.highlight_start_times_in_ms[0] if t.highlight_start_times_in_ms else 0,
                })
            logger.info(f"[Instagram] Found {len(result)} tracks for query '{query}'")
            return result
        except Exception as e:
            logger.error(f"[Instagram] Music search failed: {e}")
            return []

    def _build_music_extra_data(self, track_data: dict) -> dict:
        """Build extra_data dict for album_upload with music params."""
        from json import dumps
        return {
            "music_params": dumps({
                "audio_asset_id": track_data["id"],
                "audio_cluster_id": track_data["audio_cluster_id"],
                "audio_asset_start_time_in_ms": track_data.get("highlight_start_ms", 0),
                "derived_content_start_time_in_ms": 0,
                "overlap_duration_in_ms": 15000,
                "product": "story_camera_music_overlay_post",
                "song_name": track_data.get("title", ""),
                "artist_name": track_data.get("artist", ""),
                "alacorn_session_id": "null",
            }),
        }

    async def publish_carousel(
        self,
        client,
        image_paths: list[str],
        caption: str,
        music_track: dict | None = None,
        music_query: str | None = None,
    ) -> dict:
        """
        Publish carousel album to Instagram.
        Music can be provided in two ways:
          - music_track: {"id", "audio_cluster_id", ...} — full track data (from search)
          - music_query: "Artist - Song" — search at publish time
        """
        try:
            valid_paths = []
            for p in image_paths:
                path = Path(p)
                if path.exists():
                    valid_paths.append(path)
                else:
                    logger.warning(f"[Instagram] Image not found: {p}")

            if len(valid_paths) < 2:
                return {"status": "error", "error": "Нужно минимум 2 изображения для карусели"}

            # CRITICAL: instagrapi album_upload only supports .jpg/.jpeg/.webp
            # Convert .png files to .jpg before uploading
            converted_paths = []
            for path in valid_paths:
                if path.suffix.lower() == ".png":
                    from PIL import Image
                    jpg_path = path.with_suffix(".jpg")
                    if not jpg_path.exists():
                        img = Image.open(path)
                        # Convert RGBA to RGB (JPEG doesn't support alpha)
                        if img.mode in ("RGBA", "LA", "P"):
                            img = img.convert("RGB")
                        img.save(jpg_path, "JPEG", quality=95)
                        logger.info(f"[Instagram] Converted PNG→JPEG: {path.name} → {jpg_path.name}")
                    else:
                        logger.info(f"[Instagram] JPEG already exists: {jpg_path.name}")
                    converted_paths.append(jpg_path)
                else:
                    converted_paths.append(path)
            valid_paths = converted_paths
            logger.info(f"[Instagram] All {len(valid_paths)} images ready (format: {[p.suffix for p in valid_paths]})")

            delay = random.uniform(2, 5)
            logger.info(f"[Instagram] Waiting {delay:.1f}s before publishing...")
            await asyncio.sleep(delay)

            # Build extra_data with music if provided
            extra_data = {}

            # Option 1: full track data provided
            if music_track and music_track.get("id"):
                extra_data = self._build_music_extra_data(music_track)
                logger.info(f"[Instagram] Adding music: {music_track.get('title')} — {music_track.get('artist')}")

            # Option 2: search by query at publish time
            elif music_query:
                logger.info(f"[Instagram] Searching music at publish time: '{music_query}'")
                try:
                    tracks = await self.search_music(client, music_query)
                    if tracks:
                        best = tracks[0]
                        extra_data = self._build_music_extra_data(best)
                        logger.info(f"[Instagram] Found music: {best.get('title')} — {best.get('artist')}")
                    else:
                        logger.warning(f"[Instagram] No music found for '{music_query}', publishing without music")
                except Exception as e:
                    logger.warning(f"[Instagram] Music search failed at publish: {e}. Publishing without music")

            # Debug: verify proxy and user_id before upload
            logger.info(f"[Instagram] Client proxies: {client.private.proxies}")
            logger.info(f"[Instagram] Client user_id: {client.user_id}")
            logger.info(f"[Instagram] Publishing carousel with {len(valid_paths)} slides...")

            # If user_id is not set, try to get it from settings
            if not client.user_id:
                logger.warning("[Instagram] user_id not set! Trying account_info...")
                try:
                    info = await asyncio.to_thread(client.account_info)
                    logger.info(f"[Instagram] Got user_id: {client.user_id}")
                except Exception as e:
                    logger.warning(f"[Instagram] account_info failed: {e}")

            media = await asyncio.to_thread(
                client.album_upload,
                valid_paths,
                caption,
                extra_data=extra_data if extra_data else None,
            )

            media_id = str(media.pk)
            media_code = media.code

            logger.info(f"[Instagram] Published! media_id={media_id}, code={media_code}")
            return {
                "status": "published",
                "media_id": media_id,
                "media_code": media_code,
                "url": f"https://www.instagram.com/p/{media_code}/",
            }

        except Exception as e:
            import traceback
            error_msg = str(e)
            logger.error(f"[Instagram] Publish failed: {error_msg}")
            logger.error(f"[Instagram] Full traceback:\n{traceback.format_exc()}")
            logger.error(f"[Instagram] Client proxies at fail: {client.private.proxies if client else 'no client'}")
            logger.error(f"[Instagram] Client last_json: {getattr(client, 'last_json', 'N/A')}")

            if "login_required" in error_msg.lower():
                return {"status": "session_expired", "error": "Сессия истекла. Нужна переавторизация."}

            if "feedback_required" in error_msg.lower() or "spam" in error_msg.lower():
                return {"status": "spam_block", "error": "Instagram временно заблокировал публикацию. Подождите 24-48 часов."}

            return {"status": "error", "error": error_msg}

    async def get_post_insights(self, client, media_id: str) -> dict:
        """Get engagement data for a published post."""
        try:
            media_pk = int(media_id)
            info = await asyncio.to_thread(client.media_info, media_pk)
            return {
                "likes": info.like_count or 0,
                "comments": info.comment_count or 0,
                "media_type": info.media_type,
            }
        except Exception as e:
            logger.error(f"[Instagram] Failed to get insights: {e}")
            return {"likes": 0, "comments": 0}

    async def check_session(self, session_data: dict, proxy: str | None = None) -> bool:
        """Check if session is still valid."""
        client = await self.login_by_session(session_data, proxy)
        return client is not None


# Singleton
_publisher: InstagramPublisher | None = None


def get_publisher() -> InstagramPublisher:
    global _publisher
    if _publisher is None:
        _publisher = InstagramPublisher()
    return _publisher
