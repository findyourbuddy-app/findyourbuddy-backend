import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.notifications import get_notification_sender
from app.database import SessionLocal
from app.services.auth_service import delete_expired_reset_tokens
from app.services.bookmark_service import delete_past_event_bookmarks
from app.services.event_service import delete_expired_events
from app.services.match_feedback_service import send_pending_feedback_notifications

logger = logging.getLogger(__name__)


def run_cleanup_jobs(db: Session | None = None) -> dict[str, int]:
    """Runs all periodic data-hygiene jobs. Accepts an optional session for
    testability; opens/closes its own session when called from the scheduler."""
    settings = get_settings()
    owns_session = db is None
    session = db if db is not None else SessionLocal()
    try:
        deleted_bookmarks = delete_past_event_bookmarks(session)
        deleted_events = delete_expired_events(session, settings.event_retention_days)
        deleted_tokens = delete_expired_reset_tokens(session)
        feedback_notifications_sent = send_pending_feedback_notifications(
            session, get_notification_sender(session)
        )
        logger.info(
            "cleanup job ran deleted_bookmarks=%s deleted_events=%s deleted_tokens=%s feedback_notifications_sent=%s",
            deleted_bookmarks,
            deleted_events,
            deleted_tokens,
            feedback_notifications_sent,
        )
        return {
            "deleted_bookmarks": deleted_bookmarks,
            "deleted_events": deleted_events,
            "deleted_tokens": deleted_tokens,
            "feedback_notifications_sent": feedback_notifications_sent,
        }
    finally:
        if owns_session:
            session.close()


def start_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_cleanup_jobs, "interval", hours=settings.scheduler_interval_hours)
    scheduler.start()
    return scheduler
