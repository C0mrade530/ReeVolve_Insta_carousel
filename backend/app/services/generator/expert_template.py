"""
Expert Template Generator.

Flow:
1. User uploads their photo
2. NanoBanana API generates a professional portrait (person in suit, dark cinematic background)
3. Template is stored once per user, reused for all carousels
4. Fallback: PIL-based compositing if NanoBanana is unavailable

The generated template is a 1080x1350 PNG with:
- Dark gradient background
- Professional-looking expert photo on the right side
- Space for text on the left
- Accent lines and decorative elements
"""

import os
import json
import base64
import logging
import asyncio
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

W = 1080
H = 1350


def _get_templates_dir() -> str:
    """Get templates directory path."""
    media_dir = str(Path(settings.media_storage_path).resolve())
    templates_dir = os.path.join(media_dir, "expert_templates")
    os.makedirs(templates_dir, exist_ok=True)
    return templates_dir


def get_template_path(user_id: str) -> str | None:
    """Get path to user's expert template if it exists."""
    templates_dir = _get_templates_dir()
    path = os.path.join(templates_dir, f"{user_id}.png")
    if os.path.exists(path):
        return path
    return None


def get_template_url(user_id: str) -> str | None:
    """Get URL for user's expert template."""
    if get_template_path(user_id):
        return f"/media/expert_templates/{user_id}.png"
    return None


def get_photo_path(user_id: str) -> str | None:
    """Get path to user's uploaded photo."""
    templates_dir = _get_templates_dir()
    path = os.path.join(templates_dir, f"{user_id}_photo.png")
    if os.path.exists(path):
        return path
    return None


def _remove_background(img: Image.Image) -> Image.Image:
    """Remove background from photo using rembg. Returns RGBA image."""
    try:
        from rembg import remove
        # rembg expects bytes input, returns bytes output
        buf = BytesIO()
        img.save(buf, format="PNG")
        result_bytes = remove(buf.getvalue())
        return Image.open(BytesIO(result_bytes)).convert("RGBA")
    except ImportError:
        logger.warning("rembg not installed, skipping background removal")
        return img.convert("RGBA")
    except Exception as e:
        logger.warning(f"Background removal failed: {e}, using original photo")
        return img.convert("RGBA")


def save_uploaded_photo(user_id: str, photo_bytes: bytes, remove_bg: bool = True) -> str:
    """Save uploaded photo with optional bg removal, return file path."""
    templates_dir = _get_templates_dir()
    path = os.path.join(templates_dir, f"{user_id}_photo.png")

    # Open, validate, and resize if needed
    img = Image.open(BytesIO(photo_bytes)).convert("RGBA")

    # Resize to reasonable dimensions (max 1024px)
    max_dim = 1024
    if img.width > max_dim or img.height > max_dim:
        ratio = min(max_dim / img.width, max_dim / img.height)
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # Remove background if requested
    if remove_bg:
        logger.info(f"Removing background for user {user_id}...")
        img = _remove_background(img)
        logger.info(f"Background removal complete for user {user_id}")

    img.save(path, format="PNG")
    logger.info(f"Saved expert photo for user {user_id}: {img.width}x{img.height}")
    return path


# ═══════════════════════════════════════════════════════════════
# NANOBANANA API — AI template generation
# ═══════════════════════════════════════════════════════════════

NANOBANANA_GENERATE_URL = "https://api.nanobananaapi.ai/api/v1/nanobanana/generate"
NANOBANANA_STATUS_URL = "https://api.nanobananaapi.ai/api/v1/nanobanana/record-info"

# Polling settings
POLL_INTERVAL = 3          # seconds between polls
POLL_MAX_ATTEMPTS = 60     # max attempts (3s * 60 = 3 min max wait)


