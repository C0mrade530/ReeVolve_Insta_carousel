"""
Scheduler API — view and manage publish schedules.
"""
from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.api.deps import get_current_user, get_db

router = APIRouter()


@router.get("")
async def list_schedules(
    account_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, le=200),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    # Get user's accounts
    accounts = (
        db.table("instagram_accounts")
        .select("id")
        .eq("owner_id", user["id"])
        .execute()
    )
    account_ids = [a["id"] for a in accounts.data]
    if not account_ids:
        return []

    query = (
        db.table("publish_schedules")
        .select("*, carousels(type, caption, slides), instagram_accounts(username)")
    )

    if account_id:
        query = query.eq("account_id", account_id)
    else:
        query = query.in_("account_id", account_ids)

    if status:
        query = query.eq("status", status)

    result = query.order("scheduled_time", desc=False).limit(limit).execute()
    return result.data


@router.get("/upcoming")
async def upcoming_schedules(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get next 10 upcoming publications."""
    accounts = (
        db.table("instagram_accounts")
        .select("id")
        .eq("owner_id", user["id"])
        .execute()
    )
    account_ids = [a["id"] for a in accounts.data]
    if not account_ids:
        return []

    result = (
        db.table("publish_schedules")
        .select("*, carousels(type, caption), instagram_accounts(username)")
        .in_("account_id", account_ids)
        .eq("status", "pending")
        .order("scheduled_time")
        .limit(10)
        .execute()
    )
    return result.data
