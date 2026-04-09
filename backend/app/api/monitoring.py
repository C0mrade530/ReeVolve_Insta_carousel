"""
Task monitoring + DLQ API endpoints.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.deps import get_current_user, get_db
from app.services.task_monitor import get_task_monitor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
async def monitor_stats(
    user: dict = Depends(get_current_user),
):
    """Overall task monitoring statistics."""
    monitor = get_task_monitor()
    return monitor.get_stats()


@router.get("/running")
async def running_tasks(
    user: dict = Depends(get_current_user),
):
    """Currently running tasks for this user."""
    monitor = get_task_monitor()
    return monitor.get_running(owner_id=user["id"])


@router.get("/dlq")
async def dead_letter_queue(
    limit: int = Query(default=50, le=200),
    user: dict = Depends(get_current_user),
):
    """Get failed tasks in the Dead Letter Queue."""
    monitor = get_task_monitor()
    return {
        "tasks": monitor.get_dlq(owner_id=user["id"], limit=limit),
        "total": len([t for t in monitor._dlq if t.owner_id == user["id"]]),
    }


@router.post("/dlq/{task_id}/retry")
async def retry_dlq_task(
    task_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Retry a failed task from the DLQ.
    For generation tasks: re-triggers carousel generation.
    For publishing tasks: re-triggers publishing.
    """
    monitor = get_task_monitor()

    # Find task in DLQ
    entry = next((t for t in monitor._dlq if t.task_id == task_id and t.owner_id == user["id"]), None)
    if not entry:
        raise HTTPException(404, "Задача не найдена в очереди ошибок")

    if entry.retry_count >= monitor.MAX_RETRIES:
        raise HTTPException(400, f"Превышен лимит повторов ({monitor.MAX_RETRIES}). Удалите задачу и создайте заново.")

    # Re-queue based on task type
    context = entry.context or {}

    if entry.task_type == "generation":
        carousel_id = context.get("carousel_id")
        if carousel_id:
            # Reset carousel status to allow regeneration
            try:
                db.table("carousels").update({"status": "ready"}).eq("id", carousel_id).execute()
            except Exception as e:
                logger.warning(f"[Monitoring] Failed to reset carousel {carousel_id} for retry: {e}")
            monitor.remove_from_dlq(task_id)
            return {
                "message": "Карусель поставлена на перегенерацию",
                "carousel_id": carousel_id,
                "action": "regenerate",
            }

    elif entry.task_type == "publishing":
        carousel_id = context.get("carousel_id")
        schedule_id = context.get("schedule_id")
        if schedule_id:
            try:
                db.table("publish_schedules").update({"status": "pending"}).eq("id", schedule_id).execute()
            except Exception as e:
                logger.warning(f"[Monitoring] Failed to reset schedule {schedule_id} for retry: {e}")
        monitor.remove_from_dlq(task_id)
        return {
            "message": "Публикация поставлена на повтор",
            "carousel_id": carousel_id,
            "action": "republish",
        }

    monitor.remove_from_dlq(task_id)
    return {"message": "Задача удалена из очереди", "action": "removed"}


@router.delete("/dlq/{task_id}")
async def remove_dlq_task(
    task_id: str,
    user: dict = Depends(get_current_user),
):
    """Remove a task from the DLQ (acknowledge/dismiss)."""
    monitor = get_task_monitor()

    # Verify ownership
    entry = next((t for t in monitor._dlq if t.task_id == task_id and t.owner_id == user["id"]), None)
    if not entry:
        raise HTTPException(404, "Задача не найдена")

    monitor.remove_from_dlq(task_id)
    return {"message": "Удалено из очереди ошибок"}


@router.post("/dlq/clear")
async def clear_dlq(
    user: dict = Depends(get_current_user),
):
    """Clear all DLQ entries for this user."""
    monitor = get_task_monitor()
    monitor.clear_dlq(owner_id=user["id"])
    return {"message": "Очередь ошибок очищена"}
