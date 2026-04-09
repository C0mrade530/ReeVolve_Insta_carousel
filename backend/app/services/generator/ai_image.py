"""
NanoBanana API integration for AI-generated slide backgrounds.

Uses the async polling pattern:
1. POST /generate with prompt → get taskId
2. Poll /record-info?taskId=xxx until done
3. Download generated image

Shared polling/extraction logic reused from expert_template.py.
"""

import os
import hashlib
import logging
import asyncio
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)

# NanoBanana API endpoints (same as expert_template.py)
NANOBANANA_GENERATE_URL = "https://api.nanobananaapi.ai/api/v1/nanobanana/generate"
NANOBANANA_STATUS_URL = "https://api.nanobananaapi.ai/api/v1/nanobanana/record-info"

# Polling config
POLL_INTERVAL = 3
POLL_MAX_ATTEMPTS = 60  # 3s * 60 = 3 min max


def _get_cache_dir() -> str:
    """Get cache directory for AI backgrounds."""
    settings = get_settings()
    cache_dir = os.path.join(
        str(Path(settings.media_storage_path).resolve()),
        "ai_backgrounds",
    )
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _prompt_hash(prompt: str) -> str:
    """MD5 hash of prompt for caching."""
    return hashlib.md5(prompt.encode("utf-8")).hexdigest()


async def _poll_task_result(
    client: httpx.AsyncClient, task_id: str, headers: dict
) -> dict | None:
    """Poll NanoBanana /record-info until task completes or fails."""
    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        await asyncio.sleep(POLL_INTERVAL)
        try:
            resp = await client.get(
                NANOBANANA_STATUS_URL,
                params={"taskId": task_id},
                headers=headers,
            )
            if resp.status_code != 200:
                logger.warning(
                    f"NanoBanana bg poll {attempt}: HTTP {resp.status_code}"
                )
                continue

            data = resp.json()
            result_data = data.get("data", {})

            # Extract status from various response formats
            status = None
            if isinstance(result_data, dict):
                status = result_data.get("status", "").lower()
            elif isinstance(result_data, list) and result_data:
                if isinstance(result_data[0], dict):
                    status = result_data[0].get("status", "").lower()
            if not status:
                status = str(data.get("status", "")).lower()

            if status in ("complete", "completed", "success", "done"):
                logger.info(f"NanoBanana bg task {task_id} completed")
                return data
            elif status in ("failed", "error", "cancelled"):
                logger.error(f"NanoBanana bg task {task_id} failed: {data}")
                return None

        except Exception as e:
            logger.warning(f"NanoBanana bg poll {attempt} error: {e}")

    logger.error(f"NanoBanana bg task {task_id} timed out")
    return None


def _extract_image_url(data: dict) -> str | None:
    """Extract image URL from NanoBanana response (various formats)."""
    result_data = data.get("data", {})

    if isinstance(result_data, dict):
        images = result_data.get("images", [])
        if images:
            return images[0] if isinstance(images[0], str) else images[0].get("url", "")
        for key in ("imageUrl", "output", "resultUrl"):
            if result_data.get(key):
                return result_data[key]

    if isinstance(result_data, list) and result_data:
        item = result_data[0]
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return (
                item.get("url") or item.get("imageUrl")
                or item.get("output") or item.get("b64_json")
            )

    for key in ("images", "imageUrl", "output", "resultUrl", "image"):
        val = data.get(key)
        if val:
            if isinstance(val, list) and val:
                return val[0] if isinstance(val[0], str) else val[0].get("url", "")
            if isinstance(val, str):
                return val

    return None


