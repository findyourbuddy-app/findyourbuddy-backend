import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text
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

# Advisory-lock key so only one process runs the cleanup pass at a time, even
# with several web workers or hosts.
_CLEANUP_LOCK_KEY = 918273645

_EMPTY_RESULT = {
    "deleted_bookmarks": 0,
    "deleted_events": 0,
    "deleted_tokens": 0,
    "feedback_notifications_sent": 0,
    "no_shows_penalized": 0,
    "trust_scores_recomputed": 0,
    "accounts_suspended": 0,
}


def _acquire_cleanup_lock(session: Session) -> bool:
    """True if this process may run the cleanup pass now. No-op (always True)
    on non-Postgres sessions, e.g. the SQLite test DB."""
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return True
    got = session.execute(
        text("SELECT pg_try_advisory_lock(:k)"), {"k": _CLEANUP_LOCK_KEY}
    ).scalar()
    return bool(got)


def _release_cleanup_lock(session: Session) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _CLEANUP_LOCK_KEY})


def run_cleanup_jobs(db: Session | None = None) -> dict[str, int]:
    """Runs all periodic data-hygiene jobs. Accepts an optional session for
    testability; opens/closes its own session when called from the scheduler."""
    settings = get_settings()
    owns_session = db is None
    session = db if db is not None else SessionLocal()
    if not _acquire_cleanup_lock(session):
        logger.info("cleanup job skipped: another process holds the lock")
        if owns_session:
            session.close()
        return dict(_EMPTY_RESULT)
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
        _release_cleanup_lock(session)
        if owns_session:
            session.close()


def start_scheduler() -> BackgroundScheduler | None:
    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("scheduler disabled (SCHEDULER_ENABLED=false)")
        return None
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_cleanup_jobs,
        "interval",
        hours=settings.scheduler_interval_hours,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    scheduler.start()
    return scheduler
