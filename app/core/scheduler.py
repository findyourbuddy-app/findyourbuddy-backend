import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.notifications import get_notification_sender
from app.database import SessionLocal
from app.services.auth_service import delete_expired_reset_tokens
from app.services.bookmark_service import delete_past_event_bookmarks
from app.services.event_service import apply_no_show_penalties, delete_expired_events
from app.services.match_feedback_service import send_pending_feedback_notifications
from app.services.trust_service import recompute_all_active_trust_scores
from app.services.user_service import update_trust_suspensions

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
        no_shows_penalized = apply_no_show_penalties(session)
        trust_scores_recomputed = recompute_all_active_trust_scores(session)
        accounts_suspended = update_trust_suspensions(session)
        logger.info(
            "cleanup job ran deleted_bookmarks=%s deleted_events=%s deleted_tokens=%s "
            "feedback_notifications_sent=%s no_shows_penalized=%s trust_scores_recomputed=%s "
            "accounts_suspended=%s",
            deleted_bookmarks,
            deleted_events,
            deleted_tokens,
            feedback_notifications_sent,
            no_shows_penalized,
            trust_scores_recomputed,
            accounts_suspended,
        )
        return {
            "deleted_bookmarks": deleted_bookmarks,
            "deleted_events": deleted_events,
            "deleted_tokens": deleted_tokens,
            "feedback_notifications_sent": feedback_notifications_sent,
            "no_shows_penalized": no_shows_penalized,
            "trust_scores_recomputed": trust_scores_recomputed,
            "accounts_suspended": accounts_suspended,
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
