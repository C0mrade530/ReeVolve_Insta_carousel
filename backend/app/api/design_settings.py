"""
Design Settings API — user-level carousel design preferences.
Stored as JSONB in design_settings table (one row per user).
"""
import os
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from supabase import Client

from app.api.deps import get_current_user, get_db
from app.config import get_settings
from app.services.generator.image import get_all_templates, CARD_TEMPLATES, DESIGN_TEMPLATES

logger = logging.getLogger(__name__)
router = APIRouter()

# Default design settings (returned when user has no saved settings)
DEFAULTS = {
    "template_id": "expert",
    "bg_type": "template",
    "bg_color": "#0a0a0a",
    "bg_gradient_start": None,
    "bg_gradient_end": None,
    "bg_upload_path": None,
    "font_pairing": "luxury",
    "title_size": 62,
    "body_size": 36,
    "text_color": "#ffffff",
    "accent_color": "#d4a853",
    "text_position": "bottom",
    "image_position": "top",
    "avatar_placement": "middle",
    "canvas_width": 1080,
    "canvas_height": 1350,
    "photo_type": "expert",
}


class DesignSettingsUpdate(BaseModel):
    template_id: str | None = None
    bg_type: str | None = None
    bg_color: str | None = None
    bg_gradient_start: str | None = None
    bg_gradient_end: str | None = None
    font_pairing: str | None = None
    title_size: int | None = Field(default=None, ge=24, le=96)
    body_size: int | None = Field(default=None, ge=18, le=60)
    text_color: str | None = None
    accent_color: str | None = None
    text_position: str | None = None
    image_position: str | None = None
    avatar_placement: str | None = None
    canvas_width: int | None = Field(default=None, ge=540, le=2160)
    canvas_height: int | None = Field(default=None, ge=540, le=2700)
    photo_type: str | None = None


@router.get("")
async def get_design_settings(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get user's design settings, merged with defaults."""
    user_id = user["id"]
    try:
        result = db.table("design_settings").select("*").eq(
            "owner_id", user_id
        ).limit(1).execute()

        if result.data:
            saved = result.data[0]
            # Merge saved over defaults
            merged = {**DEFAULTS}
            for k, v in saved.items():
                if k in merged and v is not None:
                    merged[k] = v
            merged["id"] = saved.get("id")
            return merged
    except Exception as e:
        logger.warning(f"Failed to load design_settings: {e}")

    return {**DEFAULTS, "id": None}


@router.put("")
async def update_design_settings(
    req: DesignSettingsUpdate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Upsert user's design settings."""
    user_id = user["id"]
    data = {k: v for k, v in req.model_dump().items() if v is not None}

    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")

    # Check if exists
    existing = db.table("design_settings").select("id").eq(
        "owner_id", user_id
    ).limit(1).execute()

    if existing.data:
        result = db.table("design_settings").update(data).eq(
            "owner_id", user_id
        ).execute()
    else:
        data["owner_id"] = user_id
        result = db.table("design_settings").insert(data).execute()

    return result.data[0] if result.data else data


@router.post("/upload-bg")
async def upload_background(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a custom background image."""
    user_id = user["id"]
    settings = get_settings()
    media_dir = str(Path(settings.media_storage_path).resolve())
    bg_dir = os.path.join(media_dir, "backgrounds")
    os.makedirs(bg_dir, exist_ok=True)

    # Save file
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "png"
    filename = f"{user_id}.{ext}"
    filepath = os.path.join(bg_dir, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    return {
        "path": f"/media/backgrounds/{filename}",
        "size": len(content),
    }


@router.get("/templates")
async def list_available_templates(
    user: dict = Depends(get_current_user),
):
    """List all available design templates."""
    return get_all_templates()


@router.get("/stickers")
async def list_stickers(
    user: dict = Depends(get_current_user),
):
    """List available stickers (built-in + user-uploaded)."""
    settings = get_settings()
    stickers = []

    # Built-in stickers from assets/stickers/
    assets_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "assets", "stickers"
    )
    if os.path.isdir(assets_dir):
        for f in sorted(os.listdir(assets_dir)):
            if f.endswith(".png"):
                stickers.append({
                    "id": f"builtin_{f[:-4]}",
                    "name": f[:-4].replace("_", " ").title(),
                    "path": f"/assets/stickers/{f}",
                    "type": "builtin",
                })

    # User stickers from media/stickers/{user_id}/
    user_sticker_dir = os.path.join(
        str(Path(settings.media_storage_path).resolve()),
        "stickers", user["id"]
    )
    if os.path.isdir(user_sticker_dir):
        for f in sorted(os.listdir(user_sticker_dir)):
            if f.endswith(".png"):
                stickers.append({
                    "id": f"user_{f[:-4]}",
                    "name": f[:-4],
                    "path": f"/media/stickers/{user['id']}/{f}",
                    "type": "user",
                })

    return stickers


@router.post("/upload-sticker")
async def upload_sticker(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a custom sticker (PNG with transparency)."""
    user_id = user["id"]
    settings = get_settings()
    sticker_dir = os.path.join(
        str(Path(settings.media_storage_path).resolve()),
        "stickers", user_id,
    )
    os.makedirs(sticker_dir, exist_ok=True)

    filename = file.filename or "sticker.png"
    filepath = os.path.join(sticker_dir, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    return {
        "path": f"/media/stickers/{user_id}/{filename}",
        "name": filename[:-4] if filename.endswith(".png") else filename,
    }
