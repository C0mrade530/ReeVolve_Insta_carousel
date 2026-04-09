"""
Session pool & proxy pool management API.
Provides monitoring and control for Instagram session rotation.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from app.api.deps import get_current_user, get_db
from app.services.publisher.session_pool import get_session_pool, get_proxy_pool
from app.utils.encryption import decrypt_data

logger = logging.getLogger(__name__)
router = APIRouter()


class AddProxyRequest(BaseModel):
    url: str  # socks5://user:pass@host:port
    label: str = ""


class UpdateProxiesRequest(BaseModel):
    proxies: list[AddProxyRequest]


# ═══════════════════════════════════════════════════════════════════
# SESSION POOL STATUS
# ═══════════════════════════════════════════════════════════════════

@router.get("/pool/status")
async def get_pool_status(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get current session pool + proxy pool status."""
    # Fetch user's accounts
    accounts_result = (
        db.table("instagram_accounts")
        .select("id, username, is_active, session_data, proxy, last_published_at")
        .eq("owner_id", user["id"])
        .execute()
    )
    accounts = accounts_result.data or []

    session_pool = get_session_pool()
    proxy_pool = get_proxy_pool()

    return {
        "session_pool": session_pool.get_pool_status(accounts),
        "proxy_pool": proxy_pool.get_status(),
    }


@router.post("/pool/pick")
async def pick_best_account(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Pick the best account for the next action (round-robin)."""
    accounts_result = (
        db.table("instagram_accounts")
        .select("id, username, is_active, session_data, proxy, last_published_at")
        .eq("owner_id", user["id"])
        .execute()
    )
    accounts = accounts_result.data or []
    if not accounts:
        raise HTTPException(400, "Нет Instagram-аккаунтов")

    session_pool = get_session_pool()
    best = session_pool.pick_account(accounts)

    if not best:
        raise HTTPException(503, "Все аккаунты на кулдауне или отключены")

    return {
        "account_id": best["id"],
        "username": best.get("username"),
        "has_proxy": bool(best.get("proxy")),
    }


@router.post("/pool/re-enable/{account_id}")
async def re_enable_account(
    account_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Re-enable a disabled account in the session pool."""
    # Verify ownership
    result = (
        db.table("instagram_accounts")
        .select("id")
        .eq("id", account_id)
        .eq("owner_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Аккаунт не найден")

    session_pool = get_session_pool()
    session_pool.re_enable(account_id)

    return {"message": "Аккаунт включён обратно в пул"}


@router.post("/pool/reset-daily")
async def reset_daily_counters(
    user: dict = Depends(get_current_user),
):
    """Reset daily usage counters for all accounts."""
    session_pool = get_session_pool()
    session_pool.reset_daily_counts()
    return {"message": "Счётчики сброшены"}


# ═══════════════════════════════════════════════════════════════════
# PROXY POOL MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

@router.post("/proxies/set")
async def set_proxy_pool(
    req: UpdateProxiesRequest,
    user: dict = Depends(get_current_user),
):
    """Set the proxy pool (replaces current proxies)."""
    proxy_pool = get_proxy_pool()
    proxy_pool.set_proxies([{"url": p.url, "label": p.label or p.url[:40]} for p in req.proxies])

    return {
        "message": f"Установлено {len(req.proxies)} прокси",
        "status": proxy_pool.get_status(),
    }


@router.get("/proxies/status")
async def get_proxy_status(
    user: dict = Depends(get_current_user),
):
    """Get proxy pool health status."""
    proxy_pool = get_proxy_pool()
    return proxy_pool.get_status()


@router.post("/proxies/check")
async def check_proxy_health(
    user: dict = Depends(get_current_user),
):
    """Test connectivity of all proxies in the pool."""
    import asyncio
    import time
    import aiohttp

    proxy_pool = get_proxy_pool()
    results = []

    async def check_one(proxy_info):
        url = proxy_info.get("url", "")
        start = time.monotonic()
        try:
            # Test via a lightweight HTTP request
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://httpbin.org/ip",
                    proxy=url,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    data = await resp.json()
                    proxy_pool.mark_success(url, latency_ms=elapsed_ms)
                    return {
                        "label": proxy_info.get("label", ""),
                        "status": "ok",
                        "latency_ms": elapsed_ms,
                        "ip": data.get("origin", "?"),
                    }
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            proxy_pool.mark_failed(url, str(e))
            return {
                "label": proxy_info.get("label", ""),
                "status": "error",
                "latency_ms": elapsed_ms,
                "error": str(e)[:100],
            }

    proxies = proxy_pool._proxies
    if not proxies:
        return {"message": "Нет прокси в пуле", "results": []}

    tasks = [check_one(p) for p in proxies]
    results = await asyncio.gather(*tasks)

    return {
        "message": f"Проверено {len(results)} прокси",
        "results": results,
        "pool_status": proxy_pool.get_status(),
    }
