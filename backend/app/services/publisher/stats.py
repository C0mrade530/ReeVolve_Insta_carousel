"""
Post stats fetcher — collects engagement data from Instagram via instagrapi.
Fetches likes, comments, saves, reach for published carousels.
"""
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class StatsFetcher:
    """Fetches and stores Instagram post engagement stats."""

    async def fetch_media_insights(self, client, media_id: str) -> dict:
        """
        Fetch engagement data for a single media post.
        Uses instagrapi media_info + media_insights.
        Returns dict with likes, comments, saves, reach, impressions.
        """
        try:
            media_pk = int(media_id)

            # Basic engagement from media_info
            info = await asyncio.to_thread(client.media_info, media_pk)
            result = {
                "likes": info.like_count or 0,
                "comments": info.comment_count or 0,
                "media_type": info.media_type,
                "media_code": info.code,
            }

            # Try to get insights (reach, impressions, saves)
            # Only works for business/creator accounts
            try:
                insights = await asyncio.to_thread(client.insights_media, media_pk)
                if insights:
                    for metric in insights:
                        name = getattr(metric, "name", "")
                        value = getattr(metric, "value", 0) or 0
                        if name == "reach":
                            result["reach"] = value
                        elif name == "impressions":
                            result["impressions"] = value
                        elif name == "saved":
                            result["saves"] = value
                        elif name == "shares":
                            result["shares"] = value
            except Exception as e:
                # insights_media may fail for personal accounts — that's OK
                logger.debug(f"[Stats] insights_media unavailable: {e}")
                result.setdefault("reach", 0)
                result.setdefault("impressions", 0)
                result.setdefault("saves", 0)
                result.setdefault("shares", 0)

            # Calculate engagement rate
            total_engagement = result["likes"] + result["comments"] + result.get("saves", 0)
            reach = result.get("reach", 0)
            if reach > 0:
                result["engagement_rate"] = round((total_engagement / reach) * 100, 2)
            else:
                result["engagement_rate"] = 0

            return result

        except Exception as e:
            logger.error(f"[Stats] Failed to fetch media {media_id}: {e}")
            return {
                "likes": 0, "comments": 0, "saves": 0,
                "shares": 0, "reach": 0, "impressions": 0,
                "engagement_rate": 0, "error": str(e),
            }

    async def fetch_and_store(self, client, media_id: str, carousel_id: str,
                               account_id: str, published_at: str, db) -> dict:
        """
        Fetch insights from Instagram and upsert into post_stats table.
        """
        stats = await self.fetch_media_insights(client, media_id)

        if stats.get("error"):
            logger.warning(f"[Stats] Skipping store for {media_id}: {stats['error']}")
            return stats

        row = {
            "carousel_id": carousel_id,
            "account_id": account_id,
            "media_id": media_id,
            "media_code": stats.get("media_code", ""),
            "likes": stats["likes"],
            "comments": stats["comments"],
            "saves": stats.get("saves", 0),
            "shares": stats.get("shares", 0),
            "reach": stats.get("reach", 0),
            "impressions": stats.get("impressions", 0),
            "engagement_rate": stats.get("engagement_rate", 0),
            "fetched_at": datetime.utcnow().isoformat(),
            "published_at": published_at,
        }

        try:
            # Upsert: insert or update on (carousel_id, account_id)
            existing = (
                db.table("post_stats")
                .select("id")
                .eq("carousel_id", carousel_id)
                .eq("account_id", account_id)
                .execute()
            )

            if existing.data:
                # Update existing
                db.table("post_stats").update({
                    **row,
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("id", existing.data[0]["id"]).execute()
                logger.info(f"[Stats] Updated stats for carousel {carousel_id[:8]}")
            else:
                # Insert new
                db.table("post_stats").insert(row).execute()
                logger.info(f"[Stats] Inserted stats for carousel {carousel_id[:8]}")

        except Exception as e:
            logger.error(f"[Stats] DB error for {carousel_id}: {e}")

        return stats

    async def refresh_all_stats(self, db, user_id: str) -> dict:
        """
        Refresh stats for all published carousels of a user.
        Returns summary of fetched/failed.
        """
        from app.services.publisher.instagram import get_publisher
        from app.utils.encryption import decrypt_data

        # Get all active accounts
        accounts_result = (
            db.table("instagram_accounts")
            .select("id, username, session_data, proxy, is_active")
            .eq("owner_id", user_id)
            .eq("is_active", True)
            .execute()
        )
        accounts = accounts_result.data or []

        if not accounts:
            return {"fetched": 0, "failed": 0, "message": "Нет активных аккаунтов"}

        publisher = get_publisher()
        total_fetched = 0
        total_failed = 0

        for account in accounts:
            # Login via session
            try:
                session_settings = decrypt_data(account["session_data"])
            except Exception as e:
                logger.warning(f"[Stats] Can't decrypt session for @{account['username']}: {e}")
                continue

            client = await publisher.login_by_session(
                session_data={"settings": session_settings},
                proxy=account.get("proxy"),
            )

            if not client:
                logger.warning(f"[Stats] Session expired for @{account['username']}")
                continue

            # Get published carousels with media_id
            try:
                carousels = (
                    db.table("carousels")
                    .select("id, media_id, published_at")
                    .eq("owner_id", user_id)
                    .eq("status", "published")
                    .not_.is_("media_id", "null")
                    .order("published_at", desc=True)
                    .limit(50)
                    .execute()
                )
            except Exception as e:
                logger.warning(f"[Stats] Failed to query carousels by owner_id, falling back: {e}")
                carousels = (
                    db.table("carousels")
                    .select("id, media_id, published_at")
                    .eq("status", "published")
                    .not_.is_("media_id", "null")
                    .order("published_at", desc=True)
                    .limit(50)
                    .execute()
                )

            for c in (carousels.data or []):
                if not c.get("media_id"):
                    continue

                try:
                    await self.fetch_and_store(
                        client=client,
                        media_id=c["media_id"],
                        carousel_id=c["id"],
                        account_id=account["id"],
                        published_at=c.get("published_at", ""),
                        db=db,
                    )
                    total_fetched += 1

                    # Small delay between API calls to avoid rate limiting
                    await asyncio.sleep(1.5)

                except Exception as e:
                    logger.error(f"[Stats] Error fetching stats for {c['id']}: {e}")
                    total_failed += 1

        return {
            "fetched": total_fetched,
            "failed": total_failed,
            "message": f"Обновлено {total_fetched} постов",
        }


# Singleton
_fetcher: StatsFetcher | None = None


def get_stats_fetcher() -> StatsFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = StatsFetcher()
    return _fetcher
