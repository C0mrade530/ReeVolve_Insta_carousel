"""
Celery application configuration.
"""
from celery import Celery
from celery.schedules import crontab
import os

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "realpost",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.tasks.parsing",
        "app.tasks.generation",
        "app.tasks.publishing",
        "app.tasks.monitoring",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Periodic tasks (Celery Beat)
celery_app.conf.beat_schedule = {
    # Parsing
    "parse-cian-every-4h": {
        "task": "app.tasks.parsing.parse_cian_listings",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    "parse-avito-every-4h": {
        "task": "app.tasks.parsing.parse_avito_listings",
        "schedule": crontab(minute=30, hour="*/4"),
    },
    "parse-yandex-every-6h": {
        "task": "app.tasks.parsing.parse_yandex_listings",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "evaluate-featured-daily": {
        "task": "app.tasks.parsing.evaluate_featured_daily",
        "schedule": crontab(minute=0, hour=8),
    },
    "cleanup-expired-listings": {
        "task": "app.tasks.parsing.cleanup_expired_listings",
        "schedule": crontab(minute=0, hour=3),
    },

    # Generation
    "generate-daily-content": {
        "task": "app.tasks.generation.generate_daily_content",
        "schedule": crontab(minute=0, hour=6),
    },

    # Publishing
    "check-and-publish": {
        "task": "app.tasks.publishing.check_and_publish",
        "schedule": 60.0,  # every minute
    },

    # Monitoring
    "collect-engagement": {
        "task": "app.tasks.monitoring.collect_engagement_stats",
        "schedule": crontab(minute=0, hour="*/2"),
    },
    "session-health-check": {
        "task": "app.tasks.monitoring.session_health_check",
        "schedule": crontab(minute=0, hour="*/6"),
    },
}
