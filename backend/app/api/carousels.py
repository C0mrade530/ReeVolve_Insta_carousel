"""
Carousels API — generation + publishing.
Generation runs inline for fast dev feedback.
Multi-step: Draft → Evaluate → Refine → Generate slides.
Publish: login via instagrapi session → album_upload.
"""
import os
import json
import logging
import random
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Literal
from pydantic import BaseModel, Field
from supabase import Client

from app.api.deps import get_current_user, get_db
from app.config import get_settings
from app.utils.encryption import decrypt_data
from app.services.generator.pipeline import (
    generate_topic_carousel_pipeline,
    generate_property_carousel_pipeline,
)
from app.services.generator.image import DESIGN_TEMPLATES, get_template_names
from app.services.generator.font_manager import FONT_PAIRINGS, get_pairing_names
from app.services.generator.expert_template import get_template_path
from app.services.publisher.instagram import get_publisher
from app.services.publisher.safety import get_safety_manager

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


class TopicGenerateRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=500)
    name: str = Field(default="Эксперт", max_length=100)
    city: str = Field(default="", max_length=100)
    niche: str = Field(default="", max_length=200)
    font_style: str = Field(default="luxury", max_length=50)
    color_scheme: str = Field(default="expert", max_length=50)
    accent_color: str | None = Field(default=None, max_length=20)
    canvas_width: int | None = Field(default=None, ge=540, le=2160)
    canvas_height: int | None = Field(default=None, ge=540, le=2700)
    cta_final: str = Field(default="", max_length=300)
    lead_magnet: str = Field(default="", max_length=300)


class PropertyGenerateRequest(BaseModel):
    listing_id: str
    font_style: str = "luxury"
    cta_final: str = ""       # custom CTA for last slide
    lead_magnet: str = ""     # lead magnet text


class CarouselUpdate(BaseModel):
    caption: str | None = None
    hashtags: str | None = None
    slides: list[dict] | None = None


class ScheduleRequest(BaseModel):
    scheduled_at: datetime
    account_id: str  # Which IG account to publish from


class MusicTrackData(BaseModel):
    id: str
    audio_cluster_id: str
    highlight_start_ms: int = 0
    title: str = ""
    artist: str = ""


class PublishNowRequest(BaseModel):
    account_id: str  # Which IG account to publish from
    music_track: MusicTrackData | None = None  # Optional music (full track data from search)
    music_query: str | None = None  # Optional: search music by name at publish time (e.g. "The xx - Intro")


class BatchGenerateRequest(BaseModel):
    """Generate multiple carousels and auto-schedule them."""
    account_id: str
    days: int = Field(default=7, ge=1, le=14)
    posts_per_day: int = Field(default=1, ge=1, le=5)
    start_date: str | None = None
    posting_hours: list[int] = Field(default=[10, 14, 19], max_length=5)
    name: str = Field(default="Эксперт", max_length=100)
    city: str = Field(default="", max_length=100)
    niche: str = Field(default="", max_length=200)
    font_style: FontStyleType = "modern_clean"
    color_scheme: ColorSchemeType = "dark_luxury"
    skip_weekends: bool = False
    cta_final: str = Field(default="", max_length=300)
    lead_magnet: str = Field(default="", max_length=300)
    auto_music: bool = True


class CarouselApproveRequest(BaseModel):
    """Approve or reject a carousel for publishing."""
    status: str  # "approved", "rejected", "needs_edit"


class CarouselBulkApproveRequest(BaseModel):
    """Bulk approve carousels."""
    carousel_ids: list[str]
    status: str = "approved"


class RescheduleRequest(BaseModel):
    new_date: str  # ISO date: "2025-03-15"
    new_time: str | None = None  # "14:30" — if None, keep original time


# Music pool for auto-assignment (shuffled per batch)
MUSIC_POOL = [
    "The xx - Intro",
    "Ludovico Einaudi - Nuvole Bianche",
    "Hans Zimmer - Time",
    "Billie Eilish - Lovely",
    "Arctic Monkeys - Do I Wanna Know",
    "Lana Del Rey - Summertime Sadness",
    "Gregory Alan Isakov - Sweet Heat Lightning",
    "Giulio Cercato - Beautiful",
    "Morunas - Spring is Coming",
    "Kaan Simseker - Deep Force",
    "Hippie Sabotage - Devil Eyes",
    "Gibran Alcocer - Idea 10",
    "David Kushner - Daylight",
    "flora cash - You re Somebody Else",
    "Piano Peace - Save Me",
    "Interstellar Main Theme Piano",
    "Post Malone - Sunflower",
    "JONY - Allergy",
    "Rauf Faik - Childhood",
    "Luke Willies - everything works out in the end",
]


