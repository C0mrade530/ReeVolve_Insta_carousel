"""
Celery tasks for monitoring — engagement collection, session health.
"""
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.monitoring.collect_engagement_stats")
def collect_engagement_stats():
    """Collect likes/comments for published carousels every 2 hours."""
    # TODO: Implement via apigram media_info
    print("[Monitor] Collecting engagement stats...")
    return {"status": "ok", "updated": 0}


@celery_app.task(name="app.tasks.monitoring.session_health_check")
def session_health_check():
    """Check all Instagram sessions are valid every 6 hours."""
    # TODO: Implement
    # 1. Get all active accounts
    # 2. For each: try login_by_session
    # 3. If failed: mark is_active=False, notify admin
    print("[Monitor] Session health check...")
    return {"status": "ok", "checked": 0, "failed": 0}
