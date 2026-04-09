"""
Full carousel generation pipeline.
Multi-step: GPT Draft → Evaluate → Refine → Pillow slides → save to disk → update DB.
CPU-bound image rendering runs in thread pool to avoid blocking the event loop.
"""
import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime

from app.config import get_settings
from app.services.generator.content import generate_topic_content, generate_property_content, ProgressCallback
from app.services.generator.image import (
    generate_topic_slide, generate_property_slide,
    generate_property_carousel_slide, CARD_TEMPLATES,
)
from app.services.generator.expert_template import get_photo_path, get_template_path
from app.services.generator.ai_image import generate_ai_background, build_bg_prompt
from app.database import get_supabase_admin

logger = logging.getLogger(__name__)
settings = get_settings()


def _ensure_media_dir() -> str:
    """Ensure media directory exists and return absolute path."""
    media_dir = str(Path(settings.media_storage_path).resolve())
    os.makedirs(media_dir, exist_ok=True)
    return media_dir


def _save_slide(image_bytes: bytes, carousel_id: str, slide_number: int) -> str:
    """Save slide image to disk, return relative path."""
    media_dir = _ensure_media_dir()
    carousel_dir = os.path.join(media_dir, "carousels", carousel_id)
    os.makedirs(carousel_dir, exist_ok=True)

    filename = f"slide_{slide_number}.png"
    filepath = os.path.join(carousel_dir, filename)

    with open(filepath, "wb") as f:
        f.write(image_bytes)

    return f"/media/carousels/{carousel_id}/{filename}"


