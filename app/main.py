import sentry_sdk
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    users,
)

configure_logging()
settings = get_settings()

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
    )

_is_production = settings.environment == "production"
app = FastAPI(
    title="FindYourBuddy API",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

cors_origin_regex = (
    r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.0\.\d+\.\d+)(:\d+)?"
    if not _is_production
    else r"https://.*\.findyourbuddy\.dev|https://findyourbuddy\.dev"
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
]

for r in routers:
    app.include_router(r)
    app.include_router(r, prefix="/api")

app.mount(
    settings.media_base_url,
    StaticFiles(directory=settings.media_root, check_dir=False),
    name="media",
)


@app.on_event("startup")
def _start_background_jobs() -> None:
    from app.core.scheduler import run_cleanup_jobs
    from app.database import Base, engine
    from sqlalchemy import text, inspect

    try:
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            inspector = inspect(engine)
            if "users" in inspector.get_table_names():
                cols = {c["name"] for c in inspector.get_columns("users")}
                if "hidden_fields" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN hidden_fields JSON DEFAULT '[]'"))
                    conn.commit()
                if "languages_spoken" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN languages_spoken JSON DEFAULT '[]'"))
                    conn.commit()
    except Exception:
        pass

    start_scheduler()
    try:
        run_cleanup_jobs()
    except Exception:
        pass


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
