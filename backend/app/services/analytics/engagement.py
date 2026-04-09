"""
Engagement analytics service.
"""
from app.database import get_supabase_admin


async def collect_stats_for_account(account_id: str):
    """Collect engagement stats for all published carousels of an account."""
    db = get_supabase_admin()

    carousels = (
        db.table("carousels")
        .select("id, instagram_post_id")
        .eq("account_id", account_id)
        .eq("status", "published")
        .not_.is_("instagram_post_id", "null")
        .execute()
    )

    # TODO: For each carousel, fetch insights via apigram
    # and update engagement JSON in DB

    return {"updated": len(carousels.data)}
