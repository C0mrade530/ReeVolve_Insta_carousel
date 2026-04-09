"""
Brand profile API — personality unpacking endpoints.
Upload files → AI analyzes → structured brand profile.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import Client

from app.api.deps import get_current_user, get_db
from app.services.brand.unpacker import extract_text_from_file, unpack_brand_profile

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".md", ".txt", ".pdf", ".docx", ".doc"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file
MAX_FILES = 10


# ═══════════════════════════════════════════════════════════════════
# Upload files and create brand profile
# ═══════════════════════════════════════════════════════════════════

@router.post("/upload")
async def upload_brand_files(
    files: list[UploadFile] = File(...),
    account_id: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Upload files for brand personality unpacking.
    Creates a brand_profile record with status='draft' and extracted raw_text.
    """
    if len(files) > MAX_FILES:
        raise HTTPException(400, detail=f"Максимум {MAX_FILES} файлов за раз")

    # Extract text from all files
    all_texts = []
    file_metadata = []

    for f in files:
        # Validate extension
        ext = "." + f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                400,
                detail=f"Неподдерживаемый формат: {f.filename}. "
                       f"Поддерживаются: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Read content
        content = await f.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(400, detail=f"Файл {f.filename} превышает 10 МБ")

        # Extract text
        try:
            text = extract_text_from_file(f.filename, content)
        except ValueError as e:
            raise HTTPException(400, detail=str(e))

        if text.strip():
            all_texts.append(f"=== {f.filename} ===\n{text}")
            file_metadata.append({
                "filename": f.filename,
                "size": len(content),
                "type": ext,
                "chars_extracted": len(text),
            })

    if not all_texts:
        raise HTTPException(400, detail="Не удалось извлечь текст ни из одного файла")

    raw_text = "\n\n".join(all_texts)

    # Create brand_profile record
    profile_data = {
        "owner_id": user["id"],
        "source_files": file_metadata,
        "raw_text": raw_text,
        "status": "draft",
    }

    result = db.table("brand_profiles").insert(profile_data).execute()
    if not result.data:
        raise HTTPException(500, detail="Не удалось создать профиль бренда")

    profile = result.data[0]

    # Link to account if provided
    if account_id:
        try:
            db.table("instagram_accounts").update({
                "brand_profile_id": profile["id"]
            }).eq("id", account_id).eq("owner_id", user["id"]).execute()
        except Exception as e:
            logger.warning(f"Failed to link brand_profile to account: {e}")

    return {
        "id": profile["id"],
        "files_processed": len(file_metadata),
        "total_chars": len(raw_text),
        "status": "draft",
    }


# ═══════════════════════════════════════════════════════════════════
# Run AI unpacking (SSE progress)
# ═══════════════════════════════════════════════════════════════════

