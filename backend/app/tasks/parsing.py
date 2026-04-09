"""
Celery tasks for property listing parsing.
"""
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.parsing.parse_cian_listings")
def parse_cian_listings():
    """Parse CIAN listings every 4 hours."""
    # TODO: Implement CIAN parser
    print("[Parser] CIAN parsing started...")
    return {"status": "ok", "source": "cian", "found": 0}


@celery_app.task(name="app.tasks.parsing.parse_avito_listings")
def parse_avito_listings():
    """Parse Avito listings every 4 hours."""
    # TODO: Implement Avito parser
    print("[Parser] Avito parsing started...")
    return {"status": "ok", "source": "avito", "found": 0}


@celery_app.task(name="app.tasks.parsing.parse_yandex_listings")
def parse_yandex_listings():
    """Parse Yandex listings every 6 hours."""
    # TODO: Implement Yandex parser
    print("[Parser] Yandex parsing started...")
    return {"status": "ok", "source": "yandex", "found": 0}


@celery_app.task(name="app.tasks.parsing.evaluate_featured_daily")
def evaluate_featured_daily():
    """Select 'apartment of the day' based on special conditions."""
    # TODO: Implement evaluator logic
    print("[Parser] Evaluating featured listings...")
    return {"status": "ok", "featured": 0}


@celery_app.task(name="app.tasks.parsing.cleanup_expired_listings")
def cleanup_expired_listings():
    """Remove expired/inactive listings."""
    # TODO: Implement cleanup
    print("[Parser] Cleaning up expired listings...")
    return {"status": "ok", "removed": 0}
