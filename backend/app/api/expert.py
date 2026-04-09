"""
Expert Template API.
User uploads a ready-made background image (подложка).
It's used directly as the background for all carousel slides.
Text, username, page counter, arrows are overlaid on top.
"""
import os
import logging
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from PIL import Image

from app.api.deps import get_current_user
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
W, H = 1080, 1350


def _get_templates_dir() -> str:
    from pathlib import Path
    media_dir = str(Path(settings.media_storage_path).resolve())
    templates_dir = os.path.join(media_dir, "expert_templates")
    os.makedirs(templates_dir, exist_ok=True)
    return templates_dir


@router.post("/upload-photo")
async def upload_background(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """
    Upload a ready background image for carousel slides.
    Image is resized to 1080x1350 (4:5) and saved as template immediately.
    """
    user_id = user["id"]

    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "Поддерживаются только JPG, PNG и WebP")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, "Файл слишком большой (макс. 10 МБ)")
    if len(contents) < 1000:
        raise HTTPException(400, "Файл слишком маленький или повреждён")

    # Open and resize to exact carousel dimensions
    img = Image.open(BytesIO(contents)).convert("RGB")
    img = img.resize((W, H), Image.LANCZOS)

    templates_dir = _get_templates_dir()

    # Save as both photo (original preview) and template (used for slides)
    photo_path = os.path.join(templates_dir, f"{user_id}_photo.png")
    template_path = os.path.join(templates_dir, f"{user_id}.png")

    img.save(photo_path, format="PNG", quality=95)
    img.save(template_path, format="PNG", quality=95)

    logger.info(f"Background uploaded for user {user_id}: {img.width}x{img.height}")

    return {
        "message": "Подложка загружена и готова к использованию",
        "photo_url": f"/media/expert_templates/{user_id}_photo.png",
        "template_url": f"/media/expert_templates/{user_id}.png",
    }


@router.get("/status")
async def get_template_status(
    user: dict = Depends(get_current_user),
):
    """Check if user has an uploaded background."""
    user_id = user["id"]
    templates_dir = _get_templates_dir()

    photo_path = os.path.join(templates_dir, f"{user_id}_photo.png")
    template_path = os.path.join(templates_dir, f"{user_id}.png")

    has_photo = os.path.exists(photo_path)
    has_template = os.path.exists(template_path)

    return {
        "has_photo": has_photo,
        "has_template": has_template,
        "template_url": f"/media/expert_templates/{user_id}.png" if has_template else None,
        "photo_url": f"/media/expert_templates/{user_id}_photo.png" if has_photo else None,
    }