def build_bg_prompt(title: str, body: str = "", niche: str = "") -> str:
    """Build a NanoBanana prompt for slide background image."""
    # Extract topic keywords from title
    topic = title.strip()
    if len(topic) > 120:
        topic = topic[:120]

    niche_hint = ""
    if niche:
        niche_map = {
            "недвижимость": "real estate, architecture, modern buildings",
            "ai": "artificial intelligence, technology, futuristic digital",
            "психология": "psychology, human emotions, mindfulness",
            "бизнес": "business, entrepreneurship, success",
            "фитнес": "fitness, health, active lifestyle",
        }
        niche_hint = niche_map.get(niche.lower(), niche)

    prompt = (
        f"Create a cinematic, high-quality background image for an Instagram carousel slide. "
        f"Topic: {topic}. "
    )
    if niche_hint:
        prompt += f"Theme: {niche_hint}. "
    prompt += (
        "Style: photorealistic, dramatic lighting, dark moody atmosphere, "
        "professional editorial look. "
        "The image should be visually striking and relevant to the topic. "
        "CRITICAL: NO text, NO watermarks, NO logos, NO typography of any kind. "
        "NO faces in the center — leave the center area clean for text overlay. "
        "Resolution: vertical 4:5 format (1080x1350). "
        "Cinematic color grading, shallow depth of field, premium quality."
    )
    return prompt


async def generate_ai_background(
    prompt: str,
    width: int = 1080,
    height: int = 1350,
) -> bytes | None:
    """
    Generate background image via NanoBanana API with async polling.

    Returns image bytes or None on failure.
    Uses caching by prompt hash.
    """
    settings = get_settings()
    api_key = settings.nanobanana_api_key
    if not api_key:
        logger.warning("NanoBanana API key not set, cannot generate AI background")
        return None

    # Check cache
    cache_dir = _get_cache_dir()
    cache_key = _prompt_hash(prompt)
    cache_path = os.path.join(cache_dir, f"{cache_key}.jpg")
    if os.path.exists(cache_path):
        logger.info(f"AI background cache hit: {cache_key}")
        with open(cache_path, "rb") as f:
            return f.read()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        # Step 1: Submit generation task
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"NanoBanana bg: submitting task, prompt={prompt[:80]}...")
            response = await client.post(
                NANOBANANA_GENERATE_URL,
                headers=headers,
                json={
                    "prompt": prompt,
                    "aspectRatio": "4:5",
                    "numImages": 1,
                },
            )

            if response.status_code != 200:
                logger.error(
                    f"NanoBanana bg API error: {response.status_code} {response.text[:300]}"
                )
                return None

            result = response.json()

            # Extract taskId
            task_id = None
            if isinstance(result.get("data"), dict):
                task_id = result["data"].get("taskId")
            if not task_id:
                task_id = result.get("taskId")

            if not task_id:
                # Maybe sync response with image
                image_url = _extract_image_url(result)
                if not image_url:
                    logger.error(f"NanoBanana bg: no taskId or image: {result}")
                    return None
            else:
                image_url = None

        # Step 2: Poll for result
        if task_id:
            async with httpx.AsyncClient(timeout=30.0) as poll_client:
                poll_result = await _poll_task_result(poll_client, task_id, headers)
                if not poll_result:
                    return None
                image_url = _extract_image_url(poll_result)
                if not image_url:
                    logger.error(f"NanoBanana bg: no image in result")
                    return None

        # Step 3: Download image
        if not image_url:
            return None

        if image_url.startswith("http"):
            async with httpx.AsyncClient(timeout=60.0) as dl_client:
                img_resp = await dl_client.get(image_url)
                if img_resp.status_code != 200:
                    logger.error(f"NanoBanana bg: download failed: {img_resp.status_code}")
                    return None
                img_bytes = img_resp.content
        else:
            # Base64
            import base64
            if "base64," in image_url:
                image_url = image_url.split("base64,")[1]
            img_bytes = base64.b64decode(image_url)

        # Step 4: Resize to target dimensions and cache
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        img = img.resize((width, height), Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, format="JPEG", quality=90)
        result_bytes = buf.getvalue()

        # Save to cache
        with open(cache_path, "wb") as f:
            f.write(result_bytes)
        logger.info(f"AI background generated and cached: {cache_key}")

        return result_bytes

    except httpx.TimeoutException:
        logger.error("NanoBanana bg: request timed out")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"NanoBanana bg: HTTP error: {e}")
        return None
    except Exception as e:
        logger.error(f"NanoBanana bg generation failed: {e}", exc_info=True)
        return None
