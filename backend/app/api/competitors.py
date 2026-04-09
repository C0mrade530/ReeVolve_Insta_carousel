"""
Competitor analysis API.
Three modes:
  1. Manual paste — user copies competitor post texts
  2. Auto-scrape — add @username, system fetches top posts via instagrapi
  3. AI ideas — GPT generates viral topic ideas from scratch

Flow: Add competitor → Scrape posts → Analyze → Select viral topic → Rewrite → Generate carousel
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Literal
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.utils.encryption import decrypt_data
from app.services.competitor.parser import (
    analyze_competitor_posts,
    rewrite_viral_post,
    generate_viral_ideas,
    extract_posts_from_text,
    analyze_viral_reels,
    rewrite_reel_to_carousel,
)
from app.services.competitor.scraper import InstagramScraper
from app.services.generator.pipeline import generate_topic_carousel_pipeline
from app.services.generator.expert_template import get_template_path

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════════

class AddCompetitorRequest(BaseModel):
    username: str = Field(..., pattern=r"^@?[a-zA-Z0-9._]{1,30}$")
    notes: str | None = Field(default=None, max_length=500)


class ScrapeCompetitorRequest(BaseModel):
    """Scrape a competitor's posts via instagrapi."""
    competitor_username: str = Field(..., pattern=r"^@?[a-zA-Z0-9._]{1,30}$")
    post_count: int = Field(default=30, ge=1, le=50)
    top_n: int = Field(default=10, ge=1, le=50)
    carousels_only: bool = False
    account_id: str | None = None


class AnalyzeRequest(BaseModel):
    posts_text: str
    competitor_username: str | None = None


FontStyleType = Literal["modern_clean", "luxury", "minimalist", "bold", "handwritten"]
ColorSchemeType = Literal["dark_luxury", "light_clean", "gradient_warm", "neon_dark", "corporate", "expert"]


class RewriteRequest(BaseModel):
    original_theme: str = Field(..., max_length=1000)
    why_viral: str = Field(..., max_length=1000)
    rewrite_angle: str = Field(..., max_length=1000)
    name: str = Field(default="Эксперт", max_length=100)
    city: str = Field(default="", max_length=100)
    niche: str = Field(default="", max_length=200)
    font_style: FontStyleType = "modern_clean"
    color_scheme: ColorSchemeType = "dark_luxury"
    generate_slides: bool = True


class ViralIdeasRequest(BaseModel):
    niche: str = Field(default="", max_length=200)
    city: str = Field(default="", max_length=100)
    count: int = Field(default=5, ge=1, le=20)


class ScrapeReelsRequest(BaseModel):
    """Scrape viral reels from a competitor."""
    competitor_username: str = Field(..., pattern=r"^@?[a-zA-Z0-9._]{1,30}$")
    reel_count: int = Field(default=30, ge=1, le=50)
    top_n: int = Field(default=10, ge=1, le=50)
    account_id: str | None = None


class ReelToCarouselRequest(BaseModel):
    """Generate carousel from a viral reel concept."""
    reel_theme: str = Field(..., max_length=1000)
    why_viral: str = Field(..., max_length=1000)
    carousel_adaptation: str = Field(..., max_length=1000)
    hook: str = Field(..., max_length=500)
    name: str = Field(default="Эксперт", max_length=100)
    city: str = Field(default="", max_length=100)
    niche: str = Field(default="", max_length=200)
    font_style: FontStyleType = "modern_clean"
    color_scheme: ColorSchemeType = "dark_luxury"
    generate_slides: bool = True


# ═══════════════════════════════════════════════════════════════════
# COMPETITOR MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

