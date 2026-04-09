"""
Behavioral factor simulator — mimics real Instagram user activity.
Scrolls feed, likes posts, comments, watches Stories and Reels.

Uses instagrapi client methods with human-like delays.
Thread-safe, runs in background via asyncio.to_thread().
"""
import random
import time
import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from app.config import get_settings
from app.services.publisher.instagram import get_publisher
from app.utils.encryption import decrypt_data
from app.database import get_supabase_admin

logger = logging.getLogger(__name__)
settings = get_settings()

# Human-like comment presets (safe, generic, positive)
COMMENT_PRESETS = [
    "Отличный контент!",
    "Интересная мысль",
    "Полностью согласен",
    "Спасибо за пост!",
    "Очень полезно",
    "Сохранил себе",
    "Круто!",
    "Топ!",
    "Классно подмечено",
    "Сильный пост",
    "Согласен на все 100",
    "Прям в точку!",
    "Полезная информация",
    "Благодарю за контент",
    "Подписался!",
]

# Safety limits per session
INTENSITY_PROFILES = {
    "light": {
        "feed_scrolls": (3, 8),
        "likes": (1, 4),
        "comments": (0, 1),
        "stories_view": (1, 4),
        "reels_view": (2, 5),
        "reels_like": (0, 2),
        "pause_min": 3.0,
        "pause_max": 8.0,
    },
    "normal": {
        "feed_scrolls": (5, 15),
        "likes": (3, 8),
        "comments": (1, 2),
        "stories_view": (3, 7),
        "reels_view": (5, 10),
        "reels_like": (1, 3),
        "pause_min": 2.0,
        "pause_max": 6.0,
    },
    "aggressive": {
        "feed_scrolls": (10, 20),
        "likes": (5, 15),
        "comments": (2, 4),
        "stories_view": (5, 10),
        "reels_view": (8, 15),
        "reels_like": (2, 5),
        "pause_min": 1.5,
        "pause_max": 4.0,
    },
}

# Track running sessions to prevent duplicates
_running_sessions: dict[str, bool] = {}
_running_lock = threading.Lock()


def _human_pause(min_s: float, max_s: float):
    """Sleep for a random human-like duration."""
    time.sleep(random.uniform(min_s, max_s))


