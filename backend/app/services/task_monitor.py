"""
Task monitoring + Dead Letter Queue (DLQ) for failed tasks.
Catches generation/publishing failures, stores them for retry or inspection.
In-memory DLQ with Supabase persistence via failed_tasks table.
"""
import logging
import traceback
import threading
from datetime import datetime
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    GENERATION = "generation"
    PUBLISHING = "publishing"
    SCRAPING = "scraping"
    ANALYSIS = "analysis"
    BATCH = "batch"


class TaskStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD = "dead"  # In DLQ, max retries exceeded


class FailedTask:
    """Represents a failed task in the DLQ."""

    def __init__(
        self,
        task_type: TaskType,
        task_id: str,
        owner_id: str,
        error: str,
        context: dict | None = None,
        traceback_str: str = "",
        retry_count: int = 0,
    ):
        self.task_type = task_type
        self.task_id = task_id
        self.owner_id = owner_id
        self.error = error
        self.context = context or {}
        self.traceback_str = traceback_str
        self.retry_count = retry_count
        self.created_at = datetime.utcnow()
        self.last_attempt_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "task_id": self.task_id,
            "owner_id": self.owner_id,
            "error": self.error,
            "context": self.context,
            "traceback": self.traceback_str[:2000],
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat(),
            "last_attempt_at": self.last_attempt_at.isoformat(),
        }


class TaskMonitor:
    """
    Central task monitor with DLQ.
    Tracks running tasks, records failures, supports retry.
    """

    MAX_RETRIES = 3
    DLQ_MAX_SIZE = 500  # In-memory limit

    def __init__(self):
        self._lock = threading.Lock()
        self._running: dict[str, dict] = {}  # task_id -> {type, owner_id, started_at}
        self._dlq: deque[FailedTask] = deque(maxlen=self.DLQ_MAX_SIZE)
        self._stats = {
            "total_started": 0,
            "total_succeeded": 0,
            "total_failed": 0,
            "total_retried": 0,
            "total_dead": 0,
        }

    def start_task(self, task_id: str, task_type: TaskType, owner_id: str, context: dict | None = None):
        """Register a task as started. Thread-safe."""
        with self._lock:
            self._running[task_id] = {
                "type": task_type,
                "owner_id": owner_id,
                "started_at": datetime.utcnow(),
                "context": context or {},
            }
            self._stats["total_started"] += 1
        logger.info(f"[TaskMonitor] Started {task_type} task {task_id}")

    def complete_task(self, task_id: str):
        """Mark task as completed successfully. Thread-safe."""
        with self._lock:
            if task_id in self._running:
                del self._running[task_id]
            self._stats["total_succeeded"] += 1
        logger.info(f"[TaskMonitor] Completed task {task_id}")

    def fail_task(
        self,
        task_id: str,
        error: Exception | str,
        context: dict | None = None,
    ) -> FailedTask:
        """
        Record task failure. Thread-safe.
        If under max retries, marks for retry.
        If max retries exceeded, moves to DLQ as 'dead'.
        """
        error_str = str(error)
        if isinstance(error, Exception) and error.__traceback__:
            tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        else:
            tb = ""

        with self._lock:
            task_info = self._running.pop(task_id, {})

            # Find existing DLQ entry for this task
            existing = next((t for t in self._dlq if t.task_id == task_id), None)
            retry_count = (existing.retry_count + 1) if existing else 1

            failed = FailedTask(
                task_type=task_info.get("type", TaskType.GENERATION),
                task_id=task_id,
                owner_id=task_info.get("owner_id", context.get("owner_id", "") if context else ""),
                error=error_str,
                context={**task_info.get("context", {}), **(context or {})},
                traceback_str=tb,
                retry_count=retry_count,
            )

            # Remove old entry if exists
            self._dlq = deque(
                (t for t in self._dlq if t.task_id != task_id),
                maxlen=self.DLQ_MAX_SIZE,
            )
            self._dlq.append(failed)

            self._stats["total_failed"] += 1

            if retry_count >= self.MAX_RETRIES:
                self._stats["total_dead"] += 1

        if retry_count >= self.MAX_RETRIES:
            logger.error(f"[TaskMonitor] Task {task_id} DEAD after {retry_count} retries: {error_str}")
        else:
            logger.warning(f"[TaskMonitor] Task {task_id} failed (attempt {retry_count}): {error_str}")

        return failed

    def get_dlq(self, owner_id: str | None = None, limit: int = 50) -> list[dict]:
        """Get DLQ entries, optionally filtered by owner. Thread-safe."""
        with self._lock:
            entries = list(self._dlq)
        if owner_id:
            entries = [t for t in entries if t.owner_id == owner_id]
        # Most recent first
        entries.sort(key=lambda t: t.last_attempt_at, reverse=True)
        return [t.to_dict() for t in entries[:limit]]

    def remove_from_dlq(self, task_id: str) -> bool:
        """Remove a task from the DLQ (e.g., after manual resolution). Thread-safe."""
        with self._lock:
            before = len(self._dlq)
            self._dlq = deque(
                (t for t in self._dlq if t.task_id != task_id),
                maxlen=self.DLQ_MAX_SIZE,
            )
            removed = len(self._dlq) < before
        if removed:
            logger.info(f"[TaskMonitor] Removed {task_id} from DLQ")
        return removed

    def clear_dlq(self, owner_id: str | None = None):
        """Clear DLQ, optionally for a specific owner. Thread-safe."""
        with self._lock:
            if owner_id:
                self._dlq = deque(
                    (t for t in self._dlq if t.owner_id != owner_id),
                    maxlen=self.DLQ_MAX_SIZE,
                )
            else:
                self._dlq.clear()
        logger.info(f"[TaskMonitor] DLQ cleared{' for ' + owner_id if owner_id else ''}")

    def get_running(self, owner_id: str | None = None) -> list[dict]:
        """Get currently running tasks. Thread-safe."""
        with self._lock:
            now = datetime.utcnow()
            result = []
            for tid, info in self._running.items():
                if owner_id and info.get("owner_id") != owner_id:
                    continue
                elapsed = (now - info["started_at"]).total_seconds()
                result.append({
                    "task_id": tid,
                    "type": info["type"],
                    "started_at": info["started_at"].isoformat(),
                    "elapsed_seconds": round(elapsed),
                    "context": info.get("context", {}),
                })
        return result

    def get_stats(self) -> dict:
        """Get overall monitoring stats. Thread-safe."""
        with self._lock:
            return {
                **self._stats,
                "currently_running": len(self._running),
                "dlq_size": len(self._dlq),
            }

    async def persist_to_db(self, db, task: FailedTask):
        """Optionally persist failed task to Supabase for durability."""
        try:
            db.table("failed_tasks").upsert({
                "task_id": task.task_id,
                "task_type": task.task_type,
                "owner_id": task.owner_id,
                "error": task.error[:1000],
                "context": task.context,
                "traceback": task.traceback_str[:2000],
                "retry_count": task.retry_count,
                "status": "dead" if task.retry_count >= self.MAX_RETRIES else "failed",
                "created_at": task.created_at.isoformat(),
                "last_attempt_at": task.last_attempt_at.isoformat(),
            }, on_conflict="task_id").execute()
        except Exception as e:
            # Table may not exist yet — that's ok
            logger.debug(f"[TaskMonitor] DB persist skipped: {e}")


# Thread-safe singleton
_monitor = None
_monitor_lock = threading.Lock()


def get_task_monitor() -> TaskMonitor:
    global _monitor
    if _monitor is None:
        with _monitor_lock:
            if _monitor is None:  # Double-check locking
                _monitor = TaskMonitor()
    return _monitor
