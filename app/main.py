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
from app.routers import auth, events, health, matches, messages, safety, swipes, users

configure_logging()
settings = get_settings()

app = FastAPI(title="FindYourBuddy API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(events.router)
app.include_router(swipes.router)
app.include_router(matches.router)
app.include_router(messages.router)
app.include_router(safety.router)

app.mount(
    settings.media_base_url,
    StaticFiles(directory=settings.media_root, check_dir=False),
    name="media",
)

if __name__ == "__main__":
    uvicorn.run("app.main:app", reload=True)