@router.post("/add")
async def add_competitor(
    req: AddCompetitorRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Add competitor account for tracking."""
    username = req.username.lstrip("@").strip()
    if not username:
        raise HTTPException(400, "Укажите username конкурента")

    try:
        # Check if already exists
        existing = db.table("competitor_accounts").select("id").eq(
            "owner_id", user["id"]
        ).eq("username", username).execute()

        if existing.data:
            return {"message": f"@{username} уже добавлен", "id": existing.data[0]["id"], "exists": True}

        result = db.table("competitor_accounts").insert({
            "owner_id": user["id"],
            "username": username,
            "platform": "instagram",
            "notes": req.notes,
        }).execute()
        return {
            "message": f"Конкурент @{username} добавлен",
            "id": result.data[0]["id"],
            "exists": False,
        }
    except Exception as e:
        logger.warning(f"DB insert failed (table may not exist): {e}")
        return {"message": f"@{username} записан", "id": None}


@router.get("/list")
async def list_competitors(
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """List saved competitor accounts."""
    try:
        result = (
            db.table("competitor_accounts")
            .select("*")
            .eq("owner_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.warning(f"[list_competitors] {e}")
        return []


@router.delete("/{competitor_id}")
async def remove_competitor(
    competitor_id: str,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Remove a saved competitor."""
    try:
        db.table("competitor_accounts").delete().eq(
            "id", competitor_id
        ).eq("owner_id", user["id"]).execute()
        return {"message": "Удалён"}
    except Exception as e:
        logger.warning(f"[remove_competitor] {e}")
        return {"message": "OK"}


# ═══════════════════════════════════════════════════════════════════
# AUTO-SCRAPE — fetch posts from Instagram
# ═══════════════════════════════════════════════════════════════════

@router.post("/scrape")
async def scrape_competitor(
    req: ScrapeCompetitorRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Scrape competitor's Instagram posts using user's IG account session.
    Returns top posts sorted by engagement + auto-analyzes with GPT.
    """
    username = req.competitor_username.lstrip("@").strip()
    if not username:
        raise HTTPException(400, "Укажите username конкурента")

    # Get user's Instagram account for login
    try:
        if req.account_id:
            account_result = (
                db.table("instagram_accounts")
                .select("username, session_data, proxy")
                .eq("id", req.account_id)
                .eq("owner_id", user["id"])
                .limit(1)
                .execute()
            )
            if not account_result.data:
                raise HTTPException(400, "Аккаунт не найден. Возможно он был удалён — выберите другой аккаунт в шапке.")
        else:
            account_result = (
                db.table("instagram_accounts")
                .select("username, session_data, proxy")
                .eq("owner_id", user["id"])
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            if not account_result.data:
                raise HTTPException(400, "Нет активных Instagram аккаунтов. Добавьте аккаунт в разделе 'Аккаунты'.")

        accounts_list = account_result.data if isinstance(account_result.data, list) else [account_result.data]
        ig_account = accounts_list[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get IG account: {e}")
        raise HTTPException(400, "Не удалось получить аккаунт Instagram. Добавьте аккаунт в разделе 'Аккаунты'.")

    # Decrypt session data
    try:
        raw_session = ig_account.get("session_data", "")
        if not raw_session:
            logger.error(f"[Competitors] No session_data in account @{ig_account.get('username', '?')}")
            raise HTTPException(400, "Сессия аккаунта пуста. Переавторизуйтесь в разделе 'Аккаунты'.")
        session_data = decrypt_data(raw_session)
        logger.info(f"[Competitors] Decrypted session for @{ig_account.get('username', '?')}: type={type(session_data).__name__}, keys={list(session_data.keys())[:5] if isinstance(session_data, dict) else 'N/A'}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Competitors] Failed to decrypt session: {e}")
        raise HTTPException(400, "Сессия повреждена. Переавторизуйтесь в разделе 'Аккаунты'.")

    # Init scraper
    scraper = InstagramScraper()

    # Try session login
    logged_in = False
    if session_data:
        logged_in = await scraper.login_by_session(
            session_data, proxy=ig_account.get("proxy")
        )
        logger.info(f"[Competitors] Scraper login result: {logged_in}")

    if not logged_in:
        raise HTTPException(
            401,
            "Сессия Instagram истекла. Переавторизуйтесь в разделе 'Аккаунты'."
        )

    # Fetch user info
    competitor_info = await scraper.get_user_info(username)

    # Check if session became invalid during the call
    if not scraper._logged_in:
        raise HTTPException(
            401,
            "Сессия Instagram истекла при запросе данных. Переавторизуйтесь в разделе 'Аккаунты'."
        )

    # Fetch top posts
    top_posts = await scraper.get_top_posts(
        username,
        count=req.post_count,
        top_n=req.top_n,
        sort_by="engagement",
        carousels_only=req.carousels_only,
    )

    # Check again after fetching posts
    if not scraper._logged_in:
        raise HTTPException(
            401,
            "Сессия Instagram истекла при запросе данных. Переавторизуйтесь в разделе 'Аккаунты'."
        )

    if not top_posts:
        raise HTTPException(404, f"Не удалось получить посты @{username}. Аккаунт может быть закрытым.")

    # Format for GPT analysis
    posts_text = await scraper.get_post_captions_text(
        username,
        count=req.post_count,
        top_n=req.top_n,
        carousels_only=req.carousels_only,
    )

    # Auto-analyze with GPT
    analysis = await analyze_competitor_posts(posts_text)

    # Update competitor record with scrape data
    try:
        db.table("competitor_accounts").update({
            "last_scraped_at": "now()",
            "followers": competitor_info.get("followers") if competitor_info else None,
            "bio": competitor_info.get("biography") if competitor_info else None,
            "posts_count": competitor_info.get("media_count") if competitor_info else None,
        }).eq("owner_id", user["id"]).eq("username", username).execute()
    except Exception as e:
        logger.warning(f"[scrape_competitor] update competitor record: {e}")

    return {
        "competitor": competitor_info,
        "posts": top_posts,
        "posts_found": len(top_posts),
        "viral_topics": analysis.get("viral_topics", []),
        "niche_insights": analysis.get("niche_insights", ""),
        "message": f"Спарсено {len(top_posts)} постов @{username}, найдено {len(analysis.get('viral_topics', []))} виральных тем",
    }


# ═══════════════════════════════════════════════════════════════════
# MANUAL ANALYZE — paste text
# ═══════════════════════════════════════════════════════════════════

@router.post("/analyze")
async def analyze_posts(
    req: AnalyzeRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Analyze pasted competitor posts, find viral angles."""
    if not req.posts_text.strip():
        raise HTTPException(400, "Вставьте текст постов конкурента")

    if len(req.posts_text) > 15000:
        raise HTTPException(400, "Слишком много текста (макс. 15000 символов)")

    try:
        posts = extract_posts_from_text(req.posts_text)
        analysis = await analyze_competitor_posts(req.posts_text)

        try:
            db.table("competitor_analyses").insert({
                "owner_id": user["id"],
                "competitor_username": req.competitor_username,
                "posts_count": len(posts),
                "analysis": analysis,
            }).execute()
        except Exception as e:
            logger.warning(f"[analyze_posts] save analysis: {e}")

        return {
            "posts_found": len(posts),
            "viral_topics": analysis.get("viral_topics", []),
            "niche_insights": analysis.get("niche_insights", ""),
            "message": f"Найдено {len(posts)} постов, выделено {len(analysis.get('viral_topics', []))} виральных тем",
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка анализа: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# REWRITE + GENERATE CAROUSEL
# ═══════════════════════════════════════════════════════════════════

@router.post("/rewrite")
async def rewrite_post(
    req: RewriteRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Rewrite a viral topic and optionally generate carousel slides."""
    try:
        content = await rewrite_viral_post(
            original_theme=req.original_theme,
            why_viral=req.why_viral,
            rewrite_angle=req.rewrite_angle,
            name=req.name,
            city=req.city,
            niche=req.niche,
        )

        if not req.generate_slides:
            return {
                "status": "text_ready",
                "content": content,
                "message": "Текст готов!",
            }

        # Generate slides
        carousel_data = {
            "type": "topic",
            "status": "generating",
            "owner_id": user["id"],
            "generation_params": {
                "source": "competitor_rewrite",
                "original_theme": req.original_theme,
                "font_style": req.font_style,
                "color_scheme": req.color_scheme,
            },
        }

        try:
            result = db.table("carousels").insert(carousel_data).execute()
        except Exception as e:
            logger.warning(f"[rewrite_post] carousel insert fallback: {e}")
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
        }

        expert_tmpl_path = get_template_path(user["id"])

        updated = await generate_topic_carousel_pipeline(
            carousel_id=carousel_id,
            account=virtual_account,
            topic_hint=None,
            font_style=req.font_style,
            color_scheme=req.color_scheme,
            expert_template_path=expert_tmpl_path,
            pre_generated_content=content,
        )

        return {
            "carousel_id": carousel_id,
            "status": "ready",
            "slides": updated.get("slides", []),
            "caption": updated.get("caption", ""),
            "hashtags": updated.get("hashtags", ""),
            "quality_score": updated.get("generation_params", {}).get("content", {}).get("_meta", {}).get("final_score", 0),
            "source": "competitor_rewrite",
            "message": "Карусель из виральной темы готова!",
        }

    except Exception as e:
        logger.error(f"Rewrite failed: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка рерайта: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# VIRAL IDEAS (AI generated)
# ═══════════════════════════════════════════════════════════════════

@router.post("/viral-ideas")
async def get_viral_ideas(
    req: ViralIdeasRequest,
    user: dict = Depends(get_current_user),
):
    try:
        ideas = await generate_viral_ideas(niche=req.niche, city=req.city, count=req.count)
        return {
            "viral_topics": ideas.get("viral_topics", []),
            "niche_insights": ideas.get("niche_insights", ""),
            "message": f"Сгенерировано {len(ideas.get('viral_topics', []))} идей",
        }
    except Exception as e:
        logger.error(f"Viral ideas failed: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка генерации идей: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# VIRAL REELS ANALYSIS → CAROUSEL GENERATION
# ═══════════════════════════════════════════════════════════════════

@router.post("/scrape-reels")
async def scrape_viral_reels(
    req: ScrapeReelsRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Scrape competitor's viral Reels, analyze them with AI,
    and generate carousel ideas based on what's working.
    """
    username = req.competitor_username.lstrip("@").strip()
    if not username:
        raise HTTPException(400, "Укажите username конкурента")

    # Get user's IG account for session
    try:
        if req.account_id:
            account_result = (
                db.table("instagram_accounts")
                .select("username, session_data, proxy")
                .eq("id", req.account_id)
                .eq("owner_id", user["id"])
                .limit(1)
                .execute()
            )
            if not account_result.data:
                raise HTTPException(400, "Аккаунт не найден")
        else:
            account_result = (
                db.table("instagram_accounts")
                .select("username, session_data, proxy")
                .eq("owner_id", user["id"])
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            if not account_result.data:
                raise HTTPException(400, "Нет активных Instagram аккаунтов")

        ig_account = account_result.data[0] if isinstance(account_result.data, list) else account_result.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get IG account: {e}")
        raise HTTPException(400, "Не удалось получить аккаунт Instagram")

    # Decrypt session
    try:
        raw_session = ig_account.get("session_data", "")
        if not raw_session:
            raise HTTPException(400, "Сессия аккаунта пуста. Переавторизуйтесь.")
        session_data = decrypt_data(raw_session)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Competitors] Failed to decrypt session: {e}")
        raise HTTPException(400, "Сессия повреждена. Переавторизуйтесь.")

    # Init scraper and login
    scraper = InstagramScraper()
    logged_in = False
    if session_data:
        logged_in = await scraper.login_by_session(session_data, proxy=ig_account.get("proxy"))

    if not logged_in:
        raise HTTPException(401, "Сессия Instagram истекла. Переавторизуйтесь.")

    # Get user info
    competitor_info = await scraper.get_user_info(username)
    if not scraper._logged_in:
        raise HTTPException(401, "Сессия истекла при запросе данных.")

    # Fetch top viral reels
    top_reels = await scraper.get_top_reels(username, count=req.reel_count, top_n=req.top_n)

    if not scraper._logged_in:
        raise HTTPException(401, "Сессия истекла при получении Reels.")

    if not top_reels:
        raise HTTPException(404, f"Не удалось получить Reels @{username}. Аккаунт может быть закрытым или не иметь Reels.")

    # Get text for AI analysis
    reels_text = await scraper.get_reels_analysis_text(username, count=req.reel_count, top_n=req.top_n)

    # AI analysis: extract carousel ideas from viral reels
    analysis = await analyze_viral_reels(reels_text)

    # Update competitor record
    try:
        db.table("competitor_accounts").update({
            "last_scraped_at": "now()",
            "followers": competitor_info.get("followers") if competitor_info else None,
        }).eq("owner_id", user["id"]).eq("username", username).execute()
    except Exception as e:
        logger.warning(f"[scrape_viral_reels] update competitor record: {e}")

    return {
        "competitor": competitor_info,
        "reels": top_reels,
        "reels_found": len(top_reels),
        "carousel_ideas": analysis.get("viral_reels_analysis", []),
        "reels_insights": analysis.get("reels_insights", ""),
        "trending_formats": analysis.get("trending_formats", []),
        "message": f"Спарсено {len(top_reels)} Reels @{username}, извлечено {len(analysis.get('viral_reels_analysis', []))} идей для каруселей",
    }


@router.post("/reel-to-carousel")
async def generate_carousel_from_reel(
    req: ReelToCarouselRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Generate a full carousel from a viral reel concept.
    AI rewrites the reel theme into carousel format, then renders slides.
    """
    try:
        # Step 1: AI rewrite reel → carousel content
        content = await rewrite_reel_to_carousel(
            reel_theme=req.reel_theme,
            why_viral=req.why_viral,
            carousel_adaptation=req.carousel_adaptation,
            hook=req.hook,
            name=req.name,
            city=req.city,
            niche=req.niche,
        )

        if not req.generate_slides:
            return {
                "status": "text_ready",
                "content": content,
                "message": "Текст карусели из Reels готов!",
            }

        # Step 2: Create carousel in DB
        carousel_data = {
            "type": "topic",
            "status": "generating",
            "owner_id": user["id"],
            "generation_params": {
                "source": "reel_to_carousel",
                "original_reel_theme": req.reel_theme,
                "font_style": req.font_style,
                "color_scheme": req.color_scheme,
            },
        }

        try:
            result = db.table("carousels").insert(carousel_data).execute()
        except Exception as e:
            logger.warning(f"[reel_to_carousel] carousel insert fallback: {e}")
            accounts = db.table("instagram_accounts").select("id").eq("owner_id", user["id"]).limit(1).execute()
            if accounts.data:
                carousel_data["account_id"] = accounts.data[0]["id"]
            carousel_data.pop("owner_id", None)
            result = db.table("carousels").insert(carousel_data).execute()

        carousel_id = result.data[0]["id"]

        # Step 3: Generate slides
        virtual_account = {
            "username": req.name,
            "city": req.city,
            "niche": req.niche,
            "brand_style": _get_color_scheme(req.color_scheme),
        }

        expert_tmpl_path = get_template_path(user["id"])

        updated = await generate_topic_carousel_pipeline(
            carousel_id=carousel_id,
            account=virtual_account,
            topic_hint=None,
            font_style=req.font_style,
            color_scheme=req.color_scheme,
            expert_template_path=expert_tmpl_path,
            pre_generated_content=content,
        )

        return {
            "carousel_id": carousel_id,
            "status": "ready",
            "slides": updated.get("slides", []),
            "caption": updated.get("caption", ""),
            "hashtags": updated.get("hashtags", ""),
            "quality_score": updated.get("generation_params", {}).get("content", {}).get("_meta", {}).get("final_score", 0),
            "source": "reel_to_carousel",
            "message": "Карусель из залетевшего Reels готова!",
        }

    except Exception as e:
        logger.error(f"Reel to carousel failed: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка генерации из Reels: {str(e)}")


def _get_color_scheme(scheme: str) -> dict:
    schemes = {
        "dark": {"bg_color": "#0f0f0f", "text_color": "#ffffff", "accent_color": "#ff6b35"},
        "dark_luxury": {"bg_color": "#0f0f0f", "text_color": "#ffffff", "accent_color": "#ff6b35"},
        "light": {"bg_color": "#fafafa", "text_color": "#1a1a1a", "accent_color": "#e74c3c"},
        "light_clean": {"bg_color": "#fafafa", "text_color": "#1a1a1a", "accent_color": "#3498db"},
        "gradient": {"bg_color": "#1a1a2e", "text_color": "#ffffff", "accent_color": "#e94560"},
        "gradient_warm": {"bg_color": "#1a1a2e", "text_color": "#ffffff", "accent_color": "#e94560"},
        "neon_dark": {"bg_color": "#0a0a0a", "text_color": "#ffffff", "accent_color": "#00ff88"},
        "corporate": {"bg_color": "#1c2433", "text_color": "#ffffff", "accent_color": "#4a90d9"},
    }
    return schemes.get(scheme, schemes["dark_luxury"])
