"""Trust score = a 0-100 number recomputed from a user's real signals.

It is never a running +/- total: every call rebuilds the score from the current
verification flags, attendance history, host ratings, confirmed meetups, and
reports/blocks. That keeps it bounded, explainable, and recoverable (a user who
cleans up their act climbs back).
"""

import logging
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.config import get_settings
from app.core.datetime_utils import utcnow
from app.models.block import Block
from app.models.event import Event
from app.models.event_attendance import EventAttendance
from app.models.event_rating import EventRating
from app.models.match_feedback import MatchFeedback
from app.models.report import Report, ReportStatus
from app.models.user import User

# An event only counts toward attendance reliability once its check-in window
# has definitely closed (see event_service.CHECK_IN_WINDOW_AFTER_HOURS).
_ATTENDANCE_SETTLE_HOURS = 8


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return int(round(max(low, min(high, value))))


def compute_trust_score(db: Session, user: User) -> int:
    s = get_settings()
    score = float(s.trust_base_score)

    # --- verification ---
    if user.is_verified:
        score += s.trust_photo_verified_points
    if user.phone_verified:
        score += s.trust_phone_verified_points
    if user.firebase_uid:
        score += s.trust_email_verified_points

    settled_before = utcnow() - timedelta(hours=_ATTENDANCE_SETTLE_HOURS)

    # --- attendance reliability (RSVP'd -> actually showed up) ---
    rsvp_total, checked_in = (
        db.query(
            func.count(EventAttendance.id),
            func.count(EventAttendance.checked_in_at),
        )
        .join(Event, Event.id == EventAttendance.event_id)
        .filter(
            EventAttendance.user_id == user.id,
            EventAttendance.status == "approved",
            Event.starts_at < settled_before,
        )
        .one()
    )
    if rsvp_total:
        score += s.trust_attendance_max_points * (checked_in / rsvp_total)

    # --- no-shows ---
    no_shows = (
        db.query(func.count(EventAttendance.id))
        .filter(
            EventAttendance.user_id == user.id,
            EventAttendance.no_show_penalized_at.is_not(None),
        )
        .scalar()
    ) or 0
    score -= min(s.trust_no_show_max_penalty, s.trust_no_show_penalty_each * no_shows)

    # --- ratings received as an event host ---
    try:
        rating_count, rating_avg = (
            db.query(func.count(EventRating.id), func.avg(EventRating.rating))
            .join(Event, Event.id == EventRating.event_id)
            .filter(Event.creator_id == user.id)
            .one()
        )
    except SQLAlchemyError:
        # event_ratings table not migrated yet -- skip this component.
        db.rollback()
        rating_count, rating_avg = 0, None
    if rating_count >= s.trust_rating_min_count and rating_avg is not None:
        # avg 3 -> 0, avg 5 -> +swing, avg 1 -> -swing
        score += (float(rating_avg) - 3.0) / 2.0 * s.trust_rating_swing_points

    # --- confirmed real-life meetups ---
    meetups = (
        db.query(func.count(MatchFeedback.id))
        .filter(MatchFeedback.rated_id == user.id, MatchFeedback.met_in_person.is_(True))
        .scalar()
    ) or 0
    score += min(s.trust_meetup_max_points, s.trust_meetup_points_each * meetups)

    # --- reports filed against this user ---
    reviewed_reports = (
        db.query(func.count(Report.id))
        .filter(Report.reported_user_id == user.id, Report.status == ReportStatus.REVIEWED)
        .scalar()
    ) or 0
    pending_reports = (
        db.query(func.count(Report.id))
        .filter(Report.reported_user_id == user.id, Report.status == ReportStatus.PENDING)
        .scalar()
    ) or 0
    score -= min(
        s.trust_report_max_penalty,
        s.trust_report_reviewed_penalty * reviewed_reports
        + s.trust_report_pending_penalty * pending_reports,
    )

    # --- blocks against this user ---
    blocks = (
        db.query(func.count(Block.id)).filter(Block.blocked_id == user.id).scalar()
    ) or 0
    score -= min(s.trust_block_max_penalty, s.trust_block_penalty_each * blocks)

    return _clamp(score)


def recompute_trust_score(db: Session, user_id: int, *, commit: bool = True) -> int | None:
    """Recomputes and persists one user's trust score. Returns the new value,
    or None if the user does not exist. Caller commits when commit=False."""
    user = db.get(User, user_id)
    if user is None:
        return None
    try:
        user.trust_score = compute_trust_score(db, user)
    except SQLAlchemyError:
        # Never let a trust recompute break the action that triggered it
        # (check-in, verification, ...). Leave the score as-is.
        logger.exception("trust score recompute failed for user_id=%s", user_id)
        db.rollback()
        return user.trust_score
    if commit:
        db.commit()
    return user.trust_score


def recompute_trust_scores(db: Session, user_ids: list[int]) -> int:
    """Recomputes a batch of users in one commit. Returns how many were updated."""
    updated = 0
    for uid in {u for u in user_ids if u}:
        if recompute_trust_score(db, uid, commit=False) is not None:
            updated += 1
    if updated:
        db.commit()
    return updated


def recompute_all_active_trust_scores(db: Session) -> int:
    """Scheduler pass -- keeps time-sensitive components (an event crossing into
    the 'past' window, a report moving to reviewed) reflected without waiting for
    the user to trigger something."""
    ids = [row[0] for row in db.query(User.id).filter(User.is_active.is_(True)).all()]
    return recompute_trust_scores(db, ids)
