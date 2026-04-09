import os
import uuid
import logging
from pathlib import Path
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pythonjsonlogger import jsonlogger

# --- Structured JSON logging ---
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get("")
        return True


handler = logging.StreamHandler()
handler.setFormatter(jsonlogger.JsonFormatter(
    "%(asctime)s %(name)s %(levelname)s %(message)s %(request_id)s"
))
handler.addFilter(RequestIdFilter())
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.middleware.rate_limit import RateLimitMiddleware

from app.api import auth, accounts, carousels, scheduler, analytics, expert, competitors, sessions, monitoring, brand, behavior, design_settings
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="ReevolveAI",
    description="Instagram AI — автогенерация и публикация каруселей для экспертов",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Request ID middleware ---
class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

app.add_middleware(RequestIdMiddleware)

# --- Rate limiting ---
app.add_middleware(RateLimitMiddleware, enable=True)

# --- Global error handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = logging.getLogger("app.error")
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера. Попробуйте позже."},
    )

# --- Static media serving (slide images) ---
# Resolve relative path from project root (where uvicorn is run)
media_path = str(Path(settings.media_storage_path).resolve())
os.makedirs(media_path, exist_ok=True)
app.mount("/media", StaticFiles(directory=media_path), name="media")

# --- Routers ---
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Accounts"])
app.include_router(carousels.router, prefix="/api/carousels", tags=["Carousels"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["Scheduler"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(expert.router, prefix="/api/expert-template", tags=["Expert Template"])
app.include_router(competitors.router, prefix="/api/competitors", tags=["Competitors"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["Monitoring"])
app.include_router(brand.router, prefix="/api/brand", tags=["Brand Profile"])
app.include_router(behavior.router, prefix="/api/behavior", tags=["Behavior"])
app.include_router(design_settings.router, prefix="/api/design-settings", tags=["Design Settings"])


@app.get("/api/health")
async def health_check():
    import asyncio
    checks = {"db": False, "storage": False, "llm": False}
    overall = "ok"

    # Check Supabase DB
    try:
        from app.database import get_supabase_admin
        db = get_supabase_admin()
        await asyncio.to_thread(
            lambda: db.table("instagram_accounts").select("id").limit(1).execute()
        )
        checks["db"] = True
    except Exception as e:
        logger = logging.getLogger("app.health")
        logger.warning(f"[Health] DB check failed: {e}")
        overall = "unhealthy"

    # Check media storage path is writable
    try:
        test_file = Path(settings.media_storage_path).resolve() / ".health_check"
        await asyncio.to_thread(lambda: test_file.write_text("ok"))
        await asyncio.to_thread(lambda: test_file.unlink())
        checks["storage"] = True
    except Exception as e:
        logger = logging.getLogger("app.health")
        logger.warning(f"[Health] Storage check failed: {e}")
        if overall != "unhealthy":
            overall = "unhealthy"

    # Check CometAPI (LLM) — optional, degraded if unavailable
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.openai_base_url}/models",
                                     headers={"Authorization": f"Bearer {settings.openai_api_key}"})
            checks["llm"] = resp.status_code == 200
        if not checks["llm"] and overall == "ok":
            overall = "degraded"
    except Exception as e:
        logging.getLogger("app.health").debug(f"[Health] LLM check failed: {e}")
        if overall == "ok":
            overall = "degraded"

    status_code = 200 if overall in ("ok", "degraded") else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": overall, "version": "0.2.0", "checks": checks},
    )