async def generate_topic_carousel_pipeline(
    carousel_id: str,
    account: dict,
    topic_hint: str | None = None,
    font_style: str = "luxury",
    color_scheme: str = "expert",
    expert_template_path: str | None = None,
    pre_generated_content: dict | None = None,
    on_progress: ProgressCallback = None,
    used_topics: list[str] | None = None,
) -> dict:
    """
    Full pipeline:
    1. GPT generates text (multi-step with self-evaluation) — or use pre_generated_content
    2. Pillow generates 8 slides with chosen design
    3. Save to disk and DB
    """
    db = get_supabase_admin()
    username = account.get("username", "Эксперт")
    style = account.get("brand_style") or {}
    speaker_photo = account.get("speaker_photo_url")
    account_id = account.get("id", "")

    # For expert template: auto-resolve photo and template paths from expert_templates dir
    if color_scheme == "expert" and account_id:
        expert_photo = get_photo_path(account_id)
        if expert_photo:
            speaker_photo = expert_photo  # Use bg-removed photo
        if not expert_template_path:
            expert_template_path = get_template_path(account_id)

    # Load brand_profile if account has one linked
    brand_profile = None
    brand_profile_id = account.get("brand_profile_id")
    if brand_profile_id:
        try:
            bp_result = db.table("brand_profiles").select("*").eq(
                "id", brand_profile_id
            ).eq("status", "ready").limit(1).execute()
            if bp_result.data:
                brand_profile = bp_result.data[0]
                logger.info(f"[Pipeline] Loaded brand_profile: niche='{brand_profile.get('niche', '')}'")
        except Exception as e:
            logger.warning(f"[Pipeline] Failed to load brand_profile: {e}")

    # 1. Generate text content via CometAPI (multi-step) — or use pre-generated
    if pre_generated_content:
        logger.info(f"[Pipeline] Using pre-generated content for carousel {carousel_id}")
        content = pre_generated_content
    else:
        logger.info(f"[Pipeline] Generating topic text for carousel {carousel_id}")
        logger.info(f"[Pipeline] Font: {font_style}, Colors: {color_scheme}")
        try:
            # Use brand_profile niche/city if available, fallback to account defaults
            effective_niche = (brand_profile or {}).get("niche") or account.get("niche") or ""
            effective_city = account.get("city") or ""

            content = await generate_topic_content(
                name=username,
                city=effective_city,
                niche=effective_niche,
                topic_hint=topic_hint or "",
                on_progress=on_progress,
                used_topics=used_topics,
                brand_profile=brand_profile,
            )
        except Exception as e:
            logger.error(f"[Pipeline] GPT error: {e}", exc_info=True)
            db.table("carousels").update({
                "status": "failed",
                "generation_params": {"error": str(e)},
            }).eq("id", carousel_id).execute()
            raise

    # Extract _meta for quality info
    meta = content.pop("_meta", {})
    logger.info(f"[Pipeline] Text quality: score={meta.get('final_score', '?')}, "
                f"rounds={meta.get('generation_rounds', '?')}")

    hook_title = content.get("hook_title", "Заголовок")
    points = content.get("points", [])
    cta_text = content.get("cta_text", "Подпишись!")
    caption = content.get("caption", "")

    # Append lead_magnet to caption (same text as last slide)
    lead_magnet = account.get("lead_magnet", "") or account.get("bio_offer", "")
    if lead_magnet and lead_magnet.strip():
        caption = f"{caption}\n\n{lead_magnet.strip()}" if caption else lead_magnet.strip()

    # Dynamic slide count: AI decides 5-9 slides (3-7 content points)
    ai_slide_count = content.get("slide_count")
    if ai_slide_count and isinstance(ai_slide_count, int):
        # AI returned a slide count — use it (clamp to 5-9)
        total_slides = max(5, min(9, ai_slide_count))
        num_content = total_slides - 2  # minus cover and CTA
    else:
        num_content = 5  # default
        total_slides = 7

    # Pad or trim points to match
    while len(points) < num_content:
        points.append({"title": f"Пункт {len(points)+1}", "body": "..."})
    points = points[:num_content]

    logger.info(f"[Pipeline] Slide count: {total_slides} (AI requested: {ai_slide_count})")

    # Get accent_color and design-specific params
    accent_color = account.get("accent_color") or None
    avatar_path = account.get("avatar_path") or None
    niche_for_bg = (brand_profile or {}).get("niche") or account.get("niche") or ""

    # 2. Generate AI backgrounds in parallel if using ai_design template
    ai_backgrounds = [None] * total_slides
    if color_scheme == "ai_design":
        if on_progress:
            on_progress("ai_backgrounds", 3, 5)
        logger.info(f"[Pipeline] Generating {total_slides} AI backgrounds via NanoBanana...")

        # Build prompts for each slide
        bg_tasks = []
        for i in range(1, total_slides + 1):
            if i == 1:
                slide_title = hook_title
                slide_body = ""
            elif i == total_slides:
                slide_title = account.get("cta_final", "").strip() or cta_text
                slide_body = ""
            else:
                pt = points[i - 2]
                slide_title = pt.get("title", "")
                slide_body = pt.get("body", "")

            prompt = build_bg_prompt(slide_title, slide_body, niche_for_bg)
            bg_tasks.append(generate_ai_background(prompt))

        # Run all NanoBanana requests in parallel
        bg_results = await asyncio.gather(*bg_tasks, return_exceptions=True)
        for idx, result in enumerate(bg_results):
            if isinstance(result, bytes):
                ai_backgrounds[idx] = result
            else:
                if isinstance(result, Exception):
                    logger.warning(f"[Pipeline] AI bg {idx+1} failed: {result}")
                ai_backgrounds[idx] = None

        ok_count = sum(1 for bg in ai_backgrounds if bg is not None)
        logger.info(f"[Pipeline] AI backgrounds ready: {ok_count}/{total_slides}")

    # 3. Generate slide images
    if on_progress:
        on_progress("slides_render", 4, 5)
    logger.info(f"[Pipeline] Generating {total_slides} slides (font={font_style}, template={color_scheme})")
    slides_data = []

    for i in range(1, total_slides + 1):
        if i == 1:
            title = hook_title
            body_text = ""
        elif i == total_slides:
            title = account.get("cta_final", "").strip() or cta_text
            body_text = account.get("lead_magnet", "") or account.get("bio_offer", "")
        else:
            point = points[i - 2]
            title = point.get("title", "")
            body_text = point.get("body", "")

        # Run CPU-bound Pillow rendering in thread pool
        image_bytes = await asyncio.to_thread(
            generate_topic_slide,
            slide_number=i,
            total_slides=total_slides,
            title=title,
            body=body_text,
            username=username,
            style=style,
            font_style=font_style,
            design_template=color_scheme,
            speaker_photo_path=speaker_photo,
            expert_template_path=expert_template_path,
            ai_background_bytes=ai_backgrounds[i - 1] if ai_backgrounds else None,
            accent_color=accent_color,
            avatar_path=avatar_path,
        )

        image_path = await asyncio.to_thread(_save_slide, image_bytes, carousel_id, i)

        slides_data.append({
            "slide_number": i,
            "image_path": image_path,
            "text_overlay": title,
            "body": body_text,
        })

    # 3. Update carousel in DB
    update_data = {
        "status": "ready",
        "slides": slides_data,
        "caption": caption,
        "hashtags": _extract_hashtags(caption),
        "generated_at": datetime.utcnow().isoformat(),
        "generation_params": {
            "content": {**content, "_meta": meta},
            "model": settings.openai_model,
            "font_style": font_style,
            "color_scheme": color_scheme,
        },
    }

    result = db.table("carousels").update(update_data).eq("id", carousel_id).execute()
    if on_progress:
        on_progress("done", 5, 5)
    logger.info(f"[Pipeline] Carousel {carousel_id} ready with {total_slides} slides")

    return result.data[0] if result.data else update_data


