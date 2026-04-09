"""
Instagram Accounts CRUD API.
Real instagrapi login + encrypted session storage.
"""
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from supabase import Client

from app.api.deps import get_current_user, get_db
from app.utils.encryption import encrypt_data, decrypt_data
from app.services.publisher.instagram import get_publisher
from app.services.publisher.safety import get_safety_manager

logger = logging.getLogger(__name__)
router = APIRouter()


class AccountCreate(BaseModel):
    username: str = Field(..., max_length=100)
    password: str  # Instagram password — used for login, NOT stored raw
    proxy: str | None = None
    daily_post_limit: int = Field(default=3, ge=1, le=20)
    posting_schedule: list[int] = Field(default=[10, 14, 19], max_length=10)
    niche: str = Field(default="", max_length=200)
    city: str = Field(default="", max_length=100)
    brand_style: dict | None = None
    cta_text: str = Field(default="", max_length=300)
    cta_keyword: str = Field(default="", max_length=50)
    bio_offer: str = Field(default="", max_length=300)


class AccountUpdate(BaseModel):
    proxy: str | None = None
    is_active: bool | None = None
    daily_post_limit: int | None = None
    posting_schedule: list[int] | None = None
    niche: str | None = None
    city: str | None = None
    brand_style: dict | None = None
    speaker_photo_url: str | None = None
    cta_text: str | None = None
    cta_keyword: str | None = None
    bio_offer: str | None = None


