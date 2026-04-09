"""
Behavioral factor API — Instagram activity simulation.
Start/stop/monitor behavior sessions, configure settings.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from supabase import Client

from app.api.deps import get_current_user, get_db
from app.services.publisher.behavior import (
    start_behavior_session,
    stop_behavior_session,
    is_session_running,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class BehaviorStartRequest(BaseModel):
    intensity: str = Field(default="normal", pattern="^(light|normal|aggressive)$")
    enable_likes: bool = True
    enable_comments: bool = True
    enable_stories: bool = True
    enable_reels: bool = True


class BehaviorSettingsUpdate(BaseModel):
    behavior_enabled: Optional[bool] = None
    behavior_intensity: Optional[str] = None
    behavior_schedule: Optional[dict] = None


# ═══ Start session ═══
@router.post("/start/{account_id}")
async def start_session(
    account_id: str,
    req: BehaviorStartRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Start a behavior session for an Instagram account."""
    # Verify ownership
    account = db.table("instagram_accounts").select("id, is_active").eq(
        "id", account_id
    ).eq("owner_id", user["id"]).single().execute()

    if not account.data:
        raise HTTPException(404, detail="Аккаунт не найден")
    if not account.data.get("is_active"):
        raise HTTPException(400, detail="Аккаунт неактивен — сначала подключите его")

    if is_session_running(account_id):
        raise HTTPException(409, detail="Сессия уже запущена для этого аккаунта")

    # Run in background
    async def run():
        try:
            await start_behavior_session(
                account_id=account_id,
                owner_id=user["id"],
                intensity=req.intensity,
                enable_likes=req.enable_likes,
                enable_comments=req.enable_comments,
                enable_stories=req.enable_stories,
                enable_reels=req.enable_reels,
            )
        except Exception as e:
            logger.error(f"[Behavior API] Background session failed: {e}")

    background_tasks.add_task(run)

    return {"detail": "Сессия запущена", "account_id": account_id}


# ═══ Stop session ═══
@router.post("/stop/{account_id}")
async def stop_session(
    account_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Stop a running behavior session."""
    # Verify ownership
    account = db.table("instagram_accounts").select("id").eq(
        "id", account_id
    ).eq("owner_id", user["id"]).single().execute()

    if not account.data:
        raise HTTPException(404, detail="Аккаунт не найден")

    stopped = stop_behavior_session(account_id)
    if not stopped:
        raise HTTPException(404, detail="Нет активной сессии для этого аккаунта")

    return {"detail": "Сессия остановлена"}


# ═══ Status ═══
@router.get("/status/{account_id}")
async def get_status(
    account_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get current behavior session status."""
    running = is_session_running(account_id)

    # Get latest session from DB
    latest = db.table("behavior_sessions").select("*").eq(
        "account_id", account_id
    ).eq("owner_id", user["id"]).order(
        "created_at", desc=True
    ).limit(1).execute()

    return {
        "running": running,
        "latest_session": latest.data[0] if latest.data else None,
    }


# ═══ History ═══
@router.get("/history/{account_id}")
async def get_history(
    account_id: str,
    limit: int = 20,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get behavior session history."""
    result = db.table("behavior_sessions").select("*").eq(
        "account_id", account_id
    ).eq("owner_id", user["id"]).order(
        "created_at", desc=True
    ).limit(limit).execute()

    return result.data or []


# ═══ Settings ═══
@router.put("/settings/{account_id}")
async def update_settings(
    account_id: str,
    body: BehaviorSettingsUpdate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Update behavior settings for an account."""
    account = db.table("instagram_accounts").select("id").eq(
        "id", account_id
    ).eq("owner_id", user["id"]).single().execute()

    if not account.data:
        raise HTTPException(404, detail="Аккаунт не найден")

    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(400, detail="Нет данных для обновления")

    db.table("instagram_accounts").update(update).eq("id", account_id).execute()

    return {"detail": "Настройки обновлены"}


# ═══ Get settings ═══
@router.get("/settings/{account_id}")
async def get_settings_endpoint(
    account_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get behavior settings for an account."""
    result = db.table("instagram_accounts").select(
        "id, behavior_enabled, behavior_intensity, behavior_schedule, last_behavior_at"
    ).eq("id", account_id).eq("owner_id", user["id"]).single().execute()

    if not result.data:
        raise HTTPException(404, detail="Аккаунт не найден")

    return result.data
