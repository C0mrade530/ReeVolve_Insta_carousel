"""
Analytics API — dashboard stats, engagement, account health.
"""
import logging
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.api.deps import get_current_user, get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard")
async def dashboard_stats(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Main dashboard statistics.
    Returns counts, upcoming posts, recent activity, account health.
    """
    user_id = user["id"]

    # ── Accounts ──
    accounts_result = (
        db.table("instagram_accounts")
        .select("id, username, is_active, last_published_at, created_at, proxy")
        .eq("owner_id", user_id)
        .execute()
    )
    accounts = accounts_result.data or []
    account_ids = [a["id"] for a in accounts]
    active_accounts = [a for a in accounts if a.get("is_active")]

    # ── Carousels (use count queries instead of fetching all rows) ──
    total_carousels = 0
    published_total = 0
    published_today = 0
    published_week = 0
    scheduled_count = 0
    ready_count = 0

    today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
    week_start = (datetime.utcnow() - timedelta(days=7)).isoformat()

    # Use efficient count queries — no full table scan
    try:
        # Total
        r = db.table("carousels").select("id", count="exact").eq("owner_id", user_id).execute()
        total_carousels = r.count or 0

        # Published total
        r = db.table("carousels").select("id", count="exact").eq("owner_id", user_id).eq("status", "published").execute()
        published_total = r.count or 0

        # Published today
        r = db.table("carousels").select("id", count="exact").eq("owner_id", user_id).eq("status", "published").gte("published_at", today_start).execute()
        published_today = r.count or 0

        # Published this week
        r = db.table("carousels").select("id", count="exact").eq("owner_id", user_id).eq("status", "published").gte("published_at", week_start).execute()
        published_week = r.count or 0

        # Scheduled
        r = db.table("carousels").select("id", count="exact").eq("owner_id", user_id).eq("status", "scheduled").execute()
        scheduled_count = r.count or 0

        # Ready
        r = db.table("carousels").select("id", count="exact").eq("owner_id", user_id).eq("status", "ready").execute()
        ready_count = r.count or 0
    except Exception as e:
        logger.warning(f"[Dashboard] carousel count by owner_id failed: {e}")
        # Fallback: try via account_ids
        if account_ids:
            try:
                r = db.table("carousels").select("id", count="exact").in_("account_id", account_ids).execute()
                total_carousels = r.count or 0
                r = db.table("carousels").select("id", count="exact").in_("account_id", account_ids).eq("status", "published").execute()
                published_total = r.count or 0
                r = db.table("carousels").select("id", count="exact").in_("account_id", account_ids).eq("status", "published").gte("published_at", today_start).execute()
                published_today = r.count or 0
                r = db.table("carousels").select("id", count="exact").in_("account_id", account_ids).eq("status", "published").gte("published_at", week_start).execute()
                published_week = r.count or 0
                r = db.table("carousels").select("id", count="exact").in_("account_id", account_ids).eq("status", "scheduled").execute()
                scheduled_count = r.count or 0
                r = db.table("carousels").select("id", count="exact").in_("account_id", account_ids).eq("status", "ready").execute()
                ready_count = r.count or 0
            except Exception as e:
                logger.warning(f"[Dashboard] carousel count by account_ids fallback failed: {e}")

    # ── Upcoming schedules ──
    upcoming = []
    if account_ids:
        try:
            sch_result = (
                db.table("publish_schedules")
                .select("id, carousel_id, scheduled_time, status, account_id")
                .in_("account_id", account_ids)
                .eq("status", "pending")
                .order("scheduled_time")
                .limit(10)
                .execute()
            )
            for sch in (sch_result.data or []):
                # Find account username
                acct = next((a for a in accounts if a["id"] == sch["account_id"]), None)
                upcoming.append({
                    "id": sch["id"],
                    "carousel_id": sch["carousel_id"],
                    "scheduled_time": sch["scheduled_time"],
                    "username": acct["username"] if acct else "?",
                })
        except Exception as e:
            logger.warning(f"[Dashboard] upcoming schedules query failed: {e}")

    # ── Recent published ──
    recent_published = []
    try:
        recent_result = (
            db.table("carousels")
            .select("id, slides, caption, published_at, generation_params")
            .eq("owner_id", user_id)
            .eq("status", "published")
            .order("published_at", desc=True)
            .limit(5)
            .execute()
        )
        for c in (recent_result.data or []):
            first_slide = (c.get("slides") or [{}])[0] if c.get("slides") else {}
            recent_published.append({
                "carousel_id": c["id"],
                "published_at": c.get("published_at"),
                "first_slide_image": first_slide.get("image_path"),
                "title": first_slide.get("text_overlay", ""),
                "caption_preview": (c.get("caption") or "")[:60],
            })
    except Exception as e:
        logger.warning(f"[Dashboard] recent published query failed: {e}")

    # ── Account health summary ──
    accounts_summary = []
    for a in accounts:
        accounts_summary.append({
            "id": a["id"],
            "username": a["username"],
            "is_active": a.get("is_active", False),
            "last_published_at": a.get("last_published_at"),
            "has_proxy": bool(a.get("proxy")),
        })

    return {
        "accounts_count": len(accounts),
        "active_accounts": len(active_accounts),
        "total_carousels": total_carousels,
        "published_today": published_today,
        "published_week": published_week,
        "published_total": published_total,
        "scheduled": scheduled_count,
        "ready": ready_count,
        "upcoming": upcoming,
        "recent_published": recent_published,
        "accounts": accounts_summary,
    }


@router.get("/top-carousels")
async def top_carousels(
    limit: int = Query(default=10, le=50),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Top published carousels."""
    try:
        result = (
            db.table("carousels")
            .select("id, type, caption, slides, published_at, generation_params")
            .eq("owner_id", user["id"])
            .eq("status", "published")
            .order("published_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.warning(f"[TopCarousels] query failed: {e}")
        return []


# ──────────────────────────────────────────
# Post Stats endpoints
# ──────────────────────────────────────────

@router.get("/stats")
async def get_post_stats(
    limit: int = Query(default=30, le=100),
    sort: str = Query(default="published_at", pattern="^(published_at|likes|comments|engagement_rate|reach)$"),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Get engagement stats for all published carousels.
    Returns likes, comments, saves, reach, engagement_rate per post.
    """
    user_id = user["id"]

    # Get user's account IDs
    accounts_result = (
        db.table("instagram_accounts")
        .select("id, username")
        .eq("owner_id", user_id)
        .execute()
    )
    accounts = accounts_result.data or []
    account_ids = [a["id"] for a in accounts]
    account_map = {a["id"]: a["username"] for a in accounts}

    if not account_ids:
        return {"posts": [], "summary": _empty_summary()}

    # Fetch stats
    try:
        stats_result = (
            db.table("post_stats")
            .select("*")
            .in_("account_id", account_ids)
            .order(sort, desc=True)
            .limit(limit)
            .execute()
        )
        stats = stats_result.data or []
    except Exception as e:
        logger.warning(f"[Stats] DB query error: {e}")
        stats = []

    # Enrich with carousel data
    carousel_ids = [s["carousel_id"] for s in stats]
    carousel_map = {}
    if carousel_ids:
        try:
            carousels = (
                db.table("carousels")
                .select("id, slides, caption, type")
                .in_("id", carousel_ids)
                .execute()
            )
            for c in (carousels.data or []):
                carousel_map[c["id"]] = c
        except Exception as e:
            logger.warning(f"[Stats] carousel enrichment query failed: {e}")

    posts = []
    for s in stats:
        carousel = carousel_map.get(s["carousel_id"], {})
        first_slide = (carousel.get("slides") or [{}])[0] if carousel.get("slides") else {}

        posts.append({
            "id": s["id"],
            "carousel_id": s["carousel_id"],
            "account": account_map.get(s["account_id"], "?"),
            "media_code": s.get("media_code", ""),
            "likes": s.get("likes", 0),
            "comments": s.get("comments", 0),
            "saves": s.get("saves", 0),
            "shares": s.get("shares", 0),
            "reach": s.get("reach", 0),
            "impressions": s.get("impressions", 0),
            "engagement_rate": float(s.get("engagement_rate", 0)),
            "published_at": s.get("published_at"),
            "fetched_at": s.get("fetched_at"),
            "first_slide_image": first_slide.get("image_path"),
            "title": first_slide.get("text_overlay", ""),
            "caption_preview": (carousel.get("caption") or "")[:80],
            "type": carousel.get("type", "topic"),
        })

    # Summary stats
    summary = _calculate_summary(posts)

    return {"posts": posts, "summary": summary}


@router.post("/stats/refresh")
async def refresh_stats(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Refresh engagement stats from Instagram for all published posts.
    Logs into each active account and fetches latest metrics.
    """
    from app.services.publisher.stats import get_stats_fetcher

    fetcher = get_stats_fetcher()
    result = await fetcher.refresh_all_stats(db=db, user_id=user["id"])
    return result


@router.get("/stats/summary")
async def stats_summary(
    days: int = Query(default=30, le=365),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Aggregated stats summary: totals, averages, trends.
    """
    user_id = user["id"]
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    accounts_result = (
        db.table("instagram_accounts")
        .select("id")
        .eq("owner_id", user_id)
        .execute()
    )
    account_ids = [a["id"] for a in (accounts_result.data or [])]

    if not account_ids:
        return _empty_summary()

    try:
        stats_result = (
            db.table("post_stats")
            .select("likes, comments, saves, shares, reach, impressions, engagement_rate, published_at")
            .in_("account_id", account_ids)
            .gte("published_at", since)
            .order("published_at", desc=True)
            .execute()
        )
        stats = stats_result.data or []
    except Exception as e:
        logger.warning(f"[StatsSummary] stats query failed: {e}")
        stats = []

    if not stats:
        return _empty_summary()

    total_likes = sum(s.get("likes", 0) for s in stats)
    total_comments = sum(s.get("comments", 0) for s in stats)
    total_saves = sum(s.get("saves", 0) for s in stats)
    total_reach = sum(s.get("reach", 0) for s in stats)
    total_impressions = sum(s.get("impressions", 0) for s in stats)
    count = len(stats)

    avg_likes = round(total_likes / count, 1) if count else 0
    avg_comments = round(total_comments / count, 1) if count else 0
    avg_er = round(sum(float(s.get("engagement_rate", 0)) for s in stats) / count, 2) if count else 0

    # Best post
    best = max(stats, key=lambda s: s.get("likes", 0) + s.get("comments", 0))

    return {
        "period_days": days,
        "total_posts": count,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_saves": total_saves,
        "total_reach": total_reach,
        "total_impressions": total_impressions,
        "avg_likes": avg_likes,
        "avg_comments": avg_comments,
        "avg_engagement_rate": avg_er,
        "best_post": {
            "likes": best.get("likes", 0),
            "comments": best.get("comments", 0),
            "published_at": best.get("published_at"),
        },
    }


def _empty_summary():
    return {
        "period_days": 0,
        "total_posts": 0,
        "total_likes": 0,
        "total_comments": 0,
        "total_saves": 0,
        "total_reach": 0,
        "total_impressions": 0,
        "avg_likes": 0,
        "avg_comments": 0,
        "avg_engagement_rate": 0,
        "best_post": None,
    }


# ──────────────────────────────────────────
# Content Performance Breakdown
# ──────────────────────────────────────────

@router.get("/breakdown")
async def content_breakdown(
    days: int = Query(default=30, le=365),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Content performance breakdown by type, posting time, template, and day of week.
    Generates actionable recommendations.
    """
    user_id = user["id"]
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    # Get accounts
    accounts_result = (
        db.table("instagram_accounts")
        .select("id")
        .eq("owner_id", user_id)
        .execute()
    )
    account_ids = [a["id"] for a in (accounts_result.data or [])]
    if not account_ids:
        return _empty_breakdown()

    # Get stats with carousel data
    try:
        stats_result = (
            db.table("post_stats")
            .select("carousel_id, likes, comments, saves, shares, reach, engagement_rate, published_at, account_id")
            .in_("account_id", account_ids)
            .gte("published_at", since)
            .execute()
        )
        stats = stats_result.data or []
    except Exception as e:
        logger.warning(f"[Breakdown] stats query failed: {e}")
        stats = []

    if not stats:
        return _empty_breakdown()

    # Get carousel metadata (type, template, generation_params)
    carousel_ids = list(set(s["carousel_id"] for s in stats if s.get("carousel_id")))
    carousel_map = {}
    if carousel_ids:
        try:
            # Fetch in chunks to avoid URL length limits
            for i in range(0, len(carousel_ids), 50):
                chunk = carousel_ids[i:i+50]
                carousels = (
                    db.table("carousels")
                    .select("id, type, generation_params")
                    .in_("id", chunk)
                    .execute()
                )
                for c in (carousels.data or []):
                    carousel_map[c["id"]] = c
        except Exception as e:
            logger.warning(f"[Breakdown] carousel metadata fetch failed: {e}")

    # ── By Type ──
    by_type = {}
    for s in stats:
        carousel = carousel_map.get(s.get("carousel_id"), {})
        ctype = carousel.get("type", "topic")
        if ctype not in by_type:
            by_type[ctype] = {"count": 0, "total_likes": 0, "total_comments": 0, "total_saves": 0, "total_reach": 0, "er_sum": 0}
        by_type[ctype]["count"] += 1
        by_type[ctype]["total_likes"] += s.get("likes", 0)
        by_type[ctype]["total_comments"] += s.get("comments", 0)
        by_type[ctype]["total_saves"] += s.get("saves", 0)
        by_type[ctype]["total_reach"] += s.get("reach", 0)
        by_type[ctype]["er_sum"] += float(s.get("engagement_rate", 0))

    type_breakdown = []
    for t, d in by_type.items():
        c = d["count"]
        type_breakdown.append({
            "type": t,
            "count": c,
            "avg_likes": round(d["total_likes"] / c, 1),
            "avg_comments": round(d["total_comments"] / c, 1),
            "avg_saves": round(d["total_saves"] / c, 1),
            "avg_reach": round(d["total_reach"] / c),
            "avg_er": round(d["er_sum"] / c, 2),
        })
    type_breakdown.sort(key=lambda x: x["avg_er"], reverse=True)

    # ── By Hour ──
    by_hour = {}
    for s in stats:
        pub = s.get("published_at")
        if not pub:
            continue
        try:
            hour = datetime.fromisoformat(pub.replace("Z", "+00:00")).hour
        except Exception as e:
            logger.warning(f"[Breakdown] hour parsing failed for '{pub}': {e}")
            continue
        if hour not in by_hour:
            by_hour[hour] = {"count": 0, "total_likes": 0, "total_comments": 0, "er_sum": 0}
        by_hour[hour]["count"] += 1
        by_hour[hour]["total_likes"] += s.get("likes", 0)
        by_hour[hour]["total_comments"] += s.get("comments", 0)
        by_hour[hour]["er_sum"] += float(s.get("engagement_rate", 0))

    hour_breakdown = []
    for h, d in sorted(by_hour.items()):
        c = d["count"]
        hour_breakdown.append({
            "hour": h,
            "label": f"{h:02d}:00",
            "count": c,
            "avg_likes": round(d["total_likes"] / c, 1),
            "avg_comments": round(d["total_comments"] / c, 1),
            "avg_er": round(d["er_sum"] / c, 2),
        })

    # ── By Day of Week ──
    by_dow = {}
    DOW_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for s in stats:
        pub = s.get("published_at")
        if not pub:
            continue
        try:
            dt_obj = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            dow = dt_obj.weekday()  # 0=Mon
        except Exception as e:
            logger.warning(f"[Breakdown] day-of-week parsing failed for '{pub}': {e}")
            continue
        if dow not in by_dow:
            by_dow[dow] = {"count": 0, "total_likes": 0, "total_comments": 0, "er_sum": 0}
        by_dow[dow]["count"] += 1
        by_dow[dow]["total_likes"] += s.get("likes", 0)
        by_dow[dow]["total_comments"] += s.get("comments", 0)
        by_dow[dow]["er_sum"] += float(s.get("engagement_rate", 0))

    dow_breakdown = []
    for d in range(7):
        if d in by_dow:
            data = by_dow[d]
            c = data["count"]
            dow_breakdown.append({
                "day": d,
                "label": DOW_NAMES[d],
                "count": c,
                "avg_likes": round(data["total_likes"] / c, 1),
                "avg_comments": round(data["total_comments"] / c, 1),
                "avg_er": round(data["er_sum"] / c, 2),
            })
        else:
            dow_breakdown.append({"day": d, "label": DOW_NAMES[d], "count": 0, "avg_likes": 0, "avg_comments": 0, "avg_er": 0})

    # ── By Template / Color Scheme ──
    by_template = {}
    for s in stats:
        carousel = carousel_map.get(s.get("carousel_id"), {})
        params = carousel.get("generation_params") or {}
        template = params.get("color_scheme", params.get("font_style", "unknown"))
        if template not in by_template:
            by_template[template] = {"count": 0, "total_likes": 0, "total_comments": 0, "er_sum": 0}
        by_template[template]["count"] += 1
        by_template[template]["total_likes"] += s.get("likes", 0)
        by_template[template]["total_comments"] += s.get("comments", 0)
        by_template[template]["er_sum"] += float(s.get("engagement_rate", 0))

    template_breakdown = []
    for t, d in by_template.items():
        c = d["count"]
        template_breakdown.append({
            "template": t,
            "count": c,
            "avg_likes": round(d["total_likes"] / c, 1),
            "avg_comments": round(d["total_comments"] / c, 1),
            "avg_er": round(d["er_sum"] / c, 2),
        })
    template_breakdown.sort(key=lambda x: x["avg_er"], reverse=True)

    # ── Recommendations ──
    recommendations = _generate_recommendations(
        type_breakdown, hour_breakdown, dow_breakdown, template_breakdown, period_days=days
    )

    return {
        "period_days": days,
        "total_posts": len(stats),
        "by_type": type_breakdown,
        "by_hour": hour_breakdown,
        "by_day_of_week": dow_breakdown,
        "by_template": template_breakdown,
        "recommendations": recommendations,
    }


def _empty_breakdown():
    return {
        "period_days": 0,
        "total_posts": 0,
        "by_type": [],
        "by_hour": [],
        "by_day_of_week": [],
        "by_template": [],
        "recommendations": [],
    }


def _generate_recommendations(by_type, by_hour, by_dow, by_template, period_days: int = 30) -> list[dict]:
    """Generate actionable recommendations from analytics data."""
    recs = []

    # Best posting time
    if by_hour:
        best_hour = max(by_hour, key=lambda h: h["avg_er"])
        if best_hour["count"] >= 3:
            recs.append({
                "type": "timing",
                "icon": "clock",
                "title": f"Лучшее время — {best_hour['label']}",
                "description": f"Посты в {best_hour['label']} получают в среднем {best_hour['avg_er']}% ER ({best_hour['count']} постов)",
                "priority": "high",
            })

    # Best day
    active_days = [d for d in by_dow if d["count"] >= 2]
    if active_days:
        best_day = max(active_days, key=lambda d: d["avg_er"])
        worst_day = min(active_days, key=lambda d: d["avg_er"])
        if best_day["avg_er"] > worst_day["avg_er"] * 1.3:
            recs.append({
                "type": "timing",
                "icon": "calendar",
                "title": f"Лучший день — {best_day['label']}",
                "description": f"{best_day['label']} даёт {best_day['avg_er']}% ER vs {worst_day['label']} с {worst_day['avg_er']}%",
                "priority": "medium",
            })

    # Best content type
    if len(by_type) > 1:
        best_type = by_type[0]  # Already sorted by ER
        TYPE_LABELS = {"topic": "Тематические", "property": "Объекты недвижимости", "competitor": "Из конкурентов"}
        recs.append({
            "type": "content",
            "icon": "trending-up",
            "title": f"Лучший тип — {TYPE_LABELS.get(best_type['type'], best_type['type'])}",
            "description": f"Средний ER: {best_type['avg_er']}%, лайков: {best_type['avg_likes']}",
            "priority": "high",
        })

    # Best template
    multi_use_templates = [t for t in by_template if t["count"] >= 3]
    if len(multi_use_templates) > 1:
        best_tmpl = multi_use_templates[0]
        recs.append({
            "type": "design",
            "icon": "palette",
            "title": f"Лучший шаблон — {best_tmpl['template']}",
            "description": f"ER: {best_tmpl['avg_er']}% на {best_tmpl['count']} постах",
            "priority": "medium",
        })

    # Posting frequency
    total_posts = sum(d["count"] for d in by_dow)
    if total_posts > 0:
        weeks = max(1, period_days / 7)
        avg_per_week = round(total_posts / weeks, 1)
        if avg_per_week < 3:
            recs.append({
                "type": "frequency",
                "icon": "zap",
                "title": "Увеличьте частоту публикаций",
                "description": f"Сейчас ~{avg_per_week:.0f} пост(а) в неделю. Для роста рекомендуем 5-7 постов",
                "priority": "medium",
            })

    return recs


def _calculate_summary(posts: list) -> dict:
    if not posts:
        return _empty_summary()

    count = len(posts)
    total_likes = sum(p["likes"] for p in posts)
    total_comments = sum(p["comments"] for p in posts)
    total_saves = sum(p["saves"] for p in posts)
    total_reach = sum(p["reach"] for p in posts)

    avg_er = round(sum(p["engagement_rate"] for p in posts) / count, 2) if count else 0
    best = max(posts, key=lambda p: p["likes"] + p["comments"])

    return {
        "total_posts": count,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_saves": total_saves,
        "total_reach": total_reach,
        "avg_likes": round(total_likes / count, 1),
        "avg_comments": round(total_comments / count, 1),
        "avg_engagement_rate": avg_er,
        "best_post": {
            "carousel_id": best["carousel_id"],
            "likes": best["likes"],
            "comments": best["comments"],
            "published_at": best.get("published_at"),
        },
    }
