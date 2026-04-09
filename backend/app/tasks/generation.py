"""
Celery tasks for carousel generation.
"""
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.generation.generate_topic_carousel_task")
def generate_topic_carousel_task(carousel_id: str):
    """Generate a topic carousel (7+1 slides) using GPT 5.2 + Pillow."""
    # TODO: Implement full pipeline
    # 1. Get carousel from DB
    # 2. Get account settings (niche, city, brand_style)
    # 3. Call GPT 5.2 for text generation
    # 4. Generate slides with Pillow
    # 5. Save slides to storage
    # 6. Update carousel in DB with slides and status='ready'
    print(f"[Generator] Generating topic carousel {carousel_id}...")
    return {"status": "ok", "carousel_id": carousel_id}


@celery_app.task(name="app.tasks.generation.generate_property_carousel_task")
def generate_property_carousel_task(carousel_id: str):
    """Generate a property carousel (3-5 slides)."""
    # TODO: Implement full pipeline
    print(f"[Generator] Generating property carousel {carousel_id}...")
    return {"status": "ok", "carousel_id": carousel_id}


@celery_app.task(name="app.tasks.generation.generate_daily_content")
def generate_daily_content():
    """
    Daily at 06:00 MSK: generate carousels for all active accounts.
    Mix: at least 1 property + remaining topic carousels.
    """
    # TODO: Implement
    # 1. Get all active accounts
    # 2. For each account:
    #    a. Check daily_post_limit
    #    b. Get featured listings
    #    c. Generate 1 property carousel if available
    #    d. Generate topic carousels for remaining slots
    #    e. Schedule publications based on posting_schedule
    print("[Generator] Daily content generation started...")
    return {"status": "ok"}