class ReloginRequest(BaseModel):
    password: str
    proxy: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_account(
    req: AccountCreate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Add Instagram account.
    Performs REAL instagrapi login and stores encrypted session.
    """
    publisher = get_publisher()

    # Real Instagram login
    login_result = await publisher.login(
        username=req.username,
        password=req.password,
        proxy=req.proxy,
    )

    login_status = login_result.get("status")

    if login_status == "bad_password":
        raise HTTPException(
            status_code=401,
            detail=login_result.get("error", "Неверный пароль Instagram."),
        )

    if login_status == "ip_blocked":
        raise HTTPException(
            status_code=429,
            detail=login_result.get("error", "IP заблокирован Instagram. Используйте прокси или подождите."),
        )

    if login_status == "rate_limited":
        raise HTTPException(
            status_code=429,
            detail=login_result.get("error", "Слишком много попыток. Подождите 10-15 минут."),
        )

    # Session expiry: 30 days from now
    session_expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

    # Challenge WITH session → save account anyway (session likely valid)
    if login_status == "challenge_required" and login_result.get("settings"):
        session_encrypted = encrypt_data(login_result["settings"])
        data = {
            "owner_id": user["id"],
            "username": req.username,
            "session_data": session_encrypted,
            "proxy": req.proxy,
            "is_active": False,  # Mark as needs_confirmation
            "daily_post_limit": req.daily_post_limit,
            "posting_schedule": req.posting_schedule,
            "niche": req.niche,
            "city": req.city,
            "cta_text": req.cta_text,
            "cta_keyword": req.cta_keyword,
            "bio_offer": req.bio_offer,
            "session_expires_at": session_expires,
        }
        if req.brand_style:
            data["brand_style"] = req.brand_style

        result = db.table("instagram_accounts").insert(data).execute()
        account = result.data[0] if result.data else {}
        account.pop("session_data", None)

        logger.info(f"[Accounts] @{req.username} added (challenge pending) for user {user['id']}")
        return {
            **account,
            "login_status": "challenge_required",
            "message": "Аккаунт сохранён! Подтвердите вход в Instagram и нажмите «Я подтвердил».",
        }

    # Challenge WITHOUT session → can't save
    if login_status == "challenge_required":
        raise HTTPException(
            status_code=403,
            detail=login_result.get("error", "Instagram требует подтверждение. Откройте приложение Instagram."),
        )

    if login_status not in ("active",):
        raise HTTPException(
            status_code=400,
            detail=login_result.get("error", "Не удалось войти в Instagram"),
        )

    # Encrypt session for storage
    session_encrypted = encrypt_data(login_result.get("settings", {}))

    data = {
        "owner_id": user["id"],
        "username": req.username,
        "session_data": session_encrypted,
        "proxy": req.proxy,
        "is_active": True,
        "daily_post_limit": req.daily_post_limit,
        "posting_schedule": req.posting_schedule,
        "niche": req.niche,
        "city": req.city,
        "cta_text": req.cta_text,
        "cta_keyword": req.cta_keyword,
        "bio_offer": req.bio_offer,
        "session_expires_at": session_expires,
    }
    if req.brand_style:
        data["brand_style"] = req.brand_style

    result = db.table("instagram_accounts").insert(data).execute()
    account = result.data[0] if result.data else {}
    account.pop("session_data", None)

    logger.info(f"[Accounts] @{req.username} added for user {user['id']}")
    return {**account, "login_status": "active", "message": f"Аккаунт @{req.username} подключён!"}


@router.get("")
async def list_accounts(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """List all Instagram accounts for current user."""
    result = (
        db.table("instagram_accounts")
        .select("id, username, is_active, daily_post_limit, posting_schedule, niche, city, brand_style, speaker_photo_url, cta_text, cta_keyword, bio_offer, created_at, last_published_at, session_expires_at")
        .eq("owner_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/{account_id}")
async def get_account(
    account_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    result = (
        db.table("instagram_accounts")
        .select("id, username, is_active, daily_post_limit, posting_schedule, niche, city, brand_style, speaker_photo_url, cta_text, cta_keyword, bio_offer, proxy, created_at, last_published_at")
        .eq("id", account_id)
        .eq("owner_id", user["id"])
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Account not found")
    return result.data


@router.patch("/{account_id}")
async def update_account(
    account_id: str,
    req: AccountUpdate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")

    result = (
        db.table("instagram_accounts")
        .update(data)
        .eq("id", account_id)
        .eq("owner_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Account not found")

    account = result.data[0]
    account.pop("session_data", None)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    result = (
        db.table("instagram_accounts")
        .delete()
        .eq("id", account_id)
        .eq("owner_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Account not found")


@router.post("/{account_id}/confirm-challenge")
async def confirm_challenge(
    account_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    User confirmed login in Instagram app.
    Activate the account, verify session actually works, and try a real API call.
    """
    account_result = (
        db.table("instagram_accounts")
        .select("username, session_data, proxy, is_active")
        .eq("id", account_id)
        .eq("owner_id", user["id"])
        .single()
        .execute()
    )
    if not account_result.data:
        raise HTTPException(status_code=404, detail="Account not found")

    account = account_result.data

    # Try to verify the session actually works after challenge confirmation
    publisher = get_publisher()
    verified = False
    try:
        session_data = decrypt_data(account["session_data"])
        client = await publisher.login_by_session(
            session_data={"settings": session_data},
            proxy=account.get("proxy"),
        )
        if client:
            # Try a real API call to verify session is unblocked
            try:
                import asyncio
                info = await asyncio.wait_for(
                    asyncio.to_thread(client.account_info),
                    timeout=15.0,
                )
                verified = True
                logger.info(f"[Accounts] @{account['username']} session verified after challenge! user_id={client.user_id}")

                # Save the refreshed settings (may have updated tokens)
                new_settings = client.get_settings()
                new_encrypted = encrypt_data(new_settings)
                db.table("instagram_accounts").update({
                    "session_data": new_encrypted,
                    "is_active": True,
                    "session_expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                }).eq("id", account_id).execute()

            except Exception as e:
                logger.warning(f"[Accounts] @{account['username']} session still challenged after confirm: {e}")
    except Exception as e:
        logger.warning(f"[Accounts] @{account['username']} session decrypt/load failed: {e}")

    if not verified:
        # Session is still broken — just activate and warn
        db.table("instagram_accounts").update({
            "is_active": True,
        }).eq("id", account_id).execute()

        logger.warning(f"[Accounts] @{account['username']} activated but session NOT verified")
        return {
            "status": "active",
            "message": f"@{account['username']} активирован, но сессия может быть неактивна. Попробуйте «Ре-логин» с паролем и прокси.",
            "warning": "session_unverified",
        }

    return {
        "status": "active",
        "message": f"@{account['username']} активирован и проверен!",
    }


@router.post("/{account_id}/verify")
async def verify_session(
    account_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Check if Instagram session is still valid."""
    # Get account with session
    account_result = (
        db.table("instagram_accounts")
        .select("username, session_data, proxy")
        .eq("id", account_id)
        .eq("owner_id", user["id"])
        .single()
        .execute()
    )
    if not account_result.data:
        raise HTTPException(status_code=404, detail="Account not found")

    account = account_result.data

    try:
        session_data = decrypt_data(account["session_data"])
    except Exception as e:
        logger.warning(f"[Accounts] Session decrypt failed for account {account_id}: {e}")
        return {"status": "invalid", "message": "Сессия повреждена. Нужна переавторизация."}

    publisher = get_publisher()
    is_valid = await publisher.check_session(
        session_data={"settings": session_data},
        proxy=account.get("proxy"),
    )

    if is_valid:
        return {"status": "active", "message": f"Сессия @{account['username']} активна"}
    else:
        # Mark as inactive
        db.table("instagram_accounts").update({"is_active": False}).eq("id", account_id).execute()
        return {"status": "expired", "message": "Сессия истекла. Нужна переавторизация."}


@router.post("/{account_id}/relogin")
async def relogin(
    account_id: str,
    req: ReloginRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Re-authenticate Instagram account with new password."""
    account_result = (
        db.table("instagram_accounts")
        .select("username")
        .eq("id", account_id)
        .eq("owner_id", user["id"])
        .single()
        .execute()
    )
    if not account_result.data:
        raise HTTPException(status_code=404, detail="Account not found")

    username = account_result.data["username"]
    publisher = get_publisher()

    login_result = await publisher.login(
        username=username,
        password=req.password,
        proxy=req.proxy,
    )

    login_status = login_result.get("status")

    if login_status == "bad_password":
        raise HTTPException(status_code=401, detail="Неверный пароль.")

    if login_status == "ip_blocked":
        raise HTTPException(
            status_code=429,
            detail=login_result.get("error", "IP заблокирован Instagram. Используйте прокси или подождите."),
        )

    if login_status == "rate_limited":
        raise HTTPException(
            status_code=429,
            detail=login_result.get("error", "Слишком много попыток. Подождите 10-15 минут."),
        )

    relogin_expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

    # Challenge WITH session → save session anyway (often valid after user confirms)
    if login_status == "challenge_required" and login_result.get("settings"):
        session_encrypted = encrypt_data(login_result["settings"])
        db.table("instagram_accounts").update({
            "session_data": session_encrypted,
            "is_active": False,  # Needs confirmation
            "proxy": req.proxy,
            "session_expires_at": relogin_expires,
        }).eq("id", account_id).execute()

        logger.info(f"[Accounts] @{username} relogin: challenge, session saved")
        return {
            "status": "challenge_required",
            "message": "Подтвердите вход в Instagram и нажмите «Я подтвердил».",
        }

    if login_status == "challenge_required":
        raise HTTPException(
            status_code=403,
            detail=login_result.get("error", "Instagram требует подтверждение."),
        )

    if login_status != "active":
        raise HTTPException(status_code=400, detail=login_result.get("error", "Ошибка входа"))

    # Update session
    session_encrypted = encrypt_data(login_result.get("settings", {}))
    db.table("instagram_accounts").update({
        "session_data": session_encrypted,
        "is_active": True,
        "proxy": req.proxy,
        "session_expires_at": relogin_expires,
    }).eq("id", account_id).execute()

    logger.info(f"[Accounts] @{username} re-logged in successfully")
    return {"status": "active", "message": f"@{username} переавторизован!"}


@router.get("/{account_id}/health")
async def account_health(
    account_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """
    Get account health score and safety recommendations.
    Shows risk level, post limits, and suggestions.
    """
    from datetime import date

    account_result = (
        db.table("instagram_accounts")
        .select("id, username, is_active, proxy, created_at, last_published_at, session_expires_at")
        .eq("id", account_id)
        .eq("owner_id", user["id"])
        .single()
        .execute()
    )
    if not account_result.data:
        raise HTTPException(status_code=404, detail="Account not found")

    account = account_result.data
    created = account.get("created_at", "")

    # Calculate account age
    account_age_days = 30
    if created:
        try:
            from dateutil.parser import parse as parse_dt
            created_dt = parse_dt(created)
            account_age_days = (datetime.utcnow() - created_dt.replace(tzinfo=None)).days
        except Exception as e:
            logger.warning(f"[Accounts] Failed to parse account created_at date: {e}")

    # Count today's posts
    posts_today = 0
    posts_this_week = 0
    try:
        today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
        week_start = (datetime.utcnow() - timedelta(days=7)).isoformat()

        today_result = (
            db.table("carousels")
            .select("id", count="exact")
            .eq("status", "published")
            .gte("published_at", today_start)
            .execute()
        )
        posts_today = today_result.count or 0

        week_result = (
            db.table("carousels")
            .select("id", count="exact")
            .eq("status", "published")
            .gte("published_at", week_start)
            .execute()
        )
        posts_this_week = week_result.count or 0
    except Exception as e:
        logger.warning(f"[Accounts] Failed to count posts for health check: {e}")

    safety = get_safety_manager()
    health = safety.calculate_health_score(
        posts_today=posts_today,
        posts_this_week=posts_this_week,
        account_age_days=account_age_days,
        has_proxy=bool(account.get("proxy")),
    )

    # Add publishing check
    last_pub = None
    if account.get("last_published_at"):
        try:
            from dateutil.parser import parse as parse_dt
            last_pub = parse_dt(account["last_published_at"]).replace(tzinfo=None)
        except Exception as e:
            logger.warning(f"[Accounts] Failed to parse last_published_at: {e}")

    can_pub = safety.can_publish(
        username=account["username"],
        last_published_at=last_pub,
        posts_today=posts_today,
    )

    # Session freshness check
    session_status = "unknown"
    session_expires_at = account.get("session_expires_at")
    days_until_expiry = None
    if session_expires_at:
        try:
            from dateutil.parser import parse as parse_dt
            expires_dt = parse_dt(session_expires_at)
            now = datetime.now(timezone.utc)
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            delta = expires_dt - now
            days_until_expiry = delta.days
            if days_until_expiry < 0:
                session_status = "expired"
            elif days_until_expiry < 3:
                session_status = "expiring_soon"
            else:
                session_status = "fresh"
        except Exception as e:
            logger.warning(f"[Accounts] Failed to parse session_expires_at: {e}")

    return {
        "username": account["username"],
        "is_active": account["is_active"],
        "health": health,
        "can_publish": can_pub,
        "session": {
            "status": session_status,
            "expires_at": session_expires_at,
            "days_until_expiry": days_until_expiry,
        },
        "stats": {
            "posts_today": posts_today,
            "posts_this_week": posts_this_week,
            "account_age_days": account_age_days,
        },
    }