def _run_behavior_session_sync(
    account_id: str,
    owner_id: str,
    session_id: str,
    intensity: str = "normal",
    enable_likes: bool = True,
    enable_comments: bool = True,
    enable_stories: bool = True,
    enable_reels: bool = True,
) -> dict:
    """
    Synchronous behavior session — runs in thread via asyncio.to_thread().
    Returns dict of action counts.
    """
    db = get_supabase_admin()
    publisher = get_publisher()
    profile = INTENSITY_PROFILES.get(intensity, INTENSITY_PROFILES["normal"])
    actions = {
        "feed_scrolls": 0, "likes": 0, "comments": 0,
        "stories_viewed": 0, "reels_viewed": 0, "reels_liked": 0,
    }

    try:
        # Load account + decrypt session
        account_result = db.table("instagram_accounts").select(
            "id, username, session_data, proxy"
        ).eq("id", account_id).eq("owner_id", owner_id).single().execute()

        if not account_result.data:
            raise ValueError(f"Account {account_id} not found")

        account = account_result.data
        session_data = decrypt_data(account["session_data"]) if account.get("session_data") else None
        if not session_data:
            raise ValueError("No session data — account not logged in")

        # Login via saved session (sync context — call the inner sync logic directly)
        cl = publisher._create_client(account.get("proxy"))
        settings = session_data.get("settings")
        if not settings:
            raise ValueError("No settings in session data — account not logged in")

        cl.set_settings(settings)
        # Don't override device — keep the one from login (prevents fingerprint mismatch)
        if account.get("proxy"):
            publisher._apply_proxy(cl, account["proxy"])

        client = cl
        if not client:
            raise ValueError("Failed to restore session")

        logger.info(f"[Behavior] Session started for @{account['username']} (intensity={intensity})")

        # ═══ Phase 1: Scroll Feed ═══
        feed_count = random.randint(*profile["feed_scrolls"])
        feed_media_pks = []

        try:
            feed = client.get_timeline_feed(reason="cold_start_fetch")
            items = feed.get("feed_items", [])
            for item in items[:feed_count]:
                media = item.get("media_or_ad")
                if media and media.get("pk"):
                    feed_media_pks.append(media["pk"])
                    actions["feed_scrolls"] += 1
                _human_pause(profile["pause_min"], profile["pause_max"])

                # Check if session was stopped
                with _running_lock:
                    if not _running_sessions.get(account_id, False):
                        logger.info(f"[Behavior] Session stopped by user for {account_id}")
                        return actions
        except Exception as e:
            logger.warning(f"[Behavior] Feed scroll error: {e}")

        # ═══ Phase 2: Like Posts ═══
        if enable_likes and feed_media_pks:
            like_count = min(random.randint(*profile["likes"]), len(feed_media_pks))
            targets = random.sample(feed_media_pks, like_count)

            for pk in targets:
                try:
                    client.media_like(pk)
                    actions["likes"] += 1
                    logger.debug(f"[Behavior] Liked media {pk}")
                    _human_pause(profile["pause_min"], profile["pause_max"])
                except Exception as e:
                    logger.warning(f"[Behavior] Like error: {e}")
                    break  # Stop if rate limited

        # ═══ Phase 3: Comment ═══
        if enable_comments and feed_media_pks:
            comment_count = random.randint(*profile["comments"])
            if comment_count > 0:
                comment_targets = random.sample(
                    feed_media_pks,
                    min(comment_count, len(feed_media_pks))
                )
                for pk in comment_targets:
                    try:
                        comment_text = random.choice(COMMENT_PRESETS)
                        client.media_comment(pk, comment_text)
                        actions["comments"] += 1
                        logger.debug(f"[Behavior] Commented on {pk}: '{comment_text}'")
                        _human_pause(profile["pause_max"], profile["pause_max"] * 2)
                    except Exception as e:
                        logger.warning(f"[Behavior] Comment error: {e}")
                        break

        # ═══ Phase 4: View Stories ═══
        if enable_stories:
            stories_count = random.randint(*profile["stories_view"])
            try:
                tray = client.get_reels_tray_feed(reason="cold_start")
                reels_data = tray.get("tray", [])
                story_pks = []

                for reel in reels_data[:stories_count]:
                    items_list = reel.get("items", [])
                    for item in items_list[:2]:
                        if item.get("pk"):
                            story_pks.append(str(item["pk"]))
                    _human_pause(1.5, 3.0)

                if story_pks:
                    try:
                        client.story_seen(story_pks[:stories_count])
                        actions["stories_viewed"] = min(len(story_pks), stories_count)
                        logger.debug(f"[Behavior] Viewed {actions['stories_viewed']} stories")
                    except Exception as e:
                        logger.warning(f"[Behavior] Story seen error: {e}")

                _human_pause(profile["pause_min"], profile["pause_max"])
            except Exception as e:
                logger.warning(f"[Behavior] Stories error: {e}")

        # ═══ Phase 5: Watch Reels ═══
        if enable_reels:
            reels_count = random.randint(*profile["reels_view"])
            reels_like_count = random.randint(*profile["reels_like"])
            try:
                reels_data = client.explore_reels(amount=reels_count)
                reel_pks = []

                if hasattr(reels_data, '__iter__'):
                    for reel in reels_data:
                        pk = getattr(reel, 'pk', None) or (reel.get('pk') if isinstance(reel, dict) else None)
                        if pk:
                            reel_pks.append(pk)
                            actions["reels_viewed"] += 1
                            _human_pause(3.0, 8.0)  # Simulate watching

                # Like some reels
                if enable_likes and reel_pks:
                    like_targets = random.sample(
                        reel_pks,
                        min(reels_like_count, len(reel_pks))
                    )
                    for pk in like_targets:
                        try:
                            client.media_like(pk)
                            actions["reels_liked"] += 1
                            _human_pause(profile["pause_min"], profile["pause_max"])
                        except Exception as e:
                            logger.warning(f"[Behavior] Reel like error: {e}")
                            break

            except Exception as e:
                logger.warning(f"[Behavior] Reels error: {e}")

        # CRITICAL: Save updated session back to DB
        # instagrapi updates cookies after each API call
        try:
            from app.utils.encryption import encrypt_data
            new_settings = client.get_settings()
            encrypted = encrypt_data({"settings": new_settings})
            db.table("instagram_accounts").update({
                "session_data": encrypted,
            }).eq("id", account_id).execute()
            logger.debug(f"[Behavior] Session saved to DB after behavior")
        except Exception as e:
            logger.warning(f"[Behavior] Failed to save session: {e}")

        logger.info(
            f"[Behavior] Session complete for @{account['username']}: "
            f"scrolls={actions['feed_scrolls']}, likes={actions['likes']}, "
            f"comments={actions['comments']}, stories={actions['stories_viewed']}, "
            f"reels={actions['reels_viewed']}"
        )
        return actions

    except Exception as e:
        logger.error(f"[Behavior] Session failed: {e}", exc_info=True)
        raise


async def start_behavior_session(
    account_id: str,
    owner_id: str,
    intensity: str = "normal",
    enable_likes: bool = True,
    enable_comments: bool = True,
    enable_stories: bool = True,
    enable_reels: bool = True,
) -> dict:
    """
    Start a behavior session for an account.
    Creates DB record, runs in thread, updates on completion.
    """
    db = get_supabase_admin()

    # Check not already running
    with _running_lock:
        if _running_sessions.get(account_id, False):
            raise ValueError("Behavior session already running for this account")
        _running_sessions[account_id] = True

    # Create session record
    session_result = db.table("behavior_sessions").insert({
        "account_id": account_id,
        "owner_id": owner_id,
        "status": "running",
        "actions": {},
    }).execute()

    session_id = session_result.data[0]["id"]

    try:
        actions = await asyncio.to_thread(
            _run_behavior_session_sync,
            account_id, owner_id, session_id, intensity,
            enable_likes, enable_comments, enable_stories, enable_reels,
        )

        # Update session as completed
        db.table("behavior_sessions").update({
            "status": "completed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "actions": actions,
        }).eq("id", session_id).execute()

        # Update account last_behavior_at
        db.table("instagram_accounts").update({
            "last_behavior_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", account_id).execute()

        return {"session_id": session_id, "status": "completed", "actions": actions}

    except Exception as e:
        db.table("behavior_sessions").update({
            "status": "failed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }).eq("id", session_id).execute()
        raise

    finally:
        with _running_lock:
            _running_sessions.pop(account_id, None)


def stop_behavior_session(account_id: str) -> bool:
    """Signal a running session to stop."""
    with _running_lock:
        if account_id in _running_sessions:
            _running_sessions[account_id] = False
            return True
    return False


def is_session_running(account_id: str) -> bool:
    """Check if a behavior session is currently running."""
    with _running_lock:
        return _running_sessions.get(account_id, False)