async def _poll_task_result(client: httpx.AsyncClient, task_id: str,
                            headers: dict) -> dict | None:
    """
    Poll NanoBanana /record-info endpoint until task completes or fails.
    Returns the full response dict or None on failure/timeout.
    """
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
                    f"NanoBanana poll attempt {attempt}: HTTP {resp.status_code}"
                )
                continue

            data = resp.json()
            logger.info(
                f"NanoBanana poll attempt {attempt}: "
                f"keys={list(data.keys())}, "
                f"code={data.get('code')}"
            )

            # Check for completion
            status = None
            result_data = data.get("data", {})
            if isinstance(result_data, dict):
                status = result_data.get("status", "").lower()
            elif isinstance(result_data, list) and result_data:
                status = result_data[0].get("status", "").lower() if isinstance(result_data[0], dict) else None

            # Also check top-level status field
            if not status:
                status = str(data.get("status", "")).lower()

            if status in ("complete", "completed", "success", "done"):
                logger.info(f"NanoBanana task {task_id} completed!")
                return data
            elif status in ("failed", "error", "cancelled"):
                logger.error(f"NanoBanana task {task_id} failed: {data}")
                return None
            # else: still processing, continue polling

        except Exception as e:
            logger.warning(f"NanoBanana poll attempt {attempt} error: {e}")

    logger.error(f"NanoBanana task {task_id} timed out after {POLL_MAX_ATTEMPTS} attempts")
    return None


def _extract_image_from_response(data: dict) -> str | None:
    """
    Extract image URL or base64 from NanoBanana record-info response.
    Handles various response formats.
    """
    result_data = data.get("data", {})

    # Format 1: data.images[] — array of image URLs
    if isinstance(result_data, dict):
        images = result_data.get("images", [])
        if images:
            return images[0] if isinstance(images[0], str) else images[0].get("url", "")

        # Format 2: data.imageUrl — single URL
        if result_data.get("imageUrl"):
            return result_data["imageUrl"]

        # Format 3: data.output — single URL or base64
        if result_data.get("output"):
            return result_data["output"]

        # Format 4: data.resultUrl
        if result_data.get("resultUrl"):
            return result_data["resultUrl"]

    # Format 5: data is array of items
    if isinstance(result_data, list) and result_data:
        item = result_data[0]
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return (
                item.get("url")
                or item.get("imageUrl")
                or item.get("b64_json")
                or item.get("output")
            )

    # Format 6: top-level fields
    for key in ("images", "imageUrl", "output", "resultUrl", "image"):
        val = data.get(key)
        if val:
            if isinstance(val, list) and val:
                return val[0] if isinstance(val[0], str) else val[0].get("url", "")
            if isinstance(val, str):
                return val

    return None