async def generate_property_carousel_pipeline(
    carousel_id: str,
    account: dict,
    listing: dict,
    font_style: str = "luxury",
    on_progress: ProgressCallback = None,
) -> dict:
    """
    Full pipeline for property carousel (6 slides).
    1. Hook — listing photo[0], hook_title + hook_subtitle
    2. Anti — listing photo[1] (or [0] fallback), anti slide content
    3. Location — listing photo[2] (or [0] fallback), location slide content
    4. Neighborhood — listing photo[3] (or [0] fallback), neighborhood slide content
    5. Features — listing photo[4] (or [0] fallback), features slide content
    6. Conditions — no photo (dark bg), conditions dict + cta_text
    """
    db = get_supabase_admin()

    # 1. Fetch listing and progress
    if on_progress:
        on_progress("fetch_listing", 1, 6)
    logger.info(f"[Pipeline] Generating property carousel text for {carousel_id}")

    # 2. Generate text via generate_property_content (multi-step with progress)
    try:
        content = await generate_property_content(listing, on_progress=on_progress)
    except Exception as e:
        logger.error(f"[Pipeline] GPT error: {e}", exc_info=True)
        db.table("carousels").update({
            "status": "failed",
            "generation_params": {"error": str(e)},
        }).eq("id", carousel_id).execute()
        raise

    meta = content.pop("_meta", {})
    logger.info(f"[Pipeline] Text quality: score={meta.get('final_score', '?')}, "
                f"rounds={meta.get('generation_rounds', '?')}")

    total_slides = 6
    slides_data = []

    # Get listing photos and resolve paths
    photo_paths = listing.get("photos", [])
    _photo_use_count: dict[int, int] = {}  # tracks how many times each photo index is used

    def _resolve_photo(index: int) -> tuple[str, int]:
        """
        Get photo path with fallback to first photo.
        Returns (path, crop_variant) — crop_variant differs when a photo is reused
        so the same image produces visually distinct crops on different slides.
        """
        actual_idx = index if index < len(photo_paths) else 0
        if not photo_paths:
            return "", 0

        photo_rel = photo_paths[actual_idx]

        # Track reuse → vary crop
        variant = _photo_use_count.get(actual_idx, 0)
        _photo_use_count[actual_idx] = variant + 1

        if not photo_rel:
            return "", variant

        # Resolve to filesystem path
        media_root = str(Path(settings.media_storage_path).resolve())
        if photo_rel.startswith("/media/"):
            photo_file = photo_rel[len("/media/"):]
            return os.path.join(media_root, photo_file), variant
        elif photo_rel.startswith("http"):
            return photo_rel, variant
        else:
            return os.path.join(media_root, photo_rel), variant

    # 3. Render slides
    if on_progress:
        on_progress("slides_render", 4, 6)
    logger.info(f"[Pipeline] Generating {total_slides} slides (font={font_style})")

    # Slide definitions: (index, photo_idx, slide_type, content_key_offset)
    slides = content.get("slides", [])

    def _get_slide(offset: int) -> dict:
        return slides[offset] if offset < len(slides) else {}

    # Slide 1: Hook
    hook_photo, hook_cv = _resolve_photo(0)
    img1 = await asyncio.to_thread(
        generate_property_carousel_slide,
        slide_number=1,
        total_slides=total_slides,
        photo_path=hook_photo,
        title=content.get("hook_title", ""),
        body=content.get("hook_subtitle", ""),
        slide_type="hook",
        font_style=font_style,
        crop_variant=hook_cv,
    )
    path1 = await asyncio.to_thread(_save_slide, img1, carousel_id, 1)
    slides_data.append({
        "slide_number": 1, "image_path": path1,
        "text_overlay": content.get("hook_title", ""),
        "body": content.get("hook_subtitle", ""),
        "type": "hook",
    })

    # Slide 2: Anti
    anti_photo, anti_cv = _resolve_photo(1)
    anti_slide = _get_slide(0)
    img2 = await asyncio.to_thread(
        generate_property_carousel_slide,
        slide_number=2,
        total_slides=total_slides,
        photo_path=anti_photo,
        title=anti_slide.get("title", ""),
        body=anti_slide.get("body", ""),
        slide_type="anti",
        font_style=font_style,
        crop_variant=anti_cv,
    )
    path2 = await asyncio.to_thread(_save_slide, img2, carousel_id, 2)
    slides_data.append({
        "slide_number": 2, "image_path": path2,
        "text_overlay": anti_slide.get("title", ""),
        "body": anti_slide.get("body", ""),
        "type": "anti",
    })

    # Slide 3: Location
    location_photo, location_cv = _resolve_photo(2)
    location_slide = _get_slide(1)
    img3 = await asyncio.to_thread(
        generate_property_carousel_slide,
        slide_number=3,
        total_slides=total_slides,
        photo_path=location_photo,
        title=location_slide.get("title", "Локация"),
        body=location_slide.get("body", ""),
        slide_type="location",
        font_style=font_style,
        crop_variant=location_cv,
    )
    path3 = await asyncio.to_thread(_save_slide, img3, carousel_id, 3)
    slides_data.append({
        "slide_number": 3, "image_path": path3,
        "text_overlay": location_slide.get("title", ""),
        "body": location_slide.get("body", ""),
        "type": "location",
    })

    # Slide 4: Neighborhood
    neighborhood_photo, neighborhood_cv = _resolve_photo(3)
    neighborhood_slide = _get_slide(2)
    img4 = await asyncio.to_thread(
        generate_property_carousel_slide,
        slide_number=4,
        total_slides=total_slides,
        photo_path=neighborhood_photo,
        title=neighborhood_slide.get("title", "Окрестности"),
        body=neighborhood_slide.get("body", ""),
        slide_type="neighborhood",
        font_style=font_style,
        crop_variant=neighborhood_cv,
    )
    path4 = await asyncio.to_thread(_save_slide, img4, carousel_id, 4)
    slides_data.append({
        "slide_number": 4, "image_path": path4,
        "text_overlay": neighborhood_slide.get("title", ""),
        "body": neighborhood_slide.get("body", ""),
        "type": "neighborhood",
    })

    # Slide 5: Features
    features_photo, features_cv = _resolve_photo(4)
    features_slide = _get_slide(3)
    img5 = await asyncio.to_thread(
        generate_property_carousel_slide,
        slide_number=5,
        total_slides=total_slides,
        photo_path=features_photo,
        title=features_slide.get("title", "Особенности"),
        body=features_slide.get("body", ""),
        slide_type="features",
        font_style=font_style,
        crop_variant=features_cv,
    )
    path5 = await asyncio.to_thread(_save_slide, img5, carousel_id, 5)
    slides_data.append({
        "slide_number": 5, "image_path": path5,
        "text_overlay": features_slide.get("title", ""),
        "body": features_slide.get("body", ""),
        "type": "features",
    })

    # Slide 6: Conditions (no photo, dark background)
    conditions = content.get("conditions", {})
    cta_text = content.get("cta_text", "Пишите в комментариях")
    img6 = await asyncio.to_thread(
        generate_property_carousel_slide,
        slide_number=6,
        total_slides=total_slides,
        photo_path="",  # No photo for conditions slide
        title="Условия",
        body="",
        slide_type="conditions",
        conditions=conditions,
        cta_text=cta_text,
        font_style=font_style,
    )
    path6 = await asyncio.to_thread(_save_slide, img6, carousel_id, 6)
    slides_data.append({
        "slide_number": 6, "image_path": path6,
        "text_overlay": "Условия",
        "body": cta_text,
        "type": "conditions",
    })

    # 4. Update carousel in DB
    caption = content.get("caption", "")

    # Append lead_magnet to caption (same text as last slide)
    lead_magnet = account.get("lead_magnet", "") or account.get("bio_offer", "")
    if lead_magnet and lead_magnet.strip():
        caption = f"{caption}\n\n{lead_magnet.strip()}" if caption else lead_magnet.strip()

    update_data = {
        "status": "ready",
        "slides": slides_data,
        "caption": caption,
        "hashtags": _extract_hashtags(caption),
        "generated_at": datetime.utcnow().isoformat(),
        "generation_params": {
            "content": {**content, "_meta": meta},
            "model": settings.openai_model,
            "font_style": font_style,
        },
    }

    result = db.table("carousels").update(update_data).eq("id", carousel_id).execute()

    # Mark listing as carousel_generated
    try:
        db.table("property_listings").update(
            {"carousel_generated": True}
        ).eq("id", listing["id"]).execute()
    except Exception as e:
        logger.warning(f"[Pipeline] Failed to mark listing as carousel_generated: {e}")

    if on_progress:
        on_progress("done", 6, 6)
    logger.info(f"[Pipeline] Carousel {carousel_id} ready with {total_slides} slides")

    return result.data[0] if result.data else update_data


def _extract_hashtags(caption: str) -> str:
    """Extract hashtags from caption text."""
    if not caption:
        return ""
    words = caption.split()
    tags = [w for w in words if w.startswith("#")]
    return " ".join(tags)
