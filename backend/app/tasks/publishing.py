"""
Celery tasks for Instagram publishing.
Real implementation: check scheduled posts → login via session → publish → update DB.
"""
import asyncio
import random
import logging
from datetime import datetime, timedelta

from app.tasks.celery_app import celery_app
from app.database import get_supabase_admin
from app.utils.encryption import decrypt_data, encrypt_data
from app.services.publisher.instagram import get_publisher
from app.services.publisher.safety import get_safety_manager

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine from sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(name="app.tasks.publishing.check_and_publish")
def check_and_publish():
    """
    Runs every minute via Celery Beat.
    Checks for scheduled publications that are due and publishes them.
    Adds random delays between publications for anti-ban.
    """
    db = get_supabase_admin()

    # Get pending schedules where scheduled_time <= now + 2min buffer
    now = datetime.utcnow()
    cutoff = (now + timedelta(minutes=2)).isoformat()

    try:
        result = (
            db.table("publish_schedules")
            .select("id, account_id, carousel_id")
            .eq("status", "pending")
            .lte("scheduled_time", cutoff)
            .order("scheduled_time")
            .limit(5)  # Max 5 per cycle to avoid overload
            .execute()
        )
    except Exception as e:
        logger.error(f"[Scheduler] Failed to query schedules: {e}")
        return {"status": "error", "error": str(e)}

    schedules = result.data or []
    if not schedules:
        return {"status": "ok", "published": 0}

    published_count = 0
    for schedule in schedules:
        try:
            # Mark as in_progress
            db.table("publish_schedules").update({
                "status": "publishing",
            }).eq("id", schedule["id"]).execute()

            # Dispatch individual publish task with random delay
            delay = random.randint(10, 120)  # 10s to 2min random delay
            publish_single.apply_async(
                args=[schedule["id"]],
                countdown=delay,
            )
            published_count += 1

        except Exception as e:
            logger.error(f"[Scheduler] Failed to dispatch schedule {schedule['id']}: {e}")
            db.table("publish_schedules").update({
                "status": "failed",
                "error_message": str(e),
            }).eq("id", schedule["id"]).execute()

    logger.info(f"[Scheduler] Dispatched {published_count} publications")
    return {"status": "ok", "dispatched": published_count}


