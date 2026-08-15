import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.services.auth_service import delete_expired_reset_tokens
from app.services.event_service import delete_expired_events

logger = logging.getLogger(__name__)


def run_cleanup_jobs(db: Session | None = None) -> dict[str, int]:
    """Runs all periodic data-hygiene jobs. Accepts an optional session for
    testability; opens/closes its own session when called from the scheduler."""
    settings = get_settings()
    owns_session = db is None
    session = db if db is not None else SessionLocal()
    try:
        deleted_events = delete_expired_events(session, settings.event_retention_days)
        deleted_tokens = delete_expired_reset_tokens(session)
        logger.info(
            "cleanup job ran deleted_events=%s deleted_tokens=%s",
            deleted_events,
            deleted_tokens,
        )
        return {"deleted_events": deleted_events, "deleted_tokens": deleted_tokens}
    finally:
        if owns_session:
            session.close()


def start_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_cleanup_jobs, "interval", hours=settings.scheduler_interval_hours)
    scheduler.start()
    return scheduler
