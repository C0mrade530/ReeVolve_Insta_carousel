"""Tests for task monitor and DLQ."""
from app.services.task_monitor import TaskMonitor, TaskType, FailedTask


class TestTaskMonitor:
    def test_start_and_complete_task(self):
        monitor = TaskMonitor()
        monitor.start_task("t1", TaskType.GENERATION, "user-1")
        assert len(monitor.get_running()) == 1
        monitor.complete_task("t1")
        assert len(monitor.get_running()) == 0
        assert monitor.get_stats()["total_succeeded"] == 1

    def test_fail_task_adds_to_dlq(self):
        monitor = TaskMonitor()
        monitor.start_task("t1", TaskType.PUBLISHING, "user-1")
        failed = monitor.fail_task("t1", "connection timeout")
        assert failed.retry_count == 1
        dlq = monitor.get_dlq()
        assert len(dlq) == 1
        assert dlq[0]["task_id"] == "t1"

    def test_fail_task_increments_retry_count(self):
        monitor = TaskMonitor()
        monitor.start_task("t1", TaskType.GENERATION, "user-1")
        monitor.fail_task("t1", "err1")
        monitor.start_task("t1", TaskType.GENERATION, "user-1")
        failed = monitor.fail_task("t1", "err2")
        assert failed.retry_count == 2

    def test_fail_task_marks_dead_after_max_retries(self):
        monitor = TaskMonitor()
        for i in range(TaskMonitor.MAX_RETRIES):
            monitor.start_task("t1", TaskType.GENERATION, "user-1")
            monitor.fail_task("t1", f"err{i}")
        stats = monitor.get_stats()
        assert stats["total_dead"] >= 1

    def test_get_dlq_filters_by_owner(self):
        monitor = TaskMonitor()
        monitor.start_task("t1", TaskType.GENERATION, "user-1")
        monitor.fail_task("t1", "err")
        monitor.start_task("t2", TaskType.GENERATION, "user-2")
        monitor.fail_task("t2", "err")
        dlq = monitor.get_dlq(owner_id="user-1")
        assert len(dlq) == 1
        assert dlq[0]["owner_id"] == "user-1"

    def test_remove_from_dlq(self):
        monitor = TaskMonitor()
        monitor.start_task("t1", TaskType.GENERATION, "user-1")
        monitor.fail_task("t1", "err")
        assert monitor.remove_from_dlq("t1") is True
        assert len(monitor.get_dlq()) == 0

    def test_remove_from_dlq_nonexistent(self):
        monitor = TaskMonitor()
        assert monitor.remove_from_dlq("nonexistent") is False

    def test_clear_dlq(self):
        monitor = TaskMonitor()
        for i in range(5):
            monitor.start_task(f"t{i}", TaskType.GENERATION, "user-1")
            monitor.fail_task(f"t{i}", "err")
        monitor.clear_dlq()
        assert len(monitor.get_dlq()) == 0

    def test_clear_dlq_by_owner(self):
        monitor = TaskMonitor()
        monitor.start_task("t1", TaskType.GENERATION, "user-1")
        monitor.fail_task("t1", "err")
        monitor.start_task("t2", TaskType.GENERATION, "user-2")
        monitor.fail_task("t2", "err")
        monitor.clear_dlq(owner_id="user-1")
        dlq = monitor.get_dlq()
        assert len(dlq) == 1
        assert dlq[0]["owner_id"] == "user-2"

    def test_get_running_filters_by_owner(self):
        monitor = TaskMonitor()
        monitor.start_task("t1", TaskType.GENERATION, "user-1")
        monitor.start_task("t2", TaskType.PUBLISHING, "user-2")
        running = monitor.get_running(owner_id="user-1")
        assert len(running) == 1

    def test_stats_counters(self):
        monitor = TaskMonitor()
        monitor.start_task("t1", TaskType.GENERATION, "user-1")
        monitor.complete_task("t1")
        monitor.start_task("t2", TaskType.GENERATION, "user-1")
        monitor.fail_task("t2", "err")
        stats = monitor.get_stats()
        assert stats["total_started"] == 2
        assert stats["total_succeeded"] == 1
        assert stats["total_failed"] == 1


class TestFailedTask:
    def test_to_dict(self):
        ft = FailedTask(
            task_type=TaskType.GENERATION,
            task_id="t1",
            owner_id="user-1",
            error="test error",
        )
        d = ft.to_dict()
        assert d["task_id"] == "t1"
        assert d["error"] == "test error"
        assert "created_at" in d