async def generate_template_nanobanana(user_id: str, photo_path: str) -> str | None:
    """
    Use NanoBanana API to generate a professional expert template.

    Flow:
    1. POST /generate with prompt + photo → get taskId
    2. Poll /record-info?taskId=xxx until done
    3. Download generated image and save

    Returns path to generated template or None if failed.
    """
    api_key = settings.nanobanana_api_key
    if not api_key:
        logger.warning("NanoBanana API key not set, falling back to PIL")
        return None

    try:
        # Compress photo for API upload (avoid 413 Payload Too Large)
        img_for_api = Image.open(photo_path).convert("RGB")
        # Resize to max 768px on longest side (keeps enough detail for face)
        max_side = 768
        if img_for_api.width > max_side or img_for_api.height > max_side:
            ratio = min(max_side / img_for_api.width, max_side / img_for_api.height)
            new_w = int(img_for_api.width * ratio)
            new_h = int(img_for_api.height * ratio)
            img_for_api = img_for_api.resize((new_w, new_h), Image.LANCZOS)
        # Encode as JPEG (much smaller than PNG)
        buf = BytesIO()
        img_for_api.save(buf, format="JPEG", quality=80)
        photo_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        photo_data_uri = f"data:image/jpeg;base64,{photo_b64}"
        logger.info(
            f"NanoBanana: photo compressed to {img_for_api.width}x{img_for_api.height}, "
            f"base64 size={len(photo_b64) // 1024}KB"
        )

        prompt = (
            "Use the uploaded photo as the ONLY source of the person. "
            "OUTPUT FORMAT (MANDATORY): Aspect ratio: 4:5 (vertical), Resolution: 1080 x 1350 px, Instagram carousel format. "
            "STRICT IDENTITY PRESERVATION: Do NOT change facial features. Do NOT change face shape, eyes, nose, lips. "
            "Do NOT beautify or stylize the face. Keep 100% likeness and identity. "
            "Realistic skin texture, natural details. No AI face modification. "
            "COMPOSITION (CRITICAL): Place the person strictly on the RIGHT THIRD of the frame. "
            "The person must occupy only the right 30-35% of the image width. "
            "Leave the LEFT 65-70% completely empty and clean. "
            "No centering, no middle placement. Head and shoulders visible. "
            "Body slightly turned toward camera. Calm, confident, professional expression. "
            "BACKGROUND: Clean, deep dark gradient background. Dark gray / charcoal / graphite tones. "
            "Smooth cinematic studio backdrop. Absolutely NO text, NO UI, NO icons. "
            "LIGHTING: Cinematic studio lighting. Soft key light from front-left. "
            "Subtle rim light on the right edge for separation. Editorial, premium portrait lighting. "
            "STYLE: Minimal, premium, expert authority style. Business / medical / thought-leader aesthetic. "
            "Photorealistic. No illustration, no fantasy, no creative distortion. "
            "FRAMING & QUALITY: Face perfectly sharp. Natural contrast and exposure. "
            "High-resolution, clean details. No blur, no noise, no artifacts. "
            "STRICT RESTRICTIONS: DO NOT add text or typography. DO NOT add logos or graphic elements. "
            "DO NOT crop head or chin. DO NOT change hairstyle, beard, age, ethnicity. DO NOT center the subject. "
            "FINAL REQUIREMENT: The final image must look like a premium Instagram carousel cover: "
            "vertical 4:5 (1080x1350), expert positioned on the right third of the frame, "
            "large empty dark space on the left, clean cinematic editorial look."
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Step 1: Submit generation task
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"NanoBanana: submitting generate task for user {user_id}...")

            response = await client.post(
                NANOBANANA_GENERATE_URL,
                headers=headers,
                json={
                    "prompt": prompt,
                    "imageUrls": [photo_data_uri],
                    "aspectRatio": "4:5",
                    "numImages": 1,
                },
            )

            logger.info(
                f"NanoBanana generate response: "
                f"status={response.status_code}, "
                f"body={response.text[:500]}"
            )

            if response.status_code != 200:
                logger.error(
                    f"NanoBanana API error: {response.status_code} "
                    f"{response.text[:500]}"
                )
                return None

            result = response.json()

            # Extract taskId from response
            task_id = None
            if isinstance(result.get("data"), dict):
                task_id = result["data"].get("taskId")
            if not task_id:
                task_id = result.get("taskId")

            if not task_id:
                # Maybe it returned the image directly (synchronous)?
                image_data = _extract_image_from_response(result)
                if image_data:
                    logger.info("NanoBanana returned image directly (sync mode)")
                else:
                    logger.error(
                        f"NanoBanana: no taskId in response: {result}"
                    )
                    return None
            else:
                logger.info(f"NanoBanana: got taskId={task_id}, polling...")

        # Step 2: Poll for result (new client with longer timeout)
        image_data = None
        if task_id:
            async with httpx.AsyncClient(timeout=30.0) as poll_client:
                poll_result = await _poll_task_result(
                    poll_client, task_id, headers
                )
                if not poll_result:
                    return None

                image_data = _extract_image_from_response(poll_result)
                if not image_data:
                    logger.error(
                        f"NanoBanana: no image in completed task: "
                        f"{json.dumps(poll_result, ensure_ascii=False)[:1000]}"
                    )
                    return None

        # Step 3: Download/decode the image
        if not image_data:
            return None

        if image_data.startswith("http"):
            # Download from URL
            logger.info(f"NanoBanana: downloading image from URL...")
            async with httpx.AsyncClient(timeout=60.0) as dl_client:
                img_resp = await dl_client.get(image_data)
                if img_resp.status_code != 200:
                    logger.error(
                        f"NanoBanana: failed to download image: "
                        f"{img_resp.status_code}"
                    )
                    return None
                img_bytes = img_resp.content
        else:
            # Base64 encoded
            if "base64," in image_data:
                image_data = image_data.split("base64,")[1]
            img_bytes = base64.b64decode(image_data)

        # Step 4: Open, resize, and save
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        img = img.resize((W, H), Image.LANCZOS)

        templates_dir = _get_templates_dir()
        output_path = os.path.join(templates_dir, f"{user_id}.png")
        img.save(output_path, format="PNG", quality=95)

        logger.info(f"NanoBanana template generated for user {user_id}")
        return output_path

    except Exception as e:
        logger.error(f"NanoBanana generation failed: {e}", exc_info=True)
        return None


