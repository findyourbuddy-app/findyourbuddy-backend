import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
import uvicorn
from fastapi import FastAPI, Request, responses
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.core.scheduler import start_scheduler
from app.routers import (
    admin,
    auth,
    bookmarks,
    calls,
    double_buddy,
    events,
    geocoding,
    health,
    internal,
    matches,
    messages,
    notifications,
    safety,
    subscriptions,
    swipes,
    universities,
    users,
)

configure_logging()
settings = get_settings()
_logger = logging.getLogger(__name__)

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
    )

_is_production = settings.environment == "production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.scheduler import run_cleanup_jobs

    if start_scheduler() is not None:
        try:
            run_cleanup_jobs()
        except Exception:
            _logger.exception("Startup cleanup jobs failed")

    yield


app = FastAPI(
    title="FindYourBuddy API",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

cors_allowed_origins = [
    origin.strip()
    for origin in settings.cors_allowed_origins.split(",")
    if origin.strip() and origin.strip() != "*"
]
cors_origin_regex = (
    r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.0\.\d+\.\d+)(:\d+)?"
    if not _is_production
    else r"https://([\w-]+\.)?findyourbuddy\.dev"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if _is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    _logger.error("Unhandled server error: %s", exc, exc_info=True)
    if settings.admin_alert_email:
        from app.core.email import send_plain_email
        subject = f"🚨 [KRİTİK ALARM] FindYourBuddy Sunucu Hatası (500) - {request.url.path}"
        body = (
            f"Kritik Sunucu Hatası Algılandı!\n\n"
            f"Endpoint: {request.method} {request.url.path}\n"
            f"İstemci IP: {request.client.host if request.client else 'Bilinmiyor'}\n"
            f"Hata Detayı: {str(exc)}\n\n"
            f"Lütfen sunucu loglarını ve monitoring panosunu inceleyin."
        )
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, send_plain_email, settings.admin_alert_email, subject, body)
    return responses.JSONResponse(
        status_code=500,
        content={"detail": "Sunucu tarafında bir hata oluştu. Lütfen tekrar deneyin."},
    )


routers = [
    health.router,
    auth.router,
    users.router,
    events.router,
    swipes.router,
    matches.router,
    messages.router,
    notifications.router,
    safety.router,
    bookmarks.router,
    admin.router,
    subscriptions.router,
    internal.router,
    geocoding.router,
    universities.router,
    double_buddy.router,
    calls.router,
]

for r in routers:
    app.include_router(r)

from pathlib import Path

media_dir = Path(settings.media_root).resolve()
media_dir.mkdir(parents=True, exist_ok=True)

@app.get(f"{settings.media_base_url}/{{file_path:path}}")
async def serve_media_file(file_path: str):
    target = (media_dir / file_path).resolve()
    if not str(target).startswith(str(media_dir)):
        return responses.JSONResponse(status_code=403, content={"detail": "Forbidden"})

    if not target.exists() or not target.is_file():
        for alt_ext in [".jpg", ".png", ".webp", ".JPG", ".PNG"]:
            alt = media_dir / f"{file_path}{alt_ext}"
            if alt.exists() and alt.is_file():
                target = alt
                break

    if not target.exists() or not target.is_file():
        return responses.JSONResponse(status_code=404, content={"detail": "File not found"})

    media_type = "image/jpeg"
    try:
        with target.open("rb") as f:
            header = f.read(16)
        if header.startswith(b"\x89PNG"):
            media_type = "image/png"
        elif header.startswith(b"\xff\xd8\xff"):
            media_type = "image/jpeg"
        elif header.startswith(b"RIFF") and b"WEBP" in header:
            media_type = "image/webp"
        elif header.startswith(b"GIF8"):
            media_type = "image/gif"
        elif target.suffix.lower() in (".m4a", ".mp4", ".mp3", ".wav"):
            media_type = "audio/mp4" if target.suffix.lower() in (".m4a", ".mp4") else "audio/mpeg"
    except Exception:
        pass

    return responses.FileResponse(
        path=str(target),
        media_type=media_type,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=86400",
        },
    )

app.mount(
    settings.media_base_url,
    StaticFiles(directory=str(media_dir), check_dir=False),
    name="media",
)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