@router.get("")
async def list_carousels(
    type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    query = db.table("carousels").select("*").eq("owner_id", user["id"])

    if type:
        query = query.eq("type", type)
    if status:
        query = query.eq("status", status)

    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return result.data


@router.get("/design-options")
async def get_design_options(user: dict = Depends(get_current_user)):
    """Return available design templates and font pairings."""
    templates = []
    for key, tmpl in DESIGN_TEMPLATES.items():
        templates.append({
            "id": key,
            "name": tmpl["name"],
            "bg": tmpl["bg"],
            "accent": tmpl["accent"],
            "text": tmpl["text"],
            "font_pairing": tmpl.get("font_pairing", "modern_clean"),
        })

    pairings = []
    for key, pair in FONT_PAIRINGS.items():
        pairings.append({
            "id": key,
            "name": pair["name"],
        })

    return {"templates": templates, "pairings": pairings}


@router.post("/generate/topic")
async def generate_topic_carousel(
    req: TopicGenerateRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Generate a topic carousel (7+1 slides). Multi-step with self-evaluation."""

    # Create carousel record — no account needed
    carousel_data = {
        "type": "topic",
        "status": "generating",
        "owner_id": user["id"],
        "generation_params": {
            "topic": req.topic,
            "niche": req.niche,
            "city": req.city,
            "name": req.name,
            "font_style": req.font_style,
            "color_scheme": req.color_scheme,
        },
    }

    # Try insert — if owner_id column doesn't exist, use account_id workaround
    try:
        result = db.table("carousels").insert(carousel_data).execute()
    except Exception as e:
        # Fallback — get first account or create without account
        logger.warning(f"[topic_carousel_insert] Primary insert failed, using fallback: {e}")
        accounts = db.table("instagram_accounts").select("id").eq("owner_id", user["id"]).limit(1).execute()
        if accounts.data:
            carousel_data["account_id"] = accounts.data[0]["id"]
        carousel_data.pop("owner_id", None)
        result = db.table("carousels").insert(carousel_data).execute()

    carousel_id = result.data[0]["id"]

    # Build virtual account from request params
    virtual_account = {
        "username": req.name,
        "city": req.city,
        "niche": req.niche,
        "brand_style": _get_color_scheme(req.color_scheme),
        "cta_final": req.cta_final,
        "lead_magnet": req.lead_magnet,
        "accent_color": req.accent_color,
    }

    # Check for expert template
    expert_tmpl_path = get_template_path(user["id"])

    try:
        updated = await generate_topic_carousel_pipeline(
            carousel_id=carousel_id,
            account=virtual_account,
            topic_hint=req.topic,
            font_style=req.font_style,
            color_scheme=req.color_scheme,
            expert_template_path=expert_tmpl_path,
        )
        return {
            "carousel_id": carousel_id,
            "status": "ready",
            "slides": updated.get("slides", []),
            "caption": updated.get("caption", ""),
            "hashtags": updated.get("hashtags", ""),
            "quality_score": updated.get("generation_params", {}).get("content", {}).get("_meta", {}).get("final_score", 0),
            "generation_rounds": updated.get("generation_params", {}).get("content", {}).get("_meta", {}).get("generation_rounds", 1),
            "message": "Карусель готова!",
        }
    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка генерации: {str(e)}")


@router.post("/generate/topic/stream")
async def generate_topic_carousel_stream(
    req: TopicGenerateRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Generate a topic carousel with real-time SSE progress.
    Streams events: {step, current, total, label} then final result.
    """
    # Create carousel record
    carousel_data = {
        "type": "topic",
        "status": "generating",
        "owner_id": user["id"],
        "generation_params": {
            "topic": req.topic,
            "niche": req.niche,
            "city": req.city,
            "name": req.name,
            "font_style": req.font_style,
            "color_scheme": req.color_scheme,
        },
    }

    try:
        result = db.table("carousels").insert(carousel_data).execute()
    except Exception as e:
        logger.warning(f"[topic_sse_carousel_insert] Primary insert failed, using fallback: {e}")
        accounts = db.table("instagram_accounts").select("id").eq("owner_id", user["id"]).limit(1).execute()
        if accounts.data:
            carousel_data["account_id"] = accounts.data[0]["id"]
        carousel_data.pop("owner_id", None)
        result = db.table("carousels").insert(carousel_data).execute()

    carousel_id = result.data[0]["id"]

    virtual_account = {
        "username": req.name,
        "city": req.city,
        "niche": req.niche,
        "brand_style": _get_color_scheme(req.color_scheme),
        "cta_final": req.cta_final,
        "lead_magnet": req.lead_magnet,
    }

    expert_tmpl_path = get_template_path(user["id"])

    # Step labels for UI
    STEP_LABELS = {
        "topic": "Придумываю тему и стратегию...",
        "slides": "Пишу слайды и описание...",
        "evaluate": "Проверяю виральность...",
        "refine": "Улучшаю контент...",
        "slides_render": "Рисую слайды...",
        "done": "Готово!",
    }

    # SSE event queue
    progress_queue: asyncio.Queue = asyncio.Queue()

    def on_progress(step_name: str, current: int, total: int):
        label = STEP_LABELS.get(step_name, step_name)
        progress_queue.put_nowait({
            "event": "progress",
            "step": step_name,
            "current": current,
            "total": total,
            "label": label,
        })

    async def event_generator():
        # Start generation in background task
        gen_task = asyncio.create_task(_run_generation(
            carousel_id, virtual_account, req, expert_tmpl_path, on_progress
        ))

        # Stream progress events
        while True:
            try:
                event = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("step") == "done" or event.get("event") == "result":
                    break
            except asyncio.TimeoutError:
                # Send keepalive
                yield f": keepalive\n\n"
                if gen_task.done():
                    break

        # Wait for result
        try:
            final_result = await gen_task
            yield f"data: {json.dumps({'event': 'result', **final_result}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    async def _run_generation(cid, account, request, tmpl_path, progress_cb):
        try:
            updated = await generate_topic_carousel_pipeline(
                carousel_id=cid,
                account=account,
                topic_hint=request.topic,
                font_style=request.font_style,
                color_scheme=request.color_scheme,
                expert_template_path=tmpl_path,
                on_progress=progress_cb,
            )
            return {
                "carousel_id": cid,
                "status": "ready",
                "slides": updated.get("slides", []),
                "caption": updated.get("caption", ""),
                "hashtags": updated.get("hashtags", ""),
                "quality_score": updated.get("generation_params", {}).get("content", {}).get("_meta", {}).get("final_score", 0),
                "generation_rounds": updated.get("generation_params", {}).get("content", {}).get("_meta", {}).get("generation_rounds", 1),
                "message": "Карусель готова!",
            }
        except Exception as e:
            logger.error(f"SSE Generation failed: {e}", exc_info=True)
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/generate/property")
async def generate_property_carousel(
    req: PropertyGenerateRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Generate a property carousel (3-5 slides)."""
    listing = (
        db.table("property_listings")
        .select("*")
        .eq("id", req.listing_id)
        .single()
        .execute()
    )
    if not listing.data:
        raise HTTPException(status_code=404, detail="Listing not found")

    carousel_data = {
        "type": "property",
        "listing_id": req.listing_id,
        "status": "generating",
        "generation_params": {"listing_id": req.listing_id},
    }

    try:
        carousel_data["owner_id"] = user["id"]
        result = db.table("carousels").insert(carousel_data).execute()
    except Exception as e:
        logger.warning(f"[property_carousel_insert] Primary insert failed, using fallback: {e}")
        accounts = db.table("instagram_accounts").select("id").eq("owner_id", user["id"]).limit(1).execute()
        if accounts.data:
            carousel_data["account_id"] = accounts.data[0]["id"]
        carousel_data.pop("owner_id", None)
        result = db.table("carousels").insert(carousel_data).execute()

    carousel_id = result.data[0]["id"]

    virtual_account = {
        "username": "Эксперт",
        "brand_style": {},
        "cta_final": req.cta_final,
        "lead_magnet": req.lead_magnet,
    }

    try:
        updated = await generate_property_carousel_pipeline(
            carousel_id=carousel_id,
            account=virtual_account,
            listing=listing.data,
            font_style=req.font_style,
            on_progress=None,
        )
        return {
            "carousel_id": carousel_id,
            "status": "ready",
            "slides": updated.get("slides", []),
            "caption": updated.get("caption", ""),
            "hashtags": updated.get("hashtags", ""),
            "message": "Карусель готова!",
        }
    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка генерации: {str(e)}")


@router.post("/generate/property/stream")
async def generate_property_carousel_stream(
    req: PropertyGenerateRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Generate a property carousel with real-time SSE progress.
    """
    # Fetch listing
    listing_result = (
        db.table("property_listings")
        .select("*")
        .eq("id", req.listing_id)
        .single()
        .execute()
    )
    if not listing_result.data:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    listing = listing_result.data

    # Create carousel record
    carousel_data = {
        "type": "property",
        "listing_id": req.listing_id,
        "status": "generating",
        "owner_id": user["id"],
        "generation_params": {
            "listing_id": req.listing_id,
            "font_style": req.font_style,
        },
    }

    try:
        result = db.table("carousels").insert(carousel_data).execute()
    except Exception as e:
        logger.warning(f"[property_sse_carousel_insert] Primary insert failed, using fallback: {e}")
        accounts = db.table("instagram_accounts").select("id").eq("owner_id", user["id"]).limit(1).execute()
        if accounts.data:
            carousel_data["account_id"] = accounts.data[0]["id"]
        carousel_data.pop("owner_id", None)
        result = db.table("carousels").insert(carousel_data).execute()

    carousel_id = result.data[0]["id"]

    virtual_account = {
        "username": "Эксперт",
        "brand_style": {},
        "cta_final": req.cta_final,
        "lead_magnet": req.lead_magnet,
    }

    STEP_LABELS = {
        "fetch_listing": "Загружаю объявление...",
        "generate_text": "Пишу тексты слайдов...",
        "evaluate": "Проверяю качество...",
        "refine": "Улучшаю контент...",
        "slides_render": "Рисую слайды с фото...",
        "done": "Готово!",
    }

    progress_queue: asyncio.Queue = asyncio.Queue()

    def on_progress(step_name: str, current: int, total: int):
        label = STEP_LABELS.get(step_name, step_name)
        progress_queue.put_nowait({
            "event": "progress",
            "step": step_name,
            "current": current,
            "total": total,
            "label": label,
        })

    async def event_generator():
        gen_task = asyncio.create_task(_run_property_generation(
            carousel_id, virtual_account, listing, req, on_progress
        ))

        while True:
            try:
                event = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("step") == "done" or event.get("event") == "result":
                    break
            except asyncio.TimeoutError:
                yield f": keepalive\n\n"
                if gen_task.done():
                    break

        try:
            final_result = await gen_task
            yield f"data: {json.dumps({'event': 'result', **final_result}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    async def _run_property_generation(cid, account, listing_data, request, progress_cb):
        try:
            updated = await generate_property_carousel_pipeline(
                carousel_id=cid,
                account=account,
                listing=listing_data,
                font_style=request.font_style,
                on_progress=progress_cb,
            )
            return {
                "carousel_id": cid,
                "status": "ready",
                "slides": updated.get("slides", []),
                "caption": updated.get("caption", ""),
                "hashtags": updated.get("hashtags", ""),
                "quality_score": updated.get("generation_params", {}).get("content", {}).get("_meta", {}).get("final_score", 0),
                "listing_id": request.listing_id,
                "message": "Карусель готова!",
            }
        except Exception as e:
            logger.error(f"SSE Property generation failed: {e}", exc_info=True)
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/calendar")
async def get_calendar(
    month: int | None = None,
    year: int | None = None,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Get calendar view of all carousels (scheduled + published).
    Returns carousels grouped by date.
    """
    from datetime import date, timedelta as td

    now = datetime.utcnow()
    target_year = year or now.year
    target_month = month or now.month

    first_day = date(target_year, target_month, 1)
    if target_month == 12:
        last_day = date(target_year + 1, 1, 1) - td(days=1)
    else:
        last_day = date(target_year, target_month + 1, 1) - td(days=1)

    range_start = (first_day - td(days=7)).isoformat()
    range_end = (last_day + td(days=7)).isoformat()

    try:
        carousels_result = (
            db.table("carousels")
            .select("id, status, type, slides, caption, hashtags, published_at, generated_at, scheduled_at, generation_params")
            .eq("owner_id", user["id"])
            .in_("status", ["scheduled", "published", "ready", "review"])
            .order("generated_at", desc=False)
            .execute()
        )
    except Exception as e:
        logger.warning(f"[calendar_carousels_query] owner_id query failed, using account_id fallback: {e}")
        accounts = db.table("instagram_accounts").select("id").eq("owner_id", user["id"]).execute()
        account_ids = [a["id"] for a in (accounts.data or [])]
        if not account_ids:
            return {"month": target_month, "year": target_year, "days": {}}
        carousels_result = (
            db.table("carousels")
            .select("id, status, type, slides, caption, hashtags, published_at, generated_at, scheduled_at, generation_params, account_id")
            .in_("account_id", account_ids)
            .in_("status", ["scheduled", "published", "ready", "review"])
            .order("generated_at", desc=False)
            .execute()
        )

    carousels = carousels_result.data or []

    schedules = {}
    try:
        accounts = db.table("instagram_accounts").select("id").eq("owner_id", user["id"]).execute()
        account_ids = [a["id"] for a in (accounts.data or [])]
        if account_ids:
            sch_result = (
                db.table("publish_schedules")
                .select("id, carousel_id, scheduled_time, status, account_id, published_at, instagram_media_id")
                .in_("account_id", account_ids)
                .gte("scheduled_time", range_start)
                .lte("scheduled_time", range_end)
                .order("scheduled_time")
                .execute()
            )
            for sch in (sch_result.data or []):
                schedules[sch["carousel_id"]] = sch
    except Exception as e:
        logger.warning(f"[calendar_schedules_query] Failed to fetch publish schedules: {e}")

    days = {}
    for c in carousels:
        schedule = schedules.get(c["id"])
        if schedule and schedule.get("scheduled_time"):
            dt_str = schedule["scheduled_time"]
        elif c.get("scheduled_at"):
            dt_str = c["scheduled_at"]
        elif c.get("published_at"):
            dt_str = c["published_at"]
        elif c.get("generated_at"):
            dt_str = c["generated_at"]
        else:
            continue

        try:
            day_key = dt_str[:10]
        except Exception as e:
            logger.warning(f"[calendar_day_key] Failed to parse date string '{dt_str}': {e}")
            continue

        if day_key not in days:
            days[day_key] = []

        first_slide = c.get("slides", [{}])[0] if c.get("slides") else {}
        days[day_key].append({
            "carousel_id": c["id"],
            "status": schedule["status"] if schedule else c["status"],
            "type": c.get("type", "topic"),
            "scheduled_time": schedule.get("scheduled_time") if schedule else None,
            "published_at": schedule.get("published_at") if schedule else c.get("published_at"),
            "instagram_media_id": schedule.get("instagram_media_id") if schedule else None,
            "first_slide_image": first_slide.get("image_path"),
            "first_slide_title": first_slide.get("text_overlay", ""),
            "caption_preview": (c.get("caption") or "")[:80],
            "slides_count": len(c.get("slides", [])),
            "quality_score": c.get("generation_params", {}).get("content", {}).get("_meta", {}).get("final_score", 0),
        })

    return {
        "month": target_month,
        "year": target_year,
        "days": days,
    }


@router.get("/music/search")
async def search_music(
    q: str = Query(..., min_length=1, description="Search query for music"),
    account_id: str = Query(..., description="Account ID for auth session"),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Search Instagram music library.
    Returns list of tracks with id, title, artist, cover_url.
    """
    account_result = (
        db.table("instagram_accounts")
        .select("id, username, session_data, proxy")
        .eq("id", account_id)
        .eq("owner_id", user["id"])
        .limit(1)
        .execute()
    )
    if not account_result.data:
        raise HTTPException(400, "Аккаунт не найден. Возможно он был удалён — выберите другой аккаунт в шапке.")

    account = account_result.data[0]

    try:
        raw = account.get("session_data", "")
        if not raw:
            raise HTTPException(401, "Сессия аккаунта пуста. Переавторизуйтесь в разделе 'Аккаунты'.")
        session_settings = decrypt_data(raw)
        logger.info(f"[MusicSearch] Session decrypted for @{account.get('username', '?')}: keys={list(session_settings.keys())[:3] if isinstance(session_settings, dict) else 'N/A'}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MusicSearch] Decrypt failed for account {account_id}: {e}")
        raise HTTPException(401, "Сессия повреждена. Переавторизуйтесь в разделе 'Аккаунты'.")

    publisher = get_publisher()
    client = await publisher.login_by_session(
        session_data={"settings": session_settings},
        proxy=account.get("proxy"),
    )

    if not client:
        raise HTTPException(401, "Сессия истекла. Переавторизуйтесь.")

    tracks = await publisher.search_music(client, q)

    # Save session after music search (cookies updated)
    await publisher.save_session_to_db(client, account["id"])

    return {"tracks": tracks}


@router.get("/{carousel_id}")
async def get_carousel(
    carousel_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    result = (
        db.table("carousels")
        .select("*")
        .eq("id", carousel_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Carousel not found")
    return result.data


@router.get("/{carousel_id}/preview")
async def preview_carousel(
    carousel_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    result = (
        db.table("carousels")
        .select("slides, caption, hashtags")
        .eq("id", carousel_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Carousel not found")
    return {
        "slides": result.data.get("slides", []),
        "caption": result.data.get("caption"),
        "hashtags": result.data.get("hashtags"),
    }


@router.post("/generate/batch")
async def generate_batch(
    req: BatchGenerateRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Generate N carousels and auto-schedule them across days.
    Returns list of generated carousels with schedule times.
    """
    from datetime import date, timedelta as td
    import random

    # Verify account
    account_result = (
        db.table("instagram_accounts")
        .select("id, username, niche, city")
        .eq("id", req.account_id)
        .eq("owner_id", user["id"])
        .single()
        .execute()
    )
    if not account_result.data:
        raise HTTPException(400, "Аккаунт не найден")

    account_db = account_result.data

    # Calculate start date
    if req.start_date:
        start = datetime.strptime(req.start_date, "%Y-%m-%d").date()
    else:
        start = date.today() + td(days=1)

    # Build schedule slots
    slots = []
    current_date = start
    for day_offset in range(req.days):
        d = start + td(days=day_offset)
        # Skip weekends if requested
        if req.skip_weekends and d.weekday() >= 5:
            continue
        # Pick posting hours for this day
        hours = req.posting_hours[:req.posts_per_day]
        for h in hours:
            # Add ±10 min jitter for human-like timing
            jitter_min = random.randint(-10, 10)
            minute = max(0, min(59, 0 + jitter_min))
            scheduled_dt = datetime(d.year, d.month, d.day, h, minute, 0)
            slots.append(scheduled_dt)

    total = len(slots)
    if total == 0:
        raise HTTPException(400, "Нет доступных слотов для расписания")
    if total > 21:
        raise HTTPException(400, f"Слишком много каруселей ({total}). Максимум 21.")

    # Virtual account for generation
    virtual_account = {
        "username": req.name,
        "city": req.city,
        "niche": req.niche,
        "brand_style": _get_color_scheme(req.color_scheme),
        "cta_final": req.cta_final,
        "lead_magnet": req.lead_magnet,
    }
    expert_tmpl_path = get_template_path(user["id"])

    results = []
    errors = []

    for idx, scheduled_at in enumerate(slots):
        logger.info(f"[Batch] Generating carousel {idx + 1}/{total} for {scheduled_at}")

        try:
            # Create carousel record
            carousel_data = {
                "type": "topic",
                "status": "generating",
                "owner_id": user["id"],
                "generation_params": {
                    "batch": True,
                    "batch_index": idx + 1,
                    "batch_total": total,
                    "niche": req.niche,
                    "city": req.city,
                    "name": req.name,
                    "font_style": req.font_style,
                    "color_scheme": req.color_scheme,
                },
            }
            try:
                cr = db.table("carousels").insert(carousel_data).execute()
            except Exception as e:
                logger.warning(f"[batch_carousel_insert] Primary insert failed, using fallback: {e}")
                carousel_data.pop("owner_id", None)
                accounts = db.table("instagram_accounts").select("id").eq("owner_id", user["id"]).limit(1).execute()
                if accounts.data:
                    carousel_data["account_id"] = accounts.data[0]["id"]
                cr = db.table("carousels").insert(carousel_data).execute()

            carousel_id = cr.data[0]["id"]

            # Generate carousel (GPT text + Pillow slides)
            updated = await generate_topic_carousel_pipeline(
                carousel_id=carousel_id,
                account=virtual_account,
                topic_hint=None,  # GPT придумает сам разную тему каждый раз
                font_style=req.font_style,
                color_scheme=req.color_scheme,
                expert_template_path=expert_tmpl_path,
            )

            # Create schedule record
            try:
                db.table("publish_schedules").insert({
                    "account_id": req.account_id,
                    "carousel_id": carousel_id,
                    "scheduled_time": scheduled_at.isoformat(),
                    "status": "pending",
                }).execute()

                # Update carousel status to scheduled
                db.table("carousels").update({
                    "status": "scheduled",
                }).eq("id", carousel_id).execute()
            except Exception as e:
                logger.warning(f"[Batch] Schedule insert error: {e}")

            slides = updated.get("slides", [])
            caption = updated.get("caption", "")
            quality = updated.get("generation_params", {}).get("content", {}).get("_meta", {}).get("final_score", 0)

            results.append({
                "carousel_id": carousel_id,
                "scheduled_at": scheduled_at.isoformat(),
                "status": "scheduled",
                "slides_count": len(slides),
                "first_slide": slides[0] if slides else None,
                "caption_preview": caption[:100] + "..." if len(caption) > 100 else caption,
                "quality_score": quality,
            })

        except Exception as e:
            logger.error(f"[Batch] Failed carousel {idx + 1}: {e}")
            errors.append({
                "index": idx + 1,
                "scheduled_at": scheduled_at.isoformat(),
                "error": str(e),
            })

    return {
        "total_generated": len(results),
        "total_errors": len(errors),
        "total_planned": total,
        "account": account_db["username"],
        "date_range": f"{slots[0].strftime('%d.%m')} — {slots[-1].strftime('%d.%m.%Y')}",
        "carousels": results,
        "errors": errors if errors else None,
    }


@router.post("/generate/batch/stream")
async def generate_batch_stream(
    req: BatchGenerateRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Generate batch carousels with SSE streaming progress.
    Streams per-carousel progress + final results for review.
    """
    from datetime import date, timedelta as td

    # Verify account
    account_result = (
        db.table("instagram_accounts")
        .select("id, username, niche, city")
        .eq("id", req.account_id)
        .eq("owner_id", user["id"])
        .single()
        .execute()
    )
    if not account_result.data:
        raise HTTPException(400, "Аккаунт не найден")

    account_db = account_result.data

    # Calculate slots
    if req.start_date:
        start = datetime.strptime(req.start_date, "%Y-%m-%d").date()
    else:
        start = date.today() + td(days=1)

    slots = []
    for day_offset in range(req.days + 14):  # +14 to handle weekend skips
        if len(slots) >= req.days * req.posts_per_day:
            break
        d = start + td(days=day_offset)
        if req.skip_weekends and d.weekday() >= 5:
            continue
        hours = req.posting_hours[:req.posts_per_day]
        for h in hours:
            jitter_min = random.randint(-10, 10)
            minute = max(0, min(59, 0 + jitter_min))
            scheduled_dt = datetime(d.year, d.month, d.day, h, minute, 0)
            slots.append(scheduled_dt)

    total = len(slots)
    if total == 0:
        raise HTTPException(400, "Нет доступных слотов для расписания")
    if total > 21:
        raise HTTPException(400, f"Слишком много каруселей ({total}). Максимум 21.")

    # Auto-assign music tracks (shuffle pool, cycle if needed)
    music_assignments = []
    if req.auto_music:
        pool = list(MUSIC_POOL)
        random.shuffle(pool)
        for i in range(total):
            music_assignments.append(pool[i % len(pool)])
    else:
        music_assignments = [None] * total

    virtual_account = {
        "username": req.name,
        "city": req.city,
        "niche": req.niche,
        "brand_style": _get_color_scheme(req.color_scheme),
        "cta_final": req.cta_final,
        "lead_magnet": req.lead_magnet,
    }
    expert_tmpl_path = get_template_path(user["id"])

    async def event_generator():
        results = []
        errors = []
        used_topics = []  # Track generated topics for diversity

        for idx, scheduled_at in enumerate(slots):
            # Send "starting" event for this carousel
            yield f"data: {json.dumps({'event': 'carousel_start', 'index': idx, 'total': total, 'scheduled_at': scheduled_at.isoformat()}, ensure_ascii=False)}\n\n"

            try:
                carousel_data = {
                    "type": "topic",
                    "status": "generating",
                    "owner_id": user["id"],
                    "generation_params": {
                        "batch": True,
                        "batch_index": idx + 1,
                        "batch_total": total,
                        "niche": req.niche,
                        "city": req.city,
                        "name": req.name,
                        "font_style": req.font_style,
                        "color_scheme": req.color_scheme,
                        "music_query": music_assignments[idx],
                        "lead_magnet": req.lead_magnet,
                        "cta_final": req.cta_final,
                    },
                }
                try:
                    cr = db.table("carousels").insert(carousel_data).execute()
                except Exception as e:
                    logger.warning(f"[batch_sse_carousel_insert] Primary insert failed, using fallback: {e}")
                    carousel_data.pop("owner_id", None)
                    accounts = db.table("instagram_accounts").select("id").eq("owner_id", user["id"]).limit(1).execute()
                    if accounts.data:
                        carousel_data["account_id"] = accounts.data[0]["id"]
                    cr = db.table("carousels").insert(carousel_data).execute()

                carousel_id = cr.data[0]["id"]

                # Progress callback for this carousel
                def make_progress_cb(cidx):
                    def on_progress(step_name: str, current: int, total_steps: int):
                        pass  # SSE per-step is too noisy for batch; we send per-carousel
                    return on_progress

                updated = await generate_topic_carousel_pipeline(
                    carousel_id=carousel_id,
                    account=virtual_account,
                    topic_hint=None,
                    font_style=req.font_style,
                    color_scheme=req.color_scheme,
                    expert_template_path=expert_tmpl_path,
                    used_topics=used_topics if used_topics else None,
                )

                # Schedule it
                try:
                    db.table("publish_schedules").insert({
                        "account_id": req.account_id,
                        "carousel_id": carousel_id,
                        "scheduled_time": scheduled_at.isoformat(),
                        "status": "pending",
                    }).execute()
                    db.table("carousels").update({
                        "status": "review",  # New status: pending user review
                    }).eq("id", carousel_id).execute()
                except Exception as e:
                    logger.warning(f"[BatchSSE] Schedule insert error: {e}")

                # Track generated topic for diversity in next iterations
                gen_content = updated.get("generation_params", {}).get("content", {})
                hook = gen_content.get("hook_title", "")
                pain = gen_content.get("_meta", {}).get("pain_trigger", "")
                if hook:
                    topic_summary = hook
                    if pain:
                        topic_summary += f" (триггер: {pain})"
                    used_topics.append(topic_summary)

                slides = updated.get("slides", [])
                caption = updated.get("caption", "")
                quality = gen_content.get("_meta", {}).get("final_score", 0)

                carousel_result = {
                    "carousel_id": carousel_id,
                    "scheduled_at": scheduled_at.isoformat(),
                    "status": "review",
                    "slides_count": len(slides),
                    "slides": slides,
                    "first_slide": slides[0] if slides else None,
                    "caption": caption,
                    "caption_preview": caption[:100] + "..." if len(caption) > 100 else caption,
                    "quality_score": quality,
                    "music_query": music_assignments[idx],
                    "lead_magnet": req.lead_magnet,
                    "cta_final": req.cta_final,
                }
                results.append(carousel_result)

                yield f"data: {json.dumps({'event': 'carousel_done', 'index': idx, 'total': total, 'carousel': carousel_result}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"[BatchSSE] Failed carousel {idx + 1}: {e}")
                error_data = {
                    "index": idx,
                    "scheduled_at": scheduled_at.isoformat(),
                    "error": str(e),
                }
                errors.append(error_data)
                yield f"data: {json.dumps({'event': 'carousel_error', 'index': idx, 'total': total, **error_data}, ensure_ascii=False)}\n\n"

        # Final summary
        date_range = ""
        if slots:
            date_range = f"{slots[0].strftime('%d.%m')} — {slots[-1].strftime('%d.%m.%Y')}"
        summary = {
            "event": "batch_done",
            "total_generated": len(results),
            "total_errors": len(errors),
            "total_planned": total,
            "account": account_db["username"],
            "date_range": date_range,
            "carousels": results,
            "errors": errors if errors else None,
        }
        yield f"data: {json.dumps(summary, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{carousel_id}/approve")
async def approve_carousel(
    carousel_id: str,
    req: CarouselApproveRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Set carousel approval status: approved / rejected / needs_edit."""
    valid_statuses = ["approved", "rejected", "needs_edit", "scheduled"]
    if req.status not in valid_statuses:
        raise HTTPException(400, f"Статус должен быть один из: {', '.join(valid_statuses)}")

    # Map status → carousel status
    new_status = req.status
    if req.status == "approved":
        new_status = "scheduled"  # Approved = ready for scheduled publishing

    result = db.table("carousels").update({
        "status": new_status,
    }).eq("id", carousel_id).execute()

    if not result.data:
        raise HTTPException(404, "Карусель не найдена")

    return {"carousel_id": carousel_id, "status": new_status, "message": "Статус обновлён"}


@router.post("/bulk-approve")
async def bulk_approve(
    req: CarouselBulkApproveRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Bulk approve multiple carousels."""
    new_status = "scheduled" if req.status == "approved" else req.status
    updated = 0
    for cid in req.carousel_ids:
        try:
            db.table("carousels").update({"status": new_status}).eq("id", cid).execute()
            updated += 1
        except Exception as e:
            logger.warning(f"[bulk_approve] Failed to update carousel {cid}: {e}")
    return {"updated": updated, "total": len(req.carousel_ids), "status": new_status}


@router.post("/{carousel_id}/regenerate")
async def regenerate_carousel(
    carousel_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Completely regenerate a carousel (new text + new slides).
    Keeps the same schedule slot and music assignment.
    """
    # Get existing carousel
    carousel_result = (
        db.table("carousels")
        .select("*")
        .eq("id", carousel_id)
        .single()
        .execute()
    )
    if not carousel_result.data:
        raise HTTPException(404, "Карусель не найдена")

    carousel = carousel_result.data
    gen_params = carousel.get("generation_params", {})

    # Mark as generating
    db.table("carousels").update({"status": "generating"}).eq("id", carousel_id).execute()

    virtual_account = {
        "username": gen_params.get("name", "Эксперт"),
        "city": gen_params.get("city", ""),
        "niche": gen_params.get("niche", ""),
        "brand_style": _get_color_scheme(gen_params.get("color_scheme", "dark_luxury")),
        "cta_final": gen_params.get("cta_final", ""),
        "lead_magnet": gen_params.get("lead_magnet", ""),
    }

    expert_tmpl_path = get_template_path(user["id"])

    try:
        updated = await generate_topic_carousel_pipeline(
            carousel_id=carousel_id,
            account=virtual_account,
            topic_hint=None,
            font_style=gen_params.get("font_style", "modern_clean"),
            color_scheme=gen_params.get("color_scheme", "dark_luxury"),
            expert_template_path=expert_tmpl_path,
        )

        # Set back to review status
        db.table("carousels").update({"status": "review"}).eq("id", carousel_id).execute()

        return {
            "carousel_id": carousel_id,
            "status": "review",
            "slides": updated.get("slides", []),
            "caption": updated.get("caption", ""),
            "hashtags": updated.get("hashtags", ""),
            "quality_score": updated.get("generation_params", {}).get("content", {}).get("_meta", {}).get("final_score", 0),
            "message": "Карусель перегенерирована!",
        }
    except Exception as e:
        db.table("carousels").update({"status": "failed"}).eq("id", carousel_id).execute()
        raise HTTPException(500, f"Ошибка перегенерации: {str(e)}")


@router.patch("/{carousel_id}/music")
async def update_carousel_music(
    carousel_id: str,
    music_query: str | None = None,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Update music assignment for a carousel."""
    carousel_result = db.table("carousels").select("generation_params").eq("id", carousel_id).single().execute()
    if not carousel_result.data:
        raise HTTPException(404, "Карусель не найдена")

    gen_params = carousel_result.data.get("generation_params", {})
    gen_params["music_query"] = music_query

    db.table("carousels").update({"generation_params": gen_params}).eq("id", carousel_id).execute()
    return {"carousel_id": carousel_id, "music_query": music_query}


@router.patch("/{carousel_id}/lead-magnet")
async def update_carousel_lead_magnet(
    carousel_id: str,
    lead_magnet: str = "",
    cta_final: str = "",
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Update lead magnet and CTA for a carousel."""
    carousel_result = db.table("carousels").select("generation_params").eq("id", carousel_id).single().execute()
    if not carousel_result.data:
        raise HTTPException(404, "Карусель не найдена")

    gen_params = carousel_result.data.get("generation_params", {})
    gen_params["lead_magnet"] = lead_magnet
    gen_params["cta_final"] = cta_final

    db.table("carousels").update({"generation_params": gen_params}).eq("id", carousel_id).execute()
    return {"carousel_id": carousel_id, "lead_magnet": lead_magnet, "cta_final": cta_final}


@router.patch("/{carousel_id}")
async def update_carousel(
    carousel_id: str,
    req: CarouselUpdate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")
    result = db.table("carousels").update(data).eq("id", carousel_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Carousel not found")
    return result.data[0]


class SlideRegenerateRequest(BaseModel):
    title: str = ""
    body: str = ""


@router.post("/{carousel_id}/regenerate-slide/{slide_number}")
async def regenerate_slide(
    carousel_id: str,
    slide_number: int,
    req: SlideRegenerateRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Regenerate a single slide image with new text.
    Re-renders the Pillow image with updated title/body, keeping same design.
    """
    from app.services.generator.image import generate_topic_slide
    from app.services.generator.pipeline import _save_slide

    # Get carousel
    carousel_result = (
        db.table("carousels")
        .select("id, slides, generation_params, owner_id")
        .eq("id", carousel_id)
        .single()
        .execute()
    )
    if not carousel_result.data:
        raise HTTPException(404, "Карусель не найдена")

    carousel = carousel_result.data

    # Verify ownership
    if carousel.get("owner_id") != user["id"]:
        raise HTTPException(403, "Нет доступа")

    slides = carousel.get("slides", [])
    if slide_number < 1 or slide_number > len(slides):
        raise HTTPException(400, f"Слайд {slide_number} не найден. Всего слайдов: {len(slides)}")

    # Get design params
    gen_params = carousel.get("generation_params", {})
    font_style = gen_params.get("font_style", "modern_clean")
    color_scheme = gen_params.get("color_scheme", "dark_luxury")

    # Get username from content
    content = gen_params.get("content", {})
    username = content.get("hook_title", "Эксперт").split("\n")[0] if content else "Эксперт"
    # Try to get from generation params
    username = gen_params.get("name", username)

    title = req.title or slides[slide_number - 1].get("text_overlay", "")
    body = req.body or slides[slide_number - 1].get("body", "")

    try:
        # Regenerate image
        image_bytes = generate_topic_slide(
            slide_number=slide_number,
            total_slides=len(slides),
            title=title,
            body=body,
            username=username,
            style={},
            font_style=font_style,
            design_template=color_scheme,
        )

        # Save to disk
        image_path = _save_slide(image_bytes, carousel_id, slide_number)

        # Update slide in DB
        slides[slide_number - 1]["image_path"] = image_path
        slides[slide_number - 1]["text_overlay"] = title
        slides[slide_number - 1]["body"] = body

        db.table("carousels").update({"slides": slides}).eq("id", carousel_id).execute()

        return {
            "status": "ok",
            "slide_number": slide_number,
            "image_path": image_path,
            "message": f"Слайд {slide_number} перегенерирован",
        }

    except Exception as e:
        logger.error(f"[Regenerate] Slide {slide_number} failed: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка перегенерации: {str(e)}")


@router.post("/{carousel_id}/schedule")
async def schedule_carousel(
    carousel_id: str,
    req: ScheduleRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Schedule carousel for future publishing."""
    # Verify account belongs to user
    account_result = (
        db.table("instagram_accounts")
        .select("id, username")
        .eq("id", req.account_id)
        .eq("owner_id", user["id"])
        .single()
        .execute()
    )
    if not account_result.data:
        raise HTTPException(400, "Аккаунт не найден")

    # Update carousel status
    db.table("carousels").update({
        "status": "scheduled",
    }).eq("id", carousel_id).execute()

    # Create publish schedule record
    try:
        db.table("publish_schedules").insert({
            "account_id": req.account_id,
            "carousel_id": carousel_id,
            "scheduled_time": req.scheduled_at.isoformat(),
            "status": "pending",
        }).execute()
    except Exception as e:
        logger.warning(f"Failed to create schedule record: {e}")

    return {
        "message": f"Карусель запланирована на {req.scheduled_at.strftime('%d.%m.%Y %H:%M')}",
        "scheduled_at": req.scheduled_at,
        "account": account_result.data["username"],
    }


@router.post("/{carousel_id}/publish-now")
async def publish_now(
    carousel_id: str,
    req: PublishNowRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Publish carousel to Instagram RIGHT NOW.
    Flow: load carousel → load account session → login → upload album → update DB.
    """
    # 1. Get carousel data
    carousel_result = (
        db.table("carousels")
        .select("id, slides, caption, hashtags, status")
        .eq("id", carousel_id)
        .single()
        .execute()
    )
    if not carousel_result.data:
        raise HTTPException(404, "Карусель не найдена")

    carousel = carousel_result.data
    slides = carousel.get("slides", [])

    if not slides or len(slides) < 2:
        raise HTTPException(400, "Нужно минимум 2 слайда для публикации")

    # 2. Get account with session
    account_result = (
        db.table("instagram_accounts")
        .select("id, username, session_data, proxy, session_expires_at")
        .eq("id", req.account_id)
        .eq("owner_id", user["id"])
        .single()
        .execute()
    )
    if not account_result.data:
        raise HTTPException(400, "Аккаунт не найден")

    account = account_result.data

    # 2.5. Check session expiry
    from datetime import timezone
    session_exp = account.get("session_expires_at")
    if session_exp:
        try:
            from dateutil.parser import parse as parse_dt
            exp_dt = parse_dt(session_exp)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if exp_dt < datetime.now(timezone.utc):
                raise HTTPException(401, "Сессия Instagram истекла. Перелогиньтесь в разделе 'Аккаунты'.")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"[Publish] Failed to check session expiry: {e}")

    # 3. Decrypt session
    try:
        session_settings = decrypt_data(account["session_data"])
    except Exception as e:
        logger.warning(f"[publish_decrypt] Failed to decrypt session for account {account.get('id')}: {e}")
        raise HTTPException(401, "Сессия повреждена. Переавторизуйтесь в разделе 'Аккаунты'.")

    # 4. Login via session
    publisher = get_publisher()
    client = await publisher.login_by_session(
        session_data={"settings": session_settings},
        proxy=account.get("proxy"),
    )

    if not client:
        # Mark account as inactive
        db.table("instagram_accounts").update({"is_active": False}).eq("id", account["id"]).execute()
        raise HTTPException(401, "Сессия Instagram истекла. Переавторизуйтесь в разделе 'Аккаунты'.")

    # 4b. Safety check: rate limits
    safety = get_safety_manager()
    # Count today's posts for this account
    today_posts = 0
    try:
        from datetime import date
        today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
        today_result = (
            db.table("carousels")
            .select("id", count="exact")
            .eq("status", "published")
            .gte("published_at", today_start)
            .execute()
        )
        today_posts = today_result.count or 0
    except Exception as e:
        logger.warning(f"[publish_safety_check] Failed to count today's posts: {e}")

    check = safety.can_publish(
        username=account["username"],
        posts_today=today_posts,
    )
    if not check["allowed"]:
        raise HTTPException(429, check["reason"])

    # 4c. Pre-publish warmup — DISABLED for now
    # feed/timeline and reels_tray trigger challenges on new sessions,
    # which taints the session and blocks album_upload.
    # TODO: re-enable once sessions are stable on mobile proxy
    logger.info("[Publish] Warmup SKIPPED (prevents challenge on fresh session)")
    await asyncio.sleep(random.uniform(3, 6))  # Just a delay to look human

    # 5. Collect image paths from slides (resolve /media/... URLs to actual filesystem paths)
    from pathlib import Path as _Path
    media_root = str(_Path(settings.media_storage_path).resolve())  # e.g. /abs/path/to/media
    image_paths = []
    for slide in slides:
        path = slide.get("image_path") or slide.get("path") or slide.get("url", "")
        if path and not path.startswith("http"):
            # DB stores URL paths like /media/carousels/xxx/slide_1.png
            # Resolve to actual filesystem: strip leading /media/ and prepend media_root
            if path.startswith("/media/"):
                fs_path = os.path.join(media_root, path[len("/media/"):])
            elif path.startswith("media/"):
                fs_path = os.path.join(media_root, path[len("media/"):])
            else:
                fs_path = path
            image_paths.append(fs_path)

    logger.info(f"[Publish] Resolved {len(image_paths)} image paths (media_root={media_root})")
    for p in image_paths:
        exists = os.path.exists(p)
        logger.info(f"[Publish]   {'OK' if exists else 'MISSING'}: {p}")

    if len(image_paths) < 2:
        raise HTTPException(400, "Не найдены локальные файлы слайдов. Нужно минимум 2 изображения.")

    # 6. Build caption
    caption = carousel.get("caption", "")
    hashtags = carousel.get("hashtags", "")
    full_caption = f"{caption}\n\n{hashtags}".strip() if hashtags else caption

    # 7. Publish!
    logger.info(f"[Publish] Publishing carousel {carousel_id} to @{account['username']}...")

    # Music track data
    music_data = None
    if req.music_track:
        music_data = req.music_track.model_dump()
        logger.info(f"[Publish] With music track: {music_data.get('title')} — {music_data.get('artist')}")

    music_query = req.music_query
    if music_query:
        logger.info(f"[Publish] With music query: {music_query}")

    result = await publisher.publish_carousel(
        client=client,
        image_paths=image_paths,
        caption=full_caption,
        music_track=music_data,
        music_query=music_query,
    )

    publish_status = result.get("status")

    # CRITICAL: Always save session back to DB after any Instagram operation.
    # instagrapi updates cookies/tokens internally after each API call.
    # Without saving, next operation uses stale session → forced re-login.
    await publisher.save_session_to_db(client, account["id"])

    if publish_status == "published":
        # Update carousel status + store media_id for stats
        db.table("carousels").update({
            "status": "published",
            "published_at": datetime.utcnow().isoformat(),
            "media_id": result.get("media_id"),
            "media_code": result.get("media_code"),
        }).eq("id", carousel_id).execute()

        # Update account last_published_at
        db.table("instagram_accounts").update({
            "last_published_at": datetime.utcnow().isoformat(),
        }).eq("id", account["id"]).execute()

        # Post-publish cooldown + log action
        safety.log_action(account["username"], "publish")
        await safety.post_publish_cooldown(client)

        logger.info(f"[Publish] Success! media_id={result.get('media_id')}")
        return {
            "status": "published",
            "media_id": result.get("media_id"),
            "media_code": result.get("media_code"),
            "url": result.get("url"),
            "message": f"Опубликовано в @{account['username']}!",
        }

    elif publish_status == "session_expired":
        db.table("instagram_accounts").update({"is_active": False}).eq("id", account["id"]).execute()
        raise HTTPException(401, "Сессия истекла во время публикации. Переавторизуйтесь.")

    elif publish_status == "spam_block":
        raise HTTPException(429, result.get("error", "Instagram заблокировал публикацию. Подождите 24-48 часов."))

    else:
        raise HTTPException(500, result.get("error", "Ошибка публикации"))


class CarouselRerenderRequest(BaseModel):
    """Re-render all slides with new design parameters."""
    font_style: str = "luxury"
    color_scheme: str = "expert"
    username: str = ""
    slides: list[dict] | None = None  # optional: updated text per slide


@router.post("/{carousel_id}/rerender")
async def rerender_carousel(
    carousel_id: str,
    req: CarouselRerenderRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Re-render all slides with new design params (template, font, username, text)."""
    from app.services.generator.image import generate_topic_slide, get_template
    from app.services.generator.expert_template import get_template_path

    # Verify ownership
    carousel_result = (
        db.table("carousels")
        .select("id, slides, generation_params, owner_id, status")
        .eq("id", carousel_id)
        .single()
        .execute()
    )
    if not carousel_result.data:
        raise HTTPException(404, "Карусель не найдена")

    carousel = carousel_result.data
    if carousel.get("owner_id") != user["id"]:
        raise HTTPException(403, "Нет доступа")

    existing_slides = carousel.get("slides") or []
    total_slides = len(existing_slides)
    if total_slides == 0:
        raise HTTPException(400, "Нет слайдов для рендеринга")

    # Get account for brand_style
    gen_params = carousel.get("generation_params") or {}
    style = get_template(req.color_scheme)

    # Apply updated text if provided
    if req.slides:
        for i, updated in enumerate(req.slides):
            if i < total_slides:
                if "text_overlay" in updated:
                    existing_slides[i]["text_overlay"] = updated["text_overlay"]
                if "body" in updated:
                    existing_slides[i]["body"] = updated["body"]

    expert_tmpl_path = get_template_path(user["id"])

    # Re-render each slide
    new_slides = []
    for i, slide_data in enumerate(existing_slides):
        slide_num = i + 1
        title = slide_data.get("text_overlay", "")
        body = slide_data.get("body", "")

        image_bytes = await asyncio.to_thread(
            generate_topic_slide,
            slide_number=slide_num,
            total_slides=total_slides,
            title=title,
            body=body,
            username=req.username or gen_params.get("name", ""),
            style=style,
            font_style=req.font_style,
            design_template=req.color_scheme,
            expert_template_path=expert_tmpl_path,
        )

        # Save slide
        from app.services.generator.pipeline import _save_slide
        image_path = await asyncio.to_thread(_save_slide, image_bytes, carousel_id, slide_num)

        new_slides.append({
            **slide_data,
            "slide_number": slide_num,
            "image_path": image_path,
            "text_overlay": title,
            "body": body,
        })

    # Update DB
    update_data = {
        "slides": new_slides,
        "generation_params": {
            **gen_params,
            "font_style": req.font_style,
            "color_scheme": req.color_scheme,
        },
    }
    db.table("carousels").update(update_data).eq("id", carousel_id).execute()

    logger.info(f"[Rerender] Carousel {carousel_id}: {total_slides} slides re-rendered with {req.color_scheme}")

    return {
        "slides": new_slides,
        "message": f"Перерендерено {total_slides} слайдов",
    }


@router.patch("/{carousel_id}/reschedule")
async def reschedule_carousel(
    carousel_id: str,
    req: RescheduleRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Move carousel to a different date/time via drag-and-drop."""
    # Get carousel
    result = db.table("carousels").select("id, status, scheduled_at, owner_id").eq("id", carousel_id).single().execute()
    if not result.data:
        raise HTTPException(404, "Карусель не найдена")
    carousel = result.data
    if carousel.get("owner_id") != user["id"]:
        raise HTTPException(403, "Нет доступа")
    if carousel.get("status") == "published":
        raise HTTPException(400, "Нельзя перенести опубликованную карусель")

    # Build new datetime
    from datetime import datetime as dt, time as t
    try:
        new_date = dt.fromisoformat(req.new_date).date()
    except Exception as e:
        logger.warning(f"[reschedule_date_parse] Invalid date format '{req.new_date}': {e}")
        raise HTTPException(400, "Неверный формат даты")

    if req.new_time:
        try:
            parts = req.new_time.split(":")
            new_time = t(int(parts[0]), int(parts[1]))
        except Exception as e:
            logger.warning(f"[reschedule_time_parse] Invalid time format '{req.new_time}': {e}")
            raise HTTPException(400, "Неверный формат времени")
    else:
        # Keep original time
        orig = carousel.get("scheduled_at")
        if orig:
            orig_dt = dt.fromisoformat(orig.replace("Z", "+00:00")) if isinstance(orig, str) else orig
            new_time = orig_dt.time() if hasattr(orig_dt, 'time') else t(10, 0)
        else:
            new_time = t(10, 0)

    new_scheduled = dt.combine(new_date, new_time)

    # Update carousel scheduled_at
    db.table("carousels").update({
        "scheduled_at": new_scheduled.isoformat(),
    }).eq("id", carousel_id).execute()

    # Update or create publish_schedule
    try:
        # Try updating existing schedule (any non-final status)
        sch_result = (
            db.table("publish_schedules")
            .update({"scheduled_time": new_scheduled.isoformat()})
            .eq("carousel_id", carousel_id)
            .in_("status", ["pending", "scheduled", "review"])
            .execute()
        )
        # If no rows updated, check if schedule exists at all
        if not sch_result.data:
            # Try broader update (any status except published)
            sch_result2 = (
                db.table("publish_schedules")
                .update({"scheduled_time": new_scheduled.isoformat()})
                .eq("carousel_id", carousel_id)
                .neq("status", "published")
                .execute()
            )
            # If still nothing, create a new schedule entry
            if not sch_result2.data:
                # Find account_id from carousel or user's accounts
                accounts = db.table("instagram_accounts").select("id").eq("owner_id", user["id"]).limit(1).execute()
                if accounts.data:
                    db.table("publish_schedules").insert({
                        "carousel_id": carousel_id,
                        "account_id": accounts.data[0]["id"],
                        "scheduled_time": new_scheduled.isoformat(),
                        "status": "pending",
                    }).execute()
                    logger.info(f"[reschedule] Created new publish_schedule for carousel {carousel_id}")
    except Exception as e:
        logger.warning(f"[reschedule_publish_schedule] Failed to update publish_schedule for carousel {carousel_id}: {e}")

    return {
        "message": f"Перенесено на {new_date.strftime('%d.%m.%Y')} {new_time.strftime('%H:%M')}",
        "scheduled_at": new_scheduled.isoformat(),
    }


@router.delete("/{carousel_id}", status_code=204)
async def delete_carousel(
    carousel_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    db.table("carousels").delete().eq("id", carousel_id).execute()


def _get_color_scheme(scheme: str) -> dict:
    """Get color config for a named scheme. Pulls from DESIGN_TEMPLATES if available."""
    from app.services.generator.image import CARD_TEMPLATES

    # Check DESIGN_TEMPLATES first
    if scheme in DESIGN_TEMPLATES:
        t = DESIGN_TEMPLATES[scheme]
        return {
            "bg_color": t["bg"], "text_color": t["text"],
            "accent_color": t["accent"],
            "gradient_start": t.get("gradient_start", t["bg"]),
            "gradient_end": t.get("gradient_end", t["bg"]),
        }

    # Check CARD_TEMPLATES
    if scheme in CARD_TEMPLATES:
        t = CARD_TEMPLATES[scheme]
        return {
            "bg_color": t["bg"], "text_color": t["text"],
            "accent_color": t["accent"],
            "gradient_start": t["bg"], "gradient_end": t["bg"],
        }

    # Legacy fallback
    schemes = {
        "dark": {"bg_color": "#0f0f0f", "text_color": "#ffffff", "accent_color": "#ff6b35"},
        "light": {"bg_color": "#fafafa", "text_color": "#1a1a1a", "accent_color": "#e74c3c"},
    }
    return schemes.get(scheme, schemes["dark"])