# ═══════════════════════════════════════════════════════════════
# PIL FALLBACK — local template generation
# ═══════════════════════════════════════════════════════════════

def _hex(c: str) -> tuple:
    c = c.lstrip("#")
    return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))


def generate_template_pil(user_id: str, photo_path: str,
                           accent_color: str = "#d4a853") -> str:
    """
    Generate expert template using PIL compositing.
    Premium dark background with expert photo on the right.

    Layout:
    - Dark gradient background (near-black with subtle blue/warm tones)
    - Expert photo on the right ~40% with smooth left+bottom fade
    - Warm accent glow behind the person
    - Gold accent lines and corner brackets
    - Left 55% empty for text overlay
    """
    from PIL import ImageChops
    import numpy as np

    # Open expert photo (should already have bg removed from upload)
    photo = Image.open(photo_path).convert("RGBA")

    # ── Background: rich dark gradient ──
    canvas = Image.new("RGB", (W, H), "#080808")
    draw = ImageDraw.Draw(canvas)

    # Vertical gradient: very dark blue-gray top → warm dark bottom
    for y in range(H):
        t = y / H
        r = int(8 + 10 * t)
        g = int(8 + 6 * t)
        b = int(14 + 18 * (1 - t))
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # ── Warm accent glow behind person position ──
    ac = _hex(accent_color)
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)

    # Main warm glow (behind person's torso area)
    cx, cy = int(W * 0.72), int(H * 0.40)
    for radius in range(700, 0, -4):
        intensity = max(0, min(255, int(18 * (1 - radius / 700))))
        color = (
            min(255, ac[0] * intensity // 255),
            min(255, ac[1] * intensity // 255),
            min(255, ac[2] * intensity // 255),
        )
        glow_draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=color,
        )

    # Secondary cooler glow (subtle blue rim on far right)
    cx2, cy2 = int(W * 0.95), int(H * 0.35)
    for radius in range(400, 0, -4):
        intensity = max(0, min(255, int(10 * (1 - radius / 400))))
        color = (
            intensity // 4,
            intensity // 3,
            min(255, intensity),
        )
        glow_draw.ellipse(
            [cx2 - radius, cy2 - radius, cx2 + radius, cy2 + radius],
            fill=color,
        )

    canvas = ImageChops.add(canvas, glow)

    # ── Process expert photo ──
    # Scale to fill right portion (larger — almost full height)
    target_h = int(H * 0.82)
    photo_ratio = target_h / photo.height
    target_w = int(photo.width * photo_ratio)
    # Clamp max width to not overflow canvas
    if target_w > int(W * 0.65):
        target_w = int(W * 0.65)
        photo_ratio = target_w / photo.width
        target_h = int(photo.height * photo_ratio)
    photo = photo.resize((target_w, target_h), Image.LANCZOS)

    # ── Gradient mask for smooth blending ──
    # Use numpy for efficient mask generation (avoids slow pixel-by-pixel)
    try:
        mask_arr = np.zeros((target_h, target_w), dtype=np.uint8)

        # Left fade: smooth power curve
        fade_w = int(target_w * 0.45)
        for x in range(target_w):
            if x < fade_w:
                val = int(255 * (x / fade_w) ** 1.8)
            else:
                val = 255
            mask_arr[:, x] = val

        # Bottom fade
        bottom_fade = int(target_h * 0.18)
        for y in range(max(0, target_h - bottom_fade), target_h):
            fade_t = (y - (target_h - bottom_fade)) / bottom_fade
            dim = 1.0 - fade_t * 0.85
            mask_arr[y, :] = (mask_arr[y, :].astype(float) * dim).astype(np.uint8)

        # Top fade (subtle)
        top_fade = int(target_h * 0.08)
        for y in range(min(top_fade, target_h)):
            fade_t = y / top_fade
            dim = fade_t ** 0.5
            mask_arr[y, :] = (mask_arr[y, :].astype(float) * dim).astype(np.uint8)

        # Also use photo's own alpha channel if available
        if photo.mode == "RGBA":
            photo_alpha = np.array(photo.split()[3])
            mask_arr = (
                mask_arr.astype(float) * photo_alpha.astype(float) / 255
            ).astype(np.uint8)

        mask = Image.fromarray(mask_arr, mode="L")
    except ImportError:
        # numpy not available — simple line-based mask
        mask = Image.new("L", (target_w, target_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        fade_w = int(target_w * 0.45)
        for x in range(target_w):
            if x < fade_w:
                val = int(255 * (x / fade_w) ** 1.8)
            else:
                val = 255
            mask_draw.line([(x, 0), (x, target_h)], fill=val)

        # Bottom fade
        bottom_fade = int(target_h * 0.18)
        for y in range(max(0, target_h - bottom_fade), target_h):
            fade_t = (y - (target_h - bottom_fade)) / bottom_fade
            dim = 1.0 - fade_t * 0.85
            for x in range(target_w):
                cur = mask.getpixel((x, y))
                mask.putpixel((x, y), int(cur * dim))

    # Position photo on right side
    photo_x = W - target_w + int(target_w * 0.08)
    photo_y = int(H * 0.08)

    # Paste photo with gradient mask
    photo_rgb = photo.convert("RGB")
    canvas.paste(photo_rgb, (photo_x, photo_y), mask)

    # ── Accent elements (RGBA overlay for proper transparency) ──
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # Top accent thin line (gold)
    od.rectangle([(0, 0), (W, 2)], fill=(*ac, 200))

    # Bottom accent thin line (gold)
    od.rectangle([(0, H - 2), (W, H)], fill=(*ac, 200))

    # Corner brackets (top-left)
    bracket_alpha = 80
    od.line([(50, 50), (170, 50)], fill=(*ac, bracket_alpha), width=2)
    od.line([(50, 50), (50, 170)], fill=(*ac, bracket_alpha), width=2)

    # Corner brackets (bottom-right)
    od.line([(W - 170, H - 50), (W - 50, H - 50)], fill=(*ac, bracket_alpha), width=2)
    od.line([(W - 50, H - 170), (W - 50, H - 50)], fill=(*ac, bracket_alpha), width=2)

    # Subtle left vertical accent line
    od.rectangle([(55, 200), (57, H - 200)], fill=(*ac, 25))

    # Composite overlay onto canvas
    canvas_rgba = canvas.convert("RGBA")
    canvas = Image.alpha_composite(canvas_rgba, overlay).convert("RGB")

    # Save
    templates_dir = _get_templates_dir()
    output_path = os.path.join(templates_dir, f"{user_id}.png")
    canvas.save(output_path, format="PNG", quality=95)

    logger.info(f"PIL template generated for user {user_id}")
    return output_path


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

async def generate_expert_template(
    user_id: str,
    photo_path: str,
    accent_color: str = "#d4a853",
    force_pil: bool = False,
) -> str:
    """
    Generate expert template. Tries NanoBanana first, falls back to PIL.
    Returns path to generated template.
    """
    if not force_pil:
        # Try NanoBanana API first
        result = await generate_template_nanobanana(user_id, photo_path)
        if result:
            return result
        logger.info("NanoBanana failed, using PIL fallback")

    # PIL fallback
    return await asyncio.to_thread(
        generate_template_pil, user_id, photo_path, accent_color
    )