@celery_app.task(
    name="app.tasks.publishing.publish_single",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def publish_single(self, schedule_id: str):
    """
    Publish a single carousel via instagrapi.
    Retries up to 3 times with exponential backoff.
    """
    db = get_supabase_admin()

    try:
        # 1. Get schedule + carousel + account
        schedule_result = (
            db.table("publish_schedules")
            .select("id, account_id, carousel_id, status")
            .eq("id", schedule_id)
            .single()
            .execute()
        )
        if not schedule_result.data:
            logger.error(f"[Publisher] Schedule {schedule_id} not found")
            return {"status": "error", "error": "Schedule not found"}

        schedule = schedule_result.data

        # Get carousel
        carousel_result = (
            db.table("carousels")
            .select("id, slides, caption, hashtags")
            .eq("id", schedule["carousel_id"])
            .single()
            .execute()
        )
        if not carousel_result.data:
            _mark_failed(db, schedule_id, "Карусель не найдена")
            return {"status": "error", "error": "Carousel not found"}

        carousel = carousel_result.data
        slides = carousel.get("slides", [])

        # Get account
        account_result = (
            db.table("instagram_accounts")
            .select("id, username, session_data, proxy")
            .eq("id", schedule["account_id"])
            .single()
            .execute()
        )
        if not account_result.data:
            _mark_failed(db, schedule_id, "Аккаунт не найден")
            return {"status": "error", "error": "Account not found"}

        account = account_result.data

        # 2. Decrypt session
        try:
            session_settings = decrypt_data(account["session_data"])
        except Exception as e:
            logger.warning(f"[Publishing] Session decrypt failed for account {account.get('username', '?')}: {e}")
            _mark_failed(db, schedule_id, "Сессия повреждена")
            db.table("instagram_accounts").update({"is_active": False}).eq("id", account["id"]).execute()
            return {"status": "error", "error": "Session corrupted"}

        # 3. Login via session (async)
        publisher = get_publisher()
        client = _run_async(publisher.login_by_session(
            session_data={"settings": session_settings},
            proxy=account.get("proxy"),
        ))

        if not client:
            db.table("instagram_accounts").update({"is_active": False}).eq("id", account["id"]).execute()
            _mark_failed(db, schedule_id, "Сессия истекла")
            return {"status": "error", "error": "Session expired"}

        # 3b. Safety check + warmup
        safety = get_safety_manager()
        check = safety.can_publish(username=account["username"])
        if not check["allowed"]:
            _mark_failed(db, schedule_id, check["reason"])
            return {"status": "rate_limited", "reason": check["reason"]}

        # Warmup DISABLED — feed/timeline calls trigger challenges on fresh sessions.
        # Behavior sessions handle warmup separately and safely.
        logger.info("[Publisher] Warmup skipped (behavior sessions handle activity)")
        import time as _time
        _time.sleep(random.uniform(3, 6))

        # 4. Collect image paths
        image_paths = []
        for slide in slides:
            path = slide.get("image_path") or slide.get("path") or slide.get("url", "")
            if path and not path.startswith("http"):
                image_paths.append(path)

        if len(image_paths) < 2:
            _mark_failed(db, schedule_id, "Менее 2 изображений")
            return {"status": "error", "error": "Not enough images"}

        # 5. Build caption
        caption = carousel.get("caption", "")
        hashtags = carousel.get("hashtags", "")
        full_caption = f"{caption}\n\n{hashtags}".strip() if hashtags else caption

        # 6. Publish! (async)
        logger.info(f"[Publisher] Publishing schedule {schedule_id} to @{account['username']}...")

        result = _run_async(publisher.publish_carousel(
            client=client,
            image_paths=image_paths,
            caption=full_caption,
        ))

        publish_status = result.get("status")

        # CRITICAL: Save updated session back to DB after ANY Instagram operation
        try:
            new_settings = client.get_settings()
            new_encrypted = encrypt_data({"settings": new_settings})
            db.table("instagram_accounts").update({
                "session_data": new_encrypted,
            }).eq("id", account["id"]).execute()
            logger.debug("[Publisher] Session saved to DB after publish")
        except Exception as e:
            logger.warning(f"[Publisher] Failed to save session: {e}")

        if publish_status == "published":
            # Update schedule
            db.table("publish_schedules").update({
                "status": "published",
                "published_at": datetime.utcnow().isoformat(),
                "instagram_media_id": result.get("media_id"),
            }).eq("id", schedule_id).execute()

            # Update carousel
            db.table("carousels").update({
                "status": "published",
                "published_at": datetime.utcnow().isoformat(),
            }).eq("id", carousel["id"]).execute()

            # Update account
            db.table("instagram_accounts").update({
                "last_published_at": datetime.utcnow().isoformat(),
            }).eq("id", account["id"]).execute()

            # Post-publish cooldown + log
            safety.log_action(account["username"], "publish")
            _run_async(safety.post_publish_cooldown(client))

            logger.info(f"[Publisher] Published! media_id={result.get('media_id')}")
            return {
                "status": "published",
                "media_id": result.get("media_id"),
                "url": result.get("url"),
            }

        elif publish_status == "session_expired":
            db.table("instagram_accounts").update({"is_active": False}).eq("id", account["id"]).execute()
            raise Exception("Session expired during publish")

        elif publish_status == "spam_block":
            _mark_failed(db, schedule_id, result.get("error", "Spam block"))
            # Don't retry spam blocks — wait 24h
            return {"status": "spam_block", "error": result.get("error")}

        else:
            raise Exception(result.get("error", "Unknown publish error"))

    except Exception as exc:
        logger.error(f"[Publisher] Task failed for schedule {schedule_id}: {exc}")
        # Exponential backoff: 5min, 10min, 20min + random jitter
        delay = 300 * (2 ** self.request.retries) + random.randint(0, 60)
        try:
            raise self.retry(exc=exc, countdown=delay)
        except self.MaxRetriesExceededError:
            _mark_failed(db, schedule_id, f"Не удалось после {self.max_retries} попыток: {str(exc)}")
            return {"status": "failed", "error": str(exc)}


def _mark_failed(db, schedule_id: str, error: str):
    """Mark a schedule as failed."""
    try:
        db.table("publish_schedules").update({
            "status": "failed",
            "error_message": error,
        }).eq("id", schedule_id).execute()
    except Exception as e:
        logger.warning(f"[Publishing] Failed to mark schedule {schedule_id} as failed: {e}")