@router.post("/unpack/{profile_id}")
async def unpack_brand_profile_endpoint(
    profile_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Start AI unpacking of brand profile. Returns SSE stream with progress."""
    # Fetch profile
    result = db.table("brand_profiles").select("*").eq(
        "id", profile_id
    ).eq("owner_id", user["id"]).limit(1).execute()

    if not result.data:
        raise HTTPException(404, detail="Профиль не найден")

    profile = result.data[0]
    raw_text = profile.get("raw_text", "")

    if not raw_text or len(raw_text.strip()) < 50:
        raise HTTPException(400, detail="Недостаточно текста для анализа. Загрузите больше материалов.")

    if profile["status"] == "processing":
        raise HTTPException(409, detail="Распаковка уже в процессе")

    # Set status to processing
    db.table("brand_profiles").update({
        "status": "processing"
    }).eq("id", profile_id).execute()

    # Run unpacking
    async def generate_sse():
        import json as json_mod
        queue = asyncio.Queue()

        def on_progress(step: str, current: int, total: int):
            queue.put_nowait({"step": step, "current": current, "total": total})

        try:
            # Start unpacking in background
            task = asyncio.create_task(_run_unpack(
                db, profile_id, raw_text, on_progress
            ))

            # Stream progress events
            while not task.done():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json_mod.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json_mod.dumps({'step': 'waiting', 'current': 0, 'total': 0})}\n\n"

            # Get result
            result = await task
            yield f"data: {json_mod.dumps({'step': 'done', 'current': 3, 'total': 3, 'profile_id': profile_id})}\n\n"

        except Exception as e:
            logger.error(f"[Brand Unpack] SSE error: {e}", exc_info=True)
            db.table("brand_profiles").update({
                "status": "error",
                "error_message": str(e),
            }).eq("id", profile_id).execute()
            yield f"data: {json_mod.dumps({'step': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate_sse(), media_type="text/event-stream")


async def _run_unpack(db, profile_id: str, raw_text: str, on_progress):
    """Run brand unpacking and save results to DB."""
    try:
        result = await unpack_brand_profile(raw_text, on_progress=on_progress)

        # Save to DB
        update_data = {
            "positioning": result.get("positioning", ""),
            "target_audience": result.get("target_audience", []),
            "services": result.get("services", []),
            "content_topics": result.get("content_topics", []),
            "tone_of_voice": result.get("tone_of_voice", {}),
            "unique_phrases": result.get("unique_phrases", []),
            "niche": result.get("niche", ""),
            "status": "ready",
            "error_message": None,
            "updated_at": datetime.utcnow().isoformat(),
        }

        db.table("brand_profiles").update(update_data).eq("id", profile_id).execute()
        logger.info(f"[Brand Unpack] Profile {profile_id} ready")
        return result

    except Exception as e:
        logger.error(f"[Brand Unpack] Failed: {e}", exc_info=True)
        db.table("brand_profiles").update({
            "status": "error",
            "error_message": str(e),
        }).eq("id", profile_id).execute()
        raise


# ═══════════════════════════════════════════════════════════════════
# CRUD endpoints
# ═══════════════════════════════════════════════════════════════════

@router.get("/profiles")
async def list_brand_profiles(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """List all brand profiles for current user (full data)."""
    result = db.table("brand_profiles").select("*").eq(
        "owner_id", user["id"]
    ).order("created_at", desc=True).execute()
    return result.data or []


@router.get("/profiles/{profile_id}")
async def get_brand_profile(
    profile_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get full brand profile."""
    result = db.table("brand_profiles").select("*").eq(
        "id", profile_id
    ).eq("owner_id", user["id"]).limit(1).execute()

    if not result.data:
        raise HTTPException(404, detail="Профиль не найден")
    return result.data[0]


class BrandProfileUpdate(BaseModel):
    positioning: Optional[str] = None
    target_audience: Optional[list] = None
    services: Optional[list] = None
    content_topics: Optional[list] = None
    tone_of_voice: Optional[dict] = None
    unique_phrases: Optional[list[str]] = None
    niche: Optional[str] = None


@router.put("/profiles/{profile_id}")
async def update_brand_profile(
    profile_id: str,
    body: BrandProfileUpdate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Update brand profile (manual edits)."""
    # Check ownership
    existing = db.table("brand_profiles").select("id").eq(
        "id", profile_id
    ).eq("owner_id", user["id"]).limit(1).execute()

    if not existing.data:
        raise HTTPException(404, detail="Профиль не найден")

    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(400, detail="Нет данных для обновления")

    update_data["updated_at"] = datetime.utcnow().isoformat()

    result = db.table("brand_profiles").update(update_data).eq(
        "id", profile_id
    ).execute()

    return result.data[0] if result.data else {"detail": "Обновлено"}


@router.delete("/profiles/{profile_id}")
async def delete_brand_profile(
    profile_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Delete brand profile."""
    # Unlink from any accounts first
    db.table("instagram_accounts").update({
        "brand_profile_id": None
    }).eq("brand_profile_id", profile_id).eq("owner_id", user["id"]).execute()

    # Delete profile
    result = db.table("brand_profiles").delete().eq(
        "id", profile_id
    ).eq("owner_id", user["id"]).execute()

    if not result.data:
        raise HTTPException(404, detail="Профиль не найден")

    return {"detail": "Профиль удалён"}


# ═══════════════════════════════════════════════════════════════════
# Link profile to account
# ═══════════════════════════════════════════════════════════════════

class LinkProfileRequest(BaseModel):
    account_id: str
    profile_id: str


@router.post("/link")
async def link_profile_to_account(
    body: LinkProfileRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Link a brand profile to an Instagram account."""
    # Verify ownership of both
    profile = db.table("brand_profiles").select("id").eq(
        "id", body.profile_id
    ).eq("owner_id", user["id"]).limit(1).execute()

    if not profile.data:
        raise HTTPException(404, detail="Профиль не найден")

    account = db.table("instagram_accounts").select("id").eq(
        "id", body.account_id
    ).eq("owner_id", user["id"]).limit(1).execute()

    if not account.data:
        raise HTTPException(404, detail="Аккаунт не найден")

    # Update account
    db.table("instagram_accounts").update({
        "brand_profile_id": body.profile_id,
        "niche": "",  # Will be pulled from brand_profile
    }).eq("id", body.account_id).execute()

    return {"detail": "Профиль привязан к аккаунту"}
